# Pure-query Planning Latency

Date: 2026-10-04 UTC. Baseline: `6b940516c59bd10832038008e0b7eed098d5a5eb`.
This continues [copy latency](ai-card-copy-latency.md), not a claim of expert AI,
matchup balance, full card support or bounded worst-case decision time.

## Profiling and Implementation

A seeded offline Blue Control/Ramp run (seed 73, Master) captured six slow
decisions across both acting archetypes. The capture stops after 384 decisions;
it is a profiling prefix, not a completed match. Boards have 8-14 permanents.
Canonical rules tests and the previous expensive live BO3 gate motivated this
work, but captured inputs use bundled offline metadata, not the live cache.

The turn-12 Ramp profile makes approximately 22.8 million calls. Repeated
land-type/ability-loss reads and planning clones are major costs. Instrumented
cProfile time is not representative wall-clock latency.

`rules_engine/query_context.py` provides a synchronous, nonmutating query scope.
It retains results only for the exact state object of that scope. Nested queries
on the same state reuse it; different projected states get their own context and
restore the parent afterward. Exceptions and threads do not leak query state.
No cache fields are added to matches, database rows or saved snapshots.

Land views (including no-effect views), effective combat stats, keyword counts,
printed ability-loss sources and AI board values use these scopes. Public legal
move reads, root AI decisions and each projected ranking establish appropriate
boundaries. Entering-card/controller projections bypass ordinary land-view reuse.
Keyword/list results are copied so caller mutation does not corrupt cached results.
Unknown-versus-zero stat flags and player-specific board values have distinct keys.

Do not hold a query scope across `take_action`, effect resolution or any direct
state mutation. Such operations are deliberately not decorated/cached. Later
queries must read fresh counters, source/controller/zone changes and resource state.
Only pure queries with immutable arguments may use the `scoped_query` decorator.

Exact `CardInstance` clones are allocated without generic shallow-copy
reconstruction. Empty standard containers use a direct copy while retaining the
shared deepcopy memo. Nested mutable data, aliases, cycles and custom fields remain
isolated; subclasses/nonstandard objects still use ordinary deepcopy. This is not
copy-on-write sharing of mutable authoritative state.

No beam width, horizon, candidate enumeration, rule result or action quality
threshold is reduced. The existing complexity limits are unchanged. Diagnostics
never cut off a decision merely because it exceeds a time target.

## Acceptance and Remaining Work

- [x] Both-seat layer/counter/flag/container isolation, fresh queries after source
  departure/control changes, nested entry/branch contexts, exceptions and threads.
- [x] Forty-two archetype/difficulty decision comparisons against uncached reads;
  authoritative snapshots, board scores and legal moves remain identical.
- [x] Six captured real-game positions retain chosen actions and legal move sets.
- [x] Full isolated backend/frontend/browser gates and measured snapshot comparison.
- [x] Compare full action traces against the baseline across multiple seat-balanced
  matchups and retain deck/corpus inputs, not merely repeat optimized execution.
- [ ] Wider late-game/token/choice boards, adversarial and multi-action search,
  additional exact-prefix reuse and a measured worst-case latency policy.

Raw profiles, private fixture snapshots, source/input hashes and executable probe
scripts are retained under RCHFiles `diagnostics/planning-latency/20261004-working`.
Private engine snapshots contain hands; do not expose them as public match views
or send them to external services. Active databases and test scratch stay local.

## Final Validation

All 6,685 backend tests pass across four independent source/database shards:
1,692 + 2,246 + 1,337 + 1,410. All 283 test files are assigned exactly once.
Fifty-five new cases plus the 166-case focused selection exercise query lifetimes
and existing layer/copy/latency contracts. Frontend lint, contract/unit tests,
production build and all 41 Chromium scripts pass. Optimized production hashes
match across all four shards, browser and replay copies. Installed dependencies
are reused; this is not a fresh-install release certification.

After other heavy validation jobs completed, three iterations per mode replayed
each captured snapshot using baseline and optimized source in separate processes:

| Position | Archetype / Turn | Baseline Median | Optimized Median | Shorter |
| --- | --- | ---: | ---: | ---: |
| 0 | Ramp / 8 | 0.767838s | 0.618494s | 19.4% |
| 1 | Ramp / 10 | 0.679701s | 0.418768s | 38.4% |
| 2 | Ramp / 12 | 4.188985s | 2.612899s | 37.6% |
| 3 | Ramp / 12 | 3.337217s | 2.130502s | 36.2% |
| 4 | Control / 12 | 1.595098s | 1.198994s | 24.8% |
| 5 | Control / 15 | 0.979313s | 0.530822s | 45.8% |

All 18 paired snapshot iterations preserve actions, legal move payloads, captured
choices and authoritative state. Timings are local measurements, not CI limits or
end-to-end/worst-case guarantees. Three optimized positions still exceed one second.
Exploratory intermediate profiles/benchmarks are retained separately from these
final measurements; profiler instrumentation adds substantial overhead.

Six seat-balanced BO1 samples (seed 4182, Master, 2,400-tick cap) cover Blue
Control/Ramp, Tempo/Tokens and Mono Red Aggro/Dimir Control. Each baseline runs
once; each optimized sample runs twice: 18 executions, not 18 independent games.
Both optimized executions reproduce the entire baseline result, action trace and
normalized log for every sample. Deck metadata inputs match byte-for-byte with
SHA-256 `d7bdac5df2d105ebb440c30978cba98474c9b03ee7bd430efdb3fe2588786c41`.
These are fixed bundled-data comparisons, not a synced-corpus balance matrix.

No sample times out or logs an announcement/cost rejection. One baseline sample
contains a Drown in the Loch resolution-time target invalidation, identically
reproduced in both optimized runs. A broad substring scan initially mislabeled
this as an invalid announcement; both the raw scan and separate validated
resolution/announcement counts are retained. Identical execution does not prove
that this or other strategic choices are optimal.

The slowest full-suite shard takes 498.55 seconds including live Control/Ramp BO3
restart. Its workload/cache history differs from the previous milestone's shards;
do not attribute the entire 1,112.66-to-498.55-second difference to this patch.
The controlled fixed-snapshot comparisons above are the performance evidence.
Later/wider boards, exact-prefix search reuse and a real latency policy remain open.

Initial query-lifetime assertions guessed a fixed number of unscoped reads;
the corrected tests assert reuse within a scope and recomputation after exit.
Initial fixture-server readiness polling failed during startup, then verified the
same process before browser execution. No application error was hidden or fixed
by restarting the test run. Source/live SQLite and the user's untracked plan remain
unchanged except for the intentionally edited tracked project files.
