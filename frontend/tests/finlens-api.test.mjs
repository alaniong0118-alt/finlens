import test from "node:test";
import assert from "node:assert/strict";
import {
  FinLensApiError,
  citationForClaim,
  describeApiError,
  firstReadyCompany,
  getAnswer,
  getCompanies,
  getFilingSources,
  getResearchAnswer,
  readyCompanyCount,
  searchableFilings,
} from "../lib/finlens-api.ts";

test("requests one company-scoped deterministic answer with cancellation and no filing or provider input", async context => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options }); return jsonResponse({ ticker: "AAPL", matched: true });
  });
  const controller = new AbortController();
  const question = "latest quarterly revenue";
  await getResearchAnswer("AAPL", question, controller.signal);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/finlens/companies/AAPL/research-answer");
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].options.body), { question });
  assert.equal(calls[0].options.signal, controller.signal);
});

function jsonResponse(body, status = 200, code = null) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...(code ? { "X-FinLens-Error-Code": code } : {}),
    },
  });
}

test("loads companies from the live API path", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return jsonResponse([{ id: 1, ticker: "AAPL", name: "Apple Inc.", cik: "0000320193", exchange: "NASDAQ", has_indexed_filing: true, indexed_filing_count: 1 }]);
  });
  const companies = await getCompanies();
  assert.equal(companies[0].ticker, "AAPL");
  assert.equal(companies[0].has_indexed_filing, true);
  assert.equal(companies[0].indexed_filing_count, 1);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/finlens/companies");
  assert.equal(calls[0].options.cache, "no-store");
});

test("selects the first Ready company in stable order and counts readiness", () => {
  const companies = [
    { ticker: "MSFT", has_indexed_filing: false, indexed_filing_count: 0 },
    { ticker: "AAPL", has_indexed_filing: true, indexed_filing_count: 1 },
    { ticker: "NVDA", has_indexed_filing: true, indexed_filing_count: 2 },
  ];
  assert.equal(firstReadyCompany(companies).ticker, "AAPL");
  assert.equal(readyCompanyCount(companies), 2);
  assert.equal(firstReadyCompany([companies[0]]).ticker, "MSFT");
  assert.equal(readyCompanyCount([companies[0]]), 0);
  assert.equal(firstReadyCompany([]), undefined);
});

test("uses the existing source API and keeps only searchable filings", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    calls.push(url);
    return jsonResponse([
      { accession_number: "indexed", has_filing_chunks: true },
      { accession_number: "facts-only", has_filing_chunks: false },
    ]);
  });
  const filings = await getFilingSources("AAPL & Co");
  assert.equal(calls[0], "/api/finlens/companies/AAPL%20%26%20Co/sources");
  assert.deepEqual(searchableFilings(filings).map((filing) => filing.accession_number), ["indexed"]);
  assert.deepEqual(searchableFilings([]), []);
});

test("submits the selected company, filing, and question to answer API", async (context) => {
  let call;
  const citation = {
    citation_id: "source_1",
    sec_url: "https://www.sec.gov/Archives/official-index.html",
    accession_number: "filing-1",
    chunk_id: "chunk_0018",
  };
  context.mock.method(globalThis, "fetch", async (url, options) => {
    call = { url, options };
    return jsonResponse({
      evidence_status: "sufficient",
      answer: "Margin rose. [source_1]",
      claims: [{ text: "Margin rose.", citation_ids: ["source_1"] }],
      citations: [citation],
    });
  });
  const result = await getAnswer("AAPL", "filing-1", "gross margin", 3);
  assert.equal(call.url, "/api/finlens/companies/AAPL/filings/filing-1/answer");
  assert.equal(call.options.method, "POST");
  assert.deepEqual(JSON.parse(call.options.body), { question: "gross margin", limit: 3 });
  assert.equal(result.evidence_status, "sufficient");
  assert.equal(citationForClaim("source_1", result.citations).sec_url, citation.sec_url);
  assert.equal(citationForClaim("source_99", result.citations), undefined);
});

test("maps missing AI capability into neutral Research Mode fallback", async (context) => {
  context.mock.method(globalThis, "fetch", async () => jsonResponse(
    { detail: "OPENAI_API_KEY is required to generate an answer." },
    503,
    "LLM_UNAVAILABLE",
  ));
  await assert.rejects(
    () => getAnswer("AAPL", "filing-1", "gross margin"),
    (error) => {
      assert.ok(error instanceof FinLensApiError);
      assert.equal(error.status, 503);
      assert.equal(error.code, "LLM_UNAVAILABLE");
      assert.match(describeApiError(error), /SEC evidence remains available/);
      assert.doesNotMatch(describeApiError(error), /OPENAI_API_KEY/);
      return true;
    },
  );
});

test("distinguishes citation validation and network errors", async (context) => {
  context.mock.method(globalThis, "fetch", async () => jsonResponse(
    { detail: "Invalid citation" }, 502, "MALFORMED_MODEL_OUTPUT",
  ));
  await assert.rejects(
    () => getAnswer("AAPL", "filing-1", "question"),
    (error) => {
      assert.match(describeApiError(error), /citation checks/);
      return true;
    },
  );
  context.mock.restoreAll();
  context.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("network down");
  });
  await assert.rejects(
    () => getCompanies(),
    (error) => {
      assert.ok(error instanceof FinLensApiError);
      assert.equal(error.code, "NETWORK_ERROR");
      assert.match(describeApiError(error), /Cannot reach/);
      return true;
    },
  );
});

test("insufficient evidence response has no invented answer or sources", async (context) => {
  context.mock.method(globalThis, "fetch", async () => jsonResponse({
    evidence_status: "insufficient",
    answer: "The filing evidence retrieved does not provide enough support.",
    claims: [],
    citations: [],
  }));
  const answer = await getAnswer("AAPL", "filing-1", "unsupported topic");
  assert.equal(answer.evidence_status, "insufficient");
  assert.deepEqual(answer.claims, []);
  assert.deepEqual(answer.citations, []);
});
