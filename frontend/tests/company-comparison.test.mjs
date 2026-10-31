import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import ts from 'typescript';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

const require = createRequire(import.meta.url);
let dom, createRoot, Comparison, contract, api, browserData, notes;
before(async () => {
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://finlens.test' });
  for (const key of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent']) {
    Object.defineProperty(globalThis, key, { configurable: true, value: dom.window[key] });
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  ({ createRoot } = await import('react-dom/client'));
  const cache = new Map();
  function load(path) {
    if (cache.has(path)) return cache.get(path);
    const exports = {}; cache.set(path, exports);
    const output = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
    } }).outputText;
    const localRequire = name => {
      if (!name.startsWith('@/')) return require(name);
      const base = fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url));
      return load(['.tsx', '.ts'].map(extension => base + extension).find(existsSync));
    };
    new Function('require', 'exports', output)(localRequire, exports);
    return exports;
  }
  Comparison = load(fileURLToPath(new URL('../components/company-comparison.tsx', import.meta.url))).default;
  contract = load(fileURLToPath(new URL('../lib/company-comparison.ts', import.meta.url)));
  api = load(fileURLToPath(new URL('../lib/finlens-api.ts', import.meta.url)));
  browserData = load(fileURLToPath(new URL('../e2e/fixtures/data.ts', import.meta.url)));
  notes = load(fileURLToPath(new URL('../lib/research-note.ts', import.meta.url)));
});
after(() => dom.window.close());

function noteColumns(count = 2) {
  return companies.slice(0, count).map((issuer, version) => ({ company: issuer, version, result: response(issuer.ticker, 2025) }));
}
function noteButton(app, metric = 'Revenue') {
  return app.host.querySelector(`button[aria-label="Copy research note for ${metric}"]`);
}
function clipboard(ctx, writeText) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: writeText ? { clipboard: { writeText } } : {} });
  ctx.after(() => { if (descriptor) Object.defineProperty(globalThis, 'navigator', descriptor); else delete globalThis.navigator; });
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const NOTE_DOCUMENT_BASE = 'https://consumer.test/notes/index.html';
const renderedNotes = new Map();
// Use the already installed backend test runtime's real CommonMark preset.
// Render offline, extract HTML hrefs, then apply WHATWG document-base resolution.
function noteLinks(markdown) {
  if (!renderedNotes.has(markdown)) {
    const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].map(p => fileURLToPath(new URL(`../../backend/${p}`, import.meta.url))).find(existsSync) ?? 'python';
    const run = spawnSync(python, ['-B', '-c', "import sys; from markdown_it import MarkdownIt; print(MarkdownIt('commonmark').render(sys.stdin.read()))"], {
      input: markdown, encoding: 'utf8', timeout: 10000, maxBuffer: 8 * 1024 * 1024,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHON_DOTENV_DISABLED: '1', PYTHONIOENCODING: 'utf-8' },
    });
    assert.equal(run.status, 0, run.stderr || run.error?.message);
    renderedNotes.set(markdown, run.stdout);
  }
  const rendered = document.createElement('div'); rendered.innerHTML = renderedNotes.get(markdown);
  return [...rendered.querySelectorAll('a')].map(anchor => {
    assert.equal(anchor.textContent, 'Open supplied SEC link', 'No unexpected injected link');
    const destination = anchor.getAttribute('href');
    return { destination, parsed: new URL(destination, NOTE_DOCUMENT_BASE) };
  });
}
function assertSecLinks(links) {
  for (const { parsed } of links) {
    assert.equal(parsed.protocol, 'https:');
    assert.ok(['sec.gov', 'www.sec.gov'].includes(parsed.hostname), `Unexpected final destination host: ${parsed.hostname}`);
    assert.equal(parsed.origin, `https://${parsed.hostname}`); assert.equal(parsed.port, '');
    assert.equal(parsed.username, ''); assert.equal(parsed.password, '');
  }
}

for (const [label, supplied] of [
  ['document-relative absolute-looking URL', 'https:sec.gov/Archives/filing.htm'],
  ['fullwidth Unicode authority', 'https://ｗｗｗ.sec.gov/a'],
]) test(`REL-PRODUCT-02D reproduce ${label} through CommonMark and document base`, () => {
  const columns = noteColumns(); columns[0].result.metrics.revenue.provenance[0].sec_url = supplied;
  const links = noteLinks(notes.serializeResearchNote('revenue', 2025, columns));
  console.log('REL-PRODUCT-02D destination evidence', JSON.stringify({ supplied, standalone: new URL(supplied).href,
    rendered: links.map(({ destination, parsed }) => ({ destination, resolved: parsed.href, origin: parsed.origin, username: parsed.username, password: parsed.password })) }));
  assertSecLinks(links);
  assert.equal(links.length, 1, 'Reject the ambiguous source; retain only the other issuer link');
});

test('REL-PRODUCT-02C exact Astra backslash authority reproduction has no unsafe final destination', () => {
  const columns = noteColumns();
  const supplied = 'https://www.sec.gov\\@evil.test/filing';
  columns[0].result.metrics.revenue.provenance[0].sec_url = supplied;
  const links = noteLinks(notes.serializeResearchNote('revenue', 2025, columns));
  console.log('REL-PRODUCT-02C destination evidence', JSON.stringify({ suppliedHost: new URL(supplied).hostname,
    final: links.map(({ destination, parsed }) => ({ destination, protocol: parsed.protocol,
      hostname: parsed.hostname, username: parsed.username, password: parsed.password })) }));
  assertSecLinks(links);
  assert.equal(links.length, 1, 'Omit the ambiguous source link; retain only the other issuer link');
});

const unsafeNoteUrls = [
  ['missing scheme slashes', 'https:sec.gov/Archives/filing.htm'],
  ['single scheme slash', 'https:/www.sec.gov/Archives/filing.htm'],
  ['uppercase scheme', 'HTTPS://www.sec.gov/Archives/filing.htm'],
  ['mixed scheme', 'hTtPs://www.sec.gov/Archives/filing.htm'],
  ['extra scheme slash', 'https:///www.sec.gov/Archives/filing.htm'],
  ['scheme-relative', '//www.sec.gov/Archives/filing.htm'],
  ['fullwidth Unicode host', 'https://ｗｗｗ.sec.gov/a'],
  ['fullwidth SEC hostname', 'https://ｓｅｃ.gov/a'],
  ['Unicode dot authority', 'https://www。sec.gov/a'],
  ['encoded ASCII hostname', 'https://%77ww.sec.gov/a'],
  ['encoded authority dot', 'https://www%2esec.gov/a'],
  ['uppercase host', 'https://WWW.SEC.GOV/a'],
  ['trailing dot authority', 'https://www.sec.gov./a'],
  ['explicit default port', 'https://www.sec.gov:443/a'],
  ['explicit custom port', 'https://www.sec.gov:8443/a'],
  ['hostname without boundary', 'https://www.sec.govmore/a'],
  ['percent authority boundary', 'https://www.sec.gov%2Fa'],
  ['empty credentials', 'https://@www.sec.gov/a'],
  ['raw brackets', 'https://www.sec.gov/a(b)[c]?x=[d]#(e)[f]'],
  ['raw Markdown delimiters', 'https://www.sec.gov/Archives/a(b)>[fake](https://evil.test)'],
  ['raw spaces and angles', 'https://www.sec.gov/Archives/a b<c>.htm?x=a b#c d'],
  ['raw Unicode path', 'https://www.sec.gov/資料?x=報告#注'],
  ['incomplete percent escape', 'https://www.sec.gov/a%2'],
  ['invalid percent escape', 'https://www.sec.gov/a%zz'],
  ['raw backtick path', 'https://www.sec.gov/a`b'],
  ['raw pipe path', 'https://www.sec.gov/a|b'],
  ['raw brace path', 'https://www.sec.gov/a{b}'],
  ['raw quote path', 'https://www.sec.gov/a"b'],
  ['backslash authority', 'https://www.sec.gov\\@evil.test/filing'],
  ['double backslash authority', 'https://www.sec.gov\\\\@evil.test/filing'],
  ['backslash credential boundary', 'https://www.sec.gov\\:password@evil.test/filing'],
  ['backslash scheme and authority', 'https:\\\\www.sec.gov\\@evil.test/filing'],
  ['backslash in path', 'https://www.sec.gov/Archives/a\\@evil.test/filing'],
  ['backslash before query', 'https://www.sec.gov\\?next=@evil.test/filing'],
  ['backslash in fragment', 'https://www.sec.gov/filing#a\\b'],
  ['authority tab', 'https://www.sec.gov\t@evil.test/filing'],
  ['path newline', 'https://www.sec.gov/Archives/a\nb'],
  ['leading whitespace', ' https://www.sec.gov/filing'],
  ['credentials', 'https://user:password@www.sec.gov/filing'],
  ['encoded credential', 'https://www.sec.gov%5C@evil.test/filing'],
  ['encoded authority slash', 'https://www.sec.gov%2F@evil.test/filing'],
  ['encoded authority host', 'https://www.sec.gov%5Cevil.test/filing'],
  ['entity authority', 'https://www.sec.gov&#64;evil.test/filing'],
  ['non SEC', 'https://evil.test/filing'],
  ['SEC suffix impostor', 'https://www.sec.gov.evil.test/filing'],
  ['non HTTPS', 'http://www.sec.gov/filing'],
  ['invalid', 'not a URL'],
];
const validNoteUrls = [
  ['ordinary', 'https://www.sec.gov/Archives/edgar/data/1/filing.htm'],
  ['query and fragment', 'https://www.sec.gov/Archives/filing.htm?view=inline&doc=annual#section-2'],
  ['bare SEC hostname', 'https://sec.gov/Archives/filing.htm?x=a%20b&x=c#notes'],
  ['parentheses and encoded brackets', 'https://www.sec.gov/Archives/a(b)%5Bc%5D.htm?x=(a)&y=%5Bb%5D#(c)%5Bd%5D'],
  ['encoded delimiters', 'https://www.sec.gov/Archives/a%5Cb%2F%40%3E.htm?x=%26%23%3B#%3C%3E'],
  ['encoded percent escapes', 'https://www.sec.gov/Archives/%255C%2540?x=%252F#%2523'],
  ['encoded Markdown boundary characters', 'https://www.sec.gov/Archives/a(b)%3E%5Bfake%5D(https://evil.test)'],
  ['HTML entity text in query', 'https://www.sec.gov/filing?x=&amp;&copy;&#x40;&NewLine;#&lt;'],
  ['HTML entity text in path', 'https://www.sec.gov/Archives/&amp;filing.htm?x=1&y=2'],
  ['encoded spaces and angle delimiters', 'https://www.sec.gov/Archives/a%20b%3Cc%3E.htm?x=a%20b#c%20d'],
  ['encoded Unicode path', 'https://www.sec.gov/%E8%B3%87%E6%96%99?x=%E5%A0%B1%E5%91%8A#%E6%B3%A8'],
  ['safe URI punctuation', "https://www.sec.gov/a-._~!$'()*+,;=:@b?x=1+2&y=@a:b/c?z#fragment!$'()*+,;=:@/?"],
  ['host only', 'https://sec.gov'],
  ['query authority boundary', 'https://www.sec.gov?x=1#part'],
  ['fragment authority boundary', 'https://sec.gov#part'],
];
for (const kind of ['selected', 'alternative']) {
  for (const [label, supplied] of unsafeNoteUrls) test(`REL-PRODUCT-02C ${kind} rejects ${label} without inventing a replacement`, () => {
    const columns = noteColumns();
    for (const { result } of columns) {
      const point = result.metrics.revenue;
      if (kind === 'selected') point.provenance[0].sec_url = supplied;
      else point.alternatives = [{ ...point.provenance[0], fact_id: 101, sec_url: supplied }];
    }
    const markdown = notes.serializeResearchNote('revenue', 2025, columns);
    const links = noteLinks(markdown); assertSecLinks(links);
    const selected = noteLinks(markdown.split('### Alternative source observations')[0]); assertSecLinks(selected);
    assert.equal(links.length, kind === 'selected' ? 0 : 2);
    if (kind === 'alternative') assert.deepEqual(links.map(link => link.parsed.href), columns.map(c => c.result.metrics.revenue.provenance[0].sec_url));
    assert.equal(markdown.split('SEC link omitted:').length - 1, 2);
    assert.match(markdown, /Accession: 0000000001-26-000001/);
    assert.match(markdown, /Original source value: 1000000000/);
  });
  for (const [label, supplied] of validNoteUrls) test(`REL-PRODUCT-02C ${kind} preserves usable ${label} final destinations`, () => {
    const columns = noteColumns();
    for (const { result } of columns) {
      const point = result.metrics.revenue;
      if (kind === 'selected') point.provenance[0].sec_url = supplied;
      else point.alternatives = [{ ...point.provenance[0], fact_id: 101, sec_url: supplied }];
    }
    const markdown = notes.serializeResearchNote('revenue', 2025, columns);
    const links = noteLinks(markdown); assertSecLinks(links);
    assert.equal(links.length, kind === 'selected' ? 2 : 4);
    const targets = kind === 'selected' ? links : links.filter((_, i) => i % 2 === 1);
    for (const { parsed } of targets) {
      const original = new URL(supplied);
      assert.equal(parsed.href, original.href); assert.equal(parsed.pathname, original.pathname);
      assert.equal(parsed.search, original.search); assert.equal(parsed.hash, original.hash);
    }
    assert.equal(markdown.includes('SEC link omitted:'), false);
  });
}

test('REL-PRODUCT-02C benign financial notes match the original candidate byte for byte', () => {
  // Captured from the original serializer with SHA-256 5bb0a12c18d6033f...
  // The baseline covers every annual metric using the existing synthetic data.
  const markdown = contract.COMPARISON_METRICS.map(metric => notes.serializeResearchNote(metric, 2025, noteColumns()));
  assert.equal(createHash('sha256').update(JSON.stringify(markdown)).digest('hex'),
    'e0fb582f52e1c288cd2cbe198a9c41c83fb18599741e997e6dc55252be315b6c');
  for (const note of markdown) assertSecLinks(noteLinks(note));
});

test('REL-PRODUCT-02D printable ASCII path/query/fragment admission survives real CommonMark resolution', () => {
  const allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=:@/?#";
  const expected = []; const markdown = [];
  // One bounded parser invocation covers every printable ASCII character in
  // each URL component. Percent triplets have separate compatibility fixtures.
  for (const part of ['path', 'query', 'fragment']) for (let cp = 32; cp <= 126; cp++) {
    const char = String.fromCharCode(cp);
    const supplied = part === 'path' ? `https://www.sec.gov/a${char}b`
      : part === 'query' ? `https://www.sec.gov/a?x=a${char}b` : `https://www.sec.gov/a#a${char}b`;
    const columns = noteColumns();
    for (const { result } of columns) result.metrics.revenue.provenance[0].sec_url = supplied;
    markdown.push(notes.serializeResearchNote('revenue', 2025, columns));
    if (allowed.includes(char)) expected.push(new URL(supplied).href, new URL(supplied).href);
  }
  const links = noteLinks(markdown.join('\n')); assertSecLinks(links);
  assert.deepEqual(links.map(link => link.parsed.href), expected);
});

for (const exact of ['900719925474099312345678901234567890', '123456789.123456789123456789', '-987654321.000000000000001', '0', '-0.000', '1.234567890123456789e+25']) {
  test(`REL-PRODUCT-02B exact decimal ${exact} survives without output conversion`, () => {
    const columns = noteColumns(); const point = columns[0].result.metrics.revenue;
    point.value = point.provenance[0].value = exact;
    const before = structuredClone(columns);
    const markdown = notes.serializeResearchNote('revenue', 2025, columns);
    assert.ok(markdown.includes(`Exact normalized value: ${exact}\n`));
    assert.ok(markdown.includes(`Original source value: ${exact}\n`));
    assert.deepEqual(columns, before);
    assert.equal(notes.serializeResearchNote('revenue', 2025, columns), markdown);
  });
}

test('REL-PRODUCT-02B ratio, formula operands and original USD source units remain distinct', () => {
  const columns = noteColumns();
  for (const column of columns) {
    const point = column.result.metrics.gross_margin;
    const gross = column.result.metrics.gross_profit.provenance[0];
    const revenue = column.result.metrics.revenue.provenance[0];
    Object.assign(point, { status: 'available', value: '0.123456789123456789123456789', reason: null,
      formula: 'gross_profit / revenue', provenance: [gross, revenue], inputs: [
        { role: 'numerator', metric: 'gross_profit', value: gross.value, unit: 'USD', fact_ids: [gross.fact_id], period: point.period },
        { role: 'denominator', metric: 'revenue', value: revenue.value, unit: 'USD', fact_ids: [revenue.fact_id], period: point.period, revenue_basis: 'total_revenue' },
      ] });
  }
  const markdown = notes.serializeResearchNote('gross_margin', 2025, columns);
  assert.match(markdown, /Exact normalized value: 0\.123456789123456789123456789\n- Unit: ratio/);
  assert.match(markdown, /Operand unit: USD/); assert.match(markdown, /Original source unit: USD/);
  assert.match(markdown, /Server-supplied formula: gross&#95;profit &#47; revenue/);
  assert.match(markdown, /Operand revenue economic basis: total&#95;revenue/);
  assert.match(markdown, /Role: denominator/); assert.match(markdown, /Source fact identities: 1/);
  assert.doesNotMatch(markdown, /12\.35%/);
});

test('REL-PRODUCT-02B all statuses, missing windows, source alternatives and limitations survive', () => {
  const columns = noteColumns(3);
  columns[0].result.metrics.gross_profit.alternatives = [{ ...columns[0].result.metrics.gross_profit.provenance[0], fact_id: 101, value: '35' }];
  columns[1].result = missing('BBB', 2025, 'Missing or ambiguous annual period; no fallback.');
  Object.assign(columns[2].result.metrics.gross_profit, { value: null, status: 'not_applicable', reason: 'Observed net-interest revenue basis.', provenance: [] });
  const markdown = notes.serializeResearchNote('gross_profit', 2025, columns);
  for (const expected of ['Status: Available', 'Status: Unavailable', 'Status: Not applicable', 'Exact normalized value: Unavailable',
    'Exact normalized value: Not applicable', 'Missing or ambiguous annual period&#59; no fallback&#46;', 'Annual period limitation:',
    'Actual annual reporting window: Unavailable', '### Selected source observations', '#### Alternative observation 1',
    'Original source value: 35', 'Original source value: 40', 'Source fiscal year: 2026', 'Fiscal year: 2025',
    'Accession: 0000000001-26-000001', 'Source selection policy:', 'missing or ambiguous', 'currency and completeness are not established',
    'does not independently verify filings', 'No cross-company calculation or causal explanation']) assert.ok(markdown.includes(expected), expected);
  assert.equal(markdown.split('#### Selected source 1').length - 1, 1);
  assert.match(markdown, /No compatible source selected/);
});

test('REL-PRODUCT-02B different actual annual windows and economic bases remain explicit', () => {
  const columns = noteColumns();
  columns[1].result = response('BBB', 2025, { basis: 'customer_contract', period: { start: '2024-09-29', end: '2025-09-27' } });
  const markdown = notes.serializeResearchNote('revenue', 2025, columns);
  for (const value of ['Reporting windows differ', 'Revenue economic bases differ', '2024-09-29 to 2025-09-27',
    '2025-01-01 to 2025-12-31', 'total&#95;revenue', 'customer&#95;contract', 'does not establish equivalent accounting periods']) assert.ok(markdown.includes(value));
});

test('REL-PRODUCT-02B Markdown, HTML, delimiter and control injection stays inert text', () => {
  const columns = noteColumns();
  const malicious = 'issuer\r\n# Forged\n|fake|table|\t[SEC](https://evil.test) www.evil.test <script>&#10; `code` \\ escape\u0000\u001b\u202e\u200b\u2028';
  columns[0].company = { ...columns[0].company, name: malicious };
  columns[0].result.company_name = malicious;
  columns[0].result.metrics.revenue.reason = malicious;
  columns[0].result.metrics.revenue.provenance[0].original_concept = malicious;
  const markdown = notes.serializeResearchNote('revenue', 2025, columns);
  assert.doesNotMatch(markdown, /\n# Forged|\|fake\||\[SEC\]|<script>|`code`|https:\/\/evil|www\.evil\.test/);
  assert.doesNotMatch(markdown, /[\r\t\u0000\u001b\u202e\u200b\u2028]/);
  assert.match(markdown, /U\+000A/); assert.match(markdown, /U\+202E/);
  assert.match(markdown, /&#38;&#35;10&#59;/);
});

for (const url of ['https://evil.test/x', 'http://www.sec.gov/x', 'https://sec.gov.evil.test/x', 'javascript:alert(1)', 'https://u:p@www.sec.gov/x', 'not a url', '']) {
  test(`REL-PRODUCT-02B filtered supplied URL ${url || '(empty)'} never becomes a link`, () => {
    const columns = noteColumns();
    for (const column of columns) column.result.metrics.revenue.provenance[0].sec_url = url;
    const markdown = notes.serializeResearchNote('revenue', 2025, columns);
    assert.doesNotMatch(markdown, /\[Open supplied SEC link\]/);
    assert.match(markdown, /SEC link omitted/); assert.match(markdown, /Accession:/);
  });
}
test('REL-PRODUCT-02D canonical supplied URL with encoded delimiters retains identity', () => {
  const columns = noteColumns();
  const url = 'https://www.sec.gov/Archives/a(b)%3E%5Bfake%5D(https://evil.test)';
  columns[0].result.metrics.revenue.provenance[0].sec_url = url;
  const markdown = notes.serializeResearchNote('revenue', 2025, columns);
  assert.ok(markdown.includes(`[Open supplied SEC link](<${url}>)`));
  const links = noteLinks(markdown); assertSecLinks(links);
  assert.equal(links[0].parsed.href, new URL(url).href);
  assert.match(markdown, /policy checks destinations, not financial evidentiary support/);
});

for (const [label, corrupt] of [
  ['value', c => { c[0].result.metrics.revenue.value = 'NaN'; }],
  ['unit', c => { c[0].result.metrics.revenue.unit = 'EUR'; }],
  ['year', c => { c[0].result.requested_fiscal_year = 2024; }],
  ['CIK', c => { c[0].result.company_cik = company('BBB').cik; }],
  ['source CIK', c => { c[0].result.metrics.revenue.provenance[0].company_cik = company('BBB').cik; }],
  ['version', c => { c[0].version = null; }],
  ['name', c => { c[0].result.company_name = {}; }],
  ['reason', c => { c[0].result.metrics.revenue.reason = {}; }],
  ['formula', c => { c[0].result.metrics.revenue.formula = []; }],
  ['basis', c => { c[0].result.metrics.revenue.revenue_basis = {}; }],
  ['concept', c => { c[0].result.metrics.revenue.provenance[0].original_concept = {}; }],
  ['source value', c => { c[0].result.metrics.revenue.provenance[0].value = 12; }],
  ['decimal trailing control', c => { c[0].result.metrics.revenue.value = '12\n'; }],
  ['filed date', c => { c[0].result.metrics.revenue.provenance[0].filed = '2026-02-30'; }],
  ['source fiscal label', c => { delete c[0].result.metrics.revenue.provenance[0].source_fiscal_year; }],
  ['source URL type', c => { c[0].result.metrics.revenue.provenance[0].sec_url = {}; }],
  ['period label basis', c => { c[0].result.period.fiscal_label_basis = {}; }],
  ['selection policy', c => { c[0].result.selection_policy = {}; }],
  ['unavailable with value', c => { c[0].result.metrics.revenue.status = 'unavailable'; }],
  ['duplicate company', c => { c[1] = c[0]; }],
]) test(`REL-PRODUCT-02B malformed ${label} fails closed`, () => {
  const columns = noteColumns(); corrupt(columns);
  assert.throws(() => notes.serializeResearchNote('revenue', 2025, columns));
});

for (const count of [2, 3, 4]) test(`REL-PRODUCT-02B copy ${count} issuers including publication zero uses an immutable row snapshot without requests`, async ctx => {
  const app = await mount(ctx); const tickers = companies.slice(0, count).map(c => c.ticker);
  for (let i = 2; i < count; i++) await app.click('Add company');
  for (const [i, ticker] of tickers.entries()) await app.change(`#comparison-company-${i}`, ticker);
  await app.discovery(tickers, [2025, 2024], tickers.map((_, i) => i));
  const writes = []; const pending = deferred(); clipboard(ctx, note => { writes.push(note); return pending.promise; });
  for (const ticker of tickers) {
    const button = noteButton(app); if (button) assert.ok(button.disabled);
    await app.release(app.request(ticker, 'financials/annual?fiscal_year=2025'), response(ticker, 2025));
  }
  const button = noteButton(app); assert.equal(button.type, 'button'); assert.equal(button.disabled, false);
  button.focus(); assert.equal(document.activeElement, button); assert.equal(button.tabIndex, 0);
  const requests = app.requests.length;
  // A click with detail zero is the native button activation delivered by keyboard/AT.
  await act(async () => { button.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 0 })); assert.equal(writes.length, 1); button.click(); });
  assert.equal(writes.length, 1, 'Synchronous admission coalesces repeated activation');
  assert.equal(writes[0].split('## Company\n').length - 1, count);
  assert.match(writes[0], /Independent publication version: 0/);
  assert.doesNotMatch(writes[0], /# FinLens research note[\s\S]*Metric: Gross profit/);
  assert.ok(button.disabled); assert.match(button.parentElement.querySelector('[role="status"]').textContent, /Copying/);
  await act(async () => pending.resolve());
  assert.match(button.parentElement.querySelector('[role="status"]').textContent, /Research note copied/);
  assert.equal(button.disabled, false); assert.equal(app.requests.length, requests);
});

for (const state of ['failed', 'unverified', 'malformed-export', 'missing-period', 'not-applicable']) test(`REL-PRODUCT-02B ${state} column export admission`, async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const writes = []; clipboard(ctx, note => { writes.push(note); return Promise.resolve(); });
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  let result = response('BBB', 2025);
  if (state === 'malformed-export') result.metrics.revenue.provenance[0].original_concept = 12;
  if (state === 'missing-period') result = missing('BBB', 2025);
  if (state === 'not-applicable') Object.assign(result.metrics.revenue, { value: null, status: 'not_applicable', reason: 'Synthetic not applicable.', provenance: [] });
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), result, state === 'unverified' ? null : '3', state === 'failed' ? 503 : 200);
  const button = noteButton(app); assert.ok(button);
  if (['failed', 'unverified'].includes(state)) assert.ok(button.disabled);
  await act(async () => button.click());
  assert.equal(writes.length, ['missing-period', 'not-applicable'].includes(state) ? 1 : 0);
  if (state === 'malformed-export') assert.match(app.host.textContent, /Could not copy research note/);
  if (state === 'missing-period') assert.match(writes[0], /Status: Unavailable/);
  if (state === 'not-applicable') assert.match(writes[0], /Status: Not applicable/);
});

for (const failure of ['missing', 'rejected', 'throws']) test(`REL-PRODUCT-02B clipboard ${failure} produces accessible failure without success or requests`, async ctx => {
  const app = await focusTable(ctx);
  clipboard(ctx, failure === 'missing' ? null : () => {
    if (failure === 'throws') throw new Error('denied');
    return Promise.reject(new Error('denied'));
  });
  const count = app.requests.length; const button = noteButton(app);
  await act(async () => button.click());
  const status = button.parentElement.querySelector('[role="status"]');
  assert.equal(status.getAttribute('aria-live'), 'polite'); assert.match(status.textContent, /Could not copy/);
  assert.doesNotMatch(status.textContent, /Research note copied/); assert.equal(button.disabled, false);
  assert.equal(app.requests.length, count);
});

for (const outcome of ['resolve', 'reject']) for (const change of ['year', 'company', 'refresh', 'cancel', 'unmount']) {
  test(`REL-PRODUCT-02B delayed clipboard ${outcome} after ${change} cannot report into another scope`, async ctx => {
    const app = await focusTable(ctx); const pending = deferred(); const writes = [];
    clipboard(ctx, note => { writes.push(note); return pending.promise; });
    await act(async () => noteButton(app).click());
    const snapshot = writes[0]; assert.equal(typeof snapshot, 'string');
    if (change === 'year') await app.change('#comparison-year', 2024);
    if (change === 'company') await app.change('#comparison-company-1', 'CCC');
    if (change === 'refresh' || change === 'cancel') await app.click('Refresh comparison');
    if (change === 'cancel') await app.click('Cancel comparison');
    if (change === 'unmount') await app.unmount();
    const requests = app.requests.length;
    await act(async () => outcome === 'resolve' ? pending.resolve() : pending.reject(new Error('denied')));
    assert.doesNotMatch(app.host.textContent, /Research note copied|Could not copy research note/);
    assert.equal(writes[0], snapshot); assert.equal(writes.length, 1); assert.equal(app.requests.length, requests);
    if (change === 'cancel') assert.equal(noteButton(app), null);
  });
}

test('REL-PRODUCT-02B obsolete clipboard and annual settlements cannot overwrite a new publication copy', async ctx => {
  const app = await focusTable(ctx); const old = deferred(); const current = deferred(); const writes = [];
  clipboard(ctx, note => { writes.push(note); return writes.length === 1 ? old.promise : current.promise; });
  await act(async () => noteButton(app).click());
  await app.change('#comparison-year', 2024);
  const late = app.request('AAA', 'financials/annual?fiscal_year=2024');
  assert.equal(noteButton(app), null);
  await app.change('#comparison-year', 2025);
  assert.equal(noteButton(app), null, 'Returning to a previous year must wait for this generation');
  await app.release(late, response('AAA', 2024));
  // The old 2025 state cannot stand in for this generation's pending annual requests.
  for (const ticker of ['AAA', 'BBB']) await app.release(app.request(ticker, 'financials/annual?fiscal_year=2025'), response(ticker, 2025));
  await act(async () => noteButton(app).click());
  assert.equal(writes.length, 2);
  await act(async () => old.resolve());
  assert.doesNotMatch(app.host.textContent, /Research note copied/);
  await act(async () => current.resolve());
  assert.match(app.host.textContent, /Research note copied/);
});

test('REL-PRODUCT-02B earlier Revenue YoY operands retain exact annual dates without recalculation', () => {
  const columns = noteColumns();
  for (const { result } of columns) {
    const current = result.metrics.revenue.provenance[0];
    const prior = { ...current, fact_id: 100, value: '800000000.000000001', period_start: '2024-01-01', period_end: '2024-12-31' };
    Object.assign(result.metrics.revenue_growth_yoy, { status: 'available', value: '0.2499999999999999999', reason: null,
      formula: '(current - prior) / prior', provenance: [current, prior], inputs: [
        { role: 'current', metric: 'revenue', value: current.value, unit: 'USD', fact_ids: [current.fact_id], period: result.period },
        { role: 'prior', metric: 'revenue', value: prior.value, unit: 'USD', fact_ids: [prior.fact_id], period: { ...result.period, start: prior.period_start, end: prior.period_end, fiscal_year: 2024 } },
      ] });
  }
  const markdown = notes.serializeResearchNote('revenue_growth_yoy', 2025, columns);
  for (const expected of ['Exact normalized value: 0.2499999999999999999', 'Exact operand value: 800000000.000000001',
    'Role: prior', 'Operand reporting window: 2024-01-01 to 2024-12-31']) assert.ok(markdown.includes(expected));
  for (const corrupt of [
    c => { c[0].result.metrics.revenue_growth_yoy.inputs[1].role = {}; },
    c => { c[0].result.metrics.revenue_growth_yoy.inputs[1].value = 'invalid'; },
    c => { c[0].result.metrics.revenue_growth_yoy.inputs[1].fact_ids = [999]; },
    c => { c[0].result.metrics.revenue_growth_yoy.inputs[1].unit = 'ratio'; },
    c => { c[0].result.metrics.revenue_growth_yoy.inputs[1].period = undefined; },
  ]) {
    const invalid = structuredClone(columns); corrupt(invalid);
    assert.throws(() => notes.serializeResearchNote('revenue_growth_yoy', 2025, invalid));
  }
});

test('REL-PRODUCT-02B export bounds and explicit fields exclude unrelated response content', () => {
  const columns = noteColumns();
  columns[0].result.unrelated = 'PRIVATE CONFIGURATION OR RAW PASSAGE MUST NOT APPEAR';
  columns[0].result.metrics.revenue.raw_text = columns[0].result.unrelated;
  assert.doesNotMatch(notes.serializeResearchNote('revenue', 2025, columns), /PRIVATE CONFIGURATION|RAW PASSAGE/);
  for (const count of [0, 1, 5]) assert.throws(() => notes.serializeResearchNote('revenue', 2025, noteColumns(count)));
  for (const metric of ['total_assets', 'unknown']) assert.throws(() => notes.serializeResearchNote(metric, 2025, columns));
  assert.throws(() => notes.serializeResearchNote('revenue', null, columns));
  const invalidBasis = noteColumns(); invalidBasis[0].result.metrics.revenue.revenue_basis = {};
  assert.throws(() => notes.serializeResearchNote('gross_profit', 2025, invalidBasis));
});

test('REL-PRODUCT-02B freshness failure never authorizes a partially populated comparison copy', async ctx => {
  const app = await mount(ctx); await app.select();
  const writes = []; clipboard(ctx, note => { writes.push(note); return Promise.resolve(); });
  await app.release(app.request('AAA', 'freshness'), { ticker: 'AAA', data_version: 0, facts_version: 0, evidence_version: 0 });
  await app.release(app.request('BBB', 'freshness'), {}, null, 503);
  await app.release(app.request('AAA', 'financials/annual'), response('AAA', null));
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  assert.ok(noteButton(app).disabled); await act(async () => noteButton(app).click());
  assert.equal(writes.length, 0);
});

test('REL-PRODUCT-02B a scope control invalidates copy admission before React commits', async ctx => {
  const app = await focusTable(ctx); const writes = [];
  clipboard(ctx, note => { writes.push(note); return Promise.resolve(); });
  const old = noteButton(app); const year = app.host.querySelector('#comparison-year');
  await act(async () => {
    year.value = '2024'; year.dispatchEvent(new Event('change', { bubbles: true }));
    old.click();
  });
  assert.equal(writes.length, 0);
});

for (const outcome of ['resolve', 'reject']) test(`REL-PRODUCT-02B a newer independent publication ignores old clipboard ${outcome}`, async ctx => {
  const app = await focusTable(ctx); const old = deferred(); const next = deferred(); const writes = [];
  clipboard(ctx, note => { writes.push(note); return writes.length === 1 ? old.promise : next.promise; });
  await act(async () => noteButton(app).click());
  await app.click('Refresh comparison');
  assert.equal(noteButton(app), null);
  await app.discovery(['AAA', 'BBB'], [2025], [5, 7]);
  for (const ticker of ['AAA', 'BBB']) await app.release(app.request(ticker, 'financials/annual?fiscal_year=2025'), response(ticker, 2025));
  await act(async () => noteButton(app).click());
  assert.equal(writes.length, 2); assert.match(writes[1], /Independent publication version: 5/); assert.match(writes[1], /Independent publication version: 7/);
  await act(async () => outcome === 'resolve' ? old.resolve() : old.reject(new Error('denied')));
  assert.doesNotMatch(app.host.textContent, /Research note copied|Could not copy research note/);
  await act(async () => next.resolve());
  assert.match(app.host.textContent, /Research note copied/);
});

const companies = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE'].map((ticker, i) => ({
  ticker, cik: `000000000${i + 1}`, id: i + 1, name: `${ticker} synthetic issuer`, exchange: 'NYSE',
  has_indexed_filing: false, indexed_filing_count: 0,
}));
const company = ticker => companies.find(c => c.ticker === ticker);
function response(ticker, year = null, options = {}) {
  const period = year === null ? null : { kind: 'annual', start: `${year}-01-01`, end: `${year}-12-31`,
    fiscal_year: year, fiscal_period: 'FY', fiscal_label_basis: 'annual_period_end_year', ...options.period };
  const metrics = {};
  if (year !== null) for (const [i, name] of contract.COMPARISON_METRICS.entries()) {
    const unit = ['revenue_growth_yoy', 'operating_margin', 'net_margin', 'gross_margin'].includes(name) ? 'ratio' : 'USD';
    const available = ['revenue', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow', 'gross_profit', 'operating_income', 'net_income'].includes(name);
    const value = name === 'revenue' ? '1000000000' : name === 'capital_expenditures' ? '3' : name === 'free_cash_flow' ? '-10'
      : name === 'gross_profit' ? '40' : name === 'operating_income' ? '0' : name === 'net_income' ? '-10' : '-7';
    metrics[name] = { metric: name, unit, status: available ? 'available' : 'unavailable', value: available ? value : null,
      reason: available ? null : 'No compatible inputs or approved denominator.', period, formula: null,
      ...(name === 'revenue' ? { revenue_basis: options.basis ?? 'total_revenue' } : {}),
      alternatives: [], inputs: [], provenance: !available ? [] : [{ fact_id: i+1, company_cik: company(ticker).cik,
        original_concept: `${ticker} ${name}`, value, unit: 'USD', period_start: period.start, period_end: period.end,
        form: '10-K', filed: `${year + 1}-02-01`, accession_number: `${company(ticker).cik}-26-000001`,
        sec_url: `https://www.sec.gov/Archives/edgar/data/${Number(company(ticker).cik)}/filing.htm`,
        source_fiscal_year: year + 1, source_fiscal_period: 'FY' }] };
  }
  return { ticker, company_cik: company(ticker).cik, company_name: company(ticker).name,
    requested_period: 'annual', requested_fiscal_year: year, fiscal_years: options.years ?? [2025, 2024], period,
    period_reason: null, selection_policy: 'Existing deterministic selection', metrics };
}
function missing(ticker, year, reason = 'No stored annual reporting window.') {
  const result = response(ticker, year); result.period = null; result.period_reason = reason;
  for (const p of Object.values(result.metrics)) Object.assign(p, { period: null, value: null, status: 'unavailable', reason, provenance: [], inputs: [] });
  return result;
}

function backendAnnual(factory, year) {
  const backend = fileURLToPath(new URL('../../backend/', import.meta.url));
  const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].map(p => fileURLToPath(new URL(`../../backend/${p}`, import.meta.url))).find(existsSync) ?? 'python';
  const serialized = spawnSync(python, ['-B', '-c', `
import sys, socket
from contextlib import ExitStack
from unittest.mock import Mock, patch
from sqlalchemy.engine import Engine
sys.path.insert(0, 'tests')
from test_company_comparison import ${factory}
forbidden = Mock(side_effect=AssertionError('Live database/network/model dependency forbidden'))
with ExitStack() as stack:
    for target in ('app.sec_client._sec_get', 'app.answer_service._get_openai_client',
                   'app.embedding_service._get_model', 'app.embedding_service._load_model'):
        stack.enter_context(patch(target, forbidden))
    for obj, name in ((Engine, 'connect'), (Engine, 'raw_connection'), (socket, 'create_connection'), (socket.socket, 'connect')):
        stack.enter_context(patch.object(obj, name, forbidden))
    print(${factory}().annual_comparison(${year}).model_dump_json())
`], { cwd: backend, encoding: 'utf8', timeout: 30000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(serialized.status, 0, serialized.stderr || serialized.error?.message);
  return JSON.parse(serialized.stdout);
}

async function mount(ctx) {
  const requests = [];
  ctx.mock.method(globalThis, 'fetch', (url, options) => new Promise(resolve => requests.push({ path: String(url), options, resolve })));
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(React.createElement(Comparison, { companies })));
  let unmounted = false;
  const unmount = async () => { if (!unmounted) { unmounted = true; await act(async () => root.unmount()); host.remove(); } };
  ctx.after(unmount);
  const release = async (req, body, version = req.options.headers?.['X-FinLens-Data-Version'], status = 200) => {
    assert.ok(req, 'Expected pending request');
    await act(async () => req.resolve(new Response(JSON.stringify(body), { status, headers: version === null || version === undefined ? {} : { 'X-FinLens-Data-Version': String(version) } })));
  };
  const request = (ticker, suffix) => requests.findLast(r => r.path === `/api/finlens/companies/${ticker}/${suffix}`);
  const change = async (selector, value) => { await act(async () => {
    const control = host.querySelector(selector); control.value = String(value); control.dispatchEvent(new Event('change', { bubbles: true }));
  }); };
  const click = async label => { const button = [...host.querySelectorAll('button')].find(b => b.textContent === label); assert.ok(button); await act(async () => button.click()); };
  const select = async (a = 'AAA', b = 'BBB') => { await change('#comparison-company-0', a); await change('#comparison-company-1', b); };
  const discovery = async (tickers = ['AAA', 'BBB'], years = [2025, 2024], versions = tickers.map((_, i) => i + 2)) => {
    for (const [index, ticker] of tickers.entries()) await release(request(ticker, 'freshness'), { ticker, data_version: versions[index], facts_version: 0, evidence_version: Math.min(1, versions[index]) });
    for (const ticker of tickers) await release(request(ticker, 'financials/annual'), response(ticker, null, { years }));
  };
  return { host, requests, release, request, change, click, select, discovery, unmount };
}

async function focusTable(ctx, count = 2) {
  const app = await mount(ctx);
  if (count === 4) { await app.click('Add company'); await app.click('Add company'); }
  const tickers = ['AAA', 'BBB', 'CCC', 'DDD'].slice(0, count);
  for (const [i, ticker] of tickers.entries()) await app.change(`#comparison-company-${i}`, ticker);
  await app.discovery(tickers, [2025, 2024], tickers.map((_, i) => i));
  for (const ticker of tickers) {
    const result = response(ticker, 2025);
    if (ticker === 'AAA') result.metrics.revenue.alternatives = [{ ...result.metrics.revenue.provenance[0], fact_id: 101, value: '900000000' }];
    await app.release(app.request(ticker, 'financials/annual?fiscal_year=2025'), result);
  }
  return { ...app, scroller: app.host.querySelector('.comparison-scroll') };
}

function focusGeometry(ctx, scroller, target, { initial = 0, x = 206, width = 216, total = 640, visible = true,
  top = 200, height = 44, initialY = 0, pageX = 0, maxY = 5000, viewportHeight = 844, viewportTop = 0, visual = true } = {}) {
  let position = initial, writes = 0, pageY = initialY;
  const verticalWrites = [];
  const property = (object, key, descriptor) => {
    const before = Object.getOwnPropertyDescriptor(object, key);
    Object.defineProperty(object, key, { configurable: true, ...descriptor });
    ctx.after(() => { if (before) Object.defineProperty(object, key, before); else delete object[key]; });
  };
  property(window, 'scrollY', { get: () => pageY });
  property(window, 'scrollX', { value: pageX });
  property(window, 'visualViewport', { value: visual ? { offsetTop: viewportTop, height: viewportHeight } : null });
  property(document, 'scrollingElement', { value: document.documentElement });
  property(document.documentElement, 'clientHeight', { value: viewportHeight });
  property(document.documentElement, 'scrollHeight', { value: maxY + viewportHeight });
  Object.defineProperties(scroller, {
    clientLeft: { configurable: true, value: 1 }, clientWidth: { configurable: true, value: 322 },
    scrollWidth: { configurable: true, value: total },
    scrollLeft: { configurable: true, get: () => position, set: value => { position = value; writes++; } },
  });
  scroller.scrollTop = 17;
  ctx.mock.method(scroller, 'getBoundingClientRect', () => ({ left: 33, right: 357, width: 324 }));
  ctx.mock.method(target, 'getBoundingClientRect', () => ({ left: x + initial - position, right: x + initial - position + width, width, top: top + initialY - pageY, bottom: top + initialY - pageY + height, height }));
  const matches = target.matches.bind(target), style = window.getComputedStyle.bind(window);
  ctx.mock.method(target, 'matches', selector => selector === ':focus-visible' ? visible : matches(selector));
  ctx.mock.method(window, 'getComputedStyle', element => element === target ? { outlineWidth: '3px', outlineOffset: '3px' } : style(element));
  ctx.mock.method(window, 'scrollTo', options => {
    assert.equal(options.left, pageX); assert.equal(options.behavior, 'instant');
    verticalWrites.push(options.top); pageY = options.top;
  });
  return { position: () => position, writes: () => writes, verticalWrites, pageY: () => pageY };
}

for (const [label, geometry, expected] of [
  ['right clipping', {}, 73],
  ['left clipping after native scrolling', { initial: 318, x: -112 }, 165],
  ['four-company right clipping', { initial: 299, x: 307, width: 176, total: 960 }, 433],
  ['already visible', { initial: 318, x: 128 }, 318],
  ['left boundary clamping', { initial: 10, x: -200 }, 0],
  ['right boundary clamping', { initial: 310, x: 400 }, 318],
  ['pointer focus exclusion', { visible: false }, 0],
  ['touch focus exclusion', { visible: false }, 0],
]) test(`comparison keyboard focus reveal: ${label}`, async ctx => {
  const app = await focusTable(ctx, geometry.total === 960 ? 4 : 2);
  const target = app.scroller.querySelector('tbody td summary');
  const requestCount = app.requests.length;
  const beforeSelection = [...app.host.querySelectorAll('.comparison-picker select')].map(el => el.value);
  const geo = focusGeometry(ctx, app.scroller, target, geometry);
  await act(async () => target.focus());
  assert.equal(geo.position(), expected);
  assert.equal(geo.writes(), expected === (geometry.initial ?? 0) ? 0 : 1);
  assert.equal(document.activeElement, target);
  assert.equal(app.scroller.scrollTop, 17);
  assert.equal(window.scrollY, 0);
  assert.deepEqual(geo.verticalWrites, []);
  assert.deepEqual([...app.host.querySelectorAll('.comparison-picker select')].map(el => el.value), beforeSelection);
  assert.equal(app.host.querySelector('#comparison-year').value, '2025');
  assert.equal(app.requests.length, requestCount);
  assert.equal(app.request('AAA', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '0');
  assert.equal(app.request('BBB', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '1');
  if (!label.includes('boundary') && geometry.visible !== false) {
    const rect = target.getBoundingClientRect();
    assert.ok(rect.left - 6 >= 34 && rect.right + 6 <= 356, 'Whole control and 6px focus indicator fit');
  }
  // A repeated native focus event must not accumulate another adjustment.
  await act(async () => target.dispatchEvent(new Event('focusin', { bubbles: true })));
  assert.equal(geo.position(), expected);
  assert.equal(geo.writes(), expected === (geometry.initial ?? 0) ? 0 : 1);
});

for (const [label, selector] of [
  ['nested disclosure', '.provenance details summary'],
  ['source link', '.provenance .source-record a'],
]) test(`comparison focus reveal covers ${label} without moving focus or fetching`, async ctx => {
  const app = await focusTable(ctx);
  app.scroller.querySelector('tbody td .provenance').open = true;
  const target = app.scroller.querySelector(selector);
  assert.ok(target);
  const count = app.requests.length;
  const geo = focusGeometry(ctx, app.scroller, target, { top: -0.15625, initialY: 500 });
  await act(async () => target.focus());
  assert.equal(geo.position(), 73);
  assert.equal(geo.pageY(), 492);
  assert.equal(document.activeElement, target);
  assert.equal(app.requests.length, count);
  assert.equal(app.scroller.scrollTop, 17);
});

for (const [label, geometry, expectedY, expectedX = 0] of [
  ['top outline clipping', { top: 5.4375 }, 498],
  ['bottom control and outline clipping', { top: 956.359375, viewportHeight: 1000 }, 508],
  ['fractional top control clipping rounds outward', { top: -0.15625 }, 492],
  ['fractional bottom outline clipping rounds outward', { top: 954.25, viewportHeight: 1000 }, 506],
  ['top document clamp', { top: -20, initialY: 2 }, 0],
  ['bottom document clamp', { top: 840, initialY: 1998, maxY: 2000 }, 2000],
  ['no document scroll range', { top: 840, initialY: 0, maxY: 0 }, 0],
  ['already visible', {}, 500],
  ['visible outline needs no extra safety scroll', { top: 6.25 }, 500],
  ['visual viewport top boundary', { top: 122, viewportTop: 120, viewportHeight: 600 }, 495],
  ['visual viewport bottom boundary', { top: 680, viewportTop: 120, viewportHeight: 600 }, 511],
  ['layout viewport fallback', { top: 840, visual: false }, 547],
  ['pointer excludes both axes', { top: -20, x: 206, visible: false }, 500],
  ['touch excludes both axes', { top: 840, x: 206, visible: false }, 500],
  ['both axes reveal together', { top: -0.15625, x: 206, pageX: 19 }, 492, 73],
  ['four-company combined reveal', { top: 840, initial: 299, x: 307, width: 176, total: 960 }, 547, 433],
]) test(`comparison vertical keyboard reveal: ${label}`, async ctx => {
  const app = await focusTable(ctx, geometry.total === 960 ? 4 : 2);
  const target = app.scroller.querySelector('tbody td summary');
  const requestCount = app.requests.length;
  const selections = [...app.host.querySelectorAll('select')].map(el => el.value);
  const headers = [...app.scroller.querySelectorAll('thead th')].map(el => el.textContent);
  const disclosures = [...app.scroller.querySelectorAll('details')].map(el => el.open);
  const initialY = geometry.initialY ?? 500;
  const geo = focusGeometry(ctx, app.scroller, target, { x: 100, initialY, ...geometry });
  await act(async () => target.focus());
  assert.equal(document.activeElement, target);
  assert.equal(geo.pageY(), expectedY);
  assert.equal(geo.position(), expectedX);
  assert.equal(window.scrollX, geometry.pageX ?? 0);
  assert.equal(app.scroller.scrollTop, 17);
  assert.deepEqual(geo.verticalWrites, expectedY === initialY ? [] : [expectedY]);
  assert.deepEqual([...app.host.querySelectorAll('select')].map(el => el.value), selections);
  assert.deepEqual([...app.scroller.querySelectorAll('thead th')].map(el => el.textContent), headers);
  assert.deepEqual([...app.scroller.querySelectorAll('details')].map(el => el.open), disclosures);
  assert.match(headers[1], /Publication 0/); assert.match(headers[2], /Publication 1/);
  assert.equal(app.requests.length, requestCount);
  for (const ticker of ['AAA', 'BBB']) assert.equal(app.request(ticker, 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], ticker === 'AAA' ? '0' : '1');
  const before = [...geo.verticalWrites];
  await act(async () => target.dispatchEvent(new Event('focusin', { bubbles: true })));
  assert.deepEqual(geo.verticalWrites, before, 'Settled or clamped focus must not schedule repeated movement');
});

test('selection limits, duplicate prevention and accessible native controls include unindexed companies', async ctx => {
  const app = await mount(ctx);
  assert.equal(app.requests.length, 0);
  const select = app.host.querySelector('#comparison-company-0'); select.focus(); assert.equal(document.activeElement, select);
  assert.equal(app.host.querySelector('label[for="comparison-company-0"]').textContent, 'Company 1');
  await app.change('#comparison-company-0', 'AAA');
  assert.ok(app.host.querySelector('#comparison-company-1 option[value="AAA"]').disabled);
  await app.change('#comparison-company-1', 'AAA');
  assert.equal(app.host.querySelector('#comparison-company-1').value, '');
  assert.equal(app.requests.length, 0);
  await app.click('Add company'); await app.click('Add company');
  assert.equal(app.host.querySelectorAll('.comparison-picker').length, 4);
  assert.ok([...app.host.querySelectorAll('button')].find(b => b.textContent === 'Add company').disabled);
  const remove = app.host.querySelector('button[aria-label="Remove company 4"]');
  await act(async () => remove.click());
  assert.equal(app.host.querySelectorAll('.comparison-picker').length, 3);
  assert.equal(document.activeElement.id, 'comparison-company-2');
  assert.equal(contract.validCompanySelection(['AAA', 'BBB']), true);
  assert.equal(contract.validCompanySelection(['AAA', 'AAA']), false);
  assert.equal(contract.validCompanySelection(['AAA', 'BBB', 'CCC', 'DDD', 'EEE']), false);
});

test('annual table retains actual windows, units, bases, negative cash flow, unavailable and SEC provenance', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025, { basis: 'customer_contract', period: { start: '2024-09-29', end: '2025-09-27' } }));
  assert.match(app.host.textContent, /Reporting windows differ/);
  assert.match(app.host.textContent, /Revenue economic bases differ/);
  assert.match(app.host.textContent, /Sep 29, 2024 – Sep 27, 2025/);
  assert.match(app.host.textContent, /Jan 1, 2025 – Dec 31, 2025/);
  assert.match(app.host.textContent, /Unavailable/); assert.match(app.host.textContent, /-\$10/);
  assert.equal(app.host.querySelectorAll('tbody tr').length, 11);
  assert.equal(app.host.querySelectorAll('th[scope="row"]').length, 11);
  const scroll = app.host.querySelector('[role="region"]'); scroll.focus(); assert.equal(document.activeElement, scroll);
  assert.equal(scroll.getAttribute('tabindex'), '0');
  const sources = app.host.querySelector('tbody td details'); assert.match(sources.querySelector('summary').textContent, /AAA Revenue sources/);
  sources.querySelector('summary').focus(); assert.equal(document.activeElement, sources.querySelector('summary'));
  assert.match(sources.textContent, /Exact API value: 1000000000 USD/);
  assert.match(sources.querySelector('a').href, /sec.gov/);
  assert.equal(app.requests.length, 6, 'One freshness, discovery and selected-year request per company');
  assert.equal(app.request('AAA', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '2');
  assert.equal(app.request('BBB', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '3');
  assert.ok(app.requests.every(r => !r.options.method && !r.options.body));
  const css = readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
  assert.match(css, /comparison-scroll/); assert.match(css, /comparison-controls \{ grid-template-columns:minmax\(0,1fr\)/);
});

test('eleven rows render backend-calculated gross margin, signed income and provenance with independent zero and one pins', async ctx => {
  const result = backendAnnual('expanded_view', 2025);
  assert.deepEqual(Object.keys(result.metrics), [
    'revenue', 'revenue_growth_yoy', 'operating_margin', 'net_margin',
    'operating_cash_flow', 'capital_expenditures', 'free_cash_flow',
    'gross_profit', 'operating_income', 'net_income', 'gross_margin',
  ]);
  assert.deepEqual(contract.COMPARISON_METRICS, Object.keys(result.metrics));
  const issuer = { ...company('AAA'), ticker: 'TEST' };
  assert.equal(contract.validateAnnualResponse(result, issuer, 2025), result);
  assert.equal(result.metrics.gross_margin.value, '0.4');
  assert.deepEqual(result.metrics.gross_margin.inputs.map(i => i.fact_ids), [[2], [1]]);
  assert.equal(result.metrics.gross_profit.alternatives[0].value, '35');
  const app = await mount(ctx); await app.select(); await app.discovery(['AAA', 'BBB'], [2025, 2024], [0, 1]);
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), { ...result, ticker: 'AAA' });
  const bank = response('BBB', 2025);
  for (const name of ['gross_profit', 'gross_margin']) Object.assign(bank.metrics[name], {
    value: null, status: 'not_applicable', reason: 'Observed net-interest revenue basis.', provenance: [], inputs: [],
  });
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), bank);
  const rows = [...app.host.querySelectorAll('tbody tr')];
  assert.equal(rows.length, 11);
  for (const [label, value] of [['Gross profit', '$40'], ['Operating income', '$0'], ['Net income', '-$10'], ['Gross margin', '40%']]) {
    const row = rows.find(r => r.querySelector('th').firstChild.textContent === label);
    assert.equal(row.querySelector('.metric-value').textContent, value);
  }
  const margin = rows.at(-1).querySelector('td');
  assert.match(margin.textContent, /Ratio · shown as percent/);
  assert.match(margin.textContent, /gross_profit \/ revenue/);
  assert.equal(margin.querySelectorAll('.source-record').length, 2);
  assert.match(rows.at(-1).querySelectorAll('td')[1].textContent, /Not applicable/);
  const disclosure = margin.querySelector('summary'); disclosure.focus();
  assert.equal(document.activeElement, disclosure);
  assert.equal(app.requests.length, 6);
  assert.equal(app.request('AAA', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '0');
  assert.equal(app.request('BBB', 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], '1');
  assert.match(app.host.querySelector('thead').textContent, /Publication 0/);

  const oldContract = structuredClone(result);
  for (const name of ['gross_profit', 'operating_income', 'net_income', 'gross_margin']) delete oldContract.metrics[name];
  assert.throws(() => contract.validateAnnualResponse(oldContract, issuer, 2025), e => e.code === 'INVALID_RESPONSE');
  for (const name of ['gross_profit', 'operating_income', 'net_income', 'gross_margin']) {
    for (const corrupt of [
      r => { r.metrics[name].unit = name === 'gross_margin' ? 'USD' : 'ratio'; },
      r => { r.metrics[name].period = { ...r.period, start: '2025-07-01' }; },
      r => { r.metrics[name].provenance[0].company_cik = company('BBB').cik; },
      r => { r.metrics[name].provenance[0].period_end = '2024-12-31'; },
    ]) {
      const invalid = structuredClone(result); corrupt(invalid);
      assert.throws(() => contract.validateAnnualResponse(invalid, issuer, 2025), e => e.code === 'INVALID_RESPONSE');
    }
  }
  const wrongOperand = structuredClone(result);
  wrongOperand.metrics.gross_margin.inputs[0].unit = 'EUR';
  assert.throws(() => contract.validateAnnualResponse(wrongOperand, issuer, 2025), e => e.code === 'INVALID_RESPONSE');
});

test('four-company comparison stays bounded with distinct provenance and not-applicable presentation', async ctx => {
  const app = await mount(ctx); await app.click('Add company'); await app.click('Add company');
  const tickers = ['AAA', 'BBB', 'CCC', 'DDD'];
  for (const [i, ticker] of tickers.entries()) await app.change(`#comparison-company-${i}`, ticker);
  await app.discovery(tickers);
  for (const ticker of tickers) {
    const result = response(ticker, 2025);
    if (ticker === 'DDD') result.metrics.operating_margin.status = 'not_applicable';
    await app.release(app.request(ticker, 'financials/annual?fiscal_year=2025'), result);
  }
  assert.equal(app.requests.length, 12);
  assert.equal(app.host.querySelectorAll('thead th').length, 5);
  assert.equal(app.host.querySelectorAll('tbody td').length, 44);
  assert.match(app.host.textContent, /Not applicable/);
  assert.doesNotMatch(app.host.textContent, /Reporting windows differ/);
  for (const [i, ticker] of tickers.entries()) {
    const source = app.host.querySelector(`tbody tr td:nth-child(${i+2}) details`);
    assert.match(source.textContent, new RegExp(`${company(ticker).cik}-26-000001`));
    assert.equal(source.querySelector('a').href, `https://www.sec.gov/Archives/edgar/data/${i+1}/filing.htm`);
  }
});

test('browser annual fixtures match the expanded contract for both issuers and fiscal years', () => {
  assert.deepEqual(browserData.annualMetrics, contract.COMPARISON_METRICS);
  for (const ticker of ['AAA', 'BBB']) {
    for (const year of [null, 2024, 2025]) {
      const result = browserData.annual(ticker, year);
      assert.equal(contract.validateAnnualResponse(result, browserData.company(ticker), year), result);
      if (year !== null) {
        assert.equal(Object.keys(result.metrics).length, 11);
        assert.equal(result.metrics.gross_margin.unit, 'ratio');
        assert.equal(result.metrics.gross_margin.status, 'unavailable');
        assert.equal(result.metrics.net_income.value, '-40000000');
      }
    }
  }
});

test('fiscal year change clears old values and rejects late responses, missing window remains explicit', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const oldA = app.request('AAA', 'financials/annual?fiscal_year=2025');
  const oldB = app.request('BBB', 'financials/annual?fiscal_year=2025');
  await app.change('#comparison-year', 2024);
  assert.ok(oldA.options.signal.aborted && oldB.options.signal.aborted);
  await app.release(oldA, response('AAA', 2025)); await app.release(oldB, response('BBB', 2025));
  assert.equal(app.host.querySelector('table'), null);
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2024'), response('AAA', 2024));
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2024'), missing('BBB', 2024, 'Ambiguous annual window.'));
  assert.match(app.host.querySelector('caption').textContent, /FY2024/);
  assert.match(app.host.textContent, /missing or ambiguous/); assert.match(app.host.textContent, /Ambiguous annual window/);
  assert.doesNotMatch(app.host.querySelector('table').textContent, /FY2025/);
  assert.equal(app.requests.filter(r => r.path.endsWith('financials/annual')).length, 2, 'Year changes reuse version-pinned discovery');
});

test('company change and incomplete selection hide previous table, with late results excluded', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const oldA = app.request('AAA', 'financials/annual?fiscal_year=2025'); const oldB = app.request('BBB', 'financials/annual?fiscal_year=2025');
  await app.change('#comparison-company-1', 'CCC');
  assert.ok(oldB.options.signal.aborted);
  await app.release(oldA, response('AAA', 2025)); await app.release(oldB, response('BBB', 2025));
  assert.equal(app.host.querySelector('table'), null);
  await app.discovery(['AAA', 'CCC']);
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  await app.release(app.request('CCC', 'financials/annual?fiscal_year=2025'), response('CCC', 2025));
  assert.doesNotMatch(app.host.querySelector('table').textContent, /BBB/);
  await app.click('Add company');
  assert.equal(app.host.querySelector('table'), null);
  assert.match(app.host.textContent, /Select 2–4 distinct/);
});

test('cancel during discovery and financial requests cannot publish ignored-abort results; retry works', async ctx => {
  const app = await mount(ctx); await app.select();
  const pending = app.request('AAA', 'freshness'); await app.click('Cancel comparison');
  assert.ok(pending.options.signal.aborted); await app.release(pending, { ticker: 'AAA', data_version: 2, facts_version: 0, evidence_version: 1 });
  assert.match(app.host.textContent, /Comparison cancelled/); assert.equal(app.requests.length, 2);
  await app.click('Refresh comparison'); await app.discovery();
  const annual = app.request('AAA', 'financials/annual?fiscal_year=2025'); const other = app.request('BBB', 'financials/annual?fiscal_year=2025');
  await app.click('Cancel comparison'); assert.ok(annual.options.signal.aborted);
  await app.release(annual, response('AAA', 2025)); await app.release(other, response('BBB', 2025));
  assert.equal(app.host.querySelector('table'), null); assert.match(app.host.textContent, /Comparison cancelled/);
  await app.click('Refresh comparison'); await app.discovery();
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025));
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025));
  assert.ok(app.host.querySelector('table'));
});

test('version changes reject stale financial column without hiding verified independent company', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025), '9');
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025));
  const first = app.host.querySelector('tbody td'); assert.match(first.textContent, /Published data changed/);
  assert.ok(!first.querySelector('details')); assert.match(app.host.querySelector('tbody td:nth-child(3)').textContent, /\$1B/);
  await app.click('Refresh comparison'); assert.equal(app.host.querySelector('table'), null);
});

test('no observed years and network/identity errors remain honest and retryable', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery(['AAA', 'BBB'], []);
  assert.match(app.host.textContent, /No observed annual fiscal years/); assert.equal(app.host.querySelector('table'), null);
  await app.click('Refresh comparison');
  await app.release(app.request('AAA', 'freshness'), { ticker: 'BBB', data_version: 2, facts_version: 0, evidence_version: 1 });
  await app.release(app.request('BBB', 'freshness'), { detail: 'Synthetic failure' }, null, 503);
  assert.match(app.host.textContent, /could not be verified/); assert.match(app.host.textContent, /Synthetic failure/);
  assert.equal(app.host.querySelector('table'), null);
});

test('union choices prefer a genuinely shared fiscal label but retain missing coverage', () => {
  assert.deepEqual(contract.comparisonYears([[2025, 2024], [2024, 2023]]), { years: [2025, 2024, 2023], preferred: 2024 });
  assert.deepEqual(contract.comparisonYears([[2025], [2024]]), { years: [2025, 2024], preferred: 2025 });
  assert.equal(contract.reportingWindowsDiffer([response('AAA', 2025), response('BBB', 2025)]), false);
});

for (const [label, mutate] of [
  ['ticker', r => { r.ticker = 'BBB'; }], ['CIK', r => { r.company_cik = company('BBB').cik; }],
  ['requested FY', r => { r.requested_fiscal_year = 2024; }], ['period FY', r => { r.period.fiscal_year = 2024; }],
  ['YTD', r => { r.period.kind = 'half_year'; }], ['falsely labeled YTD', r => { r.period.start = '2025-07-01'; }],
  ['missing metric', r => { delete r.metrics.net_margin; }], ['wrong unit', r => { r.metrics.revenue.unit = 'EUR'; }],
  ['source CIK', r => { r.metrics.revenue.provenance[0].company_cik = company('BBB').cik; }],
  ['source period', r => { r.metrics.revenue.provenance[0].period_end = '2024-12-31'; }],
  ['source accession', r => { r.metrics.revenue.provenance[0].accession_number = 'untrusted'; }],
  ['nonfinite value', r => { r.metrics.revenue.value = 'NaN'; }],
  ['duplicate years', r => { r.fiscal_years = [2025, 2025]; }],
  ['missing window with amount', r => { r.period = null; }],
]) test(`annual client scope validator rejects ${label}`, () => {
  const result = response('AAA', 2025); mutate(result);
  assert.throws(() => contract.validateAnnualResponse(result, company('AAA'), 2025), e => e.code === 'INVALID_RESPONSE');
});

test('available, unavailable and not-applicable are preserved, including week calendars', () => {
  const result = response('AAA', 2025, { period: { start: '2024-09-22', end: '2025-09-27' } });
  result.metrics.net_margin.status = 'not_applicable';
  assert.equal(contract.validateAnnualResponse(result, company('AAA'), 2025), result);
});

test('annual API requires explicit publication version and rejects missing version header', async ctx => {
  ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(response('AAA', null))));
  await assert.rejects(api.getAnnualFinancials('AAA', null, new AbortController().signal), e => e.code === 'INVALID_RESPONSE');
  await assert.rejects(api.getAnnualFinancials('AAA', null, api.versionedController(2, () => {}).signal), e => e.code === 'INVALID_RESPONSE');
});

test('backend-calculated Revenue YoY retains the isolated prior annual operand; mismatched inputs are rejected', () => {
  const result = response('AAA', 2025);
  const current = result.metrics.revenue.provenance[0];
  const prior = { ...current, fact_id: 100, value: '800000000', period_start: '2024-01-01', period_end: '2024-12-31' };
  const period = { ...result.period, start: prior.period_start, end: prior.period_end, fiscal_year: 2024 };
  result.metrics.revenue_growth_yoy = { ...result.metrics.revenue_growth_yoy, status: 'available', reason: null,
    value: '0.25', provenance: [current, prior], inputs: [
      { role: 'current', metric: 'revenue', value: current.value, unit: 'USD', period: result.period, fact_ids: [current.fact_id] },
      { role: 'prior', metric: 'revenue', value: prior.value, unit: 'USD', period, fact_ids: [prior.fact_id] },
    ] };
  assert.equal(contract.validateAnnualResponse(result, company('AAA'), 2025).metrics.revenue_growth_yoy.value, '0.25');
  for (const mutate of [r => { r.metrics.revenue_growth_yoy.inputs[1].period.kind = 'half_year'; },
    r => { r.metrics.revenue_growth_yoy.inputs[1].unit = 'EUR'; },
    r => { r.metrics.revenue_growth_yoy.provenance[1].company_cik = company('BBB').cik; },
    r => { r.metrics.revenue_growth_yoy.inputs[1].fact_ids = [999]; }]) {
    const invalid = structuredClone(result); mutate(invalid);
    assert.throws(() => contract.validateAnnualResponse(invalid, company('AAA'), 2025), e => e.code === 'INVALID_RESPONSE');
  }
});

test('serialized backend 52/53-week rollover response passes the client without relaxing incompatible prior periods', () => {
  // Requires the ordinary backend test environment. No persisted JSON, live DB,
  // network or hand-authored replacement of the backend response is involved.
  const backend = fileURLToPath(new URL('../../backend/', import.meta.url));
  const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].map(p => fileURLToPath(new URL(`../../backend/${p}`, import.meta.url))).find(existsSync) ?? 'python';
  const serialized = spawnSync(python, ['-B', '-c', `
import sys
from unittest.mock import Mock, patch
sys.path.insert(0, 'tests')
from test_company_comparison import rollover_view
with patch('app.database.engine.connect', Mock(side_effect=AssertionError('Live database forbidden'))), \\
     patch('app.sec_client._sec_get', Mock(side_effect=AssertionError('SEC requests forbidden'))), \\
     patch('app.answer_service._get_openai_client', Mock(side_effect=AssertionError('AI requests forbidden'))):
    print(rollover_view().annual_comparison(2024).model_dump_json())
`], { cwd: backend, encoding: 'utf8', timeout: 30000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(serialized.status, 0, serialized.stderr || serialized.error?.message);
  const result = JSON.parse(serialized.stdout);
  const issuer = { ...company('AAA'), ticker: 'TEST', name: 'Synthetic company' };
  assert.equal(result.metrics.revenue_growth_yoy.value, '0.25');
  assert.equal(result.metrics.revenue_growth_yoy.inputs[1].period.fiscal_year, 2022);
  assert.equal(contract.validateAnnualResponse(result, issuer, 2024), result);

  const shift = (value, days) => new Date(Date.parse(`${value}T00:00:00Z`) - days * 86400000).toISOString().slice(0, 10);
  const withPriorGaps = (startGap, endGap) => {
    const changed = structuredClone(result);
    const point = changed.metrics.revenue_growth_yoy;
    const prior = point.inputs.find(i => i.role === 'prior');
    prior.period.start = shift(changed.period.start, startGap);
    prior.period.end = shift(changed.period.end, endGap);
    prior.period.fiscal_year = Number(prior.period.end.slice(0, 4));
    for (const source of point.provenance.filter(s => prior.fact_ids.includes(s.fact_id))) {
      source.period_start = prior.period.start; source.period_end = prior.period.end;
    }
    return changed;
  };
  for (const gaps of [[357, 357], [378, 378]]) {
    assert.doesNotThrow(() => contract.validateAnnualResponse(withPriorGaps(...gaps), issuer, 2024));
  }
  // Preserve exact input/source linkage in these negatives: only the date
  // comparability rule is violated, not a convenient identity mismatch.
  for (const gaps of [[356, 365], [379, 370], [365, 356], [370, 379], [360, 370]]) {
    assert.throws(() => contract.validateAnnualResponse(withPriorGaps(...gaps), issuer, 2024), e => e.code === 'INVALID_RESPONSE');
  }
  const mislabeled = structuredClone(result);
  mislabeled.metrics.revenue_growth_yoy.inputs[1].period.fiscal_year = 2023;
  assert.throws(() => contract.validateAnnualResponse(mislabeled, issuer, 2024), e => e.code === 'INVALID_RESPONSE');
});

function inspector(app, metric = 'revenue') {
  const row = app.host.querySelectorAll('tbody tr')[contract.COMPARISON_METRICS.indexOf(metric)];
  return row?.querySelector('th details');
}

test('metric diagnostics distinguish observed differences, missing metadata, exclusions and unverified columns', () => {
  const a = response('AAA', 2025);
  const b = response('BBB', 2025, { basis: 'customer_contract', period: { start: '2024-09-29', end: '2025-09-27' } });
  assert.deepEqual(contract.metricComparability('revenue', [a, b]), {
    windowsDiffer: true, missingWindow: false, basesDiffer: true, basisUnknown: false, excluded: 0, unverified: 0,
  });
  delete b.metrics.revenue.revenue_basis;
  assert.equal(contract.validateAnnualResponse(b, company('BBB'), 2025), b);
  assert.deepEqual(contract.metricComparability('revenue', [a, b]), {
    windowsDiffer: true, missingWindow: false, basesDiffer: false, basisUnknown: true, excluded: 0, unverified: 0,
  });
  assert.deepEqual(contract.metricComparability('revenue', [a, missing('BBB', 2025), undefined]), {
    windowsDiffer: false, missingWindow: true, basesDiffer: false, basisUnknown: true, excluded: 1, unverified: 1,
  });
  assert.deepEqual(contract.metricComparability('gross_margin', [a, b]), {
    windowsDiffer: true, missingWindow: false, basesDiffer: false, basisUnknown: true, excluded: 2, unverified: 0,
  });
  assert.equal(contract.metricComparability('operating_cash_flow', [a, b]).basisUnknown, false,
    'Do not assign revenue-basis eligibility to unrelated cash-flow metrics');
  assert.equal(contract.metricComparability('operating_cash_flow', [a, b]).basesDiffer, false,
    'Do not borrow the revenue row basis for another metric');
});

test('row inspector groups exact company periods and raw bases without changing values, sources, pins or copy notes', async ctx => {
  const writes = []; clipboard(ctx, async text => { writes.push(text); });
  const app = await mount(ctx); await app.select(); await app.discovery(['AAA', 'BBB'], [2025], [0, 1]);
  const a = response('AAA', 2025);
  const b = response('BBB', 2025, { basis: 'customer_contract', period: { start: '2024-09-29', end: '2025-09-27' } });
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), a);
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), b);
  const panel = inspector(app);
  assert.equal(panel.open, false);
  assert.equal(panel.querySelector('summary').textContent, 'Inspect Revenue comparability');
  const count = app.requests.length;
  await act(async () => panel.querySelector('summary').click());
  assert.equal(panel.open, true);
  assert.match(panel.textContent, /Reported date ranges differ within this row/);
  assert.match(panel.textContent, /Reported revenue-basis labels differ/);
  const participants = panel.querySelectorAll('.source-record');
  assert.equal(participants.length, 2);
  assert.match(participants[0].textContent, /AAAAvailableReporting period: 2025-01-01 – 2025-12-31 · FY2025 FY/);
  assert.match(participants[1].textContent, /BBBAvailableReporting period: 2024-09-29 – 2025-09-27 · FY2025 FY/);
  assert.match(participants[0].textContent, /Metric revenue basis: total_revenue/);
  assert.match(participants[1].textContent, /Metric revenue basis: customer_contract/);
  assert.match(app.host.textContent, /Reporting windows differ/);
  assert.match(app.host.textContent, /Revenue economic bases differ/);
  assert.equal(app.host.querySelectorAll('tbody td').length, 22);
  for (const [i, ticker] of ['AAA', 'BBB'].entries()) {
    const cell = app.host.querySelector(`tbody tr td:nth-child(${i + 2})`);
    assert.equal(cell.querySelector('.metric-value').textContent, '$1B');
    assert.match(cell.querySelector('details').textContent, /Exact API value: 1000000000 USD/);
    assert.equal(cell.querySelector('a').href, `https://www.sec.gov/Archives/edgar/data/${i + 1}/filing.htm`);
    assert.equal(app.request(ticker, 'financials/annual?fiscal_year=2025').options.headers['X-FinLens-Data-Version'], String(i));
  }
  await act(async () => noteButton(app).click());
  assert.deepEqual(writes, [notes.serializeResearchNote('revenue', 2025, [
    { company: company('AAA'), version: 0, result: a }, { company: company('BBB'), version: 1, result: b },
  ])]);
  assert.equal(app.requests.length, count);
  await act(async () => panel.querySelector('summary').click());
  assert.equal(panel.open, false);
});

test('missing periods and exclusion reasons remain exact inert text for every selected participant', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const rawPeriod = 'unknown_window_v9  <img src=x onerror="alert(1)">\nDo not substitute.';
  const rawMetric = 'basis_rule_NEW_v7  <script>run()</script>\nkeep_original_reason';
  const a = response('AAA', 2025); const b = missing('BBB', 2025, rawPeriod);
  a.metrics.gross_margin.status = 'not_applicable'; a.metrics.gross_margin.reason = rawMetric;
  b.metrics.gross_margin.reason = 'new_exclusion_code__not_translated';
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), a);
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), b);
  const panel = inspector(app, 'gross_margin');
  assert.match(panel.textContent, /A reporting period is missing/);
  assert.match(panel.textContent, /2 of 2 companies have unavailable or not-applicable values/);
  const participants = panel.querySelectorAll('.source-record');
  assert.match(participants[0].textContent, /Not applicable — excluded/);
  assert.match(participants[1].textContent, /Unavailable — no value included/);
  assert.match(participants[1].textContent, /Unknown — no reporting period supplied/);
  const reasons = [...panel.querySelectorAll('p > span')].map(span => span.textContent);
  assert.deepEqual(reasons, [rawMetric, rawPeriod, b.metrics.gross_margin.reason]);
  assert.equal(panel.querySelector('img, script'), null);
  assert.equal(app.host.querySelectorAll('tbody tr').length, 11);
  assert.equal(noteButton(app, 'Gross margin').disabled, false, 'Verified unavailable/excluded columns retain existing export eligibility');
  assert.equal(app.requests.length, 6);
});

test('unknown metric basis stays unknown; matching labels never claim equivalent accounting scope', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const a = response('AAA', 2025); const b = response('BBB', 2025);
  delete b.metrics.revenue.revenue_basis;
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), a);
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), b);
  const panel = inspector(app);
  assert.match(panel.textContent, /Revenue basis is unknown/);
  assert.match(panel.querySelectorAll('.source-record')[1].textContent, /Metric revenue basis: Unknown — not supplied/);
  assert.doesNotMatch(panel.textContent, /Reported date ranges differ|Reported revenue-basis labels differ/);
  assert.match(panel.textContent, /Matching dates, units or basis labels do not establish equivalent accounting scope/);
  assert.match(panel.textContent, /Industry and share-basis eligibility are not established/);
  const same = contract.metricComparability('revenue', [a, response('BBB', 2025)]);
  assert.deepEqual(same, { windowsDiffer: false, missingWindow: false, basesDiffer: false, basisUnknown: false, excluded: 0, unverified: 0 });
  assert.equal(Object.hasOwn(same, 'equivalent'), false);
});

test('derived inspector uses only its own returned revenue operands and retains separate prior/current dates', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const make = ticker => {
    const result = response(ticker, 2025, { basis: 'net_interest' });
    const current = result.metrics.revenue.provenance[0];
    const prior = { ...current, fact_id: 100, period_start: '2024-01-01', period_end: '2024-12-31' };
    result.metrics.revenue_growth_yoy = { ...result.metrics.revenue_growth_yoy, status: 'available', reason: null,
      value: '0.25', provenance: [current, prior], inputs: [
        { role: 'current', metric: 'revenue', unit: 'USD', value: '100', fact_ids: [current.fact_id], period: result.period, revenue_basis: 'total_revenue' },
        { role: 'prior', metric: 'revenue', unit: 'USD', value: '80', fact_ids: [100],
          period: { ...result.period, start: '2024-01-01', end: '2024-12-31', fiscal_year: 2024 }, revenue_basis: 'total_revenue' },
      ] };
    return result;
  };
  const a = make('AAA'); const b = make('BBB');
  b.metrics.revenue_growth_yoy.inputs[0].revenue_basis = 'future_basis__literal';
  delete b.metrics.revenue_growth_yoy.inputs[1].revenue_basis;
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), a);
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), b);
  const panel = inspector(app, 'revenue_growth_yoy');
  assert.match(panel.textContent, /Reported revenue-basis labels differ/);
  assert.match(panel.textContent, /Revenue basis is unknown/);
  assert.match(panel.textContent, /Operand: current · revenueOperand reporting period: 2025-01-01 – 2025-12-31/);
  assert.match(panel.textContent, /Operand: prior · revenueOperand reporting period: 2024-01-01 – 2024-12-31/);
  assert.match(panel.textContent, /Operand revenue basis: future_basis__literal/);
  assert.match(panel.textContent, /Operand revenue basis: Unknown — not supplied for this operand/);
  assert.doesNotMatch(panel.textContent, /net_interest/, 'Never borrow the other metric basis');
  assert.equal(app.host.querySelectorAll('tbody tr')[1].querySelector('.metric-value').textContent, '25%');
  assert.equal(app.requests.length, 6);
});

test('unverified response remains an unknown inspector participant and copy stays disabled', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), response('AAA', 2025), '9');
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025));
  const panel = inspector(app);
  assert.match(panel.textContent, /1 of 2 company responses could not be verified/);
  const failed = panel.querySelector('.source-record');
  assert.match(failed.textContent, /AAAFinancial evidence not verified: Published data changed/);
  assert.doesNotMatch(failed.textContent, /Reporting period:|Metric revenue basis:|Available/);
  assert.equal(noteButton(app).disabled, true);
  assert.equal(app.requests.length, 6);
});

test('all eleven inspectors include four companies without claiming equivalence or adding requests', async ctx => {
  const app = await focusTable(ctx, 4);
  const disclosures = [...app.host.querySelectorAll('tbody th details')];
  assert.equal(disclosures.length, 11);
  for (const [index, panel] of disclosures.entries()) {
    assert.equal(panel.querySelectorAll('.source-record').length, 4);
    assert.equal(panel.querySelector('summary').textContent, `Inspect ${['Revenue', 'Revenue YoY', 'Operating margin', 'Net margin', 'Operating cash flow', 'Capital expenditures', 'Free cash flow', 'Gross profit', 'Operating income', 'Net income', 'Gross margin'][index]} comparability`);
    assert.equal(panel.open, false);
    assert.match(panel.textContent, /Matching dates, units or basis labels do not establish/);
  }
  assert.equal(app.host.querySelectorAll('tbody td').length, 44);
  assert.equal(app.requests.length, 12);
});

test('inspector focus uses existing reveal policy and a fiscal-year change discards old disclosure content', async ctx => {
  const app = await focusTable(ctx);
  const panel = inspector(app); const target = panel.querySelector('summary');
  const geo = focusGeometry(ctx, app.scroller, target, { top: -0.15625, initialY: 500 });
  await act(async () => target.focus());
  assert.equal(document.activeElement, target);
  assert.equal(geo.position(), 73); assert.equal(geo.pageY(), 492);
  await act(async () => target.click()); assert.equal(panel.open, true);
  await app.change('#comparison-year', 2024);
  assert.equal(app.host.querySelector('table'), null);
  assert.equal(panel.isConnected, false);
  for (const ticker of ['AAA', 'BBB']) await app.release(app.request(ticker, 'financials/annual?fiscal_year=2024'), response(ticker, 2024));
  const next = inspector(app);
  assert.equal(next.open, false);
  assert.match(next.textContent, /2024-01-01 – 2024-12-31/);
  assert.doesNotMatch(next.textContent, /2025-01-01|2025-12-31/);
  assert.equal(app.requests.length, 8);
});

test('malformed operand metric is contained as an unverified column while the valid peer remains visible', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const malformed = response('AAA', 2025);
  malformed.metrics.free_cash_flow.inputs = [{ role: 'operating_cash_flow', metric: { unexpected: 'value' },
    value: '-7', unit: 'USD', period: malformed.period, fact_ids: [malformed.metrics.operating_cash_flow.provenance[0].fact_id] }];
  assert.throws(() => contract.validateAnnualResponse(malformed, company('AAA'), 2025), e => e.code === 'INVALID_RESPONSE');
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), malformed);
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025));
  assert.equal(app.host.querySelectorAll('tbody tr').length, 11, 'Rendering survives the malformed column');
  assert.match(app.host.querySelector('tbody td').textContent, /does not match this company/);
  assert.equal(app.host.querySelector('tbody td:nth-child(3) .metric-value').textContent, '$1B');
  const panel = inspector(app, 'free_cash_flow');
  assert.match(panel.textContent, /1 of 2 company responses could not be verified/);
  assert.match(panel.querySelector('.source-record').textContent, /AAAFinancial evidence not verified/);
  assert.match(panel.querySelectorAll('.source-record')[1].textContent, /BBBAvailable/);
  assert.equal(noteButton(app).disabled, true);
  assert.equal(noteButton(app, 'Free cash flow').disabled, true);
  assert.equal(app.requests.length, 6);
});

test('unknown string operand metric is accepted verbatim and rendered only as inert text', async ctx => {
  const app = await mount(ctx); await app.select(); await app.discovery();
  const result = response('AAA', 2025);
  const raw = 'future_metric__v9  <img src=x onerror="run()">\nretain_label';
  result.metrics.free_cash_flow.inputs = [{ role: 'operating_cash_flow', metric: raw,
    value: '-7', unit: 'USD', period: result.period, fact_ids: [result.metrics.operating_cash_flow.provenance[0].fact_id] }];
  assert.equal(contract.validateAnnualResponse(result, company('AAA'), 2025), result);
  assert.equal(result.metrics.free_cash_flow.inputs[0].metric, raw);
  await app.release(app.request('AAA', 'financials/annual?fiscal_year=2025'), result);
  await app.release(app.request('BBB', 'financials/annual?fiscal_year=2025'), response('BBB', 2025));
  const panel = inspector(app, 'free_cash_flow');
  const operand = [...panel.querySelectorAll('p')].find(p => p.textContent.startsWith('Operand: '));
  assert.equal(operand.textContent, `Operand: operating_cash_flow · ${raw}`);
  assert.equal(panel.querySelector('img'), null);
  assert.doesNotMatch(panel.textContent, /company responses could not be verified/);
  assert.equal(noteButton(app).disabled, false);
  assert.equal(app.requests.length, 6);
});
