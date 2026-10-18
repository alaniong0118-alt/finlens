import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { filingToneIdentity, validateFilingToneResponse, countFilingToneTokens, FILING_TONE_UNICODE_VERSION } from '../lib/finlens-api.ts';
import { codePointBoundaries, toneParts } from '../lib/filing-tone.ts';

const accession = '0000320193-26-000020';
const url = `https://www.sec.gov/Archives/edgar/data/320193/${accession.replaceAll('-', '')}/${accession}-index.html`;
const company = { ticker: 'AAPL', cik: '0000320193' };
const citation = { accession_number: accession, chunk_id: 'chunk_0000', form: '10-Q', filed: '2026-07-31', filename: 'report.htm', sec_url: url };
const identity = filingToneIdentity(company, citation);
function fixture() {
  return { ticker: 'AAPL', company_cik: company.cik, company_name: 'Synthetic Apple fixture', data_version: 2, evidence_version: 1,
    publication: { accession_number: accession, data_version: 0, content_digest: 'a'.repeat(64) },
    source: { chunk_id: 'chunk_0000', form: '10-Q', filed: citation.filed, filename: citation.filename, sec_url: url },
    scope: 'published_chunk', offsets: 'unicode_code_point', text: 'strong strong weak',
    tone: { method_version: 'sec-filing-tone-v1', lexicon_version: 'authored-finance-tone-v1', status: 'scored', reason: null,
      score: { numerator: 1, denominator: 3 }, token_count: 3, positive_count: 2, negative_count: 1, negated_count: 0,
      matches: [{ text: 'strong', term: 'strong', start: 0, end: 6, polarity: 'positive', negator_span: null },
        { text: 'strong', term: 'strong', start: 7, end: 13, polarity: 'positive', negator_span: null },
        { text: 'weak', term: 'weak', start: 14, end: 18, polarity: 'negative', negator_span: null }] } };
}
const invalid = error => error.code === 'INVALID_RESPONSE' && error.status === 502;

test('P2 token_count rejects strong weak falsely declaring eleven tokens', () => {
  const value = fixture(); value.text = 'strong weak';
  Object.assign(value.tone, { token_count: 11, positive_count: 1, score: { numerator: 0, denominator: 1 },
    matches: [value.tone.matches[0], { ...value.tone.matches[2], start: 7, end: 11 }] });
  assert.throws(() => validateFilingToneResponse(value, identity, 2), invalid);
});

function tokenKernelProbe(code) {
  const python = ['.venv/Scripts/python.exe', '.venv/bin/python']
    .map(path => fileURLToPath(new URL(`../../backend/${path}`, import.meta.url))).find(existsSync) ?? 'python';
  const prefix = `import json,runpy\nrunpy.run_path('tests/run_dep01a2_increment2_offline.py',run_name='token_contract_guard')\n`;
  const result = spawnSync(python, ['-B', '-c', prefix + code], { cwd: fileURLToPath(new URL('../../backend', import.meta.url)),
    encoding: 'utf8', timeout: 20000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test('P2 token_count word categories equal the actual Python kernel for all 1114112 code points', () => {
  const expected = tokenKernelProbe(`import hashlib,unicodedata
from app.filing_tone import _word_character
mask=bytes(_word_character(chr(code)) for code in range(0x110000))
print(json.dumps({'unicode':unicodedata.unidata_version,'sha256':hashlib.sha256(mask).hexdigest()}))`);
  assert.equal(expected.unicode, FILING_TONE_UNICODE_VERSION, 'Backend Unicode changes require an explicitly regenerated and reviewed category snapshot');
  const actual = new Uint8Array(0x110000);
  for (let code = 0; code < actual.length; code++) actual[code] = countFilingToneTokens(String.fromCodePoint(code));
  assert.equal(createHash('sha256').update(actual).digest('hex'), expected.sha256);
});

test('P2 token_count accepts exact serialized cross-language Unicode boundaries and rejects count contradictions', () => {
  const samples = [
    'strong weak', '  📈\r\nSTRONG no loss; weak <script>unsafe()</script> e\u0301',
    'strong strong weak', 'not strong', 'not strong weak', 'not only strong',
    '2026', '...', ' ,\r\n\t.', '中文 日本語 한글', '𐐀 strong weak', '𐐀strong', '📈strong📉weak',
    'e\u0301 strong', '\u0301 strong', 'strong\u0301 weak', '📈\ufe0f strong', '\u{1e000}strong',
    '١٢٣ Ⅳ ½ 𝟘 strong', '123strong', 'strong_weak', 'strong\u203fweak', '\u2054',
    "can't strong", 'CAN’T strong', "'strong'", '’strong’', "strong's weak", 'strong’s weak',
    "strong''weak", 'strong’’weak', 'strong‘weak', 'strong＇weak', 'strong\u02bcweak',
    'strong’\u0301weak', "'\u0301'", 'strong—weak', 'strong,weak;loss', 'strong\r\nweak',
    'strong\u2028weak\u2029loss', 'strong\u00a0weak\u202floss', 'strong\u088fweak', '\u088f',
  ];
  const values = tokenKernelProbe(`from datetime import date
from app.filing_tone_service import PublishedPassage,TonePublication,ToneSource,score_published_passage
samples=json.loads(${JSON.stringify(JSON.stringify(samples))})
values=[]
for text in samples:
 passage=PublishedPassage('AAPL','0000320193','Synthetic token fixture',2,1,TonePublication(accession_number='${accession}',data_version=0,content_digest='a'*64),ToneSource(chunk_id='chunk_0000',form='10-Q',filed=date(2026,7,31),filename='report.htm',sec_url='${url}'),text)
 values.append(score_published_passage(passage).model_dump(mode='json'))
print(json.dumps(values,ensure_ascii=True))`);
  assert.equal(values.length, samples.length);
  for (const [index, value] of values.entries()) {
    assert.equal(value.text, samples[index]);
    assert.equal(countFilingToneTokens(value.text), value.tone.token_count, JSON.stringify(value.text));
    validateFilingToneResponse(value, identity, 2);
    assert.equal(toneParts(value).map(part => part.text).join(''), value.text);
    const contradiction = structuredClone(value); contradiction.tone.token_count++;
    assert.throws(() => validateFilingToneResponse(contradiction, identity, 2), invalid, JSON.stringify(value.text));
  }
  assert.deepEqual(values[0].tone.score, { numerator: 0, denominator: 1 });
  assert.equal(values[3].tone.reason, 'all_matches_negated');
  assert.equal(values[6].tone.reason, 'no_lexicon_matches');
  assert.equal(values[7].tone.reason, 'no_tokens');
  assert.equal(values[41].tone.token_count, 2, 'Python UCD 16 treats U+088F as a separator, regardless of browser Unicode');
  assert.equal(values[42].tone.token_count, 0);
});

test('tone source resolves optional citation CIK only through the selected company', () => {
  assert.equal(identity.company_cik, company.cik);
  assert.deepEqual(filingToneIdentity(company, { ...citation, company_cik: company.cik }), identity);
  assert.equal(filingToneIdentity(company, { ...citation, company_cik: '0000019617' }), null);
  assert.equal(filingToneIdentity(company, { ...citation, company_cik: null }), null);
  // Accession submitter digits are not used as an inferred company identity.
  const otherAccession = '0001193125-26-000001';
  const otherUrl = `https://www.sec.gov/Archives/edgar/data/320193/${otherAccession.replaceAll('-', '')}/${otherAccession}-index.html`;
  assert.equal(filingToneIdentity(company, { ...citation, accession_number: otherAccession, sec_url: otherUrl }).company_cik, company.cik);
});

for (const [name, patch] of [
  ['unknown date', { filed: null }], ['impossible date', { filed: '2026-02-30' }], ['non-date', { filed: '2026-2-3' }],
  ['year zero', { filed: '0000-01-01' }],
  ['missing filename', { filename: '' }], ['filename path', { filename: '../report.htm' }], ['dot filename', { filename: '..' }],
  ['unknown form', { form: '8-K' }], ['noncanonical chunk', { chunk_id: 'chunk_1' }], ['invalid accession', { accession_number: 'fixture' }],
  ...['https://www.sec.gov/Archives/other', url + '?x=1', url + '#passage', url.replace('320193/', '19617/'),
    url.replace('www.sec.gov', 'sec.gov'), url.replace('https:', 'http:'), url.replace('www.sec.gov', 'www.sec.gov:443'),
    url.replace('www.sec.gov', 'user@www.sec.gov'), url.replace('-index.html', '.txt')].map((sec_url, index) => [`unbound URL ${index}`, { sec_url }]),
]) test(`tone source refuses ${name}`, () => assert.equal(filingToneIdentity(company, { ...citation, ...patch }), null));

for (const version of [0, 2, Number.MAX_SAFE_INTEGER]) test(`tone accepts verified version ${version} and older intact filing publication`, () => {
  const value = fixture(); value.data_version = version; value.evidence_version = version;
  validateFilingToneResponse(JSON.parse(JSON.stringify(value)), identity, version);
  assert.deepEqual(value.tone.score, { numerator: 1, denominator: 3 });
});

const mutations = [
  ['ticker', v => { v.ticker = 'JPM'; }], ['CIK', v => { v.company_cik = '0000019617'; }],
  ['company name', v => { v.company_name = ''; }], ['body pin', v => { v.data_version = 1; }],
  ['unknown scope', v => { v.scope = 'filing'; }], ['UTF16 offsets', v => { v.offsets = 'utf16'; }],
  ['extra field', v => { v.approved = true; }], ['missing source', v => { delete v.source; }],
  ['source array', v => { v.source = []; }], ['tone null', v => { v.tone = null; }],
  ['accession', v => { v.publication.accession_number = '0000320193-25-000001'; }],
  ['publication newer than evidence', v => { v.publication.data_version = 2; }],
  ['evidence newer than company', v => { v.evidence_version = 3; }],
  ...[null, -1, 1.5, '1', true, Number.MAX_SAFE_INTEGER + 1, -0].map((bad, i) => [`invalid evidence pin ${i}`, v => { v.evidence_version = bad; }]),
  ...[null, -1, 0.5, '0', Number.MAX_SAFE_INTEGER + 1].map((bad, i) => [`invalid filing pin ${i}`, v => { v.publication.data_version = bad; }]),
  ['digest length', v => { v.publication.content_digest = 'a'.repeat(63); }],
  ['digest case', v => { v.publication.content_digest = 'A'.repeat(64); }],
  ...Object.entries({ chunk_id: 'chunk_0001', form: '10-K', filed: '2026-07-30', filename: 'other.htm', sec_url: url + '#x' })
    .map(([key, value]) => [`source ${key}`, v => { v.source[key] = value; }]),
  ['method', v => { v.tone.method_version = 'future'; }], ['lexicon', v => { v.tone.lexicon_version = 'future'; }],
  ['status', v => { v.tone.status = 'neutral'; }], ['reason on scored', v => { v.tone.reason = 'no_tokens'; }],
  ['null scored fraction', v => { v.tone.score = null; }], ['fraction unreduced', v => { v.tone.score = { numerator: 2, denominator: 6 }; }],
  ['zero denominator', v => { v.tone.score.denominator = 0; }], ['negative denominator', v => { v.tone.score.denominator = -3; }],
  ['wrong fraction', v => { v.tone.score.numerator = -1; }], ['unsafe fraction', v => { v.tone.score.numerator = Number.MAX_SAFE_INTEGER + 1; }],
  ['fraction string', v => { v.tone.score.numerator = '1'; }], ['fraction extra field', v => { v.tone.score.value = 0.33; }],
  ['token count', v => { v.tone.token_count = 2; }], ['zero tokens with words', v => { v.tone.token_count = 0; }],
  ['count string', v => { v.tone.positive_count = '2'; }], ['unsafe count', v => { v.tone.negative_count = Number.MAX_SAFE_INTEGER + 1; }],
  ['negative count', v => { v.tone.negated_count = -1; }], ['active count mismatch', v => { v.tone.positive_count = 1; }],
  ['negated count mismatch', v => { v.tone.negated_count = 1; }], ['missing match array', v => { v.tone.matches = null; }],
  ['negative offset', v => { v.tone.matches[0].start = -1; }], ['unsafe offset', v => { v.tone.matches[0].end = Number.MAX_SAFE_INTEGER + 1; }],
  ['fractional offset', v => { v.tone.matches[0].start = 0.5; }], ['string offset', v => { v.tone.matches[0].end = '6'; }],
  ['zero width', v => { v.tone.matches[0].end = 0; }], ['out of bounds', v => { v.tone.matches[2].end = 19; }],
  ['overlap', v => { v.tone.matches[1].start = 5; }], ['reordered', v => { v.tone.matches.reverse(); }],
  ['substring', v => { v.tone.matches[0].text = 'STRONG'; }], ['term', v => { v.tone.matches[0].term = 'profitable'; }],
  ['polarity', v => { v.tone.matches[0].polarity = 'negative'; }], ['unknown polarity', v => { v.tone.matches[0].polarity = 'neutral'; }],
  ['missing negator field', v => { delete v.tone.matches[0].negator_span; }],
  ['negator object', v => { v.tone.matches[0].negator_span = {}; }], ['negator at match', v => { v.tone.matches[0].negator_span = [0, 6]; }],
  ['non-negator text', v => { v.tone.matches[2].negator_span = [0, 6]; }],
  ['unknown text type', v => { v.text = 3; }], ['oversized text', v => { v.text = 'a'.repeat(3001); }],
  ['control text', v => { v.text += '\u0000'; }], ['format control', v => { v.text += '\u200d'; }], ['lone surrogate', v => { v.text += '\ud800'; }],
  ['partial word', v => { v.text = 'stronger strong weak'; }], ['apostrophe continuation', v => { v.text = "strong's strong weak"; }],
];
for (const [name, mutate] of mutations) test(`tone wire validation rejects ${name}`, () => {
  const value = fixture(); mutate(value);
  assert.throws(() => validateFilingToneResponse(value, identity, 2), invalid);
});
for (const value of [null, false, 1, '', [], {}]) test(`tone rejects malformed envelope ${JSON.stringify(value)}`, () => {
  assert.throws(() => validateFilingToneResponse(value, identity, 2), invalid);
});
for (const pin of [null, -1, '2', 2.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, -0]) test(`tone rejects unverified request pin ${String(pin)}`, () => {
  assert.throws(() => validateFilingToneResponse(fixture(), identity, pin), invalid);
});

test('tone validates actual backend serialization and converts exact Unicode spans without re-tokenizing', () => {
  const python = ['.venv/Scripts/python.exe', '.venv/bin/python']
    .map(path => fileURLToPath(new URL(`../../backend/${path}`, import.meta.url))).find(existsSync) ?? 'python';
  const code = `import json,runpy
runpy.run_path('tests/run_dep01a2_increment2_offline.py',run_name='contract_probe_guard')
from app.filing_tone_service import PublishedPassage,TonePublication,ToneSource,score_published_passage
from datetime import date
samples=['  \\U0001f4c8\\r\\nSTRONG no loss; weak <script>unsafe()</script> e\\u0301','\\U00010400 strong weak','not strong weak',"CAN’T strong",'not only strong','2026','...','strong strong weak','weak weak','STRONG','strong '*428+'word']
responses=[]
for text in samples:
 p=PublishedPassage('AAPL','0000320193','Synthetic contract fixture',2,1,TonePublication(accession_number='${accession}',data_version=0,content_digest='a'*64),ToneSource(chunk_id='chunk_0000',form='10-Q',filed=date(2026,7,31),filename='report.htm',sec_url='${url}'),text)
 responses.append(score_published_passage(p).model_dump(mode='json'))
print(json.dumps(responses,ensure_ascii=True))`;
  const run = spawnSync(python, ['-B', '-c', code], { cwd: fileURLToPath(new URL('../../backend', import.meta.url)), encoding: 'utf8', timeout: 20000,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(run.status, 0, run.stderr);
  const values = JSON.parse(run.stdout);
  for (const value of values) {
    validateFilingToneResponse(value, identity, 2);
    const parts = toneParts(value);
    assert.equal(parts.map(part => part.text).join(''), value.text);
    assert.deepEqual(parts.filter(part => part.match).map(part => part.text), value.tone.matches.map(match => match.text));
    for (const match of value.tone.matches) {
      const broken = structuredClone(value); broken.tone.matches[0].end = 0;
      assert.throws(() => validateFilingToneResponse(broken, identity, 2), invalid);
      if (match.negator_span) assert.ok(match.negator_span[1] <= match.start);
    }
  }
  assert.equal(values[0].tone.matches[0].start, 5);
  assert.notEqual(values[0].text.slice(5, 11), values[0].tone.matches[0].text);
  assert.deepEqual(values[0].tone.score, { numerator: 0, denominator: 1 });
  assert.equal(values[2].tone.score, null);
  assert.equal(values[2].tone.reason, 'all_matches_negated');
  assert.equal(values[5].tone.reason, 'no_lexicon_matches');
  assert.equal(values[6].tone.reason, 'no_tokens');
  assert.deepEqual(values[8].tone.score, { numerator: -1, denominator: 1 });
  assert.deepEqual(values[9].tone.score, { numerator: 1, denominator: 1 });
  assert.equal(Array.from(values[10].text).length, 3000);
  assert.deepEqual(codePointBoundaries('📈\r\ne\u0301𐐀'), [0, 2, 3, 4, 5, 6, 8]);
});

test('tone styles inherit wrapping, 44px controls, visible focus and both theme variables', () => {
  const css = readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
  assert.match(css, /\.excerpt\s*\{[^}]*white-space:pre-wrap;[^}]*overflow-wrap:anywhere/);
  assert.match(css, /button\s*\{[^}]*min-height:44px/);
  assert.match(css, /:focus-visible\s*\{[^}]*outline:3px/);
  assert.match(css, /\.passage-tone > section\s*\{[^}]*min-width:0;[^}]*overflow-wrap:anywhere/);
  assert.match(css, /:root\[data-theme="dark"\]/);
});
