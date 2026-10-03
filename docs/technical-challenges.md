# Technical challenges and decisions

These problems occurred in the current implementation. A local fix is distinct from proof across unseen filings.

## Hidden XBRL metadata

Hidden headers polluted narrative retrieval. The parser selects the primary document, removes scripts/styles, `ix:header`, and elements styled with `display:none`, then normalizes whitespace. Filename and cleaned-text offsets survive. Flattening HTML loses table layout; readable text does not guarantee unambiguous numerical columns.

## Multiple revenue concepts

A single SEC concept missed companies using different revenue/net-sales concepts. The importer maps supported concepts to canonical revenue, normalizes units/periods, retains provenance, and deduplicates. A canonical name does not erase industry differences; unfamiliar concepts require review.

## Fiscal-quarter YoY matching

Calendar-month matching can confuse fiscal quarters and year-to-date durations. Analysis distinguishes period types and uses fiscal information plus date/duration constraints for prior-year matching. Growth needs both reporting periods, not just two similarly labeled values.

## pgvector integration

Extension, ORM type, model dimension, and stored vectors must agree. FinLens uses `VECTOR(384)` and `all-MiniLM-L6-v2`. The fixture contains 37 chunks and 37 embeddings; read-only regression compared fingerprints before/after. This shows fixture consistency, not large-scale performance.

## Semantic retrieval weakness and hybrid ranking

Semantic search could rank a balance-sheet passage above the actual gross-margin table. Phrase matching and meaningful-term coverage now complement cosine similarity. The required gross-margin question ranks its table first. Lexical dominance is a tradeoff; ranking is not factual confidence, and current scoring scans one filing.

## Full natural-language lexical scoring bug

Short queries worked while question frames diluted coverage in “What was the gross margin?” Revenue wording also differed from “net sales increased.” Bounded frame removal and aliases improve retrieval while retaining numbers, periods, negation, and the original question. Better normalization does not authorize unsupported causality.

## Evidence-policy false positives

The Apple clinical-trial question matched unrelated boilerplate at roughly 0.40 similarity. Standalone semantic qualification was raised to 0.60; the moderate branch requires lexical support. This negative now returns insufficient evidence, empty claims/citations, and zero provider calls. One measured negative does not establish perfect abstention.

## Citation lineage versus support

A valid ID can accompany an unsupported claim. Complete SOURCE boundaries, eligible IDs, stored metadata, and server-built URLs preserve identity. Recorded checks confirm text, chunk, accession, offsets, and SEC URL. A real audit must still judge figures, percentages, fiscal period, YoY/sequential comparison, company, and causality as SUPPORTED, PARTIALLY_SUPPORTED, or NOT_SUPPORTED. That audit is incomplete.

## Prompt injection and financial safety

Question/source text may contain instructions. Policy separates untrusted inputs, limits answers to supplied evidence, and provides no tools. Structured output, allowed IDs, URL rejection, and advice guards add deterministic controls. Mock tests validate specific checks, not universal injection resistance or real-output safety.

## API-key and quota limitations

Missing configuration prevented calls; a later key received HTTP 401. After replacement, real requests encountered HTTP 429 / `insufficient_quota` / `credit_balance_exhausted`. Presence checks never print values, errors are sanitized, and reports separate SDK attempts from success. One diagnostic retry identifies the blocker without an unlimited loop. Live integration exists; five successful answers and claim audits remain incomplete.

## Build state and publication hygiene

Dev and production build shared `.next`, causing a missing-module failure. Stopping dev before building resolved it. The old Windows guide described an obsolete empty foundation. Hardcoded database credentials were moved to ignored private configuration. Dumps, backups, dependencies, logs, caches, and scratch files are excluded before staging. Local files and database volumes remain intact.
