# Shared research contracts (draft)

Status: PROPOSED semantic interfaces for independent documentation/contract review.
Recorded: 2026-10-29 (Asia/Macau).
Task: FL-ALL-1215-W1-C0.
Revision: FL-ALL-1215-W1-C0-FIX1. Local correction and proposed representation lock only; focused independent review pending. The supplied Astra C0 FAIL / C1 NO-GO is not superseded by these edits or static checks.
Source baseline: main at `b8e89ef884b96f8fd8eec1ea4daba37b2f04295a`.

## Purpose, authority and boundaries

One small set of identity, evidence, finance, ownership and job interfaces should serve the [67-record full-feature register](full-feature-requirements.md). These are documentation drafts, not implemented Python/TypeScript types, public wire schemas, migrations, approved production contracts or authority to integrate consumers. Logical names/fields below describe minimum semantics. The proposed C1 representation lock below now supplies explicit preferred field sets, caps and serialization for independent review; other consumers/storage mechanics still need bounded implementation decisions and review.

Keep the current financial engine and publication integrity model. Do not introduce a second calculator, fabricate database company/fact/chunk IDs, reinterpret a session artifact as an admitted database publication, or treat a hash/model assertion as an authority grant. Existing APIs remain unchanged by C0. No contract here activates Reader, acquires data, starts services, loads a model or authorizes cloud/Stripe use.

Reader's strict helper was independently accepted and committed as b8e89ef, per coordinator. [Current source](../backend/app/publication_admission.py) contains `admit_reader_publication`; [Reader](../backend/app/sec_reader.py) still exposes only diagnostics. Do not reopen the helper review. Its success does not establish database snapshot ownership, HTTP cleanup/cancellation, ranking protection, source rights or deployment acceptance.

The [ExecPlan rules](../.agent/PLANS.md), [financial contracts](financial-metrics.md), [source policy](data-sources.md) and existing release guards remain applicable. Later complex implementation needs its own active ExecPlan and separate authorization. This documentation task creates only the register and this draft.

## Existing interfaces: reuse map, not new implementation claims

| Existing interface | Owning source | What is reusable / boundary to preserve |
|---|---|---|
| Company, FinancialFact, FilingChunk, refresh/publication ORM records | [models.py](../backend/app/models.py) | Company has unique ticker and mandatory CIK; FinancialFact uses company_cik and stored numeric precision. These do not yet model arbitrary non-SEC issuers or private objects. |
| FinancialPeriod, FactProvenance, MetricInput, NormalizedMetric, MetricComparison, AnnualFinancialComparison | [financial_metric_schemas.py](../backend/app/financial_metric_schemas.py) | Decimal values serialize as strings; fiscal dates, alternative sources, compatible inputs and unavailable reasons survive. FactProvenance requires integer fact_id and CIK: no invented external values may satisfy those fields. |
| FinancialMetrics and load_financial_metrics | [DB facade](../backend/app/financial_metrics_service.py), [internal engine](../backend/app/financial_metric_engine.py), [registry](../backend/app/financial_metric_registry.py) | DB-only extraction candidate delegates selection/formulas to one engine; independent implementation review pending. Loader still queries stored Company/FinancialFact and obtains reviewed original-evidence authorization. No public generic external-observation adapter is claimed. |
| FinancialReference, DiagnosticReference, EvidenceNode, InsightStatement, InsightsResponse | [financial_insights_schemas.py](../backend/app/financial_insights_schemas.py) | Closed F/D reference separation and scoped financial/diagnostic graph; diagnostic nodes never authorize a financial value. These are insights-specific, not an already generic bundle API. |
| PublicationManifest, PublicationChunk, CompletePublication; two admission entries | [publication_admission.py](../backend/app/publication_admission.py), [reader_resource_policy.py](../backend/app/reader_resource_policy.py) | Tone's existing entry and the fixed strict Reader entry share complete integrity checks. Scalar detachment, pin zero, unselected-body/vector/digest validation and older intact publication semantics remain. Caller owns session/snapshot/cleanup. |
| ArtifactPin, ObservationReview, EvidencePolicy and production-evidence loader | [sec_evidence_adapter.py](../backend/app/sec_evidence_adapter.py), [scope authorization](../backend/app/revenue_scope_authorizations.py) | Narrow reviewed original-byte/locator/policy binding; not a generic license to admit any issuer/table. No new registry approval or broader scope is created here. |
| StreamState, Freshness, RefreshRequest, RefreshResult; refresh coordinator/reconciliation | [refresh_contracts.py](../backend/app/refresh_contracts.py), [refresh_service.py](../backend/app/refresh_service.py) | Independent fact/evidence versions, pending targets, bounded runs, insert-only publication and indeterminate outcomes. Reuse lifecycle concepts without assuming current live scheduling/fencing is accepted. |
| Security, Listing, SymbolMapping, Source, MarketPublication, DatasetPin, LabelWindow | [market_data_contracts.py](../backend/app/market_data_contracts.py), [returns](../backend/app/market_returns.py) | Keep security/listing/calendar/action and exact-return semantics. Current Security requires company_id/issuer_cik: an external-identity adapter is not implemented. Caller declarations/digests do not attest custody or completeness. |
| CitationClaim, AnswerDraft, eligible SOURCE blocks and answer policy | [answer_service.py](../backend/app/answer_service.py), [context](../backend/app/rag_context_service.py) | Bounded supplied IDs, server-attached URLs and optional development-only cloud generation. Identity validation is not semantic support; no accepted local/provider-independent gateway exists. |
| Strict annual comparison client, publication pins and source-backed notes | [comparison client](../frontend/lib/company-comparison.ts), [typed client](../frontend/lib/finlens-api.ts), [note serializer](../frontend/lib/research-note.ts) | Preserve paired eleven-metric client/server delivery, independent pins, stale-owner guards and safe source serialization. Do not append fields to strict schemas without a reviewed compatibility transition. |

No user/tenant/document/chat/portfolio/billing ownership interface is established by the current server-profile guard. New private-object authority cannot be inferred from a successful public financial read.

## Proposed contract set C1-C9

All C1-C9 interfaces below are PROPOSED. Reusing an existing payload inside a future envelope does not change that payload's trust, limits or acceptance scope. Shared `contract_version` identifies the future interface version and is distinct from data/publication/model versions. New records carry source-owned references; clients do not choose authority, owner or verification status.

### C1 - Entity, security and listing identity

Minimum logical records: `EntityRef`, `SecurityRef`, `ListingRef` and `IdentityResolution`.

- EntityRef: opaque namespaced entity key; legal/display names; jurisdiction; zero or more authority identifiers with scheme, identifier, supporting evidence and effective dates. CIK is optional for external/non-SEC identity, mandatory only at existing SEC-bound adapters.
- SecurityRef: distinct security/share-class key and issuer EntityRef. ListingRef: security, exchange/MIC, currency, calendar and effective interval. Symbol aliases bind provider/product, listing and dates; ticker alone never identifies an issuer/security.
- IdentityResolution: resolved, ambiguous or unresolved, with supported candidates/reasons and authoritative references. A display name or search hit cannot set resolved. Renames, ticker reuse, multiple exchanges/classes and predecessor/successor relationships need dated evidence, not company-specific code or automatic history merging.
- An external entity may lack every local DB ID. Preserve existing Company and market types; a reviewed mapping adapter, not placeholder integers/CIKs, is required before calling their existing DB-bound operations.

Producers: future authority resolver and reviewed local-catalog adapter. Consumers: U1, company research, comparisons, market/portfolio identity, news binding. The resolver's network access is C8 work, never part of a pure identity value object. The proposed C1 representation lock below defines its preferred structural scope; no decoded identity is an authority grant.

### C2 - Source authority, evidence reference and trust separation

Minimum logical records: `SourceDescriptor` and a discriminated `EvidenceRef`. Keep origin, source identity verification, content integrity, financial admission, claim support, ownership and usage rights as separate properties; no single “verified=true” flag covers them all.

SourceDescriptor records authority/provider, source/product identity, canonical source reference, original-byte digest, capture/availability metadata (C3), acquisition/parser binding, and operation-specific rights (C9). Origins include SEC, official issuer/regulator/exchange, permitted market/news provider and user upload. “Uploaded,” “official-looking,” “public URL,” and a matching digest do not establish verified authority. Search engines are discovery provenance, not unquestioned financial-fact sources. Memory/generated interpretations never become authoritative finance.

| Proposed EvidenceRef variant | Required resolution boundary | What it cannot imply |
|---|---|---|
| database_publication | Server resolves company/accession/chunk and snapshot/version pins through the existing admitted publication path; bind manifest/digest and source locators. | A caller-provided tag/digest cannot skip complete admission, financial authorization, owner checks or session cleanup. |
| session_artifact | Server-issued owner/session/artifact reference, digest, source/rights/admission decision and exact locators for externally acquired or uploaded evidence. | No fake FilingChunk/fact ID, shared database publication, catalog insertion or public visibility. |
| market_publication | Preserve existing security/listing/DatasetPin/publication-manifest references and separately verified custody/calendar/action/rights decisions. | A sealed offline dataclass/hash alone is not accepted real-data authority or SEC publication. |

The discriminator describes resolution requirements; its JSON spelling or dataclass type is not a capability. Consumers resolve references within an authorized server context. A mixed bundle retains every entry's variant and provenance. Moving a session artifact into shared data requires a separate authorized ingestion/admission/publication operation, never a cast or caller-selected flag.

### C3 - Version, availability, reporting period and vintage

Minimum logical metadata: `SourceVersion` and `TemporalScope`, referencing existing FinancialPeriod/Freshness/market pins where applicable.

Record separately: source revision/original-byte digest; source public availability; retrieval time; system admission/publication time; reporting period/as-of date; filed date/form/accession when applicable; accounting standard/basis; currency/unit/scale; dimensions; original/restated/superseding lineage. Unknown fields stay unknown. Date-only availability retains its precision; do not invent a UTC midnight timestamp or equate retrieval/filed/stored time with public availability.

Existing normalized fiscal labels and source FY/FP remain distinct. Never infer a direct quarter from YTD, a calendar quarter from filing-context labels, full issuer revenue from a component, or verified EPS split comparability from as-filed values.

Database data/facts/evidence versions and market versions are independent namespaces. Preserve pin zero and `publication.data_version <= evidence_version <= current data_version`; do not require facts/evidence equality or reject an older intact filing because facts advanced. New request/context generation checks must preserve current stale-response semantics.

Existing market DatasetPin defaults to a present-day curated universe. Version pins and cutoff checks do not establish a survivorship-free historical universe; experiments must disclose that basis separately from look-ahead checks.

As-of selection checks both public-availability and declared system-knowledge policy. Today's revised Company Facts cannot reconstruct unretained originals. Existing naive stored timestamps need an explicit adapter interpretation/review; this draft does not silently rewrite their timezone or migration history.

### C4 - Evidence bundle, artifact locators and reproducible receipt

Minimum logical records: `EvidenceBundle`, `ArtifactLocator` and `ResearchReceipt`.

EvidenceBundle is an immutable research-scope snapshot: version, authorized owner/session context, entity/security scope, explicit reporting/vintage request, entries with C2 references, admitted C5 observation/calculation references, diagnostic conflicts/coverage gaps, source/version pins, and the applicable finite C9 budget. Locators bind exact source version and text offsets/page/table/cell/row/column/footnote positions with their coordinate convention and extraction version. Cleaned-text, PDF page and OCR coordinates are not interchangeable.

Only complete, authorized entries are supplied. Valid missing coverage/insufficient evidence is distinct from invalid, unavailable, expired, blocked or resource-exceeded work. No truncated prefix of a publication, graph, table or lifecycle object can become a success. A valid independent deterministic answer may survive failure of a separately owned evidence/generation operation; do not turn all application panels into one failure domain.

ResearchReceipt records bundle/pin identity, selection/formula/parser versions, exact deterministic inputs/outputs, parameters, model/provider identity and original accepted user-facing generated output/validation status where applicable. Rejected provider assertions are excluded from the accepted-output receipt/export and cannot appear as labelled research conclusions; any separately authorized restricted diagnostic retention is outside ValidatedAnswer. Record stochastic seed/method and numerical policy for analytics; do not promise byte-identical model regeneration. Rights and deletion can prevent retention/replay; disclose that limit and do not silently substitute a newly fetched version.

Session-owned evidence may live outside Company/FinancialFact tables and support a successful no-insertion U4 request. Persisting an owned investigation does not promote its evidence to the public catalog.

### C5 - Deterministic observations, calculations and diagnostic references

Minimum logical bridge: `ObservationRef` and `CalculationRef`, preserving the existing NormalizedMetric, MetricInput, MetricComparison and financial/diagnostic distinction.

- Database observations refer to real FactProvenance IDs, entity, exact decimal value, unit/currency, scale, FinancialPeriod, basis and source/authorization lineage. External observations refer to session artifact/locator identities and an independently reviewed admission result; they do not mint fact IDs.
- Calculations reference admitted operands, reviewed metric/formula/selection versions, period/basis checks, precision/rounding policy and exact result or explained unavailable/not-applicable reason. Alternatives/rejections remain diagnostics. A D/candidate reference cannot become an F/value reference merely because the model or UI cites it.
- Reuse FinancialMetrics/registry semantics and existing market return/alignment functions. Monetary/financial values retain Decimal or existing exact rational behavior; do not round into binary floats before admission. Statistical simulation/ML may use an explicitly reviewed finite numerical method, with pins/seed/precision, without treating its estimates as reported facts.
- The current public schemas require DB IDs/CIKs and the loader performs DB reads. The bounded DB-only engine extraction below is an implementation candidate, pending independent review. An admitted-input bridge for external/non-SEC observations is **not implemented**: no duck-typed fake ORM rows, parallel financial engine or widened authorization registry.
- New currencies, accounting standards, dimensions, ratio definitions, FX policies or economic-scope mappings require reviewed semantics/fixtures; a generic schema does not make all concepts calculable.

Consumers include comparisons, portfolios (including the explicit 10a historical VaR/CVaR specification), optimization, simulations/stress, risk indicators and forecasts. These consume pinned inputs and distinguish reported, derived and estimated outputs. They do not use an LLM as a calculator or issue personalized allocation/trading instructions.

#### C5 DB-only engine extraction candidate — 2026-10-30

[FinancialMetricEngine](../backend/app/financial_metric_engine.py) holds the existing
selection, fiscal-period reasoning, precision-28 Decimal formulas and comparison
rules. Its frozen observations, periods, operand references and result records
are immediately consumed by the existing FinancialMetrics facade; they are internal
DB-adapter records, not approved external C5 ObservationRef/CalculationRef schemas.
References retain real fact IDs and no source/session admission is issued by
constructing an engine record. The engine imports only standard-library code and
the existing metric registry, with no I/O or operational dependencies.

The facade preserves original company-scoped rows, public response models,
projected `.base` (including selected negative CapEx diagnostics), `.source()` and
helper exports. Eligibility is checked against the original DB source fields
before conversion. Original-row mappings and narrow DB permission operations
retain complete same-end/kind authorization inventories, including differing
starts; the existing evaluator/registries, pinned gross-margin guard and distinct
alternative ordering remain unchanged. Missing DB fields do not establish verified
dimensions or consolidated scope. Refresh conflict admission, ordinary ID-ending
selection ranking, stricter authorization conflict rules and Insights support
rejection retain their separate owners.

The focused P2 correction captures every source-projection scalar alongside each
eligible observation, deriving its value/period from that same capture. Selected
and alternative financial provenance projects from this immutable snapshot even
if original rows later change. Original rows remain separate for the historical
authorization and raw-diagnostic operations, whose current inventories are still
projected when those operations reject evidence. `calculate()` preserves submitted
source metadata through its source-pair/coverage checks instead of replacing it
through a matching fact ID. Previous input ancestry is not a new local-row lookup
requirement. These helper conversions grant no source admission or new permission.
Baseline-sensitive post-construction and same-ID metadata mutation regressions
cover both corrections; focused independent re-review remains pending.

Conversion, delegated work and public projection participate in the existing
budget and FinancialMetrics lifecycle entry/exit checks. This adds no session
caps to DB datasets. Public DB serialization, source metadata/URLs and Decimal
behavior are checked against immutable baseline `6838af1d9164979daebb179144d67cd154da020e`;
the nine fixed fixture fingerprints were frozen before extraction. Synthetic
mutation controls check that incorrect tie-breaking, total preference, formulas,
authorization inventories and gross-margin guards are detected.

See the [bounded implementation record](exec-plans/active/2026-10-30-c5-financial-input-reuse.md)
for exact offline commands/results and unexecuted gates. This candidate introduces
no session module/API, new formulas, source policies, acquisition or activation.
Ownership, rights, real-source/native custody, extraction verification, financial
admission and session/runtime delivery remain separate prerequisites; C1
offline-injected/unverified references cannot enter financial output. U3/U4 remain
incomplete end to end. Independent implementation review and manual Git gates
remain pending.

#### Existing observation, conflict and comparability identities

Three identities have different purposes and must remain distinct. This is source inspection, not a change to ingestion/selection or a new calculation engine.

Owning source: [sec_importer.py](../backend/app/sec_importer.py) defines the exact tuple and conversions; [refresh_service.py](../backend/app/refresh_service.py) defines both conflict buckets. Economic compatibility stays with the existing metric registry/selector referenced above.

| Identity | Exact existing semantics | Purpose and non-substitutability |
|---|---|---|
| Exact source observation | `sec_importer.IDENTITY_FIELDS` / `fact_identity`: (company_cik, source, unit, period_start, period_end, value, accession_number, filed, form, frame, fiscal_year, fiscal_period). ISO date strings become dates; value becomes Decimal(str(value)). Decimal numeric equality, not original numeric-byte spelling, determines equality. DB id, created_at, stored metric and derived period_type are not members. | Insert-only deduplication retains distinct source contexts/vintages. Different raw lexemes may have different artifact hashes but equal numeric identities. Removing value would lose competing observations; using this key alone would not detect conflicts. |
| Same-vintage conflict | `refresh_service.reject_conflicts` checks BOTH `identity[:5] + identity[6:]` (everything above except value) AND broader `identity[:5] + identity[6:9]` = (company_cik, source, unit, period_start, period_end, accession_number, filed, form). The broader key also excludes frame, fiscal_year and fiscal_period. More than one Decimal value under either candidate-related key raises ambiguous_source_revision. | Catch competing same-vintage amounts even when frame/fiscal annotations differ; do not let insertion order choose. These are conflict buckets, not exact dedup IDs, financial equivalence keys or authority to discard metadata. A different accession/filed/form changes the vintage key; coexistence does not itself establish comparability. |
| Economic comparability | Reviewed metric/selection rules establish entity and metric meaning, accounting/economic scope, compatible units/currency/scale, instant/duration and fiscal windows, dimensions/consolidation, restatement/share basis and applicable source authorizations. Current FinancialMetrics/registry/period checks own the supported subset; no universal economic identity tuple is implemented. | Decide whether meaningful calculation/comparison is permitted. Neither equal values nor a shared exact/conflict key proves compatible economic scope; different legitimate vintages may be comparable only after independent review. |

Examples: exact duplicate rows deduplicate; same value with different frame/FY/FP has a distinct exact identity but need not conflict; changing the value as well triggers the broader same-vintage check. A later filing/amendment may legitimately retain a different value as a separate vintage, still subject to selection/comparability policy. Dimensions are not fields of the current DB fact identity: frame is not a replacement for explicit XBRL dimensions. Do not flatten dimensional differences into the existing key or silently widen current support.

For a future external/UCR bridge, PROPOSED exact identity includes evidence-origin namespace and owner/session where private, canonical issuer, authoritative source revision binding, artifact/context/locator, concept namespace URI plus local name, declared/canonical unit and scale, reporting dates/kind, canonical sorted explicit/typed dimensions, accounting/consolidation context, exact value and retained source frame/fiscal annotations. A proposed same-vintage conflict bucket excludes value and non-economic annotation/locator labels only after equivalent context is established; it retains source revision, origin, entity, concept namespace, unit, period, dimensions and accounting context. Distinct dimensions remain distinct observations, not silent totals or false conflicts. Changed bytes for one claimed authoritative revision require source-integrity adjudication, not inventing a new vintage merely by changing a digest.

Economic comparability remains a separate reviewed rule/result referencing these identities and evidence. No forged fact IDs, fake ORM inputs, registry relaxation or financial-definition rewrite is allowed. An external representation that current schemas cannot express stays session-owned/unavailable to that adapter until a separately reviewed bridge exists.

### C6 - Generation request, claims and citations

Minimum logical records: `GenerationRequest` and `ValidatedAnswer`, wrapping rather than weakening existing SOURCE/claim policy.

GenerationRequest specifies authorized bundle/claim scope, question/allowed follow-up context, explicit local or cloud model/provider, operation identity, cancellation/deadline/output budget and permitted privacy/spend grant. Free local generation works with cloud disabled. No automatic cloud fallback, replay on freshness changes or dispatch after budget/consent failure. Model choice cannot expand evidence or ownership.

ValidatedAnswer contains **only independently supported factual assertions** with resolved references. Unsupported factual assertions MUST NOT survive as research conclusions, even with an unverified/insufficient warning label. Server-attached source identity is necessary but not proof of semantic support; a model's self-asserted support is never sufficient. Financial numeric assertions require verified observations and deterministic formula/operand references as applicable; a plausible passage or coincident number alone is insufficient.

PROPOSED typed output semantics (not current API fields or implemented types):

| Logical type | Required semantics |
|---|---|
| SupportedAssertion | One independently supportable assertion text; nonempty resolved citation references to supplied evidence; applicable admitted financial observation/calculation references; server-owned support decision and bundle scope. No fabricated IDs, model URLs or raw candidate text disguised as supported output. |
| AbstentionDiagnostic | Server-controlled reason code and requested scope/subquestion, optionally rejected input positions for traceability. May explain missing/conflicting/insufficient evidence; must not repeat a rejected assertion/value as a factual conclusion. It confers no citation or financial authority. |
| ValidatedAnswer | Status supported / partially_supported / insufficient_evidence; immutable supported_assertions, resolved citations used by those assertions, and safe diagnostics. supported requires at least one assertion and no rejected candidate assertion/requested part; partially_supported retains at least one independent supported assertion and records at least one rejected candidate/requested part while omitting every unsupported assertion; insufficient_evidence has zero assertions and only safe abstention/diagnostic content. |

Split compound candidate assertions before admission. If supported and unsupported parts cannot be reliably separated, exclude the whole compound assertion. Partially supported does not mean displaying a partially verified assertion. Rejected provider text is absent from user-facing conclusions, accepted-output receipts/exports and the ValidatedAnswer object; do not retain it as a labelled claim in that object.

Existing production AnswerDraft has claims plus insufficient_evidence; insufficient=true requires an empty claim list, and malformed/unknown citation IDs or source framing cause CitationValidationError. Keep that current behavior unchanged. The future partially_supported semantic result needs an explicitly reviewed adapter/versioned transition; semantic filtering does not excuse forged/mismatched references or convert malformed source identity into a partial success. Independently valid deterministic results in a separately owned research operation may still remain visible.

Future negative/mutation tests: (1) two structurally valid candidates, one supported and one unsupported, yield only the supported assertion and a safe diagnostic; (2) unsupported numeric value/formula cannot enter output even with a valid citation ID or warning; (3) unknown IDs, wrong entity/period/locator, mutated digest or supplied-source mismatch reject the affected malformed generation attempt; (4) malicious document role/tool/calculation instructions cannot change policy, references or operands; (5) zero supported assertions yields abstention with no rejected claim text; (6) changing a rejection into a labelled user-facing claim must fail; (7) compound mixed support is either safely split with proof or fully excluded. Mocks verify structure; actual claim-support audits remain a separate acceptance gate.

Bounded multi-document plans preserve company/period/dimension scope per subquestion. Source text, uploaded documents, search results, user questions and remembered context are untrusted instructions. No generated code/chart specification executes; charts select/reproduce admitted series through existing presentation components. Actual generated-answer/support acceptance is distinct from mocks.

Provider/model switching preserves thread and evidence identity but requires explicit consent before transferring private content to cloud. Existing `answer_filing_question` is development-only and SEC-scoped; this draft does not activate it remotely or claim its current schema already accepts external evidence.

### C7 - User ownership, visibility and isolation

Minimum logical records: `PrincipalContext` and `OwnedObjectRef`.

PrincipalContext derives stable identity from a verified session/token boundary, never an unverified email header or caller-supplied owner ID. OwnedObjectRef identifies kind (document, investigation, portfolio, thread/turn, note, watchlist, receipt or memory), owner/realm, revision, permitted visibility and retention state. The server resolves the opaque ID under that context before reads, ranking, jobs, caches, download/export or generation.

Public admitted SEC evidence and private/session evidence can be used together only with explicit authorized scope; cross-owner dedup/cache/index reuse cannot leak existence/content. Memory is off by default and stored separately from financial facts. Review/edit/delete/export includes derived indexes/caches/artifacts, with documented backup retention/tombstone handling to avoid restore resurrection.

Long-running jobs recheck revoked/expired access before final delivery/publication. Error/status/log paths must not leak secrets, private bodies or another owner's identifiers. Native ACL/process/DB-role separation supplements application checks; Python audit hooks or a typed record are not an OS sandbox.

#### Dormant account ownership candidate — 2026-10-30

[Verifier](../backend/app/account_auth.py) and
[ownership service](../backend/app/research_ownership.py) implement a bounded,
unwired backend prerequisite. No provider, production issuer/client/public-key
snapshot, account seed, route, UI or global service instance is configured. The
default verifier returns AUTH_UNAVAILABLE before a database factory is reached.
This candidate does not complete C7, 15a/15b, a signed-in workspace or UCR.

The single configured profile is RFC 9068 RS256 with known kid, at+jwt or
application/at+jwt header, exact issuer, dedicated API audience and one interactive
client_id. Required claims are iss/aud/sub/client_id/jti/iat/exp; optional nbf is
checked. ID-token type/audience, other algorithms, delegated/agent subjects,
unknown keys and token-selected key sources are rejected. Only later provider
commissioning can establish that this client issues end-user Authorization Code
with PKCE tokens rather than machine/delegated grants; the claims alone do not
prove that configuration. No email-based account merging or entitlement grant.

Trusted server composition supplies an immutable IssuerPolicy/KeySnapshot and a
dedicated PostgreSQL Session factory, never request arguments or an authority
callback. Installation validates a bounded public RSA JWKS from the policy's
exact HTTPS source reference. This module never fetches it. Server-controlled
rotation atomically replaces the snapshot with a higher revision and invalidates
in-flight identities under the old revision. Unknown/stale keys fail without
refresh/fallback. Commissioning must establish protected configuration delivery,
TLS capture of the real issuer's JWKS, renewal at least before the one-hour expiry,
planned current/next-key overlap for 900 seconds plus 30 seconds, and emergency
key removal. Python object structure is not privileged-process isolation.

Limits: token 16384 bytes; JWKS 65536 bytes/16 keys; RSA 2048-4096 bits; JSON depth
8/1024 value nodes; at most four audiences; token lifetime 900 seconds; UTC claim
skew 30 seconds. Both verifier wall time and a fresh database clock_timestamp()
sample validate token times and must agree within 30 seconds. Verifier wall versus
monotonic sampling rejects detected jumps over that allowance. Invalidation takes
the account lock and stores max(old cutoff, ceil(DB wall time)+30), then increments
the account revision. Every authenticated operation rejects iat <= cutoff with no
skew grace. Already invalidated tokens cannot become valid as clocks move; new
tokens may require waiting past the cutoff. Actual synchronized-clock behavior is
unaccepted. Local invalidation neither terminates provider sessions nor revokes
refresh tokens; provider-only logout is not immediately observable here.

Service entrypoints authenticate raw tokens internally: create_session(token,
request_key), resolve_session(token, session_key, expected_revision),
reserve_artifact(token, session_key, expected_revision, request_key),
resolve_artifact(token, session_key, session_revision, artifact_key,
expected_revision), revoke_session(token, session_key, expected_revision), and
invalidate_account_tokens(token). Cancellation is an optional non-clearable latch;
request callers supply neither principals nor owner assertions. Returned frozen
OwnedMetadata carries C1 keys, state/revision and, only for account invalidation,
the cutoff. It contains no token, issuer/subject, content or financial reference.
Artifact reservations are not SessionArtifactRef financial evidence.

The service begins/commits/rolls back/closes each fresh transaction; repository
helpers do not commit. It sets READ COMMITTED/READ WRITE and fixed transaction-local
lock_timeout=1s, statement_timeout=2s, idle_in_transaction_session_timeout=5s.
Allocation locks account -> session -> artifact, checks retained-record quotas
(20 sessions/100 artifact reservations per account), and never releases quota on
revocation. Unique issuer/subject plus INSERT ON CONFLICT DO NOTHING followed by
a separate locked SELECT handle first-login contention. All new identity/key
columns use C collation for exact comparison. Composite owner/session foreign keys
and owner-scoped idempotency constraints are additive. Counts are serialized by
the service's account lock, not a cross-row database CHECK; direct writers must
follow this protocol. No database enforcement/concurrency proof is claimed.

Session allocation replay resolves the same owner/operation request. Artifact
replay must additionally match the original session and its revision. It still
requires valid authentication, live parent/artifact and current access. No replay
can bypass invalidation or revocation. Revocation of the same session transition
can return its already-revoked revision to its authenticated owner.

The operation has a cooperative five-second deadline, a one-second pre-COMMIT
reserve and a 65536-byte encoded result cap. Before COMMIT dispatch, failure or
cancellation rolls back pending work. Dispatch is ordered against cancellation
under the latch lock and conservatively marks the outcome indeterminate before
calling the driver. An exception then cannot prove that no COMMIT was sent.
Confirmed commits persist even when cancellation, stale configuration, expiry or
cleanup failure prevents return. Rollback/close failures invalidate the connection
and withhold the result; no cleanup can undo an acknowledged commit.

There is no automatic retry. An authenticated retry of the same allocation key is
the bounded reconciliation path, using the same account-lock/unique-key protocol;
it can recover a committed allocation or allocate once after rollback. Lock timeout
or continued uncertainty is failure, never proof of absence. Reconciliation itself
can commit and lose acknowledgement. No unlocked absence lookup proves a prior
in-flight transaction rolled back. Later revocation cannot retract a detached
snapshot already authorized; future HTTP delivery needs its own last access check
and must not hold database locks across sending bytes.

Migration a7c730103001 follows f94c6f41e0cb and creates only research_accounts,
research_sessions and research_artifacts. No existing data or migration is changed.
Automatic downgrade raises a forward-only error. Code rollback can leave the new
tables intact; deleting populated ownership records requires separate approval.

See the [ExecPlan](exec-plans/active/2026-10-30-ucr-account-ownership.md) for actual
offline commands/results. Fake sessions and compiled PostgreSQL DDL are unit/schema
evidence only. Real migrations/constraints/concurrency/rollback, provider login/key
rotation/logout, DB privileges, native Windows and HTTP/browser gates remain open.
Next integration is separately scoped authenticated session POST/GET after those
applicable gates. Source custody, rights, extraction verification, financial
admission and session-engine references remain later prerequisites. An owner, a
matching digest or a C1 capture does not authorize financial calculation.

B1-B6 reuse owned operation/event/quota primitives but require separate provider signature/account/test-mode verification and a billing ledger. Neither a Stripe/browser success redirect nor a billing entitlement attests financial evidence. Non-commercial billing accepts code/mocks/authorized sandbox workflows and rejects live-mode charging; no merchant activation is needed.

### C8 - Bounded acquisition/jobs and committed change events

Minimum logical records: `ResearchJob` and `PublicationEvent`.

ResearchJob contains server-issued operation/owner identity, entity and source-policy scope, idempotency identity, phase, resource reservation, deadline/cancellation identity, lease/fencing identity where required, attempt/outcome and sanitized reason. Shared concepts apply to acquisition, parsing, inference, update delivery and billing reconciliation; authority/transactions remain specific to the job kind.

Proposed outcomes distinguish queued/running phases from session-ready, published, quarantined, failed, cancelled and indeterminate. Discovery is not authorization to acquire; acquisition is not financial admission; admission is not shared publication. Validate rights/identity before acquiring, then preserve originals, parse, admit/quarantine and either return session evidence or explicitly publish. Existing GET/read routes remain stored-only. On-demand U2 uses an explicit authorized job action, not a hidden read-route side effect.

Reuse existing refresh attempts, per-company locks, insert-only facts and ambiguous-commit reconciliation rather than replacing them. A task retry must inspect recorded/actual outcome, not blindly repeat acquisition, publication or billing effects. Loss of lease/access/cancellation prevents later publish/delivery. Terminal session-ready does not increment shared DB versions.

PublicationEvent binds the committed stream/version, affected entity/source/observations, publication identity and event ID. Fact/evidence/market streams remain distinct. Publication and its future outbox entry must be atomic; recipients and delivery idempotency are checked afterward. Failed delivery cannot republish data. Radar/Inbox/Coverage Planner consume these events and scopes, not private worker credentials. Failed checks or recent discovery do not claim current financial coverage.

### C9 - Cancellation, resource, failure and rights/retention policy

Minimum logical context: `OperationPolicy`, resolved from reviewed server policy; never a client override.

Policy supplies finite per-operation limits for input/decoded bytes, documents/pages/chunks/vector work, retrieval/ranking/context, concurrency, duration, response encoding, storage/retention, and optional cloud cost. New operation classes need justified numeric limits and exact-limit/one-over tests before activation. Do not reuse Reader's chunk/text caps as upload, response-size, RSS, SQL-time or inference guarantees.

Existing strict Reader limits remain owned by reader_resource_policy.py: lifecycle UTF-8 131072 bytes, depth 2, pending targets 4096, chunks 4000, chunk text 3000 code points, aggregate text 12000000 code points / 48000000 UTF-8 bytes, vector dimensions 384 / aggregate components 1536000, non-text logical bytes 2000000 and detached logical bytes 50000000. These count logical payload as documented by the helper, not total Python/native memory or wire response size. Tone retains its original policy; no generic consumer can choose a legacy fallback or bypass strict admission.

Cancellation/deadline/ownership checks occur before dispatch, between bounded stages and before return/publish. Cooperative checks cannot interrupt blocked synchronous SQL/native work; separately accepted driver/worker termination, rollback/invalidation and cleanup are required. Cleanup failure withholds the affected response/publication. Render ownership/generation checks reject late results even if transport abort was ignored.

Keep failure categories separate: invalid selector, ambiguous identity, insufficient evidence, unsupported coverage, stale pin, pending/corrupt publication, denied rights/access, resource excess, cancellation/deadline, provider/driver failure and indeterminate commit. New category-to-HTTP mapping is not approved here. Preserve existing 422 and DATA_VERSION_CHANGED/EVIDENCE_PENDING/SEARCH_SCOPE_TOO_LARGE precedence and established route behavior; do not convert an error into an empty success or truncate to pass a budget.

Rights decisions are operation-specific: discover/acquire, retain, parse/OCR, display, export/redistribute, cloud transfer and training are separate. Unknown permission denies the affected operation without erasing independently usable admitted local evidence. Source date, policy version, attribution, retention/deletion restrictions and permitted purpose travel with artifacts and receipts. Official origin does not automatically license arbitrary reuse; non-commercial status does not remove provider/dataset conditions. SEC fair-access/contact policy and shared rate limits must be checked before any future acquisition. No new legal entitlement is asserted by C0.

## Universal Research trace and cross-family consistency

| Consumer family | Shared path / acceptance boundary |
|---|---|
| Catalog and Universal U1-U6 | C1 resolves entity; C2/C3 inspect local coverage; C8/C9 permit official discovery/acquisition; C4 session bundle and C5 admitted facts support deterministic answers without Company/FinancialFact insertion; C6 supplies actual local grounded narrative. |
| Statements, ratios, segments, comparisons, D2/D6/D10 | C3/C5 retain periods/bases/dimensions/vintages, operands and conflict diagnostics; C4 receipts preserve reproducibility without changing existing selectors by default. |
| Hybrid/complex RAG and D3 | C2/C4 complete scoped evidence plus C6 shared provider/claim boundary; C9 budgets/cancellation; identity alone never proves support. |
| Chat/memory/workspace/uploads and D5 | C7 authorizes owned persistence; C8/C9 handles extraction/retention; C2 distinguishes uploaded/external authority; C4 pins old investigations. |
| Markets, portfolios, VaR/CVaR, optimization, Monte Carlo/stress | C1 security/listing, C3 pinned calendar/action/availability and C5 existing exact returns followed by reviewed statistics, including 10a's explicit historical loss/quantile/tail policy; C7 owned exposure/currency inputs; C9 bounded work. |
| Risk, news/NLP and ML/forecasts, D4 | C2 source/rights, C3 as-of data, C5 reported/derived/estimated distinction, C6 narrative policy, C8/C9 experiments/jobs. Private PhraseBank or lexical-tone evidence cannot certify a public risk/forecast product. |
| Radar/Inbox/Coverage Planner D1/D7/D9 | C8 committed events and idempotent delivery, C7 recipient ownership, C3 scope/freshness and C9 permitted acquisition. |
| Exports and D8 receipts | C4 version/algorithm/model/output lineage, C7 authorized visibility, C9 retention/export rights and C5 deterministic replay. |
| Authentication/hosting/accessibility/reliability | C7 real identity/isolation and C9 resources/cleanup; existing typed clients/capabilities and actual native/browser/operations acceptance remain separate. |
| Billing B1-B6 | C7 owner and entitlement authority, C8 durable event/reconciliation primitives, C9 quotas/test-only boundary; dedicated Stripe signature/idempotency/ledger semantics remain required. |

This mapping covers all sixteen register domains, D1-D10, U1-U6 and B1-B6. Each atomic row references its applicable C contracts; a shared primitive does not collapse independent product acceptance requirements.

## Integration conflicts and decisions requiring bounded review

| Conflict / unresolved detail | Required disposition before affected integration |
|---|---|
| DB schemas require CIK/int IDs; external/non-SEC identities may lack them | Approve a reference/mapping bridge without sentinel IDs, schema coercion, fake ORM rows or automatic company insertion. Any later schema change needs its own ExecPlan/migration review. |
| FinancialMetrics and original-evidence authorization are DB/SEC-bound | Review the narrow admitted-input reuse boundary and precision/basis rules; no second engine, permissive registry or broad source approval. |
| Existing market Security requires company_id/issuer_cik | Keep it unchanged until a separate adapter or versioned transition is accepted; new C1 records are not already accepted return inputs. |
| Strict CC-02/insights clients and F/D closed schemas | Choose versioned envelopes/adapters and paired delivery/rollback before consumer edits; no additive fields silently inserted into closed existing payloads. |
| Roadmap/product-spec snapshots lag some current interfaces | Existing capability schema includes research_mode, ai_analysis_configured, ai_analysis_enabled and server_profile; do not infer active AI/Reader routes from older two-boolean prose. Preserve current source/profile semantics and leave these out-of-scope owning docs unchanged. |
| Frontend capability client recognizes development/sec_readonly, not sec_reader | Reader diagnostics are not already a compatible frontend research backend. Any future Reader capability/client transition needs an explicit paired contract and route acceptance; do not simply add the profile string or enable hidden routes in a consumer task. |
| Session evidence retention versus saved-history reproducibility/deletion | Resolve per-source rights and per-owner retention/tombstones; disclose replay limits rather than retaining prohibited originals or replacing old evidence. |
| Filed dates and naive stored_at versus point-in-time claims | Preserve granularity/unknown values; review timestamp interpretation and historical coverage before claiming exact known-at-time research. |
| Worker authority, outbox/schema, auth provider and artifact ACL/storage | Choose and review concrete implementations under separate scopes; C0 makes no deployment, migration, provider or filesystem-security acceptance claim. |
| Generation supports current SEC SOURCE IDs, not a generic external bundle | Lock namespaces/locators/support validation and explicit local/cloud privacy/cost handling before enabling consumers. |
| Resource policies beyond strict helper are uncalibrated | Lock operation-specific limits, serializer and native/DB cancellation/cleanup acceptance; do not inherit deferred ranking/time/RSS guarantees. |
| News/market/ML and Stripe test access require separate rights/configuration | Obtain source/test-mode authorization when required; no secrets in docs, no live billing or public-use inference from private academic evidence. |

These are explicit join gates, not scope removal or requests for blanket permission. No contract is production-ready merely because it is documented.

## Proposed C1 representation lock for focused review

Status: **APPROVED REPRESENTATION / C1 IMPLEMENTATION CANDIDATE, INDEPENDENT IMPLEMENTATION REVIEW PENDING** (2026-10-29). The coordinator's supplied C1 task records focused independent approval of this complete representation lock and authorizes its exact four-path bounded implementation at main `791a4c5dd93f5cf92cbc802662027126d5388cee`. That current instruction supersedes the historical pending representation review/C1 NO-GO for this inert slice only. The lock below is implemented by the uncommitted candidate; it is not a public API change or an authority grant. C2-C9 production integration and existing database/HTTP/model/activation gates remain separate.

### Representation decisions and equality

| Decision | Preferred exact representation | Alternative / tradeoff |
|---|---|---|
| Identifier namespaces | A KeyRef has exactly `namespace` and `id`. Allowed namespaces: sec_cik, external_entity, security, listing, principal, session, artifact, source_descriptor, source_revision, rights_policy, admission_record, market_publication, authority_record, calendar. The namespace expected by each field is checked. | A bare string/CIK-only key is shorter but confuses issuers, securities, sessions and external identities. Adding a namespace needs a reviewed schema-version change. |
| Stable key equality | Compare the exact (namespace,id) pair, case-sensitive, after only the explicit CIK normalization below. Never derive equality from names, symbols, numeric DB IDs or an unverified alias. Entity/security/listing record equality includes all metadata; matching stable keys do not authorize ignoring conflicting metadata. Evidence record equality includes all fields, including owner, pins and digests; it is not just an entity match. | Case folding/Unicode normalization or ticker-derived keys can merge distinct source identities. Resolver-issued mappings may later establish cross-key equivalence; C1 cannot. |
| CIK | The explicit text-only CIK factory accepts 1-10 ASCII digits, rejects all-zero values and pads to ten digits. Canonical records/wire require exactly ten digits, positive numeric meaning; no int/bool/sign/whitespace coercion. sec_cik EntityRef key.id must equal its non-null cik. external_entity EntityRef has cik=null; resolving it to SEC identity later is explicit, not a dual-key equality trick. | Padding all decoded input silently would obscure noncanonical wire values. Integer identifiers lose leading zeros. No DB ID is needed for either entity variant. |
| Issuer/security/listing | SecurityRef and ListingRef have separate namespaced keys; security.issuer_key binds an entity and listing.security_key binds a security. A supplied reference-set check requires these links to match supplied records exactly. Standalone keys cannot prove the real-world link. | A company ticker cannot represent several share classes/listings. Existing market/ORM types need explicit adapters, not placeholder company_id/CIK values. |
| Accession | Canonical ASCII pattern [0-9]{10}-[0-9]{2}-[0-9]{6}, exactly 20 characters; no undashed/int coercion. Accession prefix need not equal issuer CIK. Publication identity is the issuer-key/accession pair, with revision/pins in the evidence reference. | Enforcing a matching prefix breaks agent/successor filings. C1 constructs no URL and cannot attest filing ownership. |
| Deep immutability | Proposed standard-library frozen slotted value objects; nested collections are tuples of closed value objects/scalars. Constructors accept exact documented scalar/value-object/tuple types, not arbitrary mappings, iterators or mutable lists. Decoder copies JSON arrays into fresh tuples and retains no caller dict/list. No identity/authority resolution in equality/hash. | Frozen outer dataclass alone leaves mutable nested payloads. Pydantic/ORM models would add dependencies and operational coupling to this inert slice. |

KeyRef.id is 1-128 ASCII characters matching [A-Za-z0-9][A-Za-z0-9._:-]{0,127}, except sec_cik's stricter ten-digit rule. Server-issued UUID strings fit, but the module generates no IDs or randomness. Keys are opaque labels, not paths, URLs, secrets or authentication tokens. Reusing an existing free-form market ID that violates this syntax requires a reviewed mapping adapter; never silently strip/change it. Deep immutability concerns supported constructors/APIs and all nested values; it is not a sandbox against hostile in-process Python/native code or object.__setattr__ bypasses.

### Closed field sets and tagged variants

Every listed field is required on the wire, including fields whose allowed value is null. There are **no omitted optional fields** in C1 v1. A null is accepted only where explicitly listed. Every object rejects unknown, duplicate or mixed-variant fields. Key references below embed only KeyRef, never another EntityRef/EvidenceRef or a resolved SourceDescriptor; object graphs cannot recurse.

| Record / kind | Exact required fields and restrictions |
|---|---|
| KeyRef (nested value, no kind field) | namespace, id, under the rules above. Namespace sets below are exhaustive. |
| EntityRef / entity | kind, key, legal_name, jurisdiction, cik, authority_ids. key namespace sec_cik or external_entity; jurisdiction=null or two uppercase ASCII letters (syntax only); cik as above. authority_ids is a tuple/JSON array of AuthorityIdentifier. |
| AuthorityIdentifier (nested) | scheme, authority, identifier, evidence_key, effective. scheme is sec_cik / lei / authority_id; authority is a bounded ASCII token, not an approved-source declaration. identifier is canonical ten-digit CIK, 20 uppercase ASCII alphanumerics for LEI (structure only), or a bounded opaque authority identifier. evidence_key namespace authority_record or artifact; effective is DateInterval or null for unknown validity. No LEI/source verification is claimed. |
| SecurityRef / security | kind, key, issuer_key, share_class, authority_ids. key namespace security; issuer_key namespace sec_cik or external_entity; share_class is a label, not an identity key; authority_ids use scheme=authority_id only (CIK/LEI are issuer identifiers, not security identity). |
| ListingRef / listing | kind, key, security_key, mic, currency, calendar_key, calendar_version, effective, aliases. key namespace listing; security_key namespace security; mic exactly four uppercase ASCII letters/digits; currency exactly three uppercase ASCII letters; calendar_key namespace calendar; effective is DateInterval or null for unknown validity. No automatic exchange/calendar/currency authority is implied. |
| SymbolAlias (nested) | provider, product, symbol, effective, evidence_key. evidence_key namespace authority_record or artifact; effective is DateInterval or null for unknown validity. Preserve provider/product and symbol case/spelling. The listing supplies MIC/security context. Same provider/product/symbol cannot have duplicate or overlapping effective intervals within one listing; multiple such aliases with an unknown interval reject because disjointness cannot be established. Distinct listings may legitimately have the same symbol and require disambiguation. |
| IdentityResolution / identity_resolution | kind, status, candidate_keys, evidence_keys, reason_code. status resolved / ambiguous / unresolved. candidate_keys are unique entity keys: exactly one / 2-16 / zero respectively. resolved/ambiguous require 1-16 evidence keys in authority_record or artifact; unresolved allows zero. This records a producer's result; decoding cannot certify it. |
| TimePoint / unknown | Exactly kind=unknown; no value field and no invented epoch or null instant. |
| TimePoint / date | Exactly kind=date, value=valid YYYY-MM-DD. Date-only is not a midnight instant or interchangeable with unknown. |
| TimePoint / instant | Exactly kind=instant, value=timezone-aware RFC3339 text. Decode allows Z or explicit +/-HH:MM offset, seconds and 0-6 fractional digits; normalize to UTC output YYYY-MM-DDTHH:MM:SS.ffffffZ. Reject naive times, timezone names, leap seconds, >6 fractional digits or range/UTC-conversion overflow. |
| DateInterval (nested) | Exactly start, end: valid date text start and date text or null end; rules below. |

An authority_id identifier uses the same opaque ASCII syntax/128-character bound as KeyRef.id; scheme sec_cik must have authority=sec and any sec_cik authority identifier on an EntityRef must agree with its cik. A non-SEC EntityRef cannot smuggle in a conflicting sec_cik authority identifier. No global authority registry or external lookup is loaded by C1.

All EvidenceRef variants have these exact common fields: `kind, entity_key, origin, owner_key, session_key, source_descriptor_key, source_revision_key, rights_policy_key, admission_record_key, public_available_at, retrieved_at`. entity_key is an entity KeyRef; public_available_at/retrieved_at are TimePoint values, including explicit unknown when necessary. Source descriptor/revision, rights and admission fields are KeyRef in their matching namespace or null unless a variant below requires one. Null rights/admission means unresolved/denied for affected use, never permission.

| Evidence kind | Additional exact fields | Common-field constraints |
|---|---|---|
| database_publication | accession, publication_data_version, evidence_version, data_version, manifest_sha256, chunk_id | entity_key namespace sec_cik; origin=sec; owner_key=null and session_key=null. chunk_id=null for publication-only reference, otherwise 1-50 ASCII identifier characters. Preserve publication_data_version <= evidence_version <= data_version and zero. Optional-in-meaning metadata keys remain present as null until resolved. Decoding does not run the accepted publication helper. |
| session_artifact | artifact_key, artifact_sha256 | artifact_key namespace artifact; non-null owner_key namespace principal and session_key namespace session; source_descriptor_key required non-null. origin is official_sec / official_issuer / official_exchange / official_regulator / user_upload. Source revision/rights/admission keys may be null. Claimed official origin is not verified authority; uploaded/private material is never reclassified by changing this string or supplying an admission key. |
| market_publication | security_key, listing_key, market_publication_key, market_data_version, manifest_sha256 | security/listing/market_publication namespaces must match their fields; source_descriptor_key non-null; origin=market_provider. owner_key is null or principal; session_key is null or session, and a non-null session requires a non-null owner. Other metadata keys may be null. C1 does not attest provider custody, action completeness, license or existing MarketPublication compatibility. |

No variant accepts database fact IDs, DB company IDs, embedded raw content, arbitrary locators, URLs, financial values, a trusted/admitted boolean, recursive evidence bundles or an alternative variant's fields. Hash fields are exactly 64 lowercase ASCII hexadecimal characters; reject uppercase rather than silently normalizing. Existing native dataclasses/IDs and public response shapes stay unchanged.

A pure supplied-context check can compare a reference's owner/session/entity/security/listing keys with explicit expected keys and reject a substitution/mismatch. Without authenticated C7 context and server-side C2 resolution, structurally valid same-namespace substitutions remain **untrusted references**, never authorized results. A syntactically valid rights/admission-record key cannot self-issue the corresponding decision.

### Serialization, limits, pins and intervals

- **Envelope:** decode consumes exact immutable bytes, encode returns bytes; constructors accept the documented scalar strings/closed value objects rather than user-defined datetime/tzinfo or coercion callbacks. JSON object with exactly schema_version and record; schema_version is exact int 1, not true, string "1", 1.0 or a future version. record is exactly one root record kind from the tables (entity, security, listing, identity_resolution, database_publication, session_artifact, market_publication). Nested TimePoint/KeyRef/interval values follow their field context, not arbitrary root types.
- **Canonical output:** UTF-8 without BOM; JSON sorted keys, separators comma/colon without spaces, ensure_ascii=false, allow_nan=false. Preserve tuple order as arrays; do not sort away source/alias order or normalize descriptive text. Reject duplicate decoded object keys before a dict can discard them, including escaped spellings of the same key. Decoder may accept JSON whitespace/key order but only exact field sets/types; canonical re-encoding is stable. Object -> encode -> decode is exact value equality; canonical encode -> decode -> encode is byte-identical. Noncanonical input byte equality is not promised.
- **Pins/numbers:** every pin is type(value) is int, 0 <= value <= 9007199254740991 (existing MAX_SAFE_VERSION boundary). Reject bool, float, numeric string, negative, -0 token and oversize values. Bounded JSON integer parsing checks <=16 digit characters and numeric range before building a number; no numeric exponents, NaN or Infinity. Schema version uses the same non-coercive integer discipline. No financial numeric payload is part of C1.
- **Per-field limits:** namespace <=32 ASCII characters and enumerated; KeyRef.id/opaque authority identifier <=128 ASCII characters; legal_name 1-200 Unicode code points / <=800 UTF-8 bytes; share_class 1-64 code points / <=256 bytes; authority/provider/product/calendar_version/reason_code 1-64 ASCII token characters [A-Za-z0-9._:-]; symbol 1-64 ASCII characters matching [A-Za-z0-9][A-Za-z0-9._:/+-]{0,63}; chunk_id 1-50 characters under the opaque identifier syntax. Fixed CIK/accession/LEI/MIC/currency/date/hash widths above override generic bounds. Reject empty/leading-or-trailing whitespace, control characters, unpaired surrogates and bidi override/isolate controls U+202A-U+202E and U+2066-U+2069; do not truncate, case fold or Unicode-normalize labels/keys.
- **Collection limits:** authority_ids <=16, aliases <=64, candidate_keys <=16, evidence_keys <=16. Reject exact duplicate members and duplicate keys with conflicting metadata; preserve input order. Constructors accept tuples; JSON arrays are copied/frozen. There is no unbounded recursive component or arbitrary metadata dict.
- **Whole-record limits:** <=65536 input UTF-8 bytes, <=8 JSON object/array nesting levels (root envelope is level 1), <=2048 nodes counting containers, scalar values and member-name strings. Scan byte/depth limits before full materialization, then bounded parsing/shape validation. Direct construction enforces field/collection/aggregate limits before accepting the immutable result. These are proposed finite metadata bounds, not measured runtime/RSS guarantees or replacements for accepted Reader limits. Inclusive boundaries pass only if the rest of the schema is valid; one-over rejects without truncation. Unreachable aggregate limits cannot be advertised as valid whole-record fixtures.
- **Date intervals:** start inclusive, non-null; end exclusive, nullable for unknown/open end. If end is present require start < end; equal/reversed dates reject. A null whole effective field means unknown validity, not an open interval or an invented start; it cannot establish dated alias disambiguation. Adjacent aliases [a,b) and [b,c) do not overlap; gaps stay gaps. An open end is source-declared coverage, not proof of indefinite future continuity. Do not compare a date-only availability with an instant cutoff by inventing timezone/time: the temporal selector must disclose ambiguity or abstain. Existing market last_session/effective_to endpoint conventions need an explicit adapter; this proposal does not change them.

These limits reuse existing safe pin and familiar scalar widths where applicable; the new metadata envelope/collection limits are explicit preferred engineering bounds pending review, not measurements of live corpus compatibility. Alternative larger/extensible metadata records would reduce adapter work but increase ambiguity/resource surface; prefer this closed v1 slice and a reviewed later version rather than unknown-field pass-through.

### Dependency direction and future test matrix

Preferred acyclic direction: standard-library primitives -> inert research_contracts value objects -> future authority/ownership/admission adapters -> orchestration/API/consumers. Existing financial/market/publication modules do not import the new module in C1. The new module imports no application/configuration/ORM/database/reader/model/provider/network/filesystem modules and performs no environment reads, path opening, ID generation, registry discovery, logging setup or import-time object resolution. Internal records contain identifier-only links, not embedded C1/C2 recursive object graphs.

| Future negative / mutation case | Required result |
|---|---|
| Same ticker on different MICs/share classes; BRK.B versus a provider BRK-B spelling | Distinct keys/listings remain distinct. Aliases need provider/product/interval evidence; no symbol normalization or automatic equality. |
| Non-SEC entity without DB IDs; SEC CIK factory input versus wire | external_entity+cik=null works; fake required DB IDs are absent. Factory pads valid ASCII digit strings; noncanonical wire, bool/int/all-zero/oversized CIK rejects. |
| Security issuer/listing security mismatch; accession prefix differs from issuer | Supplied-chain check rejects wrong links. Valid independently scoped accession prefix difference passes syntax; no URL/source verification implied. |
| Unknown kind/namespace/schema version, duplicate JSON keys or mixed EvidenceRef fields | Closed decoder rejects, including escaped duplicate keys and null/omitted fields not explicitly allowed. |
| Owner/session/entity/namespace substitution | Wrong field namespace/expected-context link rejects. Same-namespace well-formed replacement without trusted context remains untrusted; decoder cannot promote it to authorized evidence. |
| Pins 0 / -1 / true / "0" / 1.0 / exponent / max / max+1 / -0 | Only exact 0..9007199254740991 integers pass, with publication/evidence/current ordering checked. |
| Unknown/date-only/aware/naive time; offset UTC conversion; overflow | Variants stay distinct; aware instant normalizes without precision loss; naive/excess precision/invalid dates and invalid UTC range reject. |
| Equal/reversed interval, adjacent/nonadjacent/overlapping dated aliases | Reject empty/reversed/overlapping duplicate-symbol intervals; retain adjacency and honest gaps under half-open semantics. |
| Exact-boundary/one-over bytes, strings, collection length, depth/components | Enforce every applicable inclusive limit without truncation or bypass by escaped text; invalid shape never becomes an accepted boundary case. |
| Mutation of input lists/dicts after decode; nested record mutation; equality/hash substitution | Decoder copies/freezes, constructors reject mutable containers; no caller mutation changes stored value or canonical output. Full evidence equality detects changed pins/owner/digest. |
| Canonical round trip, reordered input keys/whitespace, non-ASCII label and duplicate member | Canonical output stable; no lossy normalization; duplicates/unknown fields fail, source spelling preserved. |
| Import/constructor forbidden-effect sentinels | Any configuration/env, file, DB, socket, model/provider, registry lookup or ID-generation effect fails guarded tests. No sentinel merely masks the attempted effect. |

Historical FIX1 wrote no C1 implementation, tests or ExecPlan; its matrix was proposed acceptance. The separately authorized C1 candidate now implements the locked values and tests below. Source registries, real authentication, financial bridges, rights retention/storage, runtime cancellation and public integration remain later adapter decisions, not hidden C1 capabilities.

## C1 bounded implementation record

**FL-ALL-1215-W1-C1 - Inert identity and evidence-reference value objects.**

Implement only C1 entity/security/listing reference metadata and the C2 discriminated reference variants, with minimal C3 version/time precision metadata needed to identify them. This slice resolves/validates record structure, not authoritative company lookup, evidence admission or financial calculations. Treat decoded references as untrusted until a later authorized server resolver supplies the context.

Exact coordinator-authorized scope:

1. New `backend/app/research_contracts.py`: inert standard-library value objects/validation; no imports of config, dotenv, ORM/database, model/provider, acquisition or operational modules.
2. New `backend/tests/test_research_contracts.py`: guarded offline identity/collision/reference/temporal tests; no real I/O/services.
3. New `docs/exec-plans/active/2026-10-29-shared-research-reference-values.md`: required implementation record, scope, decisions and actual checks.
4. This contract document: record approved representation decisions and actual slice evidence only; preserve proposed status for every unimplemented consumer.

Entry dependencies satisfied by the supplied coordinator task and local baseline checks: C0 accepted/committed/pushed; focused independent representation approval; separate exact C1 implementation authorization; main at the expected HEAD, empty index, only the three protected exceptions and matching hashes. Existing helper acceptance is reused, not rerun. C1 uses synthetic reference values without DB/model/source credentials; it cannot activate Reader or make caller-provided evidence “admitted.”

Definition of done: no-DB entity and multiple listing/share-class references; ticker collisions cannot collapse identities; DB/session/market namespaces cannot be confused; zero pins and unknown/date-only times are preserved; invalid/missing/foreign-owner reference shape is rejected where structural context is available; import/constructor guards detect forbidden operational effects. No ownership authorization or source verification is claimed from pure validation. No financial ID fabrication, mutation of existing schemas/digests or consumer integration. Independent review must judge new boundaries before any follow-on scope.

Later resolver, artifact store, financial-input bridge, generation, jobs, ownership, billing and public routes require their own authorizations and relevant acceptance. Do not begin them as part of C0 or C1.

### C1 candidate behavior and verification (2026-10-29)

- [research_contracts.py](../backend/app/research_contracts.py) implements frozen slotted KeyRef, EntityRef, AuthorityIdentifier, SecurityRef, ListingRef, SymbolAlias, IdentityResolution, DateInterval, distinct unknown/date/instant TimePoint classes, and the closed DatabasePublicationRef / SessionArtifactRef / MarketPublicationRef variants of EvidenceRef. All constructor fields, including nullable fields, are explicit; nested collections require tuples. Full-record equality/hash includes metadata; KeyRef compares only its exact namespace/id pair.
- `canonical_sec_cik(text)` is the sole CIK padding factory. `encode(record)` returns canonical v1 UTF-8 bytes; `decode(bytes)` returns fresh immutable values. Byte/depth preflight precedes bounded recursive parsing; node counts include member names, containers and scalar values. Duplicate decoded names reject before dict insertion. Integer lexemes are bounded before int construction; floats/exponents/negative zero/nonfinite values reject. All lock field/collection/aggregate limits apply to constructors and decoding.
- `check_reference_context` compares supplied entity/security/listing records and explicit expected keys, rejecting mismatches and conflicting full records. An expected relationship with no comparable supplied link rejects. Owner/session expectations default to null, so private references require both explicit keys. It returns no authority decision, performs no lookup and never treats origin/rights/admission labels as verified.
- Focused isolated command from repository root: `backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_research_contracts.py`. Actual passing candidate run: **49 tests, 609 successful subtests, zero failures/errors/skips**. Includes eight in-memory semantic mutants (each baseline rejects and changed branch accepts), ten positive forbidden-effect sentinel controls, and a fresh-process guarded module execution covering all root constructors, nested values, context checks and codec. The guard compiles the candidate source before installing sentinels so ordinary source loading is outside the operational-effect boundary.
- Negative checks cover missing/null/unknown/mixed fields, escaped duplicate keys, namespaces/context substitutions, CIK/accession/LEI/hash syntax, pin zero/max/coercion/order, temporal/offset/overflow precision, duplicate/conflicting members, dated alias adjacency/overlap, Unicode controls, nested mutation, and exact/one-over field/collection limits. A valid envelope padded with JSON whitespace passes at 65536 input bytes; 65537 rejects before parsing. Generic parser depth 8/nodes 2048 boundary fixtures are explicitly invalid C1 schema, with one-over rejection; the actual closed schema reaches at most depth 5 and remains below 2048 nodes. Reduced-cap controls verify direct-constructor aggregate checks without inventing valid unreachable schema fixtures. No measured wall-time/RSS claim is made.
- Initial execution: 45 tests with two failed subtests. One test incorrectly rejected allowed null jurisdiction and was corrected. The other exposed Python's ISO parser accepting `24:00:00`; explicit RFC3339 clock ranges now reject it before normalization. Expanded coverage and self-review also require actual comparable context links. No locked representation deviation or unresolved contradiction was found.
- Syntax, whitespace, exact-scope and final preservation checks are recorded in the [C1 ExecPlan](exec-plans/active/2026-10-29-shared-research-reference-values.md). Independent Astra High implementation review remains pending; local GO is only readiness for that review. No C2-C9 consumers, authentication, real-source authority, Universal Research acquisition, services, Reader activation or deployment were implemented or exercised.

## C0 verification boundary

C0 checks only the two-document inventory, links, every requirement/category and contract mapping, whitespace, exact changed-path set and protected baseline. It does not execute application/DB/browser/provider/model tests or update historical acceptance. See the register for the Git/protected-file handoff and per-requirement pending evidence fields.
