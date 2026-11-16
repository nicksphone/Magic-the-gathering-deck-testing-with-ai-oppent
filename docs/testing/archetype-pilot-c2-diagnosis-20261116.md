# Pilot c2 diagnosis and proposed next experiment

This report diagnoses `archetype-pilot-20261116-v2-c2` at
`93bd597185557767f4350355cd6608061ed354e8`. It does not change that plan,
accept the matrix, or accept AI strength. Private traces, hands, decision text,
snapshots and profiles are not included here. Only aggregate measurements and
source findings are published. No rules, AI, adapter, source pins or budgets
were changed for this investigation.

## Finding

The games are progressing. They are too expensive for the declared budget;
there is no evidence of a stuck priority loop in these traces. Both repeated
full-state construction and master-AI simulations matter. Writing trace bytes
to disk is a small CPU component in the measured samples. Compressing files
alone will not address the dominant costs or demonstrate that games finish.
The final interrupted operation has no completed after-record; this evidence
cannot exclude a loop within that unrecorded operation.

Claude's host run used a clean source clone and fresh hash-locked environment.
Its 36/36 cells terminated at the CPU limit, with no completed game/replay
verification. The pilot is complete only in scheduling/accounting terms.
It is **not healthy, not matrix acceptance, and not a completed-game timing
forecast**. The reported 65,353-second/319-GB full-matrix projection extrapolates
resource-limited prefixes, not finished games plus verification.

## Original trace measurements

A streaming read of all 36 private traces found:

- **12,228 accepted actions**, 36 initial records, no final records and no
  partial JSON lines. Cell 000 has 293 records: one initial plus **292 actions**.
- **7,985,144,851 bytes**, about 653,021 bytes per accepted action including
  each file's initial record. Every action contains full before/after states.
- Every game started at turn 1 and reached turn **9–16**. There were 89–173
  step changes per cell. Each final approximately 16-MB tail still spans
  **4–11 different turn/step pairs**; there is no stationary tail in this sample.
- Cell 000 reaches turn 11, `declare_blockers`, with life changing from 20/20
  to 16/20. Its last action is indeed seat 2 passing priority. Its last 22
  actions span eight turn/step pairs over two turns, so that line alone does
  not identify a loop.
- The original records contain **wall** decision/transition timers, not CPU
  attribution. Summed decision wall time is 1,591.048 seconds; accepted
  transition wall time is 264.315 seconds; summed cell wall time is
  3,267.669 seconds. The difference also includes snapshots, legality, hashing,
  output, setup and an interrupted final operation. It must not be labelled
  trace CPU or engine CPU.

The 36 original `cell-result.json` CPU fields are null. SIGXCPU and the declared
90-second limit identify why the workers stopped; they do not recover exact
per-category CPU usage. A measured CPU split for each original cell is
therefore **unavailable**. The table below gives exact action counts and the
available wall timers; the following section gives measured CPU splits for
bounded samples of **one cell only**.

| Cell | Accepted actions | Last turn | Step changes | AI wall s | Transition wall s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 000 | 292 | 11 | 116 | 53.577 | 6.661 |
| 001 | 245 | 10 | 100 | 57.726 | 5.435 |
| 002 | 428 | 16 | 173 | 37.429 | 9.292 |
| 003 | 397 | 16 | 167 | 38.578 | 9.247 |
| 004 | 255 | 10 | 102 | 52.238 | 5.157 |
| 005 | 365 | 14 | 146 | 31.323 | 10.550 |
| 006 | 349 | 13 | 141 | 46.968 | 7.179 |
| 007 | 339 | 12 | 130 | 47.351 | 7.254 |
| 008 | 258 | 9 | 99 | 60.801 | 4.810 |
| 009 | 364 | 12 | 130 | 41.290 | 8.709 |
| 010 | 420 | 16 | 167 | 39.289 | 8.402 |
| 011 | 402 | 14 | 146 | 38.104 | 8.609 |
| 012 | 331 | 11 | 113 | 44.252 | 7.371 |
| 013 | 303 | 10 | 109 | 53.075 | 6.014 |
| 014 | 257 | 9 | 89 | 55.385 | 5.527 |
| 015 | 326 | 12 | 123 | 50.930 | 6.173 |
| 016 | 362 | 14 | 149 | 44.828 | 7.462 |
| 017 | 371 | 13 | 137 | 42.861 | 7.748 |
| 018 | 323 | 12 | 124 | 48.128 | 6.624 |
| 019 | 341 | 12 | 126 | 41.014 | 7.171 |
| 020 | 365 | 13 | 138 | 42.243 | 8.028 |
| 021 | 411 | 15 | 163 | 35.734 | 8.999 |
| 022 | 370 | 14 | 144 | 43.186 | 7.915 |
| 023 | 331 | 12 | 122 | 48.009 | 6.845 |
| 024 | 360 | 13 | 133 | 41.893 | 7.866 |
| 025 | 379 | 13 | 140 | 37.830 | 9.016 |
| 026 | 316 | 11 | 117 | 20.600 | 6.351 |
| 027 | 339 | 12 | 128 | 28.310 | 7.364 |
| 028 | 348 | 13 | 135 | 44.115 | 7.601 |
| 029 | 316 | 12 | 126 | 44.555 | 6.658 |
| 030 | 317 | 12 | 125 | 48.066 | 7.071 |
| 031 | 290 | 11 | 112 | 44.394 | 6.493 |
| 032 | 377 | 13 | 142 | 40.892 | 8.453 |
| 033 | 306 | 11 | 115 | 52.997 | 6.055 |
| 034 | 347 | 13 | 135 | 43.135 | 7.326 |
| 035 | 328 | 12 | 124 | 49.941 | 6.879 |

## Bounded cell-000 CPU profile

The diagnostic used a disposable archive of the exact measured revision and
the existing local Python 3.12 application environment, not a newly installed
hash-locked environment. Its timing is not a replacement for the host pilot.
No new pilot or full game was launched. Each diagnostic stopped at its stated
action bound, with one-core affinity, 2-GiB address-space cap, 55-second soft
CPU cap and 75-second alarm. Imports/deck setup precede the reported timed
region. The pilot's policy was passed unchanged to `play_game`; a diagnostic
emit callback stopped the sample rather than returning a game outcome.

Boundary wrappers use `time.process_time()`. They attribute nested calls to
the outer operation: AI includes its simulations/copies/engine calls; engine
columns below cover direct legality/accepted-transition calls outside AI.
Categories do not double count. Residual time includes orchestration, copies
outside these boundaries and timer overhead.

| CPU category | First 128 actions, seconds (%) | Last 16 recorded actions, seconds (%) |
| --- | ---: | ---: |
| Full snapshot construction and JSON normalization | 4.460 (42.91%) | 0.775 (35.14%) |
| State digest encoding/hash | 0.408 (3.92%) | 0.066 (2.99%) |
| Other adapter JSON normalization | 0.004 (0.04%) | 0.002 (0.09%) |
| Output JSON encoding | 0.366 (3.52%) | 0.060 (2.72%) |
| Output write/flush | 0.024 (0.23%) | 0.007 (0.32%) |
| AI decision, inclusive | 3.556 (34.20%) | 0.751 (34.06%) |
| Direct engine legal moves | 0.296 (2.85%) | 0.187 (8.48%) |
| Direct checked transition | 1.161 (11.17%) | 0.309 (14.01%) |
| Residual | 0.121 (1.16%) | 0.048 (2.18%) |
| **Total** | **10.396 CPU / 10.401 wall** | **2.205 CPU / 2.204 wall** |

The first sample reproduced the original initial record and all 128 actions
exactly, excluding the two timing fields. The tail sample restored the first
of the last 16 recorded before-states and created fresh master agents. All 16
actor/action/legal/before/after/knowledge/reasoning records matched the original;
its local step counter is diagnostic, not the original absolute counter.
This agreement does not make fresh-agent tail timing equivalent to a full
uninterrupted game.

A separate function-level `cProfile` of the first 64 actions reproduced that
prefix too. It took 19.175 CPU seconds: profiling millions of Python calls
materially adds overhead, so use the boundary-clock table for proportions.
It identified `deepcopy`, card-snapshot construction and card-field copying
as major hot paths. There were **193 snapshots for 64 actions**: initial plus
three per action (before decision, mutation check after decision, after action).
The 128-action clock sample likewise made 385 snapshots and 256 state digests.
The serializer already copies nested card/deck/observation metadata, and
`snapshot()` then performs an additional JSON encode/decode in `plain()`.
An early cell-000 state was 249,089 compact-JSON bytes; its `cards` field alone
was 222,741 bytes. The duplication is structural, not mainly a growing log.

### Genuine expensive AI decision

Cell 000's slowest recorded decision is action 214, turn 9 draw step,
`cycle_card`: **7.246 wall seconds in the original run**. A bounded one-action
function profile restored that exact before-state, used fresh master agents,
and reproduced the full action/legal/before/after/knowledge/reasoning record.
It took 18.119 instrumented CPU seconds, **17.344 inside AI**. These instrumented
times are not an estimate of unprofiled latency.

The call graph is `choose_action` -> `_strategic_plan_action` ->
`_strategic_line_score` / `_stack_two_ply_value` -> ranked simulations.
That one diagnostic action made 277 `planning_copy` calls, 285
`copy_match_state` calls, 733 `simulation_take_action` calls and 169 engine
`legal_moves` calls. These nested costs overlap and must not be summed.
Trace-output optimization cannot remove this AI search work. No change to
master difficulty or its decisions is proposed as a hidden performance fix.

One boundary-clock diagnostic completed its 128 actions but failed while
formatting an empty `pstats` object. Its CPU totals were not recovered or used.
The corrected diagnostic used a new output filename and generated the table
above. This was a diagnostic reporting defect, not an adapter/game failure.

## Proposed adapter and trace work — not implemented or approved to run

Keep the existing pilot and its timeouts unchanged. There is no demonstrated
incorrect accepted action, replay result or source mutation here requiring an
immediate adapter correctness fix. The problem demonstrated is cost and trace
volume; a revised trace implementation needs equivalence tests before use.

1. **Keep complete-state fidelity, change representation.** Store one initial
   full state plus lossless deltas and periodic full checkpoints, with exact
   canonical full-state hashes before/after every action. Factor repeated
   card/deck metadata only through content-addressed, verified records. Keep
   RNG, actor, all legal moves, complete action, knowledge/reasoning, history,
   pending choices and every state field. A reconstructed state must be
   byte-identical in canonical JSON to the old full snapshot. Missing/null,
   booleans/numbers, array order and field deletion must remain distinct.
2. **Avoid redundant encoding before changing serializers.** Build canonical
   state bytes/hash once per snapshot and reuse them for hashing/output instead
   of normalizing through JSON and encoding the same large tree repeatedly.
   Keep the AI-input-mutation check, checked actions and per-boundary serde
   verification. Do not assume `legal_moves` is pure or reuse a previous state
   without proving equivalence. Do not edit production serializers/copy helpers
   or omit fields just to improve this benchmark. Compression alone addresses
   volume, not the measured snapshot-building/AI costs.
3. **Measure before promising a speedup.** Record process CPU separately for
   setup, direct legality, AI (inclusive), accepted transition, snapshot,
   encoding/hash, write/flush, replay and selected handler checks. Persist small
   progress counters outside the full trace periodically so killed workers
   retain exact completed-action attribution, while marking interrupted
   operations and unattributed residual explicitly. Do not infer CPU from wall
   timers or count a partial operation as completed.
4. **Test the new codec against the existing complete trace contract.** Cover
   round-trip reconstruction of every state field, RNG, log append and deletion,
   card creation/zone changes, nested pending choices, list reordering,
   altered/missing/reordered records, corrupt checkpoints and altered hashes.
   Mutating AI input, one action or one RNG field must still fail at the first
   divergent step. Retain fresh-process replay and separately labelled
   real-handler/SQLite comparisons. Exact action-prefix equality is required;
   no state normalization or sample-based replacement for these checks.
5. **Keep AI search a separate decision.** The heavy cycling decision needs its
   own behavior-preserving performance investigation if the revised adapter
   still exceeds limits. Do not lower difficulty, cut search or raise the
   budget silently. A changed AI policy requires a separately reviewed revision
   and fresh pilot/matrix registration.

## Proposed new registration policy

This is a proposal for Claude's decision, **not a changed c2 plan and not launch
approval**. The current v2 CLI does not support this proposed v3 registration;
no executable v3 command is claimed here.

- Use new pilot ID **`archetype-pilot-20261116-v3-trace1`**, after the final
  adapter/codec revision and source/dependency identities are known. Freeze its
  schema, source hash, trace format, checkpoint interval, instrumentation,
  output quota, seeds and policy before execution. If that ID is already used,
  choose and publish another fresh ID before any worker starts.
- Proposed pilot seeds: **2026112001 and 2026112002**, disjoint from c2 and the
  v2 matrix. Retain the same nine-deck adjacent-pair/both-seat 36-cell schedule
  to expose comparable workloads without splicing old outcomes into it.
- Retain two workers, one core each, 2-GiB address space, **90 CPU / 120 wall
  seconds for the whole game plus verification**, 10,000 actions and 100 turns.
  Propose a **64-MiB per-cell trace cap**, declared in the new plan and enforced
  before excess writes; overflow is an explicit resource-limited cell, never
  truncation, success or silent omission. This proposed cap needs approval.
- Pilot usability target: all 36 game/replay/selected-handler checks complete,
  no crash, invalid accepted action, divergence, missing cell/trace or resource
  limit. It is a prerequisite to a budget decision, not RC/strength acceptance
  or a statistical claim about the full matrix's resource-limit rate.
- Forecast **completed game plus verification** CPU/wall/bytes, including
  checkpoint/delta decode overhead. Report limit-hit cases separately. If any
  hit limits, the completed-game forecast remains censored; do not repeat the
  c2 prefix forecast as expected completion time.
- No resume, retry, reused prefix or mixed revision. Host sleep/crash or lost
  worker identity invalidates the run; preserve it and register a fresh ID.
- A future full-matrix run also gets a new ID, for example
  `archetype-admitted-20261116-v3-trace1`, with a freshly frozen complete plan
  and seeds (proposed **2026112101–2026112120**). Keep the existing health
  thresholds, nine-deck exclusions and AI-strength non-acceptance explicit.
  Do not reinterpret the old 110-series, c2 pilot or incomplete v2 results.

Only this report is committed. Diagnostic source archives, profiler scripts,
stats, generated samples and original pilot outputs remain private and outside
the repository. No new acceptance result is claimed.
