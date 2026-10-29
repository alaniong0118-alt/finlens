# FL-UCR-01A — Pure universal issuer candidate kernel

Status: active for independent review; bounded implementation and local validation complete.
Roadmap phase: scoped U1 enabling task only.

## Objective

Resolve supplied structured metadata into deterministic, immutable **unverified
candidates**, conflicts and explained abstentions without a local company row.
Never produce C1 `IdentityResolution(status="resolved")` or confer authority.

## Current architecture and context

Read root AGENTS, `.agent/PLANS.md`, ROADMAP, engineering standards, U1-U6 in
[requirements](../../full-feature-requirements.md), C1-C9 and especially C1-C3 in
[contracts](../../shared-research-contracts.md), `research_contracts.py`, relevant
SEC client identity validation and [source policy](../../data-sources.md).
C1 provides inert reference values, not registry admission. SEC discovery checks
the returned registrant CIK; an accession prefix can identify a submitting entity
and must not substitute for the issuer. This kernel does not import that client.

Starting branch `main`, HEAD `237a378cc1a0d754fb7a4412843a306c960116dd`, empty
index. Exactly three protected exceptions were observed and hashed before work:

| Path | SHA-256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

## Constraints

Create only `backend/app/universal_identity.py`, its dedicated test file and this
plan. Preserve existing files, index and protected exceptions. Never inspect,
hash or modify `backend/.env`. No network, paths, credentials, database, HTTP,
persistence, model, acquisition, integration, staging, commit or push.

## Non-goals

No UCR-01B, registry authority admission, issuer-specific maps, finance extraction,
predecessor consolidation or completed C1/Quant review. Synthetic fixtures do not
establish real source/runtime/product acceptance.

## Implementation stages

1. Verify baseline and inspect authoritative relevant contracts (done).
2. Implement closed queries, bounded inventory validation and pure matching.
3. Add positive, adversarial, isolation and in-memory mutation controls.
4. Run focused verification; self-review scope, semantics, bounds and preservation.
5. Record actual commands/results and remaining blockers; stop for review.

Recovery: the only implementation artifacts are these three newly created files;
no existing runtime/data state is changed and no rollback operation is needed.

## Decisions

- 2026-10-29: use a separate `CandidateResolution` instead of C1's resolved status.
  Uniqueness is structural agreement with supplied metadata, not trusted identity.
- 2026-10-29: require exact MIC and provider/product for dated symbols. Exchange
  name translation and namespace normalization belong in a later reviewed adapter.
- 2026-10-29: keep inactive matching records as diagnostics in the returned
  candidate tuple; never truncate, silently merge or promote unknown date ranges.
- 2026-10-29: retain this plan at the user's exact active path for independent
  review rather than moving it outside the three permitted additions.

## Exact interface and matching semantics

Public entry: `resolve_candidates(query, inventory) -> CandidateResolution`.
All new values are frozen, slotted dataclasses with exact scalar/tuple/C1 types.
The resolver revalidates the complete inventory, including unrelated records,
before matching. Structural errors raise `IdentityInputError` or C1
`ContractError`; error messages omit supplied labels. These are Python value
APIs only, with no new wire format, route or persisted registry.

| Query | Exact fields and semantics |
|---|---|
| `CikQuery` | `cik`: exact nonzero ten-ASCII-digit C1 CIK. `from_unpadded(text)` is the explicit text-only C1 normalization factory. Match entity key in `sec_cik`; never infer a CIK from a symbol, accession prefix, external key or DB ID. |
| `SymbolQuery` | `symbol, mic, as_of, provider, product`: all required, exact case/spelling; MIC is four uppercase ASCII letters/digits, date is valid `YYYY-MM-DD`. No ticker-only or exchange-name query; provider/product scopes are independent. |
| `AuthorityQuery` | `scheme, authority, identifier, as_of=None`: exact triple, optionally dated. C1 schemes `sec_cik`, `lei`, `authority_id` and their syntax apply; SEC scheme requires authority `sec`. Search explicit supplied authority IDs on entities and securities only; no fallback from an entity key to a claimed authority record. |
| `NameQuery` | `name, mode="exact"`: mode `exact` or `contains`, latter requires at least three folded characters. NFC + casefold + whitespace folding is search-only; no punctuation/suffix stripping, NFKC, fuzzy score or identity verification. Current legal name and supplied historical names both search. This query is undated; historical name intervals are retained without asserting current validity. |

`IdentityInventory(entities, securities=(), listings=(), names=())` uses C1
`EntityRef`, `SecurityRef`, `ListingRef`, `AuthorityIdentifier`, `SymbolAlias`,
`KeyRef` and `DateInterval`. `NameAlias(entity_key, name, evidence_key, effective)`
adds a bounded historical/search label with a C1 artifact/authority evidence key.
No synthetic CIK, company ID, financial value, registry ID or evidence is minted.
Exact inventory key duplicates reject, whether metadata agrees or conflicts;
duplicate entity/folded-name/effective name entries reject rather than choosing
an evidence reference. Distinct keys always remain distinct, even when names,
classes or authority IDs coincide. A consistent same-namespace substitution is
not detectable as false real-world metadata by this pure kernel and remains
unverified; namespace, CIK and explicit chain contradictions do reject.

`IdentityCandidate` fields are `entity, security, listing, match_basis,
temporal_state, matched_authorities=(), matched_aliases=(), matched_names=()`.
Issuer/CIK/name hits return an entity; security-authority hits also retain the
security; symbol hits retain the complete listing/security/issuer chain. Match
bases are `canonical_cik`, `dated_symbol_mic_provider_product`,
`exact_authority_identifier`, `name_exact`, `name_contains`. Evidence keys derive
from all authorities/aliases on the returned chain plus matching historical
names; full C1 records preserve each evidence/interval association. Irrelevant
inventory records are not added as candidate evidence. Missing evidence stays
empty, never fabricated. Distinct matching listings of the same security, or
securities of one issuer, remain distinct candidates.

`CandidateResolution(status, candidates, reasons)` has only `unique_candidate`,
`ambiguous`, `unresolved` outcomes. `candidates` retains all scoped matches,
including inactive diagnostics; `possible_candidates` excludes known inactive
records and retains unknown-effective rivals. Consumers must use temporal state
or this property, never select the first sorted diagnostic as the chosen match.
Both result and candidate expose fixed, non-constructor `verification_status =
"unverified"` and `required_verification`. No caller flag can grant authority.

Temporal states: `not_requested`, `in_effect`, `unknown_effective`,
`outside_effective`. Intervals are C1 half-open `[start,end)`, with open end
allowed and null whole interval unknown. Dated symbol matching requires both
listing and alias coverage; known exclusion wins over unknown coverage. Several
disjoint matching aliases on one listing remain one listing candidate with all
matching aliases preserved. Known alias bounds outside known listing bounds
reject as contradictory. Same-symbol/provider/product overlapping or unknown
disjointness within one listing rejects under C1; overlapping claims across
distinct listings survive as competing candidates.

- No possible match: unresolved, reason `no_candidates` or
  `outside_effective_dates`.
- One unknown-effective possible match: unresolved, `unknown_effective_dates`.
- Exactly one supported possible match and no unknown rival: unique candidate,
  `unverified_structural_match`. Undated CIK/authority/name discovery also uses
  this status without claiming real-world or temporal verification.
- Multiple possible matches: ambiguous, `multiple_candidates`; symbol adds
  `competing_listings`, authority adds `competing_authority_claims`. Unknown
  rivals add `unknown_effective_dates`. Name queries add `name_search_only`.
- No auto-merging by ticker, share-class label, name, authority assertion or
  predecessor/successor resemblance. No ranking breaks a tie.

Stable order: candidates sort by exact `(entity namespace,id)`, then optional
security and listing keys (absent sorts first). Inventory root collections sort
by key. Authority tuples sort by scheme/authority/identifier/interval/evidence;
aliases by provider/product/symbol/interval/evidence; name records by entity,
original name/interval/evidence. Unknown interval sorts before known; open end
sorts before a dated end with equal start. Evidence keys sort by namespace/id.
Labels, IDs and intervals are otherwise preserved. Reordering any input
collection or nested authority/alias tuple produces equal results.

## Resource bounds

| Budget | Inclusive cap and accounting |
|---|---|
| Inventory collections | 128 entities, 256 securities, 512 listings, 256 name aliases; exact tuples, checked before traversal. |
| C1 records | Existing per-field, 16 authority IDs, 64 aliases, 65,536 bytes, depth 8 and 2,048 nodes remain enforced through C1 validation. A preliminary bounded walk rejects malformed/forged nested values before encoding. |
| Inventory logical bytes | 1,048,576: sum of canonical C1 root encoding lengths plus compact UTF-8 arrays of each name's entity key, name, evidence key and nullable start/end. All entries counted before accepting inventory. |
| Candidate collection | 128 total matching records, including inactive diagnostics; reject on the 129th rather than return a prefix. |
| Result reference bytes | 1,048,576: sum of each candidate's C1 entity/security/listing encodings and matching name encodings, counting repeated chain references for each candidate. All candidates counted, including inactive. |
| Queries and new labels | C1 widths: CIK 10, symbol/provider/product 64, MIC 4, authority identifier 128 (LEI 20), date 10, names 200 code points / 800 UTF-8 bytes. Contains needs 3 folded characters. |

These are logical metadata/work bounds, not measured RSS, elapsed-time, native
cancellation, full wire-response or production capacity guarantees. There is no
serializer/endpoint here. Input already exists in caller memory; the kernel
accepts no parser stream, file path or iterator. Overflow never yields partial
success. Tests cover inclusive/one-under byte budgets via temporary in-process
policy patching plus reachable overflows at actual fixed caps.

## Future authority adapter seam and remaining trust boundary

A separately reviewed server adapter can acquire permitted original SEC/issuer/
exchange/regulator records, validate original source identity and exact issuer
CIK (without accession-prefix substitution), capture original-byte provenance,
revision, retrieval/public-availability precision, effective dates and
operation-specific rights, and supply these immutable references. It can use
candidate evidence references as lookup inputs, not as admission decisions.
Conflicts and unknown dates require official corroboration or abstention. A
server-owned authority admission mechanism must independently bind the source,
issuer/security/listing chain, owner/operation and rights before any verified
resolution. Supplying keys, scheme `sec_cik`, syntactically valid LEI/MIC,
calendar labels, hashes or a unique hit cannot satisfy that gate. The kernel has
no verification flag, trust override, network client, ID generator or adapter
activation. No direct conversion to C1 resolved status is provided.

## Discovered issues

No baseline mismatch. C1 reference evidence keys contain neither original source
bytes nor proof of provenance/rights; their presence cannot authorize a candidate.
Self-review found that output-only frozen dataclasses also needed constructor
checks against mutable collections and invalid status/chain values. Added closed
candidate/result validation and direct-construction adversarial tests. Result
constructors now enforce count, byte, stable-order and candidate-status coherence
as well as immutable field types; no resolved/trusted status is supported.

## Progress

- [x] 2026-10-29: baseline/contract inspection.
- [x] 2026-10-29: kernel implementation and exact interface/budget record.
- [x] 2026-10-29: focused positive/adversarial/isolation tests and eight mutation controls.
- [x] 2026-10-29: self-review and preservation checks; prepared concise final report.

## Test and validation strategy

Run the dedicated standard-library unittest script with isolated Python, no site
initialization and bytecode writes disabled. Test synthetic issuers, independent
security/listing chains, exact namespace matching, rename/name ambiguity, dates,
duplicates, resource boundaries, immutable output and deterministic ordering.
Use a fresh subprocess with forbidden-effect guards for import and resolution;
use ephemeral in-memory module mutants to prove negative controls can fail.
Do not run operational legacy scripts or access database/application services.

Actual commands/results: initial 45-test run: 43 passed, 2 fixture assertion
failures (wrong expected key order and byte-overflow fixture below actual cap).
Corrected those fixtures; next run 45/45 passed. Additional self-review cases
added one out-of-listing date fixture, correctly rejected by the kernel; fixture
corrected. Final focused run and preservation checks are recorded below.

Final command, repository root `D:\Projects\finlens-foundation`, 2026-10-29:

```powershell
& backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_universal_identity.py
```

**51 tests passed, 0 failures, 0 errors, 0 skips** (2.052 seconds). This includes
48 synthetic behavioral/resource/constructor tests plus three isolation/mutation
tests. No completed C1 or Quant review was repeated and no operational tests ran.

Eight in-memory mutants were killed, each with its unmodified probe passing:
authority-status promotion, unknown-date promotion, ignored MIC, inclusive alias
end date, ignored authority namespace, accepted duplicate key, discarded competing
candidate and raised candidate count cap. Mutants never touched source files.
Rejection by a constructor or failure of the behavioral assertion counts as a
killed mutant; no surviving mutant was accepted as a passing control.

Fresh-process import/resolution passed with prohibited app/provider/database/
model imports guarded, environment reads disabled, filesystem mutations/network/
subprocess effects guarded, source-only import reads allowed and all file opens
disabled after import. Static AST confirms only dataclasses/json/re/unicodedata/
typing and C1 imports. This is evidence about this module's exercised path, not
an OS sandbox or real-source/runtime acceptance.

Whitespace checks ran using `git diff --check` plus
`git diff --no-index --check -- NUL <each-new-file>` for all three additions,
because ordinary Git diff excludes untracked additions. All passed; Git emitted
only normal Windows LF-to-CRLF notices. HEAD/main/index and all three protected
hashes were rechecked unchanged; tracked diff names contain only the pre-existing
`frontend/next-env.d.ts`. Final status is precisely the three additions plus the
three historical exceptions. No staging, commit or push was performed.

## Completion criteria

Only three allowed additions; positive/adversarial/isolation/mutation checks pass;
no authority grant, discarded competitor, invalid accepted chain or truncated
success; documented budgets and future adapter seam; HEAD/index and protected
files unchanged. Independent Astra High review is a subsequent gate.

## Final outcome

Implementation complete: pure bounded CIK, dated symbol/MIC/provider/product,
authority-triple and name candidate matching, with preserved competing records,
evidence, temporal diagnostics and fixed unverified semantics. Local verdict:
**GO for independent Astra High review of these three files only**. This is not
independent approval, U1 completion, registry authority, activation or deployment.

Remaining U1: reviewed official-source
registry/admission and real authority acceptance. U2 acquisition/policy/worker,
U3 fact admission/calculation bridge, U4 session workflow without insertion,
U5 actual local generation and U6 end-to-end negative/runtime acceptance remain.
C2 source identity/admission, C3 provenance/version/vintage, C4 bundle/receipt,
C5 financial bridge, C6 generation/claim support, C7 ownership, C8 jobs/events
and C9 resource/cancellation/rights acceptance remain separately scoped blockers.
No source authenticity, evidence ownership, listing authority or usage rights
were verified. No live SEC/provider/database/API/browser/model acceptance ran.
Suggested commit (not executed): `feat(identity): add pure universal issuer candidate kernel`.
