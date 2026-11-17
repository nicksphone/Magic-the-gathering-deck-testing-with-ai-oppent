# V3 trace2 pilot result — 2026-11-16

**Accounting complete; pilot unusable.** The operator confirmed termination
before authorizing this read-only review. `PILOT-COMPLETE.json` accounts for
36/36 cells: **35 resolved, one CPU-limit timeout**, with `complete: true`,
`usable: false`, `budget_refused: false`, and all forecast fields `null`.
The original plan is unchanged. No rerun, resume, new plan or game execution
was performed for this review. This dated result fills the former evidence-scope
template; it does not turn either failed predecessor into acceptance.

## Identity and evidence checked

| Item | Reviewed identity |
| --- | --- |
| Run ID | `archetype-pilot-20261116-v3-trace2` |
| Measured source commit | `495d820325179a625b5a63b2d62847718d5d5706` |
| Plan **file-byte** SHA-256 | `79beba36d65d6745a363f2e9a4063ee8c5fb25f553b1e6bea77746cdcc26389d` |
| Plan **canonical-object** SHA-256 | `7e29a160fd142d766ada934a32e09f1b1a020a7a9e019a41035cf6114132481d` |
| Source canonical-object SHA-256 | `a2aead6b678a7c0252c9fd6058960364662d8bd0440b313af9d9b184f3683b90` |
| Runtime canonical-object SHA-256 | `d852ff25e25a0dc238a71f7ff9595f76f50dc0da184d2cddc1bb1181b3e0b72a` |
| Source manifest file-byte SHA-256 | `ea08045e64dc9a4bf3b82b776d151d543860424d0cf397dccac5d2a543303b7a` |
| Runtime manifest file-byte SHA-256 | `8c3aebc8be6a4832e85361b0ad29c1fe974b77900637e6b4113ac893f88a27a0` |
| Final report file-byte SHA-256 | `8d8311c0180586dd5dcda1cacb2e7b93ee3e5723f9d488c82213671e28ec0893` |

The source/runtime/plan objects match the report's canonical digests; file hashes
are kept distinct. All 36 ordered cell IDs match the frozen schedule without
missing, duplicate or undeclared rows. All trace byte counts and whole-file hashes
match their receipts. Every retained JSONL record was checked for complete line,
sequence, previous-record binding and the trace-schema-4 domain-separated digest,
with the initial identity bound to the expected cell/source/runtime/plan.
This is an artifact audit, **not a fresh execution of replay**.

All 71 attempted game/verification children have started-and-waited receipts;
all cells report handles reaped and `run_invalid: false`. The operator reports
the controller finished. Its actual shell exit/status receipt is not included
in the reviewed output directory, so no numeric controller exit is asserted.
No live registry was read or changed: final-report campaign figures below are
point-in-time evidence, not a current registry-closure audit or future admission.
The operator reports the same fresh hash-locked environment as trace1; the
reviewed runtime object and all worker identities bind its exact digest.

## Frozen scope

- 36 single games: **nine adjacent pairs × two seeds × both seats**, on nine
  unchanged admitted deck lists. The seeds remain 2026112001 and 2026112002;
  Burn/Mono Red remain explicitly excluded. No sideboarding or AI/rules change.
- Master AI; engine seed with seats swapped, not deck-fixed shuffles. Mirrored
  seats need not receive the same hands/draws and are not independent seeds.
- Two slots, one-core affinity and 2-GiB address-space cap per worker;
  **1,200 CPU / 1,500 wall seconds shared by game plus verification**,
  10,000 actions and 100 turns. These process/affinity limits are not cgroups
  or an aggregate host-memory guarantee. Host-idle/headroom is an operator
  prerequisite, not independently measured by this review.
- Schema-4 authenticated explicit card order; full checkpoints every 64 actions
  and at the declared decision/handler/final boundaries; every-action replay and
  serde. **128 MiB per-cell trace limit**, whole-record refusal, no truncation.
- No retries/resume; host sleep/crash invalidates rather than produces a draw.
  This is not the original 1,440-game statistical gate, all 36 pairs, BO3,
  AI-strength acceptance or RC acceptance.

## Timeout classification

The single limited cell is ordinal **001**. Its game child returned **-24
(SIGXCPU)** and was waited, with termination `cpu_limit`. Actual waited CPU is
**1,199.922 seconds**; cell wall is **1,205.364 seconds**, below the 1,500-second
wall limit. This is **not** a trace, turn, action or memory-limit refusal.

Its intact trace contains **1,282 accepted actions**, zero-based indices
0–1281, ending at **turn 44 / upkeep**, and **78,417,648 bytes**, below the
134,217,728-byte quota. The bound progress receipt also reports 1,282 actions.
There is no final record, game outcome or verification attempt; `winner`,
completed-action count and replay time are null. These partial actions are
not a loss, draw or completed game. Peak child RSS is 109,957,120 bytes,
not the configured address-space cap.

The last flushed CPU receipt reaches 1,175.006 process-CPU seconds, including
922.229 in AI (inclusive of its simulations) and 168.194 in snapshot work.
The last operation after that receipt is unclassified; it cannot be assigned
from the final action or from elapsed time. Whole-cell CPU not assigned to
completed named buckets is **28.084 seconds**, including residual/setup and
interrupted work, not necessarily all AI. `cpu_attribution_complete: false`
is retained for this cell. There is no basis to call the timeout an adapter
ordering recurrence or a demonstrated stuck loop.

## Completed replay and selected parity

All **35** resolved cells have successful, identity-bound game and verification
receipts, child exits zero, `parity_checked: true`, valid completion CPU receipts
and no reported replay divergence. Each verification outcome equals its game
outcome and authenticated final trace record. **17,195 actions** match sequential
replay, with **17,195 serde restarts**.

All **227** expected selected boundaries (first, every 100th, last) have true
transition equality, original-key retry and SQLite round-trip checks, including
explicit card-order equality through transition, persistence and restoration.
These are real **direct-handler/SQLite comparisons**, not an uninterrupted API
game, HTTP/browser parity, or independent Oracle/rules correctness. The CPU-
limited cell has no replay/parity pass and is not silently included in these 35.
The earlier trace1 ordering failure remains recorded separately; these receipts
support the fix on this schedule, not an unlimited correctness guarantee.

## Aggregate outcomes and measurements

The 35 verified outcomes are all `life` terminations: **21 seat-1 and 14 seat-2
wins**, zero completed draws. This is accounting, **not a win-rate or strength
estimate**; the censored cell receives no score. Final turns range **9–29**
(median 16); accepted actions range **254–817** (median 476), totaling 17,195.
Including the censored prefix gives 18,477 written actions, not 36 completed
outcomes. All traces total **735,620,930 bytes** (735.621 decimal MB), with
886 full action checkpoint records; databases and other output are additional.

Quantiles use nearest rank `ceil(p × n)` on the named sample; medians here use
the same rule, with no interpolation. CPU sums are actual waited child CPU,
not charged slot time. Resolved-only and censored-inclusive rows stay separate.

| Seconds / scope | n | Min | p50 | Mean | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Game + verification CPU, all cells | 36 | 97.630 | 260.613 | 321.036 | 781.997 | 1,199.922 |
| Game + verification CPU, resolved only | 35 | 97.630 | 260.613 | 295.925 | 601.610 | 781.997 |
| Game CPU, resolved only | 35 | 53.333 | 162.902 | 196.113 | 428.806 | 608.106 |
| Verification child CPU | 35 | 44.074 | 92.630 | 99.593 | 182.238 | 195.919 |
| Cell wall, all cells | 36 | 99.652 | 264.151 | 324.608 | 787.546 | 1,205.364 |
| Cell wall, resolved only | 35 | 99.652 | 264.151 | 299.443 | 607.340 | 787.546 |
| Replay + selected-handler elapsed | 35 | 43.626 | 92.645 | 99.759 | 182.897 | 197.065 |

Replay time totals **3,491.561 seconds** across 35 cells, includes selected
handler/SQLite setup/checks, and excludes other controller/worker setup as
specified by the timer; it is not pure engine transition time. Actual waited
CPU is available for all 36 cells: **11,557.299 seconds** total, of which
10,357.377 belongs to resolved cells. Completed phase CPU attribution exists
for 35 cells, with the timeout's flushed partial attribution retained separately.
Across all available phase receipts, 176.609 waited CPU seconds are outside
completed named buckets. Residual is not treated as trace CPU. Maximum observed
per-child RSS is **138,395,648 bytes**; summing peak RSS would not measure host
peak memory.

Controller elapsed is **5,868.353 seconds**. Charged current-run worker-slot
time is **11,736.705 seconds** (two slots through controller lifetime), cumulative
campaign charge **17,310.238**, and reported remainder **155,489.762 seconds**
of 172,800. The health reservation remains **108,000 seconds / 30 hours**,
leaving 47,489.762 seconds outside that reserve before later charges. Prior
charges are not reset. Actual CPU, summed cell durations and charged slot time
are different measurements; external operator setup/installation overhead
still requires accounting. Later admission must recheck the real registry.

## Non-binding arithmetic from resolved cells only

The controller's three forecast fields remain **null**, reason
`incomplete_or_censored_or_failed_cells`. The following are separately labelled
**conditional arithmetic scenarios**, not a usable-pilot forecast or approval.
They use only the 35 resolved cell durations (game + verification), omit the
censored long cell, and can underestimate workload from the 27 unseen pairs.
A p95-duration scenario is not a confidence bound on a 72-game total.

| Scenario: assume every new cell takes the named resolved duration | Per cell s | 72 worker-s | 72 worker-h | Ideal two-slot elapsed h | Headroom within 108,000 s reserve |
| --- | ---: | ---: | ---: | ---: | ---: |
| Resolved mean | 299.443 | 21,559.902 | 5.989 | 2.994 | 86,440.098 s |
| Resolved p95 | 607.340 | 43,728.452 | 12.147 | 6.073 | 64,271.548 s |

These sums exclude charged setup, idle slots, postprocessing, imbalance and
external overhead. They do not guarantee the run fits. The hard 72 × 1,500-wall
cell ceiling already consumes the entire 108,000-second reserve before that
extra overhead; a cooperative controller must refuse further admission at its
budget bound, not promise all 72 worst-case cells can finish.

**1,440 × the resolved-only mean = 119.777 worker-hours**, already above the
entire 48-hour campaign, before overhead and prior charges. Roughly **129.843
hours** comes from 1,440 × the report's all-36 mean (324.608 seconds), which
includes the censored timeout and is **not** a completed-game forecast. Neither
figure supports fitting the original statistical gate within this campaign.
No hard impossibility for every conceivable future game duration is inferred;
the observed planning basis cannot meet that gate inside the approved budget.
A 72-game health-only run cannot be relabelled as completing it.

## Conclusion and next decision

The complete pilot remains **`usable: false`** because one scheduled game did
not finish under its frozen limits. No resource-limited game, failed predecessor
or partial prefix is promoted to a resolved result. Rules/AI and pilot budgets
remain unchanged; no rerun or resume is proposed here.

The evidence supports reviewing a separately predeclared **72-game, all-36-pair,
one-new-seed, both-seat health-only** entry point, with the explicit unusable-pilot
exception and budget decisions in the [design note](archetype-health-entry-design-20261116.md).
It does not authorize implementation or execution. Final-source CI, clean-
checkout/advisory workflow evidence, browser/operator checks, data/rules scope,
statistical evaluation, strength and RC sign-off remain separate open gates.

Private plans, traces, hands, actions, reasons, logs, databases and registry
payloads remain private. Only aggregates and identity hashes are published.
References: [adapter/runbook](archetype-v3-adapter-20261116.md),
[trace1 diagnosis](archetype-v3-trace1-diagnosis-20261116.md),
[c2 diagnosis](archetype-pilot-c2-diagnosis-20261116.md) and
[AI status](../../AI-STATUS.md).

## Reading a future health result — operator checklist (2026-11-17)

This section explains how to read a future result from the separately approved
72-game health implementation. At this edit, PR #95 is awaiting its CI rerun
and merge; the operator will issue and launch the health plan only afterwards.
Implementation approval is not launch approval. This section records no
health execution or result. Review output only after the operator confirms the run
has terminated; keep complete traces, hands, actions, reasoning, logs, databases
and registry payloads private. Publish reviewed aggregates and identity hashes.

### Check identity and closure before interpreting status

1. Record the actual terminal exit and exact run ID. Match the issued plan's
   full clean source commit, runtime digest, 72 ordered cell IDs, all 36 pairs,
   new seed and both seats to the final report and bound per-cell receipts.
   Compare file-byte hashes with file-byte hashes and canonical-object digests
   with canonical-object digests. A directory or elapsed time is not evidence
   of termination or completion.
2. Require a role-specific `HEALTH-COMPLETE.json` or `HEALTH-INCOMPLETE.json` and
   the matching closed registry record. Match its report hash and prior/current
   campaign and health charges. Check actual attempted child wait/accounting
   closure, the health-overrun flag, charged totals against the 30-hour health
   and 48-hour campaign limits, and remaining allocations. The report
   is published before registry closure; it cannot certify final accounting
   alone. A publication-time overrun can leave a nominal report while the CLI
   refuses success and the closed ledger records the overrun.
3. Check completeness against the entire declared schedule, not a count alone:
   no duplicate, undeclared or missing IDs. Check each game/verification identity,
   trace hash, verified full outcome and selected parity evidence. Keep the
   terminal exit, report and ledger together; contradictions leave acceptance
   unverified, not repaired by choosing the most favorable artifact.

If a guard fails before a report exists, record that refusal and its stage;
do not infer an accounted health result. If child closure is unproven, the
registry remains blocking. Never delete owner locks, reset HOME, move the
registry, overwrite a run or resume it to obtain a cleaner result.

### Interpret accounting and health separately

| Evidence | Meaning and reporting |
| --- | --- |
| `complete: true`, `health_passed: true`, exit 0, matching closed budget-valid ledger | All declared games completed under the frozen limits with the configured replay/serde and selected handler/SQLite checks. This is a health pass only for that exact scope/source/runtime. |
| `complete: true`, `health_passed: false` | Schedule accounting completed, but health failed. `HEALTH-COMPLETE.json` is not a pass certificate. Include every resource/error/divergence outcome; do not remove the expensive cell. |
| `complete: false` or missing/contradictory evidence | Incomplete or unverified. Report attempted, unstarted, missing and censored cells separately. A resolved subset cannot accept the original declaration. |
| A CPU/wall/memory/trace/action/turn limit | Incomplete game, no winner or draw score. Preserve the exact termination, actual waited CPU/wall, last authenticated action/turn and available partial attribution; unknown interrupted work is not zero. |
| A canceled peer after fail-fast stop | Censored attempt, not automatically an independent engine exception or a loss. Distinguish actual exception evidence from a signal/cancellation label. Unstarted cells are not censored attempted games. |
| A genuine engine `draw` or deck-out outcome with complete verification | Retain the engine outcome under the frozen policy; distinguish it from resource exhaustion. |
| Budget refusal, overrun or unproven child closure | Not acceptance, even if a preliminary report or some game receipts look successful. Preserve every charge and the permanent run-ID consumption. |

Zero resource-limit tolerance is predeclared: **one limited cell fails health**.
One of 72 is 1.389%, not rounded to zero; do not relax the integer threshold after
seeing results. Failure is a plausible and acceptable result to report given
the earlier pilot's 1/36 timeout. It is not a reason to change AI quality,
budgets, seeds or deck lists in place. Any further attempt needs its own reviewed
plan, fresh ID, remaining-budget check and explicit operator launch approval.

### What may be claimed

After all identity, receipt and closure checks, a passing result supports:

> On the recorded source/runtime/plan, all 72 declared single games passed the
> configured engine-health checks, every-action replay/serde and selected
> direct-handler/SQLite comparisons, within their declared resource policy.

Report exact status/termination counts, completed and partial action counts,
turn ranges, CPU and replay-time availability, missing attribution, trace bytes
and charged slot time. Keep actual CPU, summed cell durations and two-slot
campaign charges separate. State any failures or censorship in the conclusion.
A failed run supports a diagnosis of its observed failure, not the quoted pass.

Selected direct-handler/SQLite parity is not HTTP/browser parity or independent
Oracle correctness. Swapped seats share one engine seed, not deck-fixed hands;
one seed supplies no independent seed-cluster interval or AI-strength estimate.
Outcome counts are accounting, not a playing-strength percentage. The result
cannot complete the original 1,440-game statistical gate, qualify excluded decks,
turn old pilot failures into passes or establish RC readiness. Forecast fields
remain null even for a health pass; do not fill them from a surviving subset.
Current-source CI, browser/operator, rules/data, statistical/strength and release
sign-off retain their separate requirements.

## 72-game health result — 2026-11-17

**Health FAILED by predeclared zero tolerance: 71/72 resolved, one CPU-limit
timeout, no replay divergence among the 71 verified games.** The operator
confirmed termination and authorized read-only review. This is the terminal
record for `archetype-health-20261116-v3-trace1`, not a new run or reclassification of prior pilots.
`HEALTH-COMPLETE.json` means schedule accounting completed; it records
`complete: true`, `health_passed: false`, `usable: false`, `health_only: true`
and `budget_refused: false`. No error, divergence, draw or cancellation is
reported beyond the single CPU-limited game. Forecast fields remain null.

### Launch, identity and terminal evidence

| Item | Reviewed identity / operator-supplied terminal fact |
| --- | --- |
| Run ID | `archetype-health-20261116-v3-trace1` |
| Full measured source commit | `1a54be1f7fc71884336d790c55bb935a7037fbb0` |
| Issued plan **file-byte** SHA-256 | `601a8d68cf04c02ac4734bef034f9a58390dad1eafdd9da933c346e509859dc4` |
| Plan **canonical-object** SHA-256 | `c921d07f6e731c187ca5c0aa7992f2ad934ad4d238587766200b01327da11a35` |
| Source canonical-object SHA-256 | `a75446e9111ae55c3c9e19f8f032a9f800f79e84ffad6a43ada128728e4432f4` |
| Runtime canonical-object SHA-256 | `d852ff25e25a0dc238a71f7ff9595f76f50dc0da184d2cddc1bb1181b3e0b72a` |
| Source manifest file-byte SHA-256 | `fac18bee1b0e6b4cbf93b196e971b201b6828c54ec955d7eebfa5dfeb5dcf26f` |
| Runtime manifest file-byte SHA-256 | `8c3aebc8be6a4832e85361b0ad29c1fe974b77900637e6b4113ac893f88a27a0` |
| Final report file-byte SHA-256 | `e213787c3e81779eb288afa92536a5d2ed64a9b531e554c68b3ee5488598c22c` |
| Launch time, operator-reported | 2026-11-17 03:39:15 UTC; directory created 03:39:16 UTC |
| Completion time, operator-reported | 2026-11-17 06:46:40 UTC, final-report mtime |
| Numeric controller exit | **Not captured**; detached launch, not inferred from the code |
| Registry closure, operator-reported | `state: closed`, `child_handles_reaped: true`, `health_budget_exceeded: false`, `pilot_budget_exceeded: false`, report hash matching above |

The run-ID grammar hard-codes `20261116`; launch actually occurred on
**2026-11-17**, not on the identifier's date. Completion mtime is not an actual
shell-exit timestamp. The operator supplied terminal summary fields:
`complete: true`, `health_passed: false`, statuses `resolved: 71` /
`timeout: 1`, and `accepts_matrix_or_strength: false`. Missing numeric exit is
retained as missing, not converted to zero or one. The health failure is
already explicit in the bound report and predeclared criterion.

The plan/source/runtime objects match the report's canonical digests; the
operator-supplied plan-file hash matches the actual reviewed file. All 72
ordered cell IDs match the frozen plan, without missing, duplicate or undeclared
rows. All trace sizes and whole-file hashes match their receipts. Every retained
JSONL record's complete line, sequence, previous hash and schema-4 digest were
checked, with initial identity bound to its cell/source/runtime/plan. All 143
attempted children have started-and-waited receipts and every cell reports
handles reaped and `run_invalid: false`. This audits **recorded evidence**;
it is not fresh replay execution or an independent OS/registry-closure audit.
The registry facts above are supplied by the operator; it was not read here.

The exact schedule is **all 36 unordered pairs of the nine admitted lists ×
seed 2026112101 × both seats = 72 single games**, with unchanged master AI,
no sideboarding and both whole-deck exclusions retained. Mirrored seats use
engine seeds, not deck-fixed shuffles. Limits remain 1,200 shared game-plus-
verification CPU seconds, 1,500 wall seconds, 2 GiB per worker, two one-core
slots, 10,000 actions, 100 turns and 128 MiB per trace. No result is imported
from c2, either pilot or the original statistical declaration.

### Single timeout: different matchup and progression, same CPU-limit class

Ordinal **032** is **Drain Deck in seat 1 vs Ramp in seat 2**. Its game child
returned **-24/SIGXCPU**, was waited, and terminated `cpu_limit` at
**1,199.940 CPU seconds** and **1,202.771 cell wall seconds**. The trace ends at
**turn 26 / postcombat main**, with **761 accepted action records** (zero-based
0–760), **25,597,276 bytes**, and no final outcome or verification attempt.
It is below wall, trace, action and turn ceilings; it is not a trace quota,
memory-limit report, resolved loss or draw. Winner and replay time are null.

The authenticated flushed CPU-progress boundary covers **752 actions** and
25,586,537 bytes at **1,050.373 process-CPU seconds**. The nine later intact
trace actions do not supply further CPU-category attribution. Completed
prefix categories include **947.867 AI-inclusive seconds** and **73.253 snapshot
seconds**; the whole-cell waited CPU outside completed named buckets is
**151.040 seconds**. That includes residual and post-receipt/interrupted work;
it cannot be assigned wholly to AI, a specific action or a loop. Final visible
priority passes are not proof of a stuck loop: the last 20 written actions
span nine steps of turn 26. The unrecorded interrupted operation remains unknown.

Pilot trace2 cell 001 was **Blue Control seat 2 vs Dimir Control seat 1**, seed
2026112001, ending turn 44 upkeep at 1,282 actions and 78,417,648 bytes under
the same CPU ceiling. Thus the common observation is **CPU exhaustion before
verification**, not the same matchup, seat, seed, action count or turn-44
mechanism. Some resolved health games reach turn 44, so turn count alone does
not determine resource failure. See the [short options note](archetype-health-timeout-options-20261117.md).

### Verified outcomes, replay and selected parity

All **71** resolved cells have zero game/verification child exits, bound valid
receipts, `parity_checked: true` and complete phase CPU attribution. Each replay
outcome equals its game outcome and authenticated final trace outcome.
**36,404 actions and 36,404 serde restarts** match sequential replay.
All **470** expected selected first/every-100th/last boundaries have true
transition, original-key retry and SQLite round-trip comparisons, including
explicit card-order transition, persistence and restoration checks. There is
**no reported replay divergence** among these completed verifications. The
limited cell has no replay or parity pass and is not counted as one.

All 71 verified games terminate by `life`, with **41 seat-1 and 30 seat-2 wins**,
zero completed draws. These are accounting counts, not an AI win-rate estimate.
Final turns range **9–44** (nearest-rank median 17), accepted actions **246–1,242**
(median 488), totaling 36,404. Adding the incomplete trace gives **37,165 written
actions**, not 72 completed outcomes. All traces total **1,426,639,380 bytes**
(1.427 decimal GB) and 1,794 full action checkpoint records; DBs/logs/caches
are additional storage. Maximum observed per-child RSS is 142,098,432 bytes,
not aggregate host peak memory or the configured address-space limit.

Quantiles use nearest rank `ceil(p × n)`, with no interpolation. Censored-
inclusive and resolved-only samples remain separate. Actual waited child CPU
is available for all 72 cells; replay time for 71. The replay timer includes
selected handler/SQLite work and setup inside that timer, not engine replay
alone. These are descriptive measurements, **not forecasts**.

| Seconds / sample | n | Min | p50 | Mean | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Game + verification CPU, all cells | 72 | 82.898 | 236.296 | 307.065 | 833.555 | 1,199.940 |
| Game + verification CPU, resolved only | 71 | 82.898 | 236.296 | 294.489 | 781.552 | 1,017.297 |
| Cell wall, all cells | 72 | 84.781 | 239.622 | 310.676 | 841.720 | 1,202.771 |
| Cell wall, resolved only | 71 | 84.781 | 239.622 | 298.112 | 788.003 | 1,023.615 |
| Replay + selected-handler elapsed | 71 | 40.661 | 90.838 | 102.150 | 221.287 | 306.327 |

Actual waited CPU totals **22,108.686 seconds**, of which **20,908.746** belongs
to resolved cells. Replay/selected-handler elapsed totals **7,252.680 seconds**.
Across available complete and partial receipts, **460.026 waited CPU seconds**
are outside completed named buckets; missing attribution is not zero.
Controller elapsed is **11,244.556 seconds**, distinct from summed cell wall,
actual CPU and charged two-slot lifetime.

### Budget record and scope of closure

| Charge / remainder | Final report, seconds | Operator-supplied closed registry, rounded seconds |
| --- | ---: | ---: |
| Current health-role total | 22,489.112 | 22,489.12 |
| Campaign total | 39,799.358 | 39,799.37 |
| Remaining 30-hour health allocation | 85,510.888 | 85,510.88 |
| Remaining 48-hour campaign | 133,000.642 | 133,000.63 |

The report records current-run charged slots **22,489.112 seconds**. The
operator supplies **17,310.25 seconds** of prior campaign charge. Small
publication/closure differences and rounding are retained, not normalized
away; the final closed registry governs future admission. The operator reports
closed state, all handles reaped, no health/pilot budget overrun and the exact
report hash above. These are operator facts joined to reviewed report bytes,
not an independent read of the live registry. No charges, locks, HOME or registry
location were reset or modified by this review. Remaining budget is not
permission for another experiment; external setup remains operator-accounted.

### Conclusion and non-claims

**Health FAILED by its predeclared zero resource-limit tolerance.** Schedule
accounting is complete, but the one CPU-limited game prevents health success:
71/72 resolved with verified replay/parity, one unscored incomplete game.
The result is plausible and acceptable to report honestly; it does not change
the criterion. No further game, replay, rerun, resume, new plan, seed substitution,
AI/rules change or limit increase was performed for this analysis.

`forecast_72_worker_hours`, `forecast_1440_worker_hours` and `forecast_trace_bytes`
remain null, reason `incomplete_or_censored_or_failed_cells`.
`statistical_gate_complete` and `accepts_matrix_or_strength` remain false.
The selected comparisons are direct-handler/SQLite checks, **not HTTP/browser
parity or independent Oracle correctness**. One seed supplies no independent
seed-cluster interval; mirrored seats do not add independent seeds. No strength
percentage, excluded-deck qualification, original 1,440-game gate completion
or overall RC sign-off follows. All raw game artifacts remain private; only
reviewed aggregates and identity hashes are published. The [options note](archetype-health-timeout-options-20261117.md)
records possible next decisions without changing anything.
