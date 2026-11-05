# Optional company comparison chart

Status: active; scratch-only implementation. Roadmap: Research Mode.

## Objective
Plot one selected existing metric across two to four companies in the existing validated annual comparison, preserving selection order and table provenance.

## Constraints and decisions
No network, database, Docker, primary edits, external dependencies or new financial calculations. Exclude unavailable/unverified observations; suppress a shared axis for incompatible dates, units or revenue bases. Preserve warnings and exact data in the existing table. The optional chart is a visual projection, not a ranking.

## Progress and validation
- [x] Inspected AGENTS, roadmap, comparison and validation contracts; captured initial worktree status.
- [x] Implemented optional selected-metric dots, with no additional requests and request-key remount.
- [x] Four offline synthetic projection and mounted tests pass, including narrow scroll markup, keyboard-labelled controls and reset on request-key change.
- [x] Six existing mounted comparison regressions pass against the scratch component and chart. One additional regression could not start its nested Python process (EPERM); it is not counted as passing.
- [x] Scoped TypeScript check passes. Independent review remains pending.

## Implementation notes and limitations
Same-currency/period/basis gating uses existing diagnostics; unknown revenue basis is refused. Values whose decimal representation changes when converted to JavaScript Number, including underflow and overflow, are refused for plotting. Dots are a visual projection and the table remains authoritative for exact values and provenance. Excluded companies retain their original position and appear explicitly in the accompanying list. No browser, real-data, database, network or accessibility-technology acceptance was run. Narrow behavior was checked in jsdom and markup, not a rendered browser viewport. One nested process admission failed with EPERM; no escalation or retry was made.

## Completion criteria
Negative and zero values, mixed units/windows, missing observations and narrow layout checked; independent review and browser/real-data acceptance remain pending.

## Independent review corrections

The chart now suppresses unequal values when the normalized span is at most
1e-8 of the chosen magnitude, avoiding unstable spacing from floating-point
cancellation. This intentionally conservative guard may suppress legitimate
close observations; their exact values remain in the table. Equal values remain
plottable. When the gaps filter is active, a control beside the chart restores
the full evidence table without a request. Five synthetic chart tests, one
existing-harness mounted filter-restoration test and the scoped TypeScript check
pass. This does not establish real-browser or real-data acceptance.
