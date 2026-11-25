import { test, expect } from './fixtures/browser';
import * as data from './fixtures/data';

test('diagnostic: versioned filing, prompt deterministic answer, and superseded cold evidence are independent', async ({page, scenario}) => {
  const ticker = 'AAA'; // No real issuer inputs, credentials, SEC, DB, or MiniLM.
  const filing = data.accession(ticker);
  const question = 'What was the latest quarterly revenue?';
  const nextQuestion = 'services net sales';
  const inventoryPath = `/companies/${ticker}/sources`;
  const contextPath = `/companies/${ticker}/filings/${filing}/context`;
  const answerPath = `/companies/${ticker}/research-answer`;
  const stamp = (step: string) => console.log('FINLENS_BROWSER_HOME_REPLAY: ' + step);

  await scenario.ignoreTransportAbort(contextPath);
  const inventory = scenario.hold(r => r.path === inventoryPath);
  const retired = scenario.hold(r => r.path === contextPath && r.query.get('q') === question);
  const editor = page.getByRole('textbox', { name: 'Research question or search', exact: true });
  const submit = page.getByRole('button', { name: 'Research question', exact: true });
  const filingControl = page.getByRole('combobox', { name: /^Indexed SEC filing/ });
  const evidence = page.locator('.evidence-results');
  await scenario.open();
  await expect.poll(() => scenario.count(inventoryPath)).toBe(1);
  await expect(filingControl).toBeDisabled();
  expect(scenario.ledger.find(r => r.path === inventoryPath)?.pin).toBe('0');
  inventory.release();
  await expect(filingControl).toBeEnabled();
  await expect(filingControl).toHaveValue(filing);
  stamp('filing_publication_ready');

  await editor.fill(question);
  await submit.click();
  await expect.poll(() => scenario.count(contextPath)).toBe(1);
  await expect(page.getByRole('region', { name: 'Research Answer', exact: true }).locator('.metric-value')).toHaveText('$1B');
  expect(scenario.ledger.find(r => r.path === answerPath)?.pin).toBe('0');
  await expect(evidence).toHaveCount(0);
  stamp('deterministic_answer_before_context');

  await editor.fill(nextQuestion);
  await submit.click();
  await expect(evidence).toContainText('Search: “services net sales”');
  retired.release();
  const oldSearch = '?' + new URLSearchParams({ q: question, limit: '5' }).toString();
  await expect.poll(() => scenario.abortedDeliveries(contextPath, '0', 200, oldSearch)).toBe(1);
  await expect(evidence).toContainText('Search: “services net sales”');
  await expect(evidence).not.toContainText(question);
  await expect(page.locator('.evidence-results .evidence-card')).toHaveCount(1);
  expect(scenario.ledger.filter(r => r.path === contextPath).map(r => [r.pin, r.query.get('q')]))
    .toEqual([['0', question], ['0', nextQuestion]]);
  expect(scenario.ledger.some(r => r.path.endsWith('/answer'))).toBe(false);
  expect(scenario.violations).toEqual([]);
  stamp('superseded_context_ignored');
});
