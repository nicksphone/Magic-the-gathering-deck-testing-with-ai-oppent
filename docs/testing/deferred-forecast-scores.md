# Deferred Forecast Scores

## Implementation

The two-ply stack planner previously scored an intermediate position before
evaluating replies, then discarded that score whenever a valid reply existed.
It now scores that position only for terminal/resolved positions, absent replies,
or when all attempted replies fail. All response branches, actor-relative
min/max selection, depth limits and baseline deltas remain unchanged.

This is shared AI code, with no card-specific policy or additional cache.

## Validation

- 1,107 affected checks pass across 18 files in an isolated local source copy.
- Twenty new cases exercise both seats, valid/invalid/absent replies, resolved
  stacks, and real counter/pass forecasts for Control, Tempo and Tribal.
- A frozen eager reference verifies scalar parity; snapshots verify that
  forecasts leave the authoritative position unchanged.
- One retained complete decision preserves the exact action, all 17 legal moves
  and original state: 51.48 seconds versus an archived predecessor measurement
  of 55.64 seconds. This was not a fresh simultaneous baseline or statistical
  latency study. A separate exact forecast-cache probe found zero hits across
  42 calls and was rejected rather than adding an ineffective cache.

Evidence is archived on NFS under the October 5 strategic-draw diagnostics,
`deferred-forecast-scores`. The last full backend/browser integration gate is
still the frozen `91b5dff` runtime; this increment has affected-suite validation.

## Known Limitations And Next Upgrades

Approximately 51 seconds remains unacceptable interactive latency. Further
profiling must preserve response quality and hidden-information boundaries.
This optimization does not improve strategic policy or certify expert play,
arbitrary-card semantics, broader matchup balance or release readiness.
