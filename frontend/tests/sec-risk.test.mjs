import test from 'node:test';
import assert from 'node:assert/strict';
import { RISK_TOPICS, RISK_EXPLANATION, riskTopic, riskQueryLabel, validateRiskEvidence, RiskEvidenceError } from '../lib/sec-risk.ts';
import { getFilingContext, getCompanyContext, versionedController, FinLensApiError } from '../lib/finlens-api.ts';

// Handwritten synthetic responses in the exact inspected backend serialization.
const cik = '0000900001', acc = '0000900001-25-000001';
const request = (scope = 'filing', version = 0) => ({ ticker: 'AAA', cik, scope, accession: scope === 'filing' ? acc : null, version, query: 'supply chain' });
function fixture(scope = 'filing', version = 0, texts = ['Synthetic issuer: supply chain disruptions may affect operations.']) {
  const citations = texts.map((text, index) => ({ citation_id: `source_${index + 1}`, chunk_id: `chunk_${String(index).padStart(4, '0')}`,
    accession_number: acc, form: '10-Q', filed: '2025-05-01', filename: 'report.htm', start_char: index * 3000, end_char: index * 3000 + Array.from(text).length,
    sec_url: `https://www.sec.gov/Archives/edgar/data/900001/${acc.replaceAll('-', '')}/${acc}-index.html`,
    similarity: 0.87654321, semantic_similarity: 0.87654321, lexical_score: 1, hybrid_score: 1.525925926, evidence_reason: 'strong_lexical',
    ...(scope === 'company' ? { company_cik: cik } : {}) }));
  const context = citations.map((c, index) => {
    const headers = scope === 'company' ? `metadata: ${JSON.stringify(Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(k => [k, c[k]])))}`
      : `chunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: ${c.similarity.toFixed(6)}`;
    return `[SOURCE ${c.citation_id}]\n${headers}\ntext: |-\n${texts[index].split('\n').map(line => `  ${line}`).join('\n')}\n[END SOURCE ${c.citation_id}]`;
  }).join('\n\n');
  return { ticker: 'AAA', company_name: 'Synthetic issuer', query: 'supply chain', context, citations, evidence_status: citations.length ? 'sufficient' : 'insufficient',
    ...(scope === 'company' ? { retrieval_scope: 'company', company_cik: cik, data_version: version, evidence_version: version, searched_accessions: [acc], excluded_publication_count: 0 } : { accession_number: acc }) };
}

test('RISK-SEC-01 six immutable guides are exact search mappings, not scores', () => {
  assert.deepEqual(RISK_TOPICS.map(t => [t.id, t.query]), [['supply_chain', 'supply chain'], ['competition', 'competition'], ['cybersecurity', 'cybersecurity'], ['regulation', 'regulatory'], ['liquidity', 'liquidity'], ['foreign_exchange', 'foreign exchange']]);
  assert.equal(new Set(RISK_TOPICS.map(t => t.id)).size, 6);
  assert.ok(Object.isFrozen(RISK_TOPICS));
  for (const topic of RISK_TOPICS) {
    assert.ok(Object.isFrozen(topic)); assert.equal(riskTopic(topic.id), topic);
    assert.throws(() => { topic.query = 'replacement'; }, TypeError);
    assert.equal(riskQueryLabel(topic.query), topic.label);
  }
  assert.throws(() => RISK_TOPICS.push({}), TypeError);
  assert.equal(riskTopic('__proto__'), null); assert.equal(riskTopic('unknown'), null);
  assert.equal(riskQueryLabel('competition revised'), 'Custom risk-topic search');
  assert.equal(riskQueryLabel(' competition '), riskTopic('competition').label);
  assert.match(RISK_EXPLANATION, /not risk severity or probability/);
  assert.match(RISK_EXPLANATION, /Background matches may not constitute actual risk disclosures/);
  assert.match(RISK_EXPLANATION, /No result does not mean no risk/);
  assert.match(RISK_EXPLANATION, /no investment recommendation/);
  assert.doesNotMatch(RISK_EXPLANATION, /\d/);
});

for (const scope of ['filing', 'company']) for (const version of [0, 4]) {
  test(`RISK-SEC-01 ${scope} accepts real backend shape at pin ${version} without changing text or metadata`, () => {
    const value = fixture(scope, version, ['Synthetic supply chain <script>literal()</script>.\n\n  Indented text 😀.', '[SOURCE source_9]\nLiteral source-like text.']);
    const original = structuredClone(value);
    validateRiskEvidence(value, request(scope, version)); assert.deepEqual(value, original);
    const empty = fixture(scope, version, []);
    validateRiskEvidence(empty, request(scope, version)); assert.equal(empty.evidence_status, 'insufficient');
  });
}

const mutations = [
  ['wrong company', v => { v.ticker = 'BBB'; }], ['wrong query', v => { v.query += ' other'; }],
  ['missing company name', v => { delete v.company_name; }], ['unknown root shape', v => { v.fake_risk = 4; }],
  ['wrong citations type', v => { v.citations = {}; }], ['unknown status', v => { v.evidence_status = 'no_risk'; }],
  ['contradictory insufficient', v => { v.evidence_status = 'insufficient'; }], ['empty sufficient', v => { v.citations = []; v.context = ''; }],
  ['missing context body', v => { v.context = ''; }], ['orphan block', v => { v.context += '\n\n' + v.context; }],
  ['changed block ID', v => { v.context = v.context.replaceAll('source_1', 'source_2'); }],
  ['unindented body', v => { v.context = v.context.replace('\n  Synthetic', '\nSynthetic'); }],
  ['oversized context', v => { v.context = 'x'.repeat(24001); }],
  ['duplicate source IDs', v => { v.citations.push(structuredClone(v.citations[0])); v.context += '\n\n' + v.context; }],
  ['noncanonical source ID', v => { v.citations[0].citation_id = 'source_01'; }],
  ['wrong citation CIK', v => { v.citations[0].company_cik = '0000900002'; }],
  ['malformed accession', v => { v.citations[0].accession_number = 'unknown'; }],
  ['wrong accession', v => { v.citations[0].accession_number = '0000900002-25-000001'; }],
  ['wrong chunk ID', v => { v.citations[0].chunk_id = 'chunk_0001'; }],
  ['unsupported chunk shape', v => { v.citations[0].chunk_id = '../chunk_0000'; }],
  ['missing field', v => { delete v.citations[0].filename; }],
  ['unsupported citation field', v => { v.citations[0].severity = 4; }],
  ['invalid date', v => { v.citations[0].filed = '2025-02-30'; }], ['missing date', v => { v.citations[0].filed = null; }],
  ['unknown form', v => { v.citations[0].form = '8-K'; }],
  ['directory filename', v => { v.citations[0].filename = '../report.htm'; }],
  ['wrong URL CIK', v => { v.citations[0].sec_url = v.citations[0].sec_url.replace('/900001/', '/900002/'); }],
  ['wrong URL accession', v => { v.citations[0].sec_url = v.citations[0].sec_url.replace('-index.html', '.txt'); }],
  ['wrong URL host', v => { v.citations[0].sec_url = v.citations[0].sec_url.replace('www.sec.gov', 'sec.gov.evil.test'); }],
  ['URL query', v => { v.citations[0].sec_url += '?x=1'; }], ['URL credentials', v => { v.citations[0].sec_url = v.citations[0].sec_url.replace('https://', 'https://user@'); }],
  ['invalid URL', v => { v.citations[0].sec_url = 'javascript:alert(1)'; }],
  ['negative offset', v => { v.citations[0].start_char = -1; }], ['reversed offsets', v => { v.citations[0].end_char = 0; }],
  ['nonfinite score', v => { v.citations[0].similarity = NaN; }], ['invalid reason', v => { v.citations[0].evidence_reason = 'risk_confirmed'; }],
];
for (const scope of ['filing', 'company']) for (const [name, mutate] of mutations) test(`RISK-SEC-01 ${scope} rejects ${name}`, () => {
  const value = fixture(scope); mutate(value); assert.throws(() => validateRiskEvidence(value, request(scope)), RiskEvidenceError);
});

for (const [name, mutate] of [
  ['wrong parent CIK', v => { v.company_cik = '0000900002'; }], ['wrong data version', v => { v.data_version = 1; }],
  ['future evidence version', v => { v.evidence_version = 1; }], ['invalid evidence version', v => { v.evidence_version = null; }],
  ['duplicate accessions', v => { v.searched_accessions.push(acc); }], ['missing accession inventory', v => { v.searched_accessions = []; }],
  ['foreign inventory', v => { v.searched_accessions = ['0000900002-25-000001']; }],
  ['wrong scope', v => { v.retrieval_scope = 'filing'; }], ['selected root field', v => { v.accession_number = acc; }],
  ['missing citation CIK', v => { delete v.citations[0].company_cik; }],
  ['forged source metadata', v => { v.context = v.context.replace('"company_cik":"0000900001"', '"company_cik":"0000900002"'); }],
  ['non-JSON metadata', v => { v.context = v.context.replace('metadata: {', 'metadata: !{'); }],
]) test(`RISK-SEC-01 company rejects ${name}`, () => {
  const value = fixture('company'); mutate(value); assert.throws(() => validateRiskEvidence(value, request('company')), RiskEvidenceError);
});

test('RISK-SEC-01 duplicate chunk identity, overflow and unsupported request pins fail closed', () => {
  for (const scope of ['filing', 'company']) {
    const v = fixture(scope, 0, Array(6).fill('Synthetic supply chain.'));
    assert.throws(() => validateRiskEvidence(v, request(scope)), RiskEvidenceError);
    const duplicate = fixture(scope, 0, ['one', 'two']); duplicate.citations[1].chunk_id = duplicate.citations[0].chunk_id;
    assert.throws(() => validateRiskEvidence(duplicate, request(scope)), RiskEvidenceError);
    for (const pin of [null, -0, -1, 0.5, NaN, Infinity, '0', Number.MAX_SAFE_INTEGER + 1]) {
      assert.throws(() => validateRiskEvidence(fixture(scope), { ...request(scope), version: pin }), RiskEvidenceError);
    }
  }
});

for (const scope of ['filing', 'company']) for (const pin of [0, 3]) for (const header of [null, '', '00', '-1', '0, 0', 'NaN', String(pin + 1)]) {
  test(`RISK-SEC-01 strict ${scope} context pin ${pin} rejects missing/invalid/duplicated/mismatched header ${header}`, async ctx => {
    let calls = 0, reconciles = 0;
    ctx.mock.method(globalThis, 'fetch', async (input, init) => {
      calls++; assert.match(input, /^\/api\/finlens\/companies\/AAA\//);
      assert.equal(init.headers['X-FinLens-Data-Version'], String(pin));
      const headers = new Headers(); if (header !== null) headers.set('X-FinLens-Data-Version', header);
      return new Response(JSON.stringify(fixture(scope, pin)), { headers });
    });
    const signal = versionedController(pin, () => reconciles++).signal;
    await assert.rejects(scope === 'filing' ? getFilingContext('AAA', acc, 'supply chain', signal, true)
      : getCompanyContext('AAA', cik, 'supply chain', signal), FinLensApiError);
    assert.equal(calls, 1); assert.equal(reconciles, header === null ? 0 : 1);
  });
}
for (const scope of ['filing', 'company']) for (const pin of [0, 3]) test(`RISK-SEC-01 actual ${scope} client preserves canonical pin ${pin}`, async ctx => {
  ctx.mock.method(globalThis, 'fetch', async (input, init) => {
    assert.equal(init.headers['X-FinLens-Data-Version'], String(pin)); assert.equal(init.cache, 'no-store');
    return new Response(JSON.stringify(fixture(scope, pin)), { headers: { 'X-FinLens-Data-Version': String(pin) } });
  });
  const controller = versionedController(pin, () => assert.fail('Unexpected reconciliation'));
  const value = scope === 'filing' ? await getFilingContext('AAA', acc, 'supply chain', controller.signal, true)
    : await getCompanyContext('AAA', cik, 'supply chain', controller.signal);
  validateRiskEvidence(value, request(scope, pin));
});
// Re-seal SOURCE blocks after adversarial citation edits: agreement with each
// individual block must not hide an impossible span or a filing contradiction.
function p2SourceBlocks(value, texts) {
  const company = value.retrieval_scope === 'company';
  value.context = value.citations.map((c, index) => {
    const headers = company ? `metadata: ${JSON.stringify(Object.fromEntries(['company_cik', 'accession_number', 'filename', 'chunk_id', 'form', 'filed', 'start_char', 'end_char'].map(k => [k, c[k]])))}`
      : `chunk_id: ${c.chunk_id}\naccession_number: ${c.accession_number}\nform: ${c.form}\nsimilarity: ${c.similarity.toFixed(6)}`;
    return `[SOURCE ${c.citation_id}]\n${headers}\ntext: |-\n${texts[index].split('\n').map(line => `  ${line}`).join('\n')}\n[END SOURCE ${c.citation_id}]`;
  }).join('\n\n');
}

for (const scope of ['filing', 'company']) {
  test(`RISK-SEC-01 P2 reproduction: ${scope} multi-character text cannot have source span 0-1`, () => {
    const texts = ['Several characters conceal an impossible source span.'];
    const value = fixture(scope, 0, texts);
    value.citations[0].end_char = 1; p2SourceBlocks(value, texts);
    assert.throws(() => validateRiskEvidence(value, request(scope)), RiskEvidenceError);
  });
  test(`RISK-SEC-01 P2 reproduction: ${scope} same-accession chunks cannot disagree on filing metadata`, () => {
    const texts = ['First synthetic issuer passage.', 'Second synthetic issuer passage.'];
    const value = fixture(scope, 0, texts);
    Object.assign(value.citations[1], { form: '10-K', filed: '2025-06-01', filename: 'other.htm' });
    p2SourceBlocks(value, texts);
    assert.throws(() => validateRiskEvidence(value, request(scope)), RiskEvidenceError);
  });
  for (const field of ['form', 'filed', 'filename']) test(`RISK-SEC-01 P2 ${scope} rejects individually valid contradictory ${field}`, () => {
    const texts = ['First synthetic passage.', 'Second synthetic passage.'];
    const value = fixture(scope, 0, texts);
    value.citations[1][field] = { form: '10-Q/A', filed: '2025-06-01', filename: 'amended.htm' }[field];
    p2SourceBlocks(value, texts);
    assert.throws(() => validateRiskEvidence(value, request(scope)), RiskEvidenceError);
  });
  for (const [name, text] of [['plain', 'abc'], ['CRLF', 'a\r\nb'], ['combining marks', 'e\u0301x'], ['supplementary', 'A😀B']]) {
    for (const padding of [0, 7]) test(`RISK-SEC-01 P2 ${scope} accepts ${name} with ${padding ? 'shorter returned text' : 'exact code-point span'}`, () => {
      const value = fixture(scope, 0, [text]);
      value.citations[0].start_char = 17;
      value.citations[0].end_char = 17 + Array.from(text).length + padding;
      p2SourceBlocks(value, [text]);
      const before = structuredClone(value);
      validateRiskEvidence(value, request(scope));
      assert.deepEqual(value, before, 'Checking span length must not alter decoded text or metadata');
      if (name === 'supplementary' && padding === 0) assert.equal(value.citations[0].end_char - value.citations[0].start_char, 3);
    });
  }
  for (const [name, start, end] of [['negative start', -1, 3], ['unsafe start', Number.MAX_SAFE_INTEGER + 1, Number.MAX_SAFE_INTEGER + 2],
    ['unsafe end', 0, Number.MAX_SAFE_INTEGER + 1], ['fractional offset', 0.5, 3], ['reversed span', 4, 3],
    ['empty span', 0, 0], ['nonfinite end', 0, Infinity], ['negative zero', -0, 3]]) {
    test(`RISK-SEC-01 P2 ${scope} rejects consistent SOURCE metadata with ${name}`, () => {
      const value = fixture(scope, 0, ['abc']);
      Object.assign(value.citations[0], { start_char: start, end_char: end }); p2SourceBlocks(value, ['abc']);
      assert.throws(() => validateRiskEvidence(value, request(scope)), RiskEvidenceError);
    });
  }
  for (const text of ['e\u0301', 'a\r\nb', 'A😀B']) test(`RISK-SEC-01 P2 ${scope} rejects under-declared Unicode span ${JSON.stringify(text)}`, () => {
    const value = fixture(scope, 0, [text]);
    value.citations[0].end_char = Array.from(text).length - 1; p2SourceBlocks(value, [text]);
    assert.throws(() => validateRiskEvidence(value, request(scope)), RiskEvidenceError);
  });
  test(`RISK-SEC-01 P2 ${scope} accepts several consistent chunks under one accession`, () => {
    const texts = ['One issuer statement.', 'Another issuer statement.', 'Third issuer statement.'];
    const value = fixture(scope, 0, texts); const before = structuredClone(value);
    validateRiskEvidence(value, request(scope)); assert.deepEqual(value, before);
  });
}
test('RISK-SEC-01 P2 company accepts distinct filing metadata across distinct accessions', () => {
  const texts = ['First filing statement.', 'Separate filing statement.'];
  const value = fixture('company', 0, texts), other = '0000900001-25-000002';
  Object.assign(value.citations[1], { accession_number: other, form: '10-K', filed: '2025-06-01', filename: 'annual.htm',
    sec_url: `https://www.sec.gov/Archives/edgar/data/900001/${other.replaceAll('-', '')}/${other}-index.html` });
  value.searched_accessions.push(other); p2SourceBlocks(value, texts);
  const before = structuredClone(value); validateRiskEvidence(value, request('company')); assert.deepEqual(value, before);
});

test('RISK-SEC-01 selected general client retains its existing optional-header behavior', async ctx => {
  ctx.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(fixture())));
  assert.deepEqual(await getFilingContext('AAA', acc, 'supply chain', versionedController(0, () => {}).signal), fixture());
  await assert.rejects(getFilingContext('AAA', acc, 'supply chain', undefined, true), FinLensApiError);
});
