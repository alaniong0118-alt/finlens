import { readFile } from 'node:fs/promises';
import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';

test('selected-filing research saves complete browser JSON without including the independent answer or a replacement draft', async ({ page, scenario }) => {
  const ticker = 'AAA';
  const issuer = data.company(ticker);
  const filing = data.accession(ticker);
  const query = 'What was the latest quarterly revenue?';
  const draft = 'Different unfinished research question';
  const texts = [
    'The synthetic evidence refers to reported revenue.',
    'Second synthetic filing passage.\nIts second line preserves the returned text.',
    '第三段 📄 Synthetic evidence initially outside the visible cards.',
  ];
  const base = data.evidence(ticker, query, 0, filing);
  const citations = texts.map((text, i) => ({
    ...base.citations[0],
    citation_id: `source_${i + 1}`,
    chunk_id: `synthetic-download-${i + 1}`,
    start_char: i * 100,
    end_char: i * 100 + Array.from(text).length,
  }));
  const context = {
    ...base,
    citations,
    context: texts.map((text, i) => data.evidenceSourceBlock(citations[i], text, false)).join('\n\n'),
  };
  const contextPath = `/companies/${ticker}/filings/${filing}/context`;
  scenario.overrides.push(request => request.path === contextPath
    && request.query.get('q') === query ? { body: context } : undefined);

  await scenario.open();
  await scenario.ready(ticker);
  await page.getByRole('combobox', { name: 'Evidence search scope', exact: true }).selectOption('filing');
  await expect(page.getByRole('combobox', { name: 'Indexed SEC filing', exact: true })).toHaveValue(filing);
  const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
  await editor.fill(query);
  await page.getByRole('button', { name: 'Research question', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Research Answer', exact: true }).locator('.metric-value')).toHaveText('$1B');
  await expect(page.getByRole('heading', { name: '3 SEC evidence passages', exact: true })).toBeVisible();
  const cards = page.locator('.evidence-results .evidence-card');
  await expect(cards).toHaveCount(2);
  await expect(cards.first().getByRole('link', { name: /Open official SEC source/ })).toHaveAttribute('href', citations[0].sec_url);
  await cards.first().getByText('Read full evidence passage', { exact: true }).click();
  await expect(cards.first().locator('details').first().locator('p')).toHaveText(texts[0]);
  expect(scenario.ledger.filter(item => item.path === contextPath).map(item => (
    { method: item.method, pin: item.pin, params: [...item.query] }
  ))).toEqual([{ method: 'GET', pin: '0', params: [['q', query], ['limit', '5']] }]);

  const report = page.getByRole('region', { name: 'Keep an evidence report', exact: true });
  const answers = scenario.ledger.filter(item => item.path === `/companies/${ticker}/research-answer`);
  expect(answers.map(item => ({ method: item.method, pin: item.pin, body: item.body })))
    .toEqual([{ method: 'POST', pin: '0', body: { question: query } }]);
  const transportCount = scenario.ledger.length;
  async function assertDownload(referenceOnly: boolean) {
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      report.getByRole('button', { name: 'Download evidence data (.json)', exact: true }).click(),
    ]);
    expect(await download.failure()).toBeNull();
    expect(download.suggestedFilename()).toBe('finlens-AAA-evidence-v0.json');
    const bytes = await readFile(await download.path());
    const json = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    expect(Object.keys(json).sort()).toEqual(['company', 'format_version', 'limitations', 'passages', 'search']);
    expect(json.format_version).toBe('finlens-public-evidence-report-v1');
    expect(json.company).toEqual({ ticker, cik: issuer.cik, name: issuer.name });
    expect(json.search).toEqual({
      query, purpose: 'general', scope: 'filing', data_version: 0, data_version_basis: 'request_pin_only',
      evidence_version: null, accession_number: filing, searched_accessions: null, excluded_publication_count: null,
      evidence_status: 'sufficient', reference_only: referenceOnly,
    });
    expect(json.passages).toEqual(texts.map((text, index) => ({ rank: index + 1, text, source: citations[index] })));
    if (referenceOnly) expect(json.limitations).toContain(
      'Kept for reference from the original completed search. It does not support a different draft or pending question.'
    );
    expect(json.search.query).not.toBe(draft);
  }
  await assertDownload(false);
  await editor.fill(draft);
  await expect(report.getByText(/Reference only: this report belongs to/)).toContainText(query);
  await assertDownload(true);
  expect(scenario.ledger.slice(transportCount)).toEqual([]);
  expect(scenario.ledger.some(item => item.path.endsWith('/answer'))).toBe(false);
});
