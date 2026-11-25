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
const question = 'What did Nintendo report on 5 November 2026?';
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
  return {
    query, region: () => query('[aria-label="Nintendo external source"]'), requests,
    async release(rows, init = {}) {
      const item = requests.find(req => !req.released);
      assert.ok(item, 'Expected catalog request');
      item.released = true;
      await act(async () => item.resolve(new Response(JSON.stringify(rows), init)));
    },
    input,
    async keep() {
      await input(question);
      await act(async () => query('#research-draft-input').form.querySelector('button').click());
      assert.equal(query('#research-draft-premise')?.textContent, question);
    },
    choose: ticker => change(query('#company'), ticker, 'change'),
    async refresh() {
      let result;
      await act(async () => { result = refresh(new AbortController().signal); });
      return { result };
    },
  };
}

test('HOME_NINTENDO_RELEASE offers the dated official PDF from a kept Home question without retrieval', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  const before = app.requests.length;
  await app.keep();
  const region = app.region();
  assert.ok(region, 'The eligible Home draft must show an inline issuer source');
  const link = region.querySelector('a[href="' + pdf + '"]');
  assert.ok(link, 'The eligible Home draft must link directly to the dated official PDF');
  assert.equal(link.textContent, 'Nintendo six-month earnings release, 5 November 2026 (official PDF)');
  assert.equal(link.getAttribute('referrerpolicy'), 'no-referrer');
  assert.equal(link.getAttribute('target'), null);
  assert.ok(region.querySelector('a[href="' + index + '"]'));
  assert.ok(app.query('details a[href="' + index + '"]'));
  assert.equal(app.requests.length, before);
});

test('HOME_NINTENDO_RELEASE withholds the inline source for a covered catalog', async ctx => {
  const app = await mount(ctx);
  await app.release([acme, nintendo]);
  await app.keep();
  assert.equal(app.region(), null);
});

test('HOME_NINTENDO_RELEASE withholds the inline source while pending or incomplete', async ctx => {
  const app = await mount(ctx);
  await app.keep();
  assert.equal(app.region(), null);
  await app.release([acme], { status: 206, headers: { 'Content-Range': 'items 0-0/2' } });
  assert.equal(app.region(), null);
});

test('HOME_NINTENDO_RELEASE invalidates a stale catalog during refresh', async ctx => {
  const app = await mount(ctx);
  await app.release([{ ...acme, has_indexed_filing: true, indexed_filing_count: 1 }]);
  await app.keep();
  assert.ok(app.region());
  const { result } = await app.refresh();
  assert.equal(app.region(), null);
  await app.release([acme, nintendo]);
  assert.equal(await result, true);
  assert.equal(app.region(), null);
});

test('HOME_NINTENDO_RELEASE invalidates an edited draft and respects explicit company selection', async ctx => {
  const app = await mount(ctx);
  await app.release([acme, { ...acme, id: 2, ticker: 'BETA', name: 'Beta', cik: '0000000002' }]);
  await app.keep();
  assert.ok(app.region());
  await app.input(question + ' Edited.');
  assert.equal(app.query('#research-draft-premise'), null);
  assert.equal(app.region(), null);
  await app.keep();
  assert.ok(app.region());
  await app.choose('BETA');
  assert.equal(app.query('#company-title').textContent, 'Beta');
  assert.equal(app.region(), null);
});

test('HOME_NINTENDO_OFFICIAL_URL contextualizes only the explicitly kept pinned release URL', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  const before = app.requests.length;
  const { act } = await import('react');
  const keep = () => act(async () => app.query('#research-draft-input').form.querySelector('button').click());
  for (const value of [pdf + '?tracking=1', pdf + '#page=2', pdf.replace('261105e', '%3261105e'),
    pdf.replace('www.nintendo.co.jp', 'www.nintendo.co.jp.example.invalid')]) {
    await app.input(value);
    await keep();
    assert.equal(app.region(), null);
  }
  await app.input(pdf);
  assert.equal(app.region(), null);
  await keep();
  assert.equal(app.query('#research-draft-premise')?.textContent, pdf);
  assert.equal(Boolean(app.region()), true, 'A kept exact Nintendo report URL must show its static source context');
  const link = app.region().querySelector('a[href="' + pdf + '"]');
  assert.ok(link);
  assert.equal(link.getAttribute('referrerpolicy'), 'no-referrer');
  assert.equal(app.region().querySelector('time')?.dateTime, '2026-11-05');
  await app.input(pdf + '#page=2');
  assert.equal(app.region(), null);
  assert.equal(app.requests.length, before);
});

test('NINTENDO_CURATED_BINDING admits only the exact original report and distinguishes actual from forecast', () => {
  const load = componentLoader(fileURLToPath(new URL('..', import.meta.url)));
  const { getNintendoInterimNetSales } = load(fileURLToPath(new URL('../lib/nintendo-ir-reference.ts', import.meta.url)));
  assert.equal(typeof getNintendoInterimNetSales, 'function', 'Missing curated Nintendo source binding');
  const report = getNintendoInterimNetSales(pdf);
  assert.deepEqual(report, {
    issuer: 'Nintendo Co., Ltd.', pdf, page: 1, published: '2026-11-05', currency: 'JPY', unit: 'million',
    actual: { amount: '966,041', periodEnd: '2026-09-30' },
    forecast: { amount: '2,050,000', periodEnd: '2027-03-31' },
  });
  for (const variant of [pdf + '#page=1', pdf + '?x=1', pdf.replace('261105e', '261105_3e'),
    pdf.replace('261105e', '261105_2e'), pdf.replace('261105e', '261106e'), pdf.replace('261105e', '%3261105e'),
    pdf.replace('www.nintendo.co.jp', 'www.nintendo.co.jp.example.invalid'),
    question, "What were Nintendo's actual net sales for the year ending March 31, 2027?", "Why did Nintendo's operating profit rise?"]) {
    assert.equal(getNintendoInterimNetSales(variant), null);
  }
});

test('NINTENDO_CURATED_HOME shows the source-backed net sales only after keeping the exact URL', async ctx => {
  const app = await mount(ctx);
  const { act } = await import('react');
  await app.release([acme]);
  const count = app.requests.length;
  const keep = () => act(async () => app.query('#research-draft-input').form.querySelector('button').click());
  const answer = () => app.region()?.querySelector('[aria-label="Curated Nintendo net sales"]');
  await app.keep();
  assert.ok(app.region());
  assert.equal(Boolean(answer()), false, 'Generic source guide is still link-only');
  await app.input(pdf.replace('261105e', '261105_2e')); await keep();
  assert.equal(app.region(), null);
  await app.input(pdf);
  assert.equal(app.region(), null);
  await keep();
  assert.equal(Boolean(answer()), true, 'Missing curated net sales in the kept Home draft');
  const rows = [...answer().querySelectorAll('dt, dd')].map(n => n.textContent);
  assert.deepEqual(rows, [
    'Actual consolidated net sales', 'JPY 966,041 million · Six months ended 30 September 2026',
    'Nintendo full-year forecast at publication (not actual)', 'JPY 2,050,000 million · Year ending 31 March 2027',
  ]);
  assert.match(answer().textContent, /not fetched live/);
  assert.match(answer().textContent, /does not establish full-year actual sales/);
  const link = answer().querySelector('a');
  assert.equal(link.getAttribute('href'), pdf + '#page=1');
  assert.equal(link.getAttribute('referrerpolicy'), 'no-referrer');
  assert.match(link.textContent, /page 1/);
  await app.input("Why did Nintendo's operating profit rise?"); await keep();
  assert.ok(app.region());
  assert.equal(Boolean(answer()), false);
  assert.equal(app.requests.length, count);
});
