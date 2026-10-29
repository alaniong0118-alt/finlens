# FL-UCR-01B1 — Offline SEC Submissions identity source

Status: active for focused Astra High P2 re-review; correction and local validation complete.
Roadmap phase: scoped U1 enabling task; no U2 acquisition or authority admission.

## Objective

Parse immutable supplied SEC-shaped JSON bytes into bounded, structurally valid,
unverified registrant metadata and an issuer-only UCR-01A candidate inventory.
No database row, trusted resolution, listing identity or authority record is made.

## Current architecture and context

Read root AGENTS, `.agent/PLANS.md`, ROADMAP, engineering standards,
[U1-U6](../../full-feature-requirements.md#universal-company-research-u1-u6),
[C1-C3/C8-C9](../../shared-research-contracts.md), source policy, C1 values,
UCR-01A and SEC client source (read only, never imported).
Starting main HEAD: `f17dabf45447cb5dbca4e606b2c425bbc16dbbfa`; index empty.
Only the three historical protected exceptions existed:

| Path | SHA-256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

## Constraints

Original scope created exactly this plan, `backend/app/sec_identity_source.py` and
`backend/tests/test_sec_identity_source.py`. P2 edits only those three existing
untracked candidate files. No other file edits; no private
environment access, network, database, service, provider/model, persistence,
staging, commit or push. Synthetic bytes only. No subagents requested.

## Non-goals

Source acquisition, authentication, redirects, custody receipts, server authority
registry/admission, effective-date acceptance, rights and operational integration.
The SEC [API description](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
is the response-family reference, not an acquisition receipt or a field-complete
schema. Per instruction it was not fetched; no examples were fetched. Explicit
field/type policies below are conservative adapter assumptions for review.

## Implementation stages

1. Verify preservation and inspect owning contracts (done).
2. Implement bounded decoding, metadata validation and issuer-only bridge.
3. Author positive, negative, exact-limit and mutation controls plus isolation.
4. Run focused isolated suite, in-memory syntax and scoped whitespace checks.
5. Self-review and record final status; stop for independent review.

Recovery: only three new files; existing data/runtime state is never changed.

## Decisions

- 2026-10-29: SEC response CIK is decimal **text**, explicitly normalized through
  C1's text factory; expected CIK must already be canonical. No int/bool/float
  coercion. The existing operational client's permissive `str()` is not reused.
- Preserve former-name raw date text but never map it to half-open C1 effective
  intervals: boundary semantics and precise legal effectiveness are unproven.
- Pair ticker/exchange arrays by index as source hints only, require equal lengths,
  reject duplicate pairs; a ticker may occur on multiple exchanges. No MIC mapping.
- Keep fixed source-family and parser-revision labels, computed original-byte
  SHA-256, original immutable bytes and unknown public/retrieval/revision metadata.
  No caller-supplied source label, digest, URL or acquisition assertion is accepted.
- Bridge takes an explicit untrusted artifact KeyRef, never an authority record;
  it grants no evidence authenticity or rights. Former-name search aliases use
  unknown effective intervals and retain raw dates in the source result.
- 2026-10-29 P2: replace the lossy bare-inventory bridge return with a frozen
  `SourceBoundIdentityInventory`. Preserve issuer provenance independently of
  aliases and match basis; expose checked lookup scoped to that source envelope.
- Retain the plan at the exact authorized active path for independent review.

## Discovered issues

Independent Astra 6 High review returned FAIL / NO-GO for Git Step 1 with one P2:
the bare inventory retained artifact keys only on former-name aliases. CIK and
current-name matches could not trace issuer metadata to the supplied source.
Reproduced before P2 edits using `Review Issuer`, no `formerNames`, raw bytes
and raw bytes plus one space, artifact keys A/B: digests differed, inventories
compared equal and CIK candidate `evidence_keys` was empty. This supersedes the
original local GO below; independent approval has not been obtained.

P2 approach: replace the lossy default bridge result with one frozen, slotted
source-bound inventory envelope, explicit issuer/artifact keys, exact original
bytes, computed digest and expected CIK. Provide an explicit issuer-checked
candidate-to-binding lookup without changing C1/UCR-01A. Keep all associations
untrusted. Only these same three candidate paths may change; main/HEAD/index and
all three protected hashes were rechecked and match the original baseline.

No live source field schema or transport behavior is verified. The first focused
run had 27 passing tests and one failed test-helper assertion: the helper treated
explicit `None` as an omitted fixture. Replaced that default with a sentinel;
production code required no change. Added four further boundary/negative tests.

## Supported input and parsing policy

Public entries:
`parse_sec_submissions(original_bytes, *, expected_cik) -> SecIdentitySource` and
`to_identity_inventory(source, *, untrusted_evidence_key) -> SourceBoundIdentityInventory`.
Parsed source carriers must come through parser/bridge validation; no data carrier
constructor confers trust. The bridge reparses original bytes and
rejects any contradictory carrier field before emitting a source-bound result;
the envelope additionally validates direct construction and candidate lookup.

| Input | Exact supported behavior |
|---|---|
| Original response | Exact immutable `bytes`, strict UTF-8, no BOM, one complete object, no trailing content except JSON whitespace. Reject duplicate keys anywhere, including escape-equivalent keys; validate the whole tree before returning metadata. |
| `expected_cik` | Explicit canonical nonzero ten-ASCII-digit C1 text, never padded implicitly. |
| `cik` | Mandatory decimal string, 1..10 ASCII digits, nonzero, normalized by explicit `canonical_sec_cik`, must equal expected. Integers, booleans, floats, containers, whitespace and non-ASCII digits reject. No accession/parent/predecessor inference. |
| `name` | Mandatory current SEC-reported registrant name, exact nonempty text up to 200 characters/800 UTF-8 bytes, no stripping, truncation or authority implication. Used as unverified C1 `EntityRef.legal_name`; jurisdiction stays unknown. |
| `formerNames` | Optional array, at most 64 objects with mandatory `name` and optional `from`/`to` only. Names use the same 200-character policy. NFC/case/whitespace-folded duplicates reject even if dates differ, because the undated bridge cannot represent competing intervals without losing information. Current-name equality alone does not assert a succession or conflict. |
| Former `from`/`to` | Missing/null means unknown. Non-null must be valid `YYYY-MM-DD` or C1 RFC3339 aware instant (up to six fractional digits, max 32 characters). Preserve original date text, including timestamp spelling, without converting it into an effective interval. Reject known reversed order; mixed precision compares calendar dates only and leaves same-day ordering unknown. Same-date bounds are retained, not treated as an empty half-open interval. |
| `tickers`, `exchanges` | Both absent or both equal-length arrays, at most 64 pairs. Empty arrays accepted. Index pairing is an explicit conservative adapter assumption, **not verified listing linkage**. Tickers are exact ASCII `[A-Za-z0-9][A-Za-z0-9._:/+-]{0,63}`; exchange names are exact nonempty text up to 200 characters. Duplicate exact pairs reject; same ticker on distinct exchanges and several tickers on one exchange are retained. No MIC inference even when exchange text happens to look like a MIC. |
| Other root fields | Only `entityType`, `sic`, `sicDescription`, `ownerOrg`, `insiderTransactionForOwnerExists`, `insiderTransactionForIssuerExists`, `ein`, `description`, `website`, `investorWebsite`, `category`, `fiscalYearEnd`, `stateOfIncorporation`, `stateOfIncorporationDescription`, `addresses`, `phone`, `flags`, `filings` are additionally recognized. They receive complete JSON syntax/Unicode/resource checks only; their SEC-specific shapes, financial content and filing associations are **not semantically supported or admitted**. Original bytes retain them. They cannot override CIK, name, jurisdiction or source authority. Unknown root fields reject rather than silently discard identity/provenance claims. |

All decoded keys/strings reject control characters, unpaired surrogates and bidi
override/isolate characters. JSON booleans/null are allowed in unselected fields;
JSON numbers are restricted to nonnegative integer tokens of at most 16 digits
and at most C1 `MAX_PIN` (9007199254740991). Negative, fractional, exponent,
nonfinite and oversized numbers reject globally. This is a deliberately narrow
offline policy, not a general-purpose JSON decoder or complete SEC validator.

### Limits and trust boundary

Inclusive limits: 4,194,304 original UTF-8 bytes, 16 nested containers (root counts
as one), 100,000 tree nodes including object keys, 16,384 decoded characters per
generic key/string, 64 former names and 64 ticker/exchange pairs. UTF-8 decoded
character count cannot exceed input byte count. Counts are charged before
retention; strings are decoded by stdlib `scanstring` under the original-byte cap,
then checked before tree insertion. No unbounded `json.loads`, float construction,
silent truncation or partial successful return. These are logical input/work
bounds, not measured peak RSS or process-deadline guarantees. The 4 MiB/node caps
allow incidental filing metadata while bounding work; this task establishes no
real-response coverage or entitlement to enlarge them. The smaller identity
limits fit comfortably within existing UCR-01A budgets.

Result retains original bytes, computed SHA-256, expected CIK, fixed family label
`sec.submissions.registrant_metadata`, parser revision `fl-ucr-01b1.v1`, immutable
C1 entity, former-name metadata and separately labelled ticker/exchange hints.
`verification_status` is always `unverified`; source revision, public availability
and retrieval time remain unknown. The fixed source-family label describes the
format, not authenticated acquisition. A hash establishes byte integrity only.

The bridge requires an explicit structurally validated C1 **artifact** KeyRef.
That caller-supplied label remains untrusted and unresolved; it is not a custody
receipt or admission record. P2 retains it on the issuer binding for every match
basis, as well as on former-name aliases. Current-name/CIK candidates retain
their unchanged UCR-01A fields; consumers use the explicit binding lookup below.
No `AuthorityIdentifier`, `SecurityRef`, `ListingRef`, `SymbolAlias`, MIC,
effective interval, trusted C1 `IdentityResolution` or local DB ID is generated.
Ticker/exchange hints deliberately do not enter the issuer-only inventory.
UCR-01A may return `unique_candidate`; it still requires all original verification.

Failures use `SecIdentitySourceError.code` and payload-free identical message.
Stable code families cover bytes/UTF-8/BOM/syntax/duplicates/scalars/tree limits,
root/mandatory/CIK/name/date/association conflicts, forged source carriers and
untrusted evidence labels. Error objects contain no partial source result.

### P2 source-binding representation and lookup

`SourceBoundIdentityInventory` is a frozen, slotted exact dataclass with six
instance fields:

| Field | Binding semantics |
|---|---|
| `inventory` | Existing UCR-01A issuer-only inventory, reconstructed from the original bytes and supplied artifact key; no securities/listings/authority IDs. |
| `issuer_key` | Explicit C1 SEC CIK KeyRef, revalidated and required to equal the parsed registrant and inventory entity. |
| `untrusted_artifact_key` | Explicit caller-supplied C1 artifact KeyRef, structurally checked and detached. Its spelling has no official authentication meaning. |
| `original_bytes` | Exact immutable input bytes retained without reserialization or whitespace loss. |
| `response_sha256` | Computed original-byte digest, checked against reparsing; no caller hash can override it. |
| `expected_cik` | Explicit canonical expected CIK, checked against the original response at every binding validation. |

Fixed class metadata is only the already supported source-family label, parser
revision and `verification_status="unverified"`. Source revision/availability
remain unknown under the existing source-carrier policy; no new timestamps or
admission markers are introduced. Generic metadata/date/hint behavior is unchanged.

Consumer path (all three issuer match bases use the same API):

```python
bound = s.to_identity_inventory(parsed, untrusted_evidence_key=artifact_key)
result = u.resolve_candidates(u.CikQuery(bound.expected_cik), bound.inventory)
binding = bound.source_binding_for(result.candidates[0])
# binding.issuer_key / untrusted_artifact_key / original_bytes / response_sha256
```

Use `NameQuery(current_name)` or `NameQuery(former_name)` in the same path. No
current-name alias is invented. Do not infer issuer provenance from
`IdentityCandidate.evidence_keys` or `NameAlias.evidence_key`: CIK/current-name
evidence tuples can legitimately stay empty while the envelope retains binding.

Construction reparses originals, checks expected CIK/digest/issuer, revalidates the
bounded supplied inventory, requires exact agreement with the derived inventory,
and detaches nested references. `source_binding_for` revalidates the envelope,
requires an exact UCR-01A issuer candidate with identical full entity metadata,
issuer-only CIK/name match shape and matched-name records belonging to this
source's inventory. Unrelated issuers, contradictory entity metadata, foreign
alias evidence, mutable collections and forged envelope metadata reject with
payload-free stable codes. The result is a validated source envelope, not trust.

The lookup means **this source supports the same supplied issuer metadata**.
Multiple artifacts may support an identical bare candidate; lookup does not prove
exclusive origin, an authenticated artifact-key-to-byte custody mapping, or that
the candidate was produced in a particular invocation. Same issuer/different
source artifacts remain separate envelope values. A well-formed caller relabeling
artifact A to B is a new untrusted claim, not detectable authentication forgery.
Malformed keys and authority namespaces reject; official-looking artifact labels
remain unverified. Self-consistent wholly replaced external bytes remain untrusted.

Intentional compatibility change: `to_identity_inventory` now returns this
envelope, and UCR-01A requires explicit `.inventory` extraction. No lossy public
bridge remains as the default, no proxy hides the new return type, and only the
existing UCR-01B1 tests are adapted. C1/UCR-01A code and contracts are unchanged.

The bridge parses twice (carrier validation and envelope validation), and each
candidate lookup reparses once; every pass retains the existing finite limits.
The envelope shares immutable original bytes and does not reserialize them. The
existing 4 MiB cap bounds scanstring temporary allocation **before** the decoded
16,384-character guard, not a tight per-string allocation cap; the decoded tree
is bounded logically, not by measured RSS. No process deadline or operational
resource admission is established. Real SEC CIK/date/optional-field conventions,
the root allowlist and index-aligned ticker/exchange assumption still require
real-response compatibility review; this P2 makes no claim to solve those gates.

## Progress

- [x] Baseline matches all requested preservation gates.
- [x] Parser, output and bridge implemented.
- [x] Focused tests and mutation/isolation controls pass.
- [x] Self-review completed; final preservation checks recorded below.
- [x] P2 reproduction, issuer binding, candidate lookup and corrective tests complete.

## Test and validation strategy

Run only the new stdlib unittest file with isolated `-I -S -B`; no completed C1,
UCR-01A, Quant or Reader suite reruns. Compile source in memory without pyc files.
Use `git diff --no-index --check` for the three additions; ordinary diff excludes
untracked files. Record exact commands and observed counts below after execution.

### Checks actually run

Working directory for all commands: `D:\Projects\finlens-foundation`.

```powershell
.\backend\.venv\Scripts\python.exe -I -S -B backend/tests/test_sec_identity_source.py
```

Original pre-review focused result: **32 tests passed, 0 failed, 0 skipped**, including 12
in-memory mutation subcases (12/12 killed; unmodified probes pass first) and one
fresh isolated subprocess. Tests use authored synthetic bytes only. C1/UCR-01A
are called as direct bridge dependencies; their completed suites are not rerun.

Mutation controls: CIK mismatch bypass, numeric CIK coercion, duplicate-key
acceptance, unequal-array truncation, forged origin acceptance, invalid-date
acceptance, byte-cap bypass, depth-cap bypass, verification promotion, digest
substitution, invented effective interval and bridge-conflict bypass. Each mutant
is compiled in memory and is caught by its behavioral assertion, not merely by
a syntax/import failure. No disk production mutation is performed.

The subprocess blocks operational imports (config, SEC client, DB/models, HTTP,
FastAPI, LLM/model libraries), environment reads/writes, sockets, subprocesses and
non-source I/O during import. After import it denies all file opens, then parses,
bridges and resolves a synthetic uncatalogued CIK. Source-module reads during
Python import are the only permitted file reads. No actual local database was
queried to prove absence; the test proves independence from any catalog row.

```powershell
.\backend\.venv\Scripts\python.exe -I -S -B -c 'from pathlib import Path; paths = [Path("backend/app/sec_identity_source.py"), Path("backend/tests/test_sec_identity_source.py")]; [compile(p.read_bytes(), str(p), "exec") for p in paths]; print("2 syntax checks passed")'
git diff --no-index --check -- NUL backend/app/sec_identity_source.py
git diff --no-index --check -- NUL backend/tests/test_sec_identity_source.py
git diff --no-index --check -- NUL docs/exec-plans/active/2026-10-29-fl-ucr-01b1-sec-identity-source.md
```

Both syntax checks passed; all three scoped whitespace checks had no whitespace
diagnostics (`--no-index` returned 1 for each new-file difference, as expected).
Repeating with `-c core.safecrlf=false -c core.autocrlf=false` produced empty
diagnostics for each path; default Git emitted only LF-to-CRLF notices.
No pyc, report, dependency or extra
artifact was created. Exact/one-over tests exercise bytes, nodes, depth, generic
strings, name lengths, ticker/exchange lengths and both identity collections.

### P2 correction verification (2026-10-29)

The command above was rerun after the correction: **44 tests passed, 0 failed,
0 skipped**, including **15/15 in-memory mutation controls killed** and the
updated isolated subprocess. Twelve focused provenance tests cover absent/empty
former names, CIK/current/former/contains matches, original-byte and artifact-key
distinctions, issuer/alias mismatch rejection, forged digest/CIK/inventory/key
metadata, parsed-carrier byte tampering, constructor-bypassed values, immutable
detached references and the explicit envelope-return compatibility boundary.
Existing former-name/date/ticker/exchange/resource tests remain in the same run.

Three additional mutation controls remove the envelope return, bypass the
candidate issuer comparison and ignore binding digest equality. The first is
killed specifically by `issuer source binding lost for CIK without formerNames`;
the harness checks that intended provenance assertion text, avoiding an unrelated
failure being mistaken for coverage. Original controls are adapted only for the
explicit `.inventory` extraction and still run against the unmodified module
before the mutant. All mutations execute in memory without production edits.

The isolation subprocess now resolves CIK, current-name and former-name matches
and invokes the source-binding lookup under the same denied operational imports,
environment/network/database/process/file effects. Import modules are unchanged;
only `replace` is added from the already used stdlib `dataclasses` module. No SEC
schema, custody, authenticity or operational resource acceptance is claimed.
The final corrected run again passed all 44 tests and 15 mutation controls.
Two in-memory syntax checks passed. Scoped `--no-index --check` for each of the
three candidate paths returned 1 (new-file difference) with empty diagnostics
using the Git configuration overrides recorded above. The standalone corrected
reproduction returned: differing digests, equal normalized inventories, different
source-bound results, artifact A recovered from the CIK candidate lookup and
binding status `unverified`.

## Completion criteria

All requested positive/negative behavior covered, no partial results, limits
tested at/over boundary, mutation controls catch weakened guards, runtime effects
denied, exact file scope and protected hashes retained; independent review pending.

## Final outcome

Original local GO was superseded by Astra FAIL / NO-GO for Git Step 1 due to the
P2 reproduced above. After this correction: GO for **focused Astra High P2
re-review**, with independent disposition pending. This does not authorize Git
Step 1, source activation or complete U1/U2 acceptance. Self-review confirmed
issuer-level byte/artifact traceability for every supported issuer match basis,
mismatch rejection and no authority promotion. Existing modules, metrics and
publication paths untouched. Real-response and allocation qualifications remain
visible above; only the reported provenance-loss P2 was corrected.

Final branch remains `main`, HEAD `f17dabf45447cb5dbca4e606b2c425bbc16dbbfa`,
index empty. Expected worktree: exactly the three new scoped files plus the three
protected historical exceptions above; all three protected hashes unchanged.
Nothing staged, committed or pushed. Suggested future commit:
`fix(identity): preserve untrusted issuer source provenance`.

Outstanding separately authorized work: current official field/type and exchange
association semantics review; authenticated bounded acquisition with host/redirect
and transport policies; original-byte custody/receipt and source-revision binding;
server-owned source/authority registry admission; precise effective-date evidence;
operation-specific rights/retention and owner/session controls; and any security/
listing linkage proof. Only after those gates may another implementation consider
trusted source resolution or integration. No live response, DB, HTTP, browser,
provider/model, service-startup, deployment or complete product acceptance ran.
