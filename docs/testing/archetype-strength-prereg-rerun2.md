# AI strength rerun 2 pre-registration draft

Date 2026-11-24. Proposed one-shot run ID
`archetype-strength-20261124-v3-rerun2`. The first run's result remains a
failure. This draft does not issue a plan or increase the registry cap. The
bound source revision and runtime digest will come from a reviewed, clean
checkout before plan issuance.

## Design and acceptance

Carry forward the [first pre-registration](archetype-strength-prereg-20261122.md):
nine admitted built-ins, same deck at both seats, Master against random
checked-offer completions, Casual, Strong, and Master. Burn and Mono Red
remain excluded. Use both seat orientations with the same physical seed
within each pair. Use nine fresh seed labels `2026112401` through
`2026112409` across all decks and opponents. This gives exactly
9 × 9 × 2 × 4 = **648 cells**. A tenth Casual-only seed would add 18 cells,
cost about 2.2 worker-hours at the point forecast, and change the fixed
design. This draft keeps the common nine seeds and retains the budget
headroom for long games and verification.

Verified wins score 1, draws 0.5, and losses 0. Unresolved outcomes contribute
only to the pessimistic and optimistic completion bounds. Compute the same
2,000 percentile-bootstrap replicates with bootstrap seed `271828`,
resampling seed labels and retaining all matched seats and decks in each
sampled label. Report outcome counts, scores and bounds by opponent and deck.

| Comparison | Pre-registered requirement |
| --- | --- |
| Random and Casual, each independently | Lower score bound ≥ 0.80 and lower 95% bound > 0.65 |
| Strong | Lower 95% bound > 0.50 |
| Master mirror | 95% interval contains 0.50 and every pair verifies with complementary scores |

All requirements apply jointly, with complete schedule accounting, reaped
children, valid replay and selected handler/SQLite parity evidence, and a
closed, in-budget registry. Keep the 2,400 CPU-second and 3,000 wall-second
per-cell limits and existing game-end rules. Record the result either way,
including censored cells. A pass would apply to these deck mirrors and
policies. It would leave human strength and the 1,440-game cross-deck matrix
unevaluated.

## CPU evidence from the first run

Means are CPU seconds per cell, using waited worker CPU and the last published
exclusive phase counters. Counters for interrupted phases are partial. The
snapshot column includes snapshot serialization, encoding and digesting
during play and replay. “Restore” includes the replay worker's independent
copy and restoration. Wall and two-slot worker charges are separate.

| First-run outcome | Cells | Total worker CPU | AI decisions | Snapshot capture | Restore | Checked transitions and legal lists | Trace encoding, flush and sync |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All scheduled | 648 | 461.5 | 200.9 | 147.5 | 43.7 | 58.0 | 0.16 |
| Verified resolutions | 629 | 403.3 | 160.4 | 135.6 | 42.9 | 53.6 | 0.15 |
| Gameplay CPU stop | 10 | 2,399.9 | 1,802.9 | 408.8 | — | 161.2 | 0.48 |
| Verification CPU stop | 7 | 2,399.5 | 1,196.2 | 708.3 | 191.8 | 265.7 | 0.55 |
| Gameplay trace-quota stop | 2 | 2,283.5 | 1,452.4 | 617.4 | — | 201.5 | 0.72 |

AI is the largest component in gameplay-limited cells. Capture and restore
account for 900 seconds in the average verification-limited cell. Trace
writes and record-chain encoding are a small CPU component. That is separate
from the two stops caused by the trace byte quota.

All 19 unresolved traces and eight resolved traces were sampled for
master-decision timings. The resolved sample was the median AI-cost
resolved cell in each Drain/non-Drain × opponent stratum. Across the
selected cells, the mean of the per-cell maximum master-decision wall
times was 39.92 seconds in the unresolved group and 11.04 seconds in the
resolved group. The mean of the per-cell medians was about 0.06 seconds in
each group. Those are times from original trace rows, including all recorded
master decisions in the selected traces. They exclude any interrupted action
that could not write a row.

Bounded single-decision profiles used the largest recorded master decision
per opponent among the timeout traces, and the peak and largest checkpointed
master decision in each of the eight resolved samples. Fresh agents received
the reconstructed state after its complete snapshot, card order and offered
actions matched their recorded digests. The profiles identify overlapping
search costs. Counts below come from instrumentation on the candidate
code. Whole-phase CPU is measured separately in the table above.

| Search function | Four timeout peaks | Eight resolved peaks | Eight resolved checkpoint samples |
| --- | ---: | ---: | ---: |
| State copies | 4,057 | 1,721 | 177 |
| Engine action calls | 6,304 | 3,617 | 221 |
| Trigger collection calls | 12,609 | 10,573 | 229 |
| Mana payment planner calls | 3,162 | 582 | 76 |
| Legal-move calls | 693 | 199 | 34 |

Copies, checked simulation and rule work inside the simulation account for
most of the decision cost. Their timings overlap. The counts show substantial
work inside individual late-game decisions even with bounded search depth.

All 20 decisions matched the recorded action on both the base and candidate
code. The mana planner shares read-only battlefield queries while it computes
a free payment plan. The scope ends before it simulates payments.
In alternating-order runs without a profiler, the four timeout peaks took
155.60 CPU seconds on the base and 145.78 on the candidate, a 6.3% reduction.
The eight resolved checkpoint samples took 3.54 and 3.19 CPU seconds.
Instrumented timings were noisier and showed a higher total CPU cost on the
timeout sample. These are paired position checks with no whole-game estimate
of AI savings.

## Verification and trace options

Every accepted action still has a complete canonical before/after digest,
RNG and card-order checks, and a sequential checked replay and restore. The
adapter compares the complete encoded snapshot directly for the AI mutation
guard. It decodes an independent normalized snapshot for restore, with the
same digest and evidence contracts.

The median component measurements across four tail and eight normal
recorded checkpoints gave these estimates. They are local single-state
measurements, not full-game benchmarks.

| Component | Four tail checkpoints | Eight normal checkpoints |
| --- | ---: | ---: |
| Complete snapshot document | 1.04 MB | 0.48 MB |
| Serialize fields | 24.93 ms | 11.53 ms |
| Canonical encode | 9.07 ms | 4.58 ms |
| JSON decode | 9.05 ms | 4.22 ms |
| Hash bytes | 0.53 ms | 0.24 ms |
| Recursive clone for restore | 28.14 ms | 13.56 ms |
| Deserialize after clone | 30.59 ms | 15.32 ms |

The changes remove one decode and hash from the three gameplay captures
per action, and replace the restore clone with a decode. Applying median
component ratios to the old phase counters gives approximately 442 CPU
seconds per scheduled cell, around 4% below the 461.5-second observed
baseline. The implied savings are about 30 worker CPU seconds for an
average gameplay CPU stop and 90 seconds for an average verification CPU
stop. This falls short of a 30% tail reduction. The projection gives no
credit for a speedup in the AI and does not predict completion for censored
cells.

As a separate proposed trace-policy change, use 512-action periodic full
checkpoints for this run ID, retaining initial and final snapshots,
per-action digests and restarts, and the same selected handler checks.
Dropping alternate periodic checkpoints from the bytes already recorded
in the two quota-stopped traces would reduce their observed prefixes from
20.49–22.31 MiB to 10.88–13.24 MiB. Future suffix sizes are unknown.
The 23 MiB limit would remain explicit and fail closed. This proposal
addresses disk quota, with limited CPU impact.

Skipping per-action restore in favor of checkpoint-only restore could
reduce CPU further. It would change the evidence, leaving restore coverage
between checkpoints untested. Any such policy needs separate approval
and versioned tests. This draft retains per-action restore.

## Worker budget and rollout

The first run charged 301,086.76 worker-seconds (83.64 worker-hours),
including controller overhead and the incomplete cells. The registry
reports 363,883.66 seconds already charged and 68,116.34 seconds
(18.92 hours) left at the 120-hour cap.

- A timing extrapolation of 442 CPU s/cell plus the first run's mean
  3.2 seconds of charged slot overhead gives about **80.1 worker-hours**
  for 648 cells. Use **83.64 hours** as the conservative historic
  comparator. Host contention, changed seed lengths and censored tails
  can make the new run more expensive.
- The minimum combined cap implied by the point forecast plus the
  two-slot admission reserve is about **182.9 hours**. Using the historic
  comparator puts that floor at **186.4 hours**. Propose
  `STRENGTH_RERUN2_CAMPAIGN_HOURS = 200`, giving **356,116.34 worker-seconds**
  (about 98.9 hours) with the current charged history. The operator
  should verify live ledger values before issuance. At 3,000 wall seconds,
  each refill still requires 2 × 3,000 + 60 = **6,060 worker-seconds**.
- Bind the new ceiling and checkpoint interval to this exact run ID in
  plan construction, validation, run admission, the controller and
  registry. Use the same cumulative registry and charge all earlier
  runs. Preserve the original run ID's 120-hour validation and the
  pilot/health rules. Test historical plans, rejection at the new cap,
  closed-history requirements and the new trace format before issuing
  the plan.

The current CLI admits only the original strength run ID. The named cap and
new plan route are proposals. Before issuing a runnable plan, qualify the
separate quota change and produce a measured improvement or explicitly
accept the risk of another resource-limit failure. The current patch alone
does not establish viability under the existing per-cell limits.
