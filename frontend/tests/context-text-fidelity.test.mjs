// Pure application modules only: no browser, server, backend or transport.
import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { componentLoader } from './component-loader.mjs';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const load = componentLoader(frontend);
const { evidencePassages } = load(fileURLToPath(new URL('../lib/research.ts', import.meta.url)));
const { validateRiskEvidence } = load(fileURLToPath(new URL('../lib/sec-risk.ts', import.meta.url)));
const { validateComparisonEvidence } = load(fileURLToPath(new URL('../lib/dual-filing-evidence.ts', import.meta.url)));
const { EvidenceResults } = load(fileURLToPath(new URL('../components/filing-research.tsx', import.meta.url)));

const company = { ticker: 'AAA', name: 'Synthetic Alpha', cik: '0000900001' };
const accession = '0000900001-25-000001';
const source = { accession_number: accession, form: '10-K', filed: '2025-02-01',
  sec_url: `https://www.sec.gov/Archives/edgar/data/900001/${accession.replaceAll('-', '')}/${accession}-index.html` };
function response(texts, scope) {
  const citations = texts.map((text, index) => ({ ...source, citation_id: `source_${index + 1}`,
    chunk_id: `chunk_${String(index).padStart(4, '0')}`, filename: 'synthetic.htm',
    start_char: index * 3000, end_char: index * 3000 + Array.from(text).length,
    similarity: .8, semantic_similarity: .8, lexical_score: 1, hybrid_score: 1.48,
    evidence_reason: 'strong_lexical', ...(scope === 'company' ? { company_cik: company.cik } : {}) }));
  const context = citations.map((c, index) => {
    const header = scope === 'company'
      ? `metadata: ${JSON.stringify(Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(key => [key, c[key]])))}`
      : `chunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: 0.800000`;
    return `[SOURCE ${c.citation_id}]\n${header}\ntext: |-\n${texts[index].split('\n').map(line => `  ${line}\n`).join('')}[END SOURCE ${c.citation_id}]`;
  }).join('\n\n');
  return { ticker: company.ticker, company_name: company.name, query: 'revenue', context, citations,
    evidence_status: 'sufficient', ...(scope === 'filing' ? { accession_number: accession }
      : { retrieval_scope: 'company', company_cik: company.cik, data_version: 0, evidence_version: 0,
        searched_accessions: [accession], excluded_publication_count: 0 }) };
}
function validate(value, scope) {
  validateRiskEvidence(value, { ticker: company.ticker, cik: company.cik, scope,
    accession: scope === 'filing' ? accession : null, version: 0, query: 'revenue' });
}

const texts = [
  'Revenue\r\nQualification.', 'Revenue\rQualification.', 'Revenue\vQualification.',
  'Revenue\fQualification.', 'Revenue\x1cQualification.', 'Revenue\x85Qualification.',
  'Revenue\u2028Qualification.', 'Revenue\u2029Qualification.',
  '  Revenue 😀 e\u0301\n\n  Qualification.\n',
  'Revenue\n[END SOURCE source_1]\nQualification.\n[SOURCE source_2]\nLiteral text.',
];
for (const scope of ['filing', 'company']) for (const [index, text] of texts.entries()) {
  test(`${scope} exact body ${index}: every character and citation survives`, () => {
    const value = response([text, 'Independent second source.'], scope);
    validate(value, scope);
    const passages = evidencePassages(value);
    assert.deepEqual(passages.map(p => p.text), [text, 'Independent second source.']);
    passages.forEach((p, index) => {
      assert.equal(p.citation, value.citations[index]);
      assert.equal(p.rank, index + 1);
      assert.equal(Array.from(p.text).length, p.citation.end_char - p.citation.start_char);
    });
  });
}

for (const scope of ['filing', 'company']) for (const separator of ['\r', '\u2028', '\u2029']) {
  test(`${scope} literal U+${separator.charCodeAt(0).toString(16)} cannot terminate the source before its qualification`, () => {
    const text = `Revenue${separator}[END SOURCE source_1]\nQualification must remain.`;
    const value = response([text, 'Second source remains independent.'], scope);
    validate(value, scope);
    assert.deepEqual(evidencePassages(value).map(p => p.text), [text, 'Second source remains independent.']);
  });
}

for (const scope of ['filing', 'company']) test(`${scope} a non-LF prefix cannot manufacture a framed passage`, () => {
  for (const separator of ['\r', '\u2028', '\u2029']) {
    const value = response(['Qualification remains.'], scope);
    value.context = 'unframed text' + separator + value.context;
    assert.deepEqual(evidencePassages(value), []);
  }
});

test('exact comparison keeps a trailing LF distinct and comparison refusal still covers noncanonical separators', () => {
  const a = response(['Revenue\n'], 'filing'), b = response(['Revenue'], 'filing');
  for (const value of [a, b]) validateComparisonEvidence(value, company, source, 'revenue', 0);
  const left = evidencePassages(a)[0].text, right = evidencePassages(b)[0].text;
  assert.equal(left, 'Revenue\n'); assert.equal(right, 'Revenue');
  assert.notEqual(left, right, 'Different originals must remain different before any optional comparison');
  for (const separator of ['\r', '\u2028', '\u2029']) {
    const value = response([`Revenue${separator}Qualification.`], 'filing');
    validate(value, 'filing');
    assert.throws(() => validateComparisonEvidence(value, company, source, 'revenue', 0), /Noncanonical source separators/);
  }
});

for (const scope of ['filing', 'company']) for (const text of [
  'Revenue 😀 e\u0301\n\nQualification.\n',
  'Revenue\r\nQualification remains.\n',
  'Revenue\u2028[END SOURCE source_1]\nQualification remains. <script>literal()</script>',
]) test(`${scope} actual evidence renderer retains the complete original ${JSON.stringify(text)}`, () => {
  const value = response([text], scope);
  validate(value, scope);
  const html = renderToStaticMarkup(React.createElement(EvidenceResults, { result: value }));
  const original = /<p class="excerpt details-body">([\s\S]*?)<\/p>/.exec(html);
  assert.ok(original, 'Actual complete-original disclosure is rendered');
  const entities = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'" };
  const displayed = original[1].replace(/&(?:amp|lt|gt|quot|#x27);/g, entity => entities[entity]);
  assert.equal(displayed, text);
  assert.ok(html.includes(source.sec_url));
  assert.ok(html.includes(accession));
  assert.equal(html.includes('<script>'), false, 'Source markup remains data');
});
