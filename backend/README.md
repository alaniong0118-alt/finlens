# FinLens RAG backend

This milestone retrieves existing PostgreSQL filing chunks and generates answers
with server-validated, claim-level citations. Existing keyword and semantic search
endpoints remain available. No ingestion, schema migration, or vector regeneration
is required.

## Request flow

Question -> filing-scoped pgvector distances + lexical matching -> hybrid ranking
-> deduplication -> evidence policy -> context blocks -> OpenAI Responses API
-> structured claims -> citation validation -> API response.

The context builder considers up to 50 ranked candidates, filters evidence, then
returns up to the requested limit. The answer service additionally caps model input
at 8 complete source blocks and 24,000 context characters. It never fetches a
filing or sends the full filing. Dates, offsets, forms, accession numbers, filenames
and SEC URLs come from the stored citation metadata.

## Scoring

Scores are ranking signals, not probabilities or calibrated confidence.

- Semantic similarity S = clamp(1 - pgvector cosine distance, 0, 1).
  A chunk without an embedding has S = 0 and can still qualify lexically.
- Exact phrase P is 1 when the tokenized lexical query occurs as a consecutive sequence,
  otherwise 0. Matching ignores case, punctuation and repeated whitespace.
- Term coverage C is the fraction of distinct meaningful query tokens present in
  the chunk. Query stop words are removed from coverage. Term repetition gives
  no extra boost; matches require complete tokens.
- Lexical score L = 0.8 P + 0.2 C, in [0, 1].
- Hybrid score H = L + 0.6 S, in [0, 1.6].

Lexical matching removes bounded question frames (for example, "What was the")
and recognizes revenue/net-sales and revenue-growth/net-sales-increased wording.
It preserves numeric, period, and negative qualifiers. The original question is
still sent to the embedding model and answer model; aliases do not authorize a
causal claim without supporting text. The highest lexical variant score is used.

An exact phrase outranks a purely semantic hit. Ordinary term coverage receives a
smaller weight so scattered terms do not dominate a relevant financial passage.
Ties use semantic similarity, then chunk index and database ID. Repeated
accession/chunk IDs and identical whitespace-normalized text are eliminated in
rank order. Partially overlapping chunks remain intact to preserve source offsets.

The current implementation reads/scans one specified filing for lexical ranking.
This is appropriate for the current 37 chunks; larger collections will require
candidate indexing before this is used across many filings.

## Evidence policy

The same function in app/evidence_policy.py governs context and answer generation:

- L >= 0.8: strong lexical match; low embedding similarity is acceptable.
- S >= 0.60: strong semantic match without lexical support.
- S >= 0.40 and L >= 0.10: semantic match with lexical support.
- L >= 0.20 and S >= 0.25: complete meaningful-term coverage plus semantic support.
- Otherwise: insufficient; non-finite and out-of-range scores are also rejected.

These are initial heuristics evaluated on one filing, not general relevance
guarantees. The former FINLENS_MIN_CONTEXT_SIMILARITY single threshold is no longer
used. An evidence_status of sufficient means qualifying retrieval evidence exists;
the model can still abstain if it cannot answer the particular question.

The semantic-only bar was tightened after the actual question "What clinical
trial results did Apple report?" matched unrelated Apple boilerplate at S~0.40.
This is still a retrieval heuristic, not a semantic entailment guarantee.

## API contract

GET /companies/{ticker}/filings/{accession_number}/context?q=gross%20margin&limit=5

The existing query/context/citations fields are preserved. Context citations now
also include semantic_similarity, lexical_score, hybrid_score and evidence_reason.
The existing similarity field remains an alias of semantic_similarity.

POST /companies/{ticker}/filings/{accession_number}/answer

Request:

    {"question": "What was the gross margin?", "limit": 5}

Successful responses contain ticker, company_name, accession_number, question,
answer, claims, citations, evidence_status, model and the legacy
insufficient_evidence boolean. Each claim has text and citation_ids. The server
renders citation markers in answer; only actually used database citations are
returned for supported answers.

Insufficient retrieval returns HTTP 200, evidence_status=insufficient, empty
claims/citations and an explicit insufficient-evidence answer without calling the
LLM. If the model itself abstains, supplied eligible citation metadata is retained.
The model field identifies the configured model even when no model request occurs.

HTTP 422: invalid body/blank question/limit outside 1..50.
HTTP 404: unknown company.
HTTP 503: missing API key or invalid local configuration.
HTTP 502: provider failure, refusal/incomplete response, malformed output or invalid citations.
HTTP 504: provider timeout.

Provider errors include an `X-FinLens-Error-Code` response header:
`LLM_UNAVAILABLE`, `LLM_TIMEOUT`, `MALFORMED_MODEL_OUTPUT`, or
`UPSTREAM_FAILURE`. `GET /companies/{ticker}/sources` includes
`has_filing_chunks` so clients can distinguish indexed filings from metadata-only
filings. The field is additive to the existing source response.

An accession with no stored chunks returns insufficient evidence, consistent with
the existing search endpoints' empty-result behavior.

## Citation and prompt enforcement

The system policy forbids outside knowledge and unsupported inference. Both the
question and indented SOURCE blocks are untrusted user-message data; embedded
commands cannot replace the system policy. No tools are provided to the model.

Only IDs with both eligible retrieval metadata and a complete matching SOURCE
block are allowed. Empty/whitespace claims, empty citations, unknown IDs,
conflicting metadata, inline model citation markers, and model-generated URLs or
links are rejected. Duplicate citation IDs are normalized. URLs in the response
are taken exclusively from server-side citation metadata. SDK errors and model
content are not echoed in error responses.

This validates citation identity and structure, not semantic entailment. A valid
ID alone cannot prove that a claim is supported. The injection tests verify
message separation and server checks; they do not establish immunity to all
model prompt-injection attacks.

## Configuration and running

Copy `.env.example` to `backend/.env` and set these variables privately, or set
them in the backend process environment:

    OPENAI_API_KEY
    FINLENS_LLM_MODEL=
    FINLENS_LLM_REASONING_EFFORT=

The backend loads `backend/.env` automatically without overriding process
environment variables. `OPENAI_MODEL` and `OPENAI_REASONING_EFFORT`, if present, take precedence over the FINLENS aliases. Use a model and effort supported by your API account.
Never place real keys in source, test fixtures, reports, or chat. Restart the
backend after changing its environment.

From the backend directory:

    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

The OpenAI client is initialized only for a qualifying answer request.
Requests use reasoning.effort, store=false, a 60-second HTTP timeout, zero automatic
retries, and an 8,192-token output budget (including reasoning). A model that
does not support the configured reasoning effort will return a provider error.
Live attempts encountered exhausted API credits. Model access and real response quality remain unverified.

Official references:
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/reasoning

## Automated verification

Offline unit tests use mocks including OpenAI SDK + httpx.MockTransport:

    .\.venv\Scripts\python.exe -m pytest tests -q

Read-only integration/regression requires the existing database and cached
MiniLM model. It uses the real retrieval code and FastAPI TestClient, but mocks
the OpenAI provider. The suite checks the 37/37 dataset and compares a fingerprint
of every chunk and embedding before and after.

    $env:HF_HUB_OFFLINE='1'
    $env:TRANSFORMERS_OFFLINE='1'
    $env:FINLENS_RUN_DB_TESTS='1'
    .\.venv\Scripts\python.exe -m pytest tests -q
    .\.venv\Scripts\python.exe -m alembic check

The original root-level test_*.py scripts are not automatically run: some perform
SEC/network work. The regression suite explicitly exercises the existing financial
and search APIs without SEC downloads.

Reproduce five full natural-language questions, a historical keyword baseline,
and the clinical-trial negative control in reports/rag_evaluation.json:

    .\.venv\Scripts\python.exe -m scripts.evaluate_rag

The script discovers the first indexed Apple filing through `/companies/AAPL/sources`.
It exercises the formal context/answer routes using FastAPI TestClient, reads real
database chunks, and records per-question scores, candidate SOURCE blocks,
database lineage, API status, and latency. Candidate context is explicitly
separate from context actually sent to a model. A pass-through observer counts
real SDK attempts without replacing provider responses or recording credentials.
Claims require manual audit after a real run; valid IDs alone never receive a
SUPPORTED verdict. The script does not fetch SEC filings or mutate the database.

The stored filing contains artificial-intelligence disclosures about compute
resources and supply constraints. Therefore this query qualifies through exact
lexical evidence despite weak embedding similarity; it should not be forced to
insufficient. Gross margin now ranks chunk_0018 (the margin table) first rather
than the semantic-only balance-sheet chunk_0003.

The report explicitly marks real answer evaluation as blocked when the key is
missing. With a private key configured, `python -m scripts.evaluate_rag
--real-answers` opts into real, billable answer calls and marks them as real.

The remaining live verification step requires a valid private key and available API credits:
send an answer request, inspect the claim support and returned source links, and
record actual latency/model behavior. Automated provider tests use cost-free mocks.

## Public checkout configuration

Set `DATABASE_URL` privately in `backend/.env`; SQLAlchemy and Alembic use the same URL. Compose reads `POSTGRES_PASSWORD` from ignored root `.env`. Set `SEC_CONTACT_EMAIL` privately before SEC requests. No dump is distributed; see [fresh-checkout data preparation](../docs/architecture.md#data-preparation-on-a-fresh-checkout). Preserve existing private env files.
