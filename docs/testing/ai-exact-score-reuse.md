# Exact Strategic Score Reuse

## Implementation

Repeated strategic positions reuse their scalar score within one synchronous,
fixed-profile AI decision. Keys include the complete pickled planning state,
actor and agent identity. This includes RNG, priority, card metadata and opaque
information markers; only diagnostic history already excluded by planning_copy
is omitted. No untrusted pickle is loaded.

The cache stops admitting entries at 256 positions or 16 MiB of encoded keys.
Budget exhaustion and unsupported serialization fall back to ordinary scoring.
Owners remain referenced until the decision ends, preventing identity reuse.
The existing decision context resets even on exceptions. Equivalent positions
with different pickle alias topology may conservatively miss the cache.

Read-only rule queries also share a scope across strategic features and lethal
scans. Those scopes end before departures or later state-based waves; changed
zones and continuous sources are evaluated afresh. No response branches, depth,
card data or deck contents were removed or changed.

## Evidence

- 1,087 affected AI checks pass across 17 files, including private-information
  and planning paths. Earlier 139 cache/planning checks overlap with this total.
- The state-based scan increment passes 1,332 direct-caller checks and 64 initial
  focused checks. Counts overlap and are not one combined full-suite total.
- A retained Tribal decision has 17 legal moves. Its complete chosen action is
  identical before/after and both original states remain unchanged. Baseline
  80.95 seconds; bounded implementation 65.77 seconds in this measurement.
- An exploratory unbounded probe observed 112 duplicate scores in 421 requests.
  It is not the production cache and is not a statistical performance guarantee.
- The full backend/browser integration gate last exercised frozen `91b5dff`;
  these later changes use affected checks, not a fresh full-suite claim.

## Known Limitations And Next Upgrades

One retained decision does not establish general latency or stronger play.
About 66 seconds is still too slow for interactive play. Nested stack forecasts
and repeated ability/layer queries remain the next performance targets. Preserve
exact decisions and hidden-information boundaries while reducing repeated work.
