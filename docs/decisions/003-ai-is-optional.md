# ADR 003 — AI is optional

Status: Accepted
Date: 2026-10-04

## Context

FinLens already has financial analysis and filing search/context APIs independent of OpenAI. Its current frontend emphasizes single-filing Q&A, and real claim auditing is incomplete because API credits were exhausted. Making generation the only useful interaction would tie financial research to provider availability and unverifiable output. The [architecture](../architecture.md) already separates retrieval from answering.

## Decision

FinLens must remain useful without an LLM. AI enhances evidence-based financial research rather than being the product's only source of value.

Research Mode will provide source-backed financial metrics, deterministic ratios/trends/charts/comparisons, filing discovery, hybrid search, evidence excerpts, and official SEC links with no OpenAI key. Local semantic embeddings are part of retrieval and are independent of hosted answer generation.

AI Analysis is optional explanation and synthesis over bounded retrieved evidence. It does not perform deterministic arithmetic, fill missing facts, or replace evidence inspection. Preserve abstention, citation validation, financial safety, and prompt-injection controls. Missing configuration, quota, or provider failure must not disable Research Mode.

Multi-filing and cross-company AI require mature data/metric/retrieval layers and formal evaluation. Real factual claim audits are a separate acceptance gate when credits are intentionally available.

## Consequences

- Prioritize the Metrics Layer and complete Research Mode UI in the [roadmap](../../ROADMAP.md). Existing no-key APIs are a foundation, not evidence that the full target UI is already implemented.
- Keep calculations reproducible and important values/source excerpts traceable without generated prose.
- Expose optional AI availability in user terms; preserve existing API compatibility while evolving the UI.
- Evaluate deterministic data, retrieval, and generated claims separately. Mock validation and citation identity do not prove real claim support.
- Accept the added work of a useful research interface rather than making provider integration a release prerequisite for all product value.

## Alternatives considered

Generation as the primary research interface was rejected because costs, outages, and unsupported claims would gate core value. Removing AI entirely was rejected because bounded, audited synthesis can improve research after the underlying evidence is reliable.

The [product specification](../product-spec.md) is the acceptance contract for this decision. No application behavior changes as part of recording it.
