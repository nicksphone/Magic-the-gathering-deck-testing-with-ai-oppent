# AI performance implementation plan

**Goal.** Increase verified games per worker-hour while preserving the existing
Master policy and the evidence produced by replay and handler checks.

Implementation starts after strength rerun2 finishes. Use the first-run
aggregates below as the reference evidence, then freeze a new benchmark on
the implementation base. Performance diagnostics and interactive latency
never count as strength results.

## What the profiles show

| Cost | First-run evidence | Implication |
| --- | --- | --- |
| AI decisions | 200.9 CPU s per scheduled cell across 648 cells. Gameplay CPU stops averaged 1,802.9 s in AI alone. | The largest opportunity in gameplay-limited cells is inside search. |
| State copies | 4,057 state copies across four timed-out decision peaks. A separate bounded cycle decision spent 38.8% of its CPU copying. | Reduce the cost of each fork and the number of forks. |
| Simulated actions and rules queries | The same four peaks made 6,304 engine action calls, 12,609 trigger collections, 3,162 payment-planner calls and 693 legal-move calls. | Check which work repeats on identical inputs before adding caches. Function counts and inclusive times overlap. |
| Snapshot and restore | 191.1 CPU s per scheduled cell. Cells that reached the CPU cap during verification averaged about 900 s in snapshot and restore across both phases. | Reduce object copying, encoding and restoration while preserving the independent verifier. |
| Trace writing | 0.16 CPU s per scheduled cell for encoding, flush and sync. Two cells stopped on the separate byte quota. | Smaller files can address quota pressure. CPU work lies principally in state capture and verification. |
| Decision latency | Mean of the per-cell maximum recorded Master decision wall times was 39.92 s across 19 unresolved cells and 11.04 s across eight resolved samples. | Measure tail latency separately from the typical decision and from game throughput. |

The first-run aggregate includes partial counters for unresolved cells. The
cycle breakdown is one bounded profile. The last targeted patch improved
four uninstrumented timeout peaks by 6.3% with matching recorded actions.
Use these measurements to size experiments, with new process-CPU and
wall-clock measurements for each landed change.
[First-run profiles](archetype-strength-prereg-rerun2.md)
[Cycle and cache-cost measurements](python-native-performance-spike-20261117.md)

## Ranked work and implementation order

The gains below are hypotheses or conditional estimates. Each change should
land independently with its own behavior and performance checks. Measure
the combined path again after each change because the gains overlap.

### 0. Establish the comparison first

- [ ] Freeze a benchmark manifest before edits, with a base revision,
  hash-locked runtime, host affinity and worker count. Use the existing 20
  recorded positions as a development set. Hold back independent positions
  from completed and censored games across seats and decks. Include
  simultaneous deaths, stack responses, hidden choices, paid activations and
  dense boards. Compare unchanged code on both sides first to quantify timing
  variance and reproduce the recorded complete actions.
- [ ] Instrument non-overlapping process CPU for decision calls, state forks,
  legal offers, simulated transitions and the rest of search. Separately
  count trigger and mana work inside transitions without adding it twice.
  Measure production-side checked transitions separately from game-phase
  capture, verification replay, restore, selected handler/SQLite checks and
  trace encoding/I/O. Collect allocation peaks, p50/p95/p99 decision latency,
  timeout counts, verified completions per wall-hour and charged worker-hours.
  Run timing trials without a function profiler, alternate A/B order and use
  the same host conditions.
- [ ] Build a bounded comparison at the seams in
  `backend/scripts/archetype_game_v3.py` and
  `backend/scripts/archetype_worker_v3.py`. Freeze before-state, ordered card
  IDs, RNG and offered actions from approved archived traces. Compare complete
  action payloads, including targets and payments, and exact post-action
  snapshots. For saved sequences, check each available recorded action and
  report the first divergence. Report aggregates only. Report completed-game
  benchmarks separately from censored-prefix benchmarks.

### 1. Replace speculative deep copies with isolated forks

**Priority and expected gain.** Start in `backend/game_state/copying.py` and
the `planning_copy` callers in `backend/ai/pending_effects.py`. Existing code
already shares immutable atoms and drops diagnostic history for planning.
Separate immutable printed definitions from mutable gameplay state, then add
copy-on-write or structurally shared containers only for the speculative
paths that the tests can prove. Audit callers that make a second complete
copy of an already detached branch. On the cycle profile, speeding up copy
work 2–5× would improve the whole decision about **1.24–1.45×** on its own.
Copy work becoming free would cap that sample at about 1.63×.

**Behavior risk.** High. A write visible across siblings, a reordered card
map, or a changed alias can alter triggers, decisions and replay. Public
checked actions still need atomic rollback. Keep the existing copy path for
unsupported shapes and custom copy protocols.

- [ ] Prove parent and sibling isolation for taps, counters, zones, nested
  payloads, RNG, references and logs. Cover ordered simultaneous deaths,
  old snapshots and registered copy hooks using
  `test_ai_selective_copy.py`, `test_root_metadata_copy_contract.py`,
  `test_root_copy_registered_set_protocol.py` and `test_archetype_game_v3.py`.
- [ ] Migrate one speculative path at a time. Compare action payloads and
  state bytes with the old implementation. Require a measured CPU gain and
  report peak memory before expanding to more paths.

### 2. Reuse exact search work, then optimize the rules work that remains

**Priority and expected gain.** Use decision-local caching in
`backend/ai/agent.py` and `backend/ai/pending_effects.py`. Start with pure
legal-move or evaluation queries. Try transpositions for identical state,
action and search context only after forks provide cheap, immutable
identities. One audit found 31.1% candidate repeats in legal queries and
45.7% in simulated actions. With equal costs and free keys, the illustrative
whole-choice gain was **1.28×**. Full-state keys alone took 11.54 s in a
6.19 s baseline choice. Profile the actual hit rate and key cost before
retaining any cache. For residual rules work, start with read-only batching
or indexed candidates in trigger collection and mana planning, and measure
those paths independently.

**Behavior risk.** High for transpositions, lower for well-scoped pure
queries. A key needs state version and order, RNG, acting seat, visibility,
projection/choice context, search depth and policy wherever they affect the
result. Reuse must preserve expansion-budget charges, tie-breaking, choice
callbacks and exception behavior. Cache results must not share writable
state or private information with unrelated branches.

- [ ] Measure existing `reuse_position_score` key costs and hit rates.
  Prove that changed hidden information, card order, paid costs, pending
  choices and search budgets cannot collide at the chosen boundary.
- [ ] Start with exact, bounded caches that drop at decision exit. Test
  changes on the same object, nested decisions, cache expiry and independent
  writable results. Keep transition reuse gated until visible side effects
  and search-work accounting match the uncached path.
- [ ] For triggers, mana and legal moves, assert ordered offers, the same
  trigger multiplicity and APNAP order, and the same selected payment
  sources and costs across mutation boundaries. Use
  `test_ai_exact_score_reuse.py`, `test_ai_read_query_boundaries.py`,
  `test_ai_search_prefix.py`, `test_variable_mana.py`, and the exact replay
  and parity suites. Require net CPU savings after charging key creation and
  result isolation.

### 3. Make exact harness verification cheaper

**Priority and expected gain.** Prototype after the fork representation
stabilizes. Target `capture` and `replay_trace` in
`backend/scripts/archetype_game_v3.py`, using the existing serializer
contract in `backend/game_state/serializers.py`. Reuse canonical encodings of
proven-unchanged immutable subtrees and remove avoidable payload copies.
Explore a fast decoder only if it preserves the independent restore of
complete state. Aim first for a **2–3× reduction in snapshot/restore CPU**
on the paired benchmark, a hypothesis equivalent to roughly 96–127 s saved
at the old 191 s average. That alone falls short of the final overhead target.

**Behavior and evidence risk.** High. A serializer bug or a cache shared
between generator and verifier can hide divergence. Preserve independent
legality, transition and restart on every action, full canonical state and
RNG digests, card order, log deltas, chain verification, initial/final
snapshots, and selected handler/SQLite parity. Keep existing trace readers
and reject incompatible formats explicitly.

- [ ] Match canonical bytes from the reference on the sampled snapshots.
  Check decoded graph isolation and preserve the exact first divergence on
  corrupted checkpoint and non-checkpoint actions, card reorder, RNG
  drift, and illegal actions.
- [ ] In `test_archetype_game_v3.py` and `test_archetype_worker_v3.py`,
  require one independent restore per accepted action and every selected
  handler parity boundary, including ones with no stored checkpoint.
  Compare old/new replay outcomes, restart counts and selected handler
  results on an archived trace. Report the full verification cost,
  including the verifier's engine and SQLite work.

### 4. Bound interactive decision latency with an explicit policy

**Expected gain.** Reduce user-visible tail latency. For the first
interactive experiment use a **1 s p95 and 2 s p99** per decision on the
reference host, reporting how often the normal search finishes within the
budget. This is an interactive target and contributes zero to the exact
Master speedup claim.

**Behavior risk.** Deliberate when the budget is exhausted. Preserve stable
candidate order and use a deterministic node allowance. An optional wall
deadline protects responsiveness and can vary by host. It may return only
a fully checked action from completed search work, using a checked fallback
if necessary. Charge work inside expensive branches and reserve time for
validation. An outer timeout around a single long leaf does not bound
latency. A budget stop must leave the authoritative state and revision clean.

- [ ] Add the policy at the interactive autoplay boundary in
  `backend/main.py`, through the existing agent budget seams in
  `backend/ai/agent.py` and `backend/ai/pending_effects.py`. Keep it opt-in
  with its own policy identity and duration/node telemetry. Keep the
  strength runner on the uncapped-by-interactive-policy path.
- [ ] Test artificial deadline and node exhaustion before and during
  search, invalid candidate fallback, legality, input/RNG mutation and
  idempotent revision handling. Start with
  `test_ai_search_budget.py` and `test_ai_combat_expansion_budget.py`.
  Require identical decisions below budget. Separately report action
  differences and quality results at the limit before any default changes.

## Release measurements

- **Exact Master CPU target:** at least **5×** on the matched portfolio, or
  about **40 CPU s/cell** from the first run's 200.9 s reference. Report on
  the held-out and long-game strata as well as the aggregate. A 5× target
  requires removing roughly 80% of AI time. The copy and repeat estimates
  above do not establish that result.
- **Harness target:** **≤25% of total worker CPU** on the same verified
  workload. Count game-phase evidence capture and trace work, plus all
  verification-only replay, restore and handler/SQLite work. If core game
  CPU falls to 70 s/cell, the harness allowance is about 23 s/cell. Report
  both seconds and fractions so an apparent gain cannot come from a larger
  denominator or fewer verified cells.
- **Throughput target:** at least **30 verified games per wall-hour** on
  the reference two-slot host, with the same resource limits and
  verification coverage for the paired measurement. Report unresolved
  cells, whole-cell CPU, charged hours and p95/p99 latency alongside it.
  Incomplete runs produce separate diagnostics. They cannot satisfy the
  verified throughput target by dropping slow games.

Before landing a behavior-preserving change, require identical decisions on
the sampled archived inputs, the AI suites, and green replay, handler/SQLite
parity, health, strength harness and source-pin/interface-scope tests. Run
both plain and `-B` forms for touched tests. Keep the reference path available
for A/B and rollback. A changed decision blocks the exact-equivalence claim
until explained and reviewed. Any subsequent strength experiment needs its
own pre-registration and result.
