import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import ts from 'typescript';
import { componentLoader } from './component-loader.mjs';

const pdf = 'https://www.nintendo.co.jp/ir/pdf/2026/261105e.pdf';
const index = 'https://www.nintendo.co.jp/ir/en/index.html';
const question = 'Can a Wynn Macau announcement tell me who holds the gaming concession?';
const acme = { id: 1, ticker: 'ACME', name: 'Acme', cik: '0000000001', exchange: 'NASDAQ',
  has_indexed_filing: false, indexed_filing_count: 0 };
const nintendo = { ...acme, id: 2, ticker: '7974', name: 'Nintendo Co., Ltd.', cik: '0000000002', exchange: 'TSE' };

async function mount(ctx) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://finlens.test' });
  const previous = new Map(), forbidden = [], requests = [];
  const install = (key, value) => {
    previous.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  };
  const refuse = label => {
    forbidden.push(label);
    throw new Error(label);
  };
  let root, act;
  ctx.after(async () => {
    try {
      if (root) await act(async () => root.unmount());
      assert.deepEqual(forbidden, [], 'No unintended transport or browser storage');
    } finally {
      dom.window.close();
      for (const [key, descriptor] of previous) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    }
  });
  for (const key of ['window', 'document', 'HTMLElement', 'Event', 'MouseEvent']) {
    install(key, dom.window[key]);
  }
  install('IS_REACT_ACT_ENVIRONMENT', true);
  const storage = () => refuse('IndexedDB access');
  Object.defineProperty(dom.window, 'indexedDB', { get: storage });
  previous.set('indexedDB', Object.getOwnPropertyDescriptor(globalThis, 'indexedDB'));
  Object.defineProperty(globalThis, 'indexedDB', { configurable: true, get: storage });
  const mockFetch = (input, init) => {
    const url = new URL(input, dom.window.location.href);
    if (url.origin !== dom.window.location.origin || url.search || (init?.method ?? 'GET') !== 'GET')
      return refuse('Unexpected request ' + url);
    if (url.pathname === '/api/finlens/capabilities') {
      requests.push({ path: url.pathname, released: true });
      return Promise.resolve(new Response(JSON.stringify({ research_mode: false })));
    }
    if (url.pathname !== '/api/finlens/companies') return refuse('Unexpected request ' + url);
    return new Promise(resolve => requests.push({ path: url.pathname, released: false, resolve }));
  };
  install('fetch', mockFetch);
  dom.window.fetch = mockFetch;

  const { default: React, act: reactAct } = await import('react');
  act = reactAct;
  const { createRoot } = await import('react-dom/client');
  const dir = fileURLToPath(new URL('..', import.meta.url));
  const file = fileURLToPath(new URL('../app/page.tsx', import.meta.url));
  const require = createRequire(file);
  const load = componentLoader(dir);
  // Mount the actual Home, picker and API; unrelated panels are outside this acceptance.
  const unrelated = new Set(['financial-research', 'financial-insights', 'filing-research',
    'theme-control', 'company-comparison', 'sec-risk-comparison', 'annual-period-comparison',
    'quarter-window-comparison', 'financial-coverage', 'balance-date-comparison', 'cash-flow-window-comparison']);
  const output = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, esModuleInterop: true,
  } }).outputText;
  const exports = {};
  let refresh;
  new Function('require', 'exports', output)(name => {
    if (name === 'next/link') return props => React.createElement('a', props);
    if (name === '@/components/research-freshness') return ({ catalogChanged }) => {
      refresh = catalogChanged;
      return null;
    };
    if (name.startsWith('@/components/') && unrelated.has(name.slice('@/components/'.length))) return () => null;
    if (name.startsWith('@/')) {
      const extension = name.startsWith('@/components/') ? '.tsx' : '.ts';
      return load(fileURLToPath(new URL('../' + name.slice(2) + extension, import.meta.url)));
    }
    return require(name);
  }, exports);
  root = createRoot(dom.window.document.querySelector('#root'));
  await act(async () => root.render(React.createElement(exports.default)));
  const query = selector => dom.window.document.querySelector(selector);
  async function change(element, value, type) {
    assert.ok(element, 'Expected control to render');
    await act(async () => {
      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value').set.call(element, value);
      element.dispatchEvent(new dom.window.Event(type, { bubbles: true }));
    });
  }
  const input = value => change(query('#research-draft-input'), value, 'input');
  const set = (selector, value) => change(query(selector), value, 'input');
  return {
    query, region: () => query('[aria-label="Nintendo external source"]'), requests,
    async release(rows, init = {}) {
      const item = requests.find(req => !req.released);
      assert.ok(item, 'Expected catalog request');
      item.released = true;
      await act(async () => item.resolve(new Response(JSON.stringify(rows), init)));
    },
    input, set,
    async click(button) { await act(async () => button.click()); },
    async keep(value = question) {
      await input(value);
      await act(async () => query('#research-draft-input').form.querySelector('button').click());
      assert.equal(query('#research-draft-premise')?.textContent, value);
    },
    choose: ticker => change(query('#company'), ticker, 'change'),
    async refresh() {
      let result;
      await act(async () => { result = refresh(new AbortController().signal); });
      return { result };
    },
  };
}

const disclosure = 'https://www.hkexnews.hk/listedco/listconews/sehk/2026/0424/2026042401631_c.pdf';
const roster = 'https://www.dicj.gov.mo/web/EN/information/contacts_casino/content.html';
const button = (app, label) => [...app.query('main').querySelectorAll('button')].find(el => el.textContent === label);
const confirm = 'Confirm Wynn Macau, Limited (HKEX 1128)';
const region = '[aria-label="Wynn Macau official source guide"]';
test('Home requires issuer confirmation then separates the issuer notice from regulator verification', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  const before = app.requests.length;
  await app.keep();
  assert.equal(app.query('a[href="' + disclosure + '"]'), null);
  assert.equal(app.query('a[href="' + roster + '"]'), null);
  assert.ok(button(app, confirm), 'offer the missing issuer-confirmation step');
  const toggle = button(app, confirm);
  toggle.focus();
  await app.click(toggle);
  assert.ok(app.query('button[aria-controls="wynn-official-source-guide"]') === toggle, 'same keyboard control survives confirmation');
  assert.ok(app.query('main').ownerDocument.activeElement === toggle);
  assert.equal(app.query('#research-draft-premise')?.textContent, question);
  const card = app.query(region);
  assert.ok(card);
  assert.match(card.querySelector('[aria-label="Listed issuer notice"]').textContent, /Document date: 27 April 2026/);
  assert.match(card.querySelector('[aria-label="Listed issuer notice"]').textContent, /does not establish who holds a gaming concession/);
  assert.ok(card.querySelector('[aria-label="Listed issuer notice"] a[href="' + disclosure + '"][referrerpolicy="no-referrer"]'));
  assert.ok(card.querySelector('[aria-label="Check the licence holder"] a[href="' + roster + '"][referrerpolicy="no-referrer"]'));
  assert.match(card.querySelector('[aria-label="Check the licence holder"]').textContent, /Do not assume/);
  assert.equal(app.requests.length, before);
  await app.click(button(app, 'Cancel issuer confirmation'));
  assert.equal(app.query(region), null);
  await app.click(button(app, confirm));
  assert.ok(app.query(region));
  await app.input('Where does Wynn operate casinos?');
  assert.equal(app.query(region), null);
  await app.keep('Where does Wynn operate casinos?');
  assert.ok(!button(app, confirm), 'unexpected issuer confirmation offered');
});

test('The US parent and bare issuer cannot inherit the two links without a covered catalog', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  for (const draft of ['Can a Wynn Resorts (NASDAQ: WYNN) announcement tell me who holds the gaming concession?',
                      'Can a Wynn announcement tell me who holds the gaming concession?']) {
    await app.keep(draft);
    assert.ok(!button(app, confirm), 'unexpected issuer confirmation offered');
    assert.equal(app.query(region), null);
  }
});

test('A Wynn Macau company already in the local catalog suppresses the external pilot', async ctx => {
  const app = await mount(ctx);
  await app.release([acme,{ ...nintendo, ticker:'01128.HK', name:'永利澳门有限公司', exchange:'HKEX' }]);
  await app.keep();
  assert.ok(!button(app, confirm), 'unexpected issuer confirmation offered');
  assert.equal(app.query(region), null);
});
