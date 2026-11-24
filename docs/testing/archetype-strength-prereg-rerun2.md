# AI strength rerun 2 pre-registration

Date 2026-11-24. One-shot run ID
`archetype-strength-20261124-v3-rerun2`. The first run's result remains a
failure. Issue the plan only from the reviewed revision in a clean checkout
with the hash-locked runtime.

## Design and acceptance

Carry forward the [first pre-registration](archetype-strength-prereg-20261122.md):
nine admitted built-ins, same deck at both seats, Master against random
checked-offer completions, Casual, Strong, and Master. Burn and Mono Red
remain excluded. Use both seat orientations with the same physical seed
within each pair. Use nine fresh seed labels `2026112401` through
`2026112409` across all decks and opponents. This gives exactly
9 × 9 × 2 × 4 = **648 cells**. A tenth Casual-only seed would add 18 cells,
cost about 2.2 worker-hours at the point forecast, and change the fixed
design. This run uses the common nine seeds and retains the budget
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
closed, in-budget registry. This run ID admits **4,800 CPU seconds and 6,000
wall seconds per cell**, shared across gameplay and verification. The first
strength run and health rerun keep 2,400 CPU and 3,000 wall seconds. All
game-end rules are unchanged. The higher limits address the 17 CPU stops
observed under the original limit. Record the result either way,
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

This run stores periodic full checkpoints every **512 actions**, plus
the initial and final snapshots and a checkpoint at the terminal action.
It authenticates, replays and restores every action. Handler and SQLite
parity still run at zero-based steps 0, 100, 200 and so on, plus the last
accepted action, even when the full snapshot was reconstructed during replay.
Dropping alternate periodic checkpoints from the bytes already recorded
in the two quota-stopped traces would reduce their observed prefixes from
20.49–22.31 MiB to 10.88–13.24 MiB. Future suffix sizes are unknown.
The 23 MiB limit stays in force. This change addresses disk quota, with
limited CPU impact. The original run keeps its 256-action checkpoints.

## Worker budget and admission

The first run charged 301,086.76 worker-seconds (83.64 worker-hours),
including controller overhead and incomplete cells. Its closed record
reported 363,883.66 seconds already charged and 68,116.34 seconds
(18.92 hours) left at the 120-hour ceiling.

| Budget quantity | Value |
| --- | ---: |
| Cumulative rerun2 ceiling | 720,000 worker-s (200 h) |
| Remaining at the first run's close | 356,116.34 worker-s (98.92 h) |
| Two-slot admission reserve | 2 × 6,000 + 60 = 12,060 worker-s (3.35 h) |
| Point forecast for 648 cells | 288,489.6 worker-s (80.14 h) |
| Stress scenario at 1.5× the forecast | 432,734.4 worker-s (120.20 h) |

The point forecast combines about 442 CPU seconds per cell with 3.2
seconds of mean charged slot overhead from the first run. It is a projection
from censored evidence. The 1.5× scenario assumes costly tails and is a
planning stress case and exceeds the 98.92-hour balance by about 21.28
hours even before the refill reserve. Longer runs remain possible. A
forecast overrun can trigger a budget stop. Record the resulting
incomplete run as a failure.

`STRENGTH_RERUN2_CAMPAIGN_HOURS = 200` applies only to the exact rerun2 ID.
The plan, controller and registry use the same limit. They carry forward
the existing cumulative charges in the same host registry and require the
closed original strength and health-rerun charge histories. The controller
requires enough remaining budget at each refill to cover two slots for the
per-cell wall horizon plus a 60-worker-second shutdown reserve. At the point
forecast, the cumulative charges plus that reserve total about 184.56 hours.
Confirm the live charge before issuing the plan.

## Host commands

Use the same account and existing registry at
`~/.local/state/mtg/archetype-v3`. From an idle host, use a clean checkout
of the reviewed revision and a fresh Linux CPython 3.12.3 venv with the
complete application hash lock installed from
`backend/requirements-py312-linux.lock`. The controller requires at least
three available cores and 5 GiB of memory headroom. Use fresh plan and
output paths under an owned private parent outside the checkout. Allow
14.55 GiB for trace quotas plus space for SQLite, receipts and caches.

```sh
cd /absolute/clean-checkout/backend
/absolute/fresh-venv/bin/python -B -m scripts.archetype_strength_v3 plan \
  /absolute/private/strength-rerun2-plan.json \
  --run-id archetype-strength-20261124-v3-rerun2
sha256sum /absolute/private/strength-rerun2-plan.json
```

Review and record the bound source revision, runtime digest, plan hash and
prior closed charges. Execute the issued plan once on the same host and
runtime.

```sh
/absolute/fresh-venv/bin/python -B -m scripts.archetype_strength_v3 run \
  /absolute/private/strength-rerun2-plan.json /absolute/private/strength-rerun2-out \
  --execute-strength
```

Record the terminal exit code, report hash, closed registry charges and
comparison aggregates. Keep the raw evidence private. Acceptance requires
an exit of 0, `strength_passed: true`, and the matching closed, in-budget
registry record.
