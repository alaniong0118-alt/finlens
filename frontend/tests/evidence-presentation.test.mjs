import test from 'node:test';
import assert from 'node:assert/strict';
import { evidenceExcerpt } from '../lib/evidence-presentation.ts';

const answer = (value = '109417000000.0000', unit = 'USD', status = 'available') => ({ matched: true, status, metric: 'revenue', observation: { value, unit } });
const values = excerpt => excerpt.parts.filter(part => part.kind === 'value').map(part => part.text);

test('numeric marks preserve currency and sign rather than matching inside a token', () => {
 for (const [value, token, allowed] of [
  ['10000000', '$10 million', true],
  ['10000000', '-$10 million', false],
  ['10000000', '($10 million)', false],
  ['10000000', 'C$10 million', false],
  ['10000000', 'A$10 million', false],
  ['10000000', 'HK$10 million', false],
  ['10000000', 'cad $10 million', false],
  ['10000000', '€$10 million', false],
  ['-10000000', '-$10 million', true],
  ['-10000000', '($10 million)', true],
  ['-10000000', '($10) million', true],
  ['-10000000', '−$10 million', true],
  ['-10000000', '$ -10 million', true],
  ['-10000000', '$10 million', false],
  ['-10000000', 'C$10 million', false],
  ['-10000000', '(A$10 million)', false],
  ['10000000', 'CAD $10 million', false],
  ['10000000', 'C $10 million', false],
  ['10000000', '(-$10 million)', false],
  ['10000000', '($10 million', false],
  ['10000000', '$10 million)', false],
  ['10000000', '--$10 million', false],
 ]) {
  const text = `Net income ${token}.`;
  const result = evidenceExcerpt(text, 'net income', { ...answer(value), metric: 'net_income' });
  assert.deepEqual(values(result), allowed ? [token] : [], `${value}: ${token}`);
  assert.ok(result.parts.some(part => part.kind === 'term' && part.text === 'Net income'));
  assert.equal(result.parts.map(part => part.text).join(''), text);
 }
});

test('signed currency protection also applies to per-share amounts and unavailable answers', () => {
 for (const token of ['-$2.02', '($2.02)', 'C$2.02', 'A$2.02']) {
  assert.deepEqual(values(evidenceExcerpt(`Diluted earnings per share ${token}.`, 'earnings per share', answer('2.02', 'USD/share'))), []);
 }
 assert.deepEqual(values(evidenceExcerpt('Net income -$10 million.', 'net income', answer('-10000000', 'USD', 'unavailable'))), []);
});

test('excerpt selects exact scaled value and preserves original text/ranges', () => {
 const text = 'Unrelated introduction. '.repeat(35) + 'Revenue (in millions): Total net sales $ 109,417 $ 94,036. More details.';
 const result = evidenceExcerpt(text, 'How much revenue did Apple report?', answer());
 assert.match(result.text, /Total net sales \$ 109,417/);
 assert.ok(result.text.length <= 280); assert.ok(result.start > 0);
 assert.deepEqual(values(result), ['$ 109,417']);
 assert.equal(result.parts.map(part => part.text).join(''), text.slice(result.start, result.end));
});

test('unit transfer requires an identical overlapping row with a preceding table declaration', () => {
 const row = 'Services 30,739 27,423 91,728 80,408 Total net sales $ 109,417';
 assert.deepEqual(values(evidenceExcerpt(row, 'revenue', answer(), [`Revenue (in millions): ${row}`])), ['$ 109,417']);
 for (const peer of ['Another table (in millions): Different row $ 109,417', `${row} Later note (in millions)`]) {
  assert.deepEqual(values(evidenceExcerpt(row, 'revenue', answer(), [peer])), []);
 }
});

test('unknown/conflicting units, later notes, per-share boundaries and rounded values never imply exact match', () => {
 for (const text of ['Total net sales $ 109,417', 'Total net sales $109.42 billion', '(in millions) Note 3 Earnings per share $109,417', 'Total net sales $109,417 (in millions)', 'Revenue billions of dollars: $109417000000']) {
  assert.deepEqual(values(evidenceExcerpt(text, 'revenue', answer())), []);
 }
 const row = 'Services 30,739 27,423 91,728 80,408 Total net sales $ 109,417';
 assert.deepEqual(values(evidenceExcerpt(row, 'revenue', answer(), [`(in millions) ${row}`, `(in thousands) ${row}`])), []);
 assert.deepEqual(values(evidenceExcerpt(row, 'revenue', answer(), [`(in millions) ${row} Next table (in thousands) ${row}`])), []);
});

test('decimal normalization handles zero, negative currency, explicit scale, percent and EPS', () => {
 for (const [text, value, unit, expected] of [
  ['Total net sales $109.417 billion', '109417000000', 'USD', '$109.417 billion'],
  ['Revenue in dollars: $109417000000', '109417000000', 'USD', '$109417000000'],
  ['Revenue (in millions): $ -10', '-10000000', 'USD', '$ -10'],
  ['Revenue (in millions): ($10)', '-10000000', 'USD', '($10)'],
  ['Revenue (in millions): $0', '0', 'USD', '$0'],
  ['Gross margin 25 %', '0.25', 'ratio', '25 %'],
  ['Diluted earnings per share $2.02', '2.0200', 'USD/share', '$2.02'],
 ]) assert.deepEqual(values(evidenceExcerpt(text, 'revenue', answer(value, unit))), [expected]);
});

test('method intent selects reporting language instead of an amount; fallback marks meaningful terms only', () => {
 const text = 'Total net sales $109,417 million. '.repeat(12) + 'Revenue is recognized when control transfers to the customer. Accounting policies describe performance obligations.';
 const result = evidenceExcerpt(text, 'How does Apple report revenue?');
 assert.match(result.text, /Revenue is recognized/);
 assert.ok(result.parts.some(part => part.kind === 'term' && /recognized/.test(part.text)));
 assert.deepEqual(values(result), []);
 const fallback = evidenceExcerpt('The Company discussed supply constraints and supply constraints.', 'What are the supply constraints?');
 assert.equal(fallback.parts.filter(part => part.kind).length, 1);
 assert.ok(fallback.parts.every(part => !part.kind || !/the|company/i.test(part.text)));
 const capex = evidenceExcerpt('Payments for property, plant and equipment $10.', 'capex', { ...answer(), metric: 'capital_expenditures' });
 assert.ok(capex.parts.some(part => part.kind === 'term' && part.text === 'property, plant and equipment'));
});

test('unavailable answers never mark unrelated numbers; literal unsafe text stays text', () => {
 const text = 'Revenue (in millions): $109,417 <script>alert(1)</script>.';
 const result = evidenceExcerpt(text, 'revenue', answer(null, 'USD', 'unavailable'));
 assert.deepEqual(values(result), []);
 assert.equal(result.parts.map(part => part.text).join(''), text);
});
