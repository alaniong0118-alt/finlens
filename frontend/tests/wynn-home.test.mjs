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

  const blobs = [], downloads = [];
  const NativeURL = globalThis.URL;
  const createObjectURL = blob => { blobs.push(blob); return 'blob:http://finlens.test/roundtrip-' + blobs.length; };
  const revokeObjectURL = () => {};
  install('URL', class extends NativeURL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  Object.assign(dom.window.URL, { createObjectURL, revokeObjectURL });
  dom.window.HTMLAnchorElement.prototype.click = function () { downloads.push(this.download); };
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
    input, set, blobs, downloads,
    async fillLabel(name, value) {
      const label = [...query('main').querySelectorAll('label')].find(x => x.firstChild?.textContent === name);
      const control = label?.control;
      assert.ok(control, name);
      await change(control, value, control.tagName === 'SELECT' ? 'change' : 'input');
    },
    async openBytes(bytes) {
      const chooser = query('input[type=file][accept=".json,application/json"]');
      assert.ok(chooser);
      const file = new dom.window.File([bytes], 'finlens-manual-comparison-v1.json', { type: 'application/json' });
      Object.defineProperty(file, 'arrayBuffer', { value: async () => bytes });
      Object.defineProperty(chooser, 'files', { configurable: true, value: [file] });
      await act(async () => chooser.dispatchEvent(new dom.window.Event('change', { bubbles: true })));
    },
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

test('A researcher explicitly adds only the issuer notice address to the same comparison', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  await app.keep();
  await app.click(button(app, confirm));
  const optIn = button(app, 'Add issuer notice link to comparison');
  assert.ok(optIn, 'explicit notice-link handoff missing');
  const before = app.requests.length;
  await app.click(optIn);
  const manual = app.query('[aria-label="Manual evidence comparison"]');
  const source = [...manual.querySelectorAll('input')].find(x => x.value === disclosure);
  assert.ok(source, 'issuer notice URL was not copied');
  assert.ok([...manual.querySelectorAll('input[type=date]')].every(x => x.value === ''), 'printed date is not publication date');
  assert.ok([...manual.querySelectorAll('textarea')].every(x => x.value === ''), 'passages and judgments must stay empty');
  assert.ok(![...manual.querySelectorAll('input')].some(x => x.value === roster), 'regulator directory must stay independent');
  assert.equal(app.query('#research-draft-premise')?.textContent, question);
  assert.equal(app.requests.length, before);
});

test('Wynn source handoff can be compared, downloaded, and reopened without rewriting live reasoning', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  const before = app.requests.length;
  await app.keep();
  await app.click(button(app, confirm));
  await app.click(button(app, 'Add issuer notice link to comparison'));
  const values = {
    'Passage A': 'Synthetic issuer excerpt: one named operator holds the concession.',
    'Locator A': 'Synthetic locator A',
    'Assessment A': 'supports',
    'Assessment rationale A': 'Issuer identifies the operator; independent confirmation remains necessary.',
    'Source reference B': roster,
    'Passage B': 'Synthetic counterevidence: the roster alone does not establish the claimed start date.',
    'Locator B': 'Synthetic locator B',
    'Assessment B': 'challenges',
    'Assessment rationale B': 'A current roster does not settle a historical date.',
    'Provisional judgment': 'The named operator is supported, but the start date remains uncertain.',
    'Evidence that would change the judgment': 'An independently dated concession award notice.',
  };
  for (const [name, value] of Object.entries(values)) await app.fillLabel(name, value);
  await app.click(button(app, 'Record provisional judgment'));
  await app.click(button(app, 'Download recorded comparison (.json)'));
  assert.deepEqual(app.downloads, ['finlens-manual-comparison-v1.json']);
  assert.equal(app.blobs.length, 1);
  const exported = await app.blobs[0].arrayBuffer();
  const stored = JSON.parse(new TextDecoder().decode(exported));
  assert.deepEqual(stored, {
    schema_version: 1, kind: 'manual_evidence_comparison', question,
    sources: [
      { kind: 'manual_unverified', reference: disclosure, passage: values['Passage A'],
        locator: values['Locator A'], date: null, assessment: 'supports', rationale: values['Assessment rationale A'] },
      { kind: 'manual_unverified', reference: roster, passage: values['Passage B'],
        locator: values['Locator B'], date: null, assessment: 'challenges', rationale: values['Assessment rationale B'] },
    ],
    provisional_judgment: values['Provisional judgment'],
    evidence_that_would_change_judgment: values['Evidence that would change the judgment'],
  });
  await app.fillLabel('Provisional judgment', 'New live note must not be replaced');
  assert.equal(button(app, 'Download recorded comparison (.json)'), undefined);
  await app.openBytes(exported);
  const preview = app.query('[aria-label="Reopened comparison preview"]');
  assert.ok(preview);
  for (const value of [question, disclosure, roster, values['Passage A'], values['Passage B'],
    values['Assessment rationale A'], values['Assessment rationale B'],
    values['Provisional judgment'], values['Evidence that would change the judgment']]) {
    assert.ok(preview.textContent.includes(value), value);
  }
  const liveLabel = [...app.query('main').querySelectorAll('label')].find(x => x.firstChild?.textContent === 'Provisional judgment');
  assert.equal(liveLabel?.control?.value, 'New live note must not be replaced');
  assert.equal(button(app, 'Download recorded comparison (.json)'), undefined);
  assert.equal(app.requests.length, before);
});

for (const chinese of ['永利澳門的公告能告訴我誰持有博彩經營批給嗎？', '永利澳门的公告能告诉我谁持有博彩经营批给吗？']) {
  test('Wynn Chinese trial question requires the same issuer confirmation and evidence boundaries: ' + chinese, async ctx => {
    const app = await mount(ctx);
    await app.release([acme]);
    const before = app.requests.length;
    await app.keep(chinese);
    const consent = button(app, confirm);
    assert.ok(consent, 'explicit issuer confirmation is required in the localized query');
    assert.equal(app.query(region), null);
    await app.click(consent);
    assert.ok(app.query(region));
    assert.ok(app.query('a[href="' + disclosure + '"]'));
    assert.ok(app.query('a[href="' + roster + '"]'));
    assert.match(app.query(region).textContent, /does not establish who holds a gaming concession/);
    assert.equal(app.requests.length, before);
    for (const invalid of [
      '永利度假村的公告能告訴我誰持有博彩經營批給嗎？',
      '永利澳門的公告已證明它持有博彩經營批給嗎？',
      '永利澳門的公告能告訴我誰持有博彩經營批給嗎？順便查投資建議',
    ]) {
      await app.keep(invalid);
      assert.equal(button(app, confirm), undefined);
      assert.equal(app.query(region), null);
    }
    assert.equal(app.requests.length, before);
  });
}

const pastedReference = 'https://example.org/reports/quarterly%25.pdf';
const pastedButton = 'Add pasted link to comparison';
test('kept user link is an explicit, inert and unverified reference with blank metadata', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  const before = app.requests.length;
  await app.keep(pastedReference);
  const handoff = button(app, pastedButton);
  assert.ok(handoff, 'The user can explicitly use the kept reference');
  const panel = app.query('[aria-label="Manual evidence comparison"]');
  const source = () => [...panel.querySelectorAll('input')].find(node => node.labels?.[0]?.firstChild?.textContent === 'Source reference A');
  assert.equal(source()?.value, '');
  assert.equal(app.query('a[href="' + pastedReference + '"]'), null);
  await app.click(handoff);
  assert.equal(source()?.value, pastedReference);
  assert.match(panel.querySelector('[role="status"]')?.textContent ?? '', /unverified/i);
  assert.doesNotMatch(panel.querySelector('[role="status"]')?.textContent ?? '', /official/i);
  assert.ok([...panel.querySelectorAll('input[type=date], textarea')].every(node => node.value === ''));
  assert.equal(app.downloads.length, 0);
  assert.equal(app.requests.length, before);
});

test('new kept reference cannot be a credential-bearing, clickable or mixed-text URL', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  const before = app.requests.length;
  for (const input of [
    'http://example.org/file',
    'https://user:password@example.org/report',
    'https://example.org/report?signature=fixture-secret',
    'https://example.org/report#token',
    'https://example.org/%',
    'https://example.org/%GG',
    'https://example.org/%2',
    'https://127.0.0.1/report',
    'https://2130706433/report',
    'https://[::1]/report',
    'https://localhost/report',
    'https://example.org:8443/report',
    'https://例子.org/report',
    'https://example.org/Report\u202epdf',
    'https://xn--abc.example/report',
    'https://example.org/a\\b',
    'Read https://example.org/report',
  ]) {
    await app.keep(input);
    assert.equal(button(app, pastedButton), undefined, input);
    assert.ok(button(app, 'Compare two manual sources'), 'Manual entry still available');
  }
  assert.equal(app.requests.length, before);
  assert.equal(app.downloads.length, 0);
});

test('kept link handoff does not alter a filled comparison, duplicate refs, or an edited draft', async ctx => {
  const app = await mount(ctx);
  await app.release([acme]);
  const before = app.requests.length;
  await app.keep(pastedReference);
  const ref = slot => [...app.query('[aria-label="Manual evidence comparison"]').querySelectorAll('input')]
    .find(node => node.labels?.[0]?.firstChild?.textContent === 'Source reference ' + slot);
  await app.click(button(app, 'Compare two manual sources'));
  await app.fillLabel('Source reference A', 'Researcher’s existing first source');
  await app.fillLabel('Passage B', 'Second slot already contains a partial note');
  await app.click(button(app, pastedButton));
  assert.deepEqual(['A', 'B'].map(slot => ref(slot).value), ['Researcher’s existing first source', '']);
  assert.match(app.query('[aria-label="Manual evidence comparison"] [role="status"]').textContent, /No notes were replaced/);
  await app.fillLabel('Passage B', '');
  await app.click(button(app, pastedButton));
  assert.equal(ref('B').value, pastedReference);
  await app.click(button(app, pastedButton));
  assert.match(app.query('[aria-label="Manual evidence comparison"] [role="status"]').textContent, /already in your comparison/);
  await app.input('https://example.org/different.pdf');
  assert.equal(button(app, pastedButton), undefined);
  assert.equal(ref('A').value, 'Researcher’s existing first source');
  assert.equal(ref('B').value, pastedReference);
  assert.equal(app.requests.length, before);
});

test('unverified link handoff is available independently of an unavailable company catalog', async ctx => {
  const app = await mount(ctx);
  await app.release([], { status: 503 });
  const before = app.requests.length;
  await app.keep(pastedReference);
  await app.click(button(app, pastedButton));
  assert.match(app.query('[aria-label="Manual evidence comparison"] [role="status"]').textContent, /Unverified/);
  assert.equal(app.requests.length, before);
});
