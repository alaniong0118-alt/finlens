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

test('completed selected-filing passage joins a same-question comparison and survives local reopen', async ({ page, scenario }) => {
  const ticker = 'AAA';
  const filing = data.accession(ticker);
  const query = 'What was the latest quarterly revenue?';
  const prefix = 'The synthetic filing describes the sequence of deliveries and customer orders. '.repeat(5);
  const other = prefix + 'FIRST1 DOCUMENT ONLY';
  const passage = prefix + 'SECOND DOCUMENT ONLY';
  const base = data.evidence(ticker, query, 0, filing);
  const citations = [other, passage].map((body, i) => ({
    ...base.citations[0], citation_id: `source_${i + 1}`, filename: `report-${i + 1}.htm`,
    chunk_id: `shipment-fixture-${i + 1}`, start_char: 37, end_char: 37 + Array.from(body).length,
  }));
  const citation = citations[1];
  const context = { ...base, citations,
    context: [other, passage].map((body, i) => data.evidenceSourceBlock(citations[i], body, false)).join('\n\n') };
  scenario.overrides.push(request => request.path === `/companies/${ticker}/filings/${filing}/context`
    && request.query.get('q') === query ? { body: context } : undefined);
  await scenario.open();
  await scenario.ready(ticker);
  const draft = page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true });
  await draft.fill(query);
  await page.getByRole('button', { name: 'Keep research draft', exact: true }).press('Enter');
  const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
  const submit = page.getByRole('button', { name: 'Research question', exact: true });
  const actions = page.getByRole('button', { name: 'Add this passage to comparison', exact: true });
  const handoff = page.locator('.evidence-card').nth(1).getByRole('button', { name: 'Add this passage to comparison', exact: true });
  await expect(actions).toHaveCount(0);
  await editor.fill(query);
  await submit.press('Enter');
  await expect(page.getByRole('region', { name: 'Research Answer', exact: true })).toBeVisible();
  await expect(handoff).toBeVisible();
  await expect(page.locator('.evidence-card').nth(1).locator('.evidence-preview')).not.toContainText('SECOND DOCUMENT ONLY');
  await draft.fill('Another Home question');
  await expect(actions).toHaveCount(0);
  await draft.fill(query);
  await page.getByRole('button', { name: 'Keep research draft', exact: true }).press('Enter');
  await expect(actions).toHaveCount(0);
  await submit.press('Enter');
  await expect(handoff).toBeVisible();

  const comparison = page.getByRole('region', { name: 'Manual evidence comparison', exact: true });
  const field = (name: string) => comparison.getByLabel(name, { exact: true });
  const before = scenario.ledger.length;
  const storage = () => page.evaluate(() => [localStorage, sessionStorage].map(store =>
    Object.keys(store).sort().map(key => [key, store.getItem(key)])));
  const savedBefore = await storage();
  await handoff.press('Enter');
  await expect(field('Source reference A')).toHaveValue(citation.sec_url);
  await expect(field('Passage A')).toHaveValue(passage);
  const locator = `Accession ${filing} · File ${citation.filename} · Chunk ${citation.chunk_id} · Cleaned text offsets ${citation.start_char}–${citation.end_char}`;
  await expect(field('Locator A')).toHaveValue(locator);
  for (const blank of ['Publication date A', 'Assessment A', 'Assessment rationale A', 'Provisional judgment']) {
    await expect(field(blank)).toHaveValue('');
  }
  await handoff.press('Enter');
  await expect(field('Source reference B')).toHaveValue('');
  await expect(comparison.getByRole('status')).toContainText('already in your comparison');
  await editor.fill('Different current filing question');
  await expect(actions).toHaveCount(0);
  await editor.fill(query);
  await expect(actions).toHaveCount(0);
  await expect(field('Passage A')).toHaveValue(passage);

  await field('Assessment A').selectOption('supports');
  await field('Assessment rationale A').fill('The filing records a change in delivery timing.');
  await field('Source reference B').fill('Synthetic independent shipment survey');
  await field('Passage B').fill('New order counts declined before shipments moved.');
  await field('Assessment B').selectOption('challenges');
  await field('Assessment rationale B').fill('Demand may have weakened first.');
  const judgment = 'The timing explanation is plausible but not sufficient.';
  await field('Provisional judgment').fill(judgment);
  await field('Evidence that would change the judgment').fill('Compare dated orders and actual shipments.');
  await comparison.getByRole('button', { name: 'Record provisional judgment', exact: true }).press('Enter');
  const [download] = await Promise.all([page.waitForEvent('download'),
    comparison.getByRole('button', { name: 'Download recorded comparison (.json)', exact: true }).press('Enter')]);
  expect(await download.failure()).toBeNull();
  const path = await download.path();
  const result = JSON.parse(await readFile(path, 'utf8'));
  expect(result.question).toBe(query);
  expect(result.sources[0]).toEqual({ kind: 'manual_unverified', reference: citation.sec_url,
    passage, locator, date: null, assessment: 'supports', rationale: 'The filing records a change in delivery timing.' });
  expect(result.sources[1].assessment).toBe('challenges');
  expect(await storage()).toEqual(savedBefore);
  expect(scenario.ledger.slice(before)).toEqual([]);

  await scenario.open();
  await scenario.ready(ticker);
  const reopenedAt = scenario.ledger.length;
  await page.getByLabel('Open a recorded comparison (.json)', { exact: true }).setInputFiles(path);
  const preview = page.getByRole('region', { name: 'Reopened comparison preview', exact: true });
  await expect(preview).toContainText(citation.sec_url);
  await expect(preview.locator('dd').filter({ hasText: 'SECOND DOCUMENT ONLY' })).toHaveText(passage);
  await expect(preview).not.toContainText('FIRST1 DOCUMENT ONLY');
  await expect(preview).toContainText(locator);
  await expect(preview).toContainText('New order counts declined before shipments moved.');
  await expect(preview).toContainText(judgment);
  await expect(preview.locator('a')).toHaveCount(0);
  expect(scenario.ledger.slice(reopenedAt)).toEqual([]);
  expect(scenario.violations).toEqual([]);
});

test('Home can prepare a kept research question with no submission or overwrite', async ({ page, scenario }) => {
  await scenario.open();
  await scenario.ready('AAA');
  const draft = page.getByRole('textbox', { name: 'Event, question or reference URL', exact: true });
  const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
  const keep = page.getByRole('button', { name: 'Keep research draft', exact: true });
  const use = page.getByRole('button', { name: 'Use kept question', exact: true });
  const before = scenario.ledger.length;
  const question = 'What is the evidence for a change in shipment timing?';
  await draft.fill('https://example.org/quarterly-report');
  await keep.press('Enter');
  await expect(use).toHaveCount(0);
  await draft.fill(question);
  await expect(use).toHaveCount(0);
  await keep.press('Enter');
  await expect(editor).toHaveValue('');
  await use.press('Enter');
  await expect(editor).toHaveValue(question);
  await expect(editor).toBeFocused();
  await draft.fill('Different kept question with existing research notes');
  await keep.press('Enter');
  await expect(use).toHaveCount(0);
  await expect(editor).toHaveValue(question);
  expect(scenario.ledger.slice(before)).toEqual([]);
  expect(scenario.violations).toEqual([]);
});
