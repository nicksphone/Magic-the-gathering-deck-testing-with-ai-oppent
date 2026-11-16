# Trace2 quota proposal: retain checkpoints, raise trace ceiling

**Candidate policy for review, not permission to issue a plan or launch.**
The stopped trace1 result remains unusable and its charges remain in the
campaign. No trace, seed or result is rewritten or resumed.

## Proposed change

Raise the per-cell trace ceiling from **64 to 128 MiB** (134,217,728 bytes).
Keep the full-record-before-write refusal, every-64-action checkpoints and all
choice, pregame, first/every-100th/last handler and final checkpoints. Keep exact
per-action state/legal/RNG/order comparisons, sequential replay, master AI,
rules, 1,200 shared CPU / 1,500 shared wall seconds, two workers, memory limits,
zero retries and the 48-worker-hour campaign unchanged.

This is a concrete adapter/configuration patch in a separate commit from card-
order fidelity. A new merged source revision, trace-format-4 plan and fresh ID
such as `archetype-pilot-20261116-v3-trace2` must be reviewed before execution.
It does not grant a new 48 hours or authorize the conditional health run.

## Observed sizing, not a completed-game forecast

The twelve terminal cell directories contain the following private-trace byte
counts. Only aggregates appear here; no raw trace or snapshot is copied.

| Cell | Accounted status | Written action records | Trace bytes |
| --- | --- | ---: | ---: |
| 000 | resolved | 568 | 21,014,783 |
| 001 | trace-limit timeout | 1,151 | 65,890,540 |
| 002 | resolved | 813 | 31,107,414 |
| 003 | resolved | 653 | 38,224,596 |
| 004 | resolved | 708 | 30,357,085 |
| 005 | resolved | 533 | 14,505,311 |
| 006 | resolved | 810 | 37,106,587 |
| 007 | resolved | 572 | 17,153,627 |
| 008 | resolved | 499 | 12,092,911 |
| 009 | resolved | 533 | 17,123,908 |
| 010 | replay divergence | 771 | 28,530,295 |
| 011 | cancelled peer, censored | 308 | 7,660,555 |
| **Total observed** | **12/36 accounted, unusable** | | **320,767,612** |

Cell 001 refused a complete next record at 985.111 CPU / 989.636 wall seconds,
not at either time ceiling. The file can be below 64 MiB because the next whole
record must fit. Its 67 checkpoint records include 38 choice checkpoints and
16 periodic-only checkpoints; retained records reach 1,371,803 bytes each.
Across all twelve cells there are 369 checkpoints, 148 with a choice reason and
115 periodic-only. Checkpoint records account for 304,561,559 bytes (about 94.95%
of observed trace bytes).

Reducing periodic density would leave all mandatory choice checkpoints in
place. Checkpoints dominate overall bytes, and decision snapshots are useful
for small faithful reproductions such as action 647.
Therefore this proposal retains the current density and buys bounded headroom
instead. It does **not** promise that 128 MiB is sufficient for every game:
full histories and decision frequency can still grow. Another quota refusal
must remain a failed/incomplete cell, not a reason for an automatic retry.

A byte-length-only calculation adding the new order lists/digests to those
recorded bodies adds 2,435,015 bytes (about 0.76%) across twelve cells. Cell 001
adds 394,538 bytes, for 66,285,078 bytes over its already-written prefix. Order
is irrelevant to that length calculation; it is not a generated replacement
trace, a replay pass or a prediction of future game decisions.

The old twelve-cell volume times three is 962,302,836 bytes; with only that
metadata addition it is 969,607,881 bytes. **Neither is a valid 36-game forecast**:
these cells are a selected incomplete prefix, including resource limitation,
failed verification and peer cancellation. The report's completed-game forecast
fields stay null. For storage admission use the declared trace-only ceiling:

- 36 × 128 MiB = **4,831,838,208 bytes (4.5 GiB)**, twice the old 2.25-GiB ceiling.
- Worker logs, DBs, caches and reports are additional; prior private outputs must
  also be retained. This is not a disk quota on the whole output directory.
- A later separately approved 72-cell health schedule would have a 9-GiB
  trace-only ceiling, not an already authorized run or an observed forecast.

## Campaign arithmetic

The trace1 report records **167,226.509 worker-slot seconds remaining** after
5,573.491 charged seconds. Its nine good cells do not erase the other charges.
The registry ledger is authoritative and external install/setup work must also
be charged before approving another cohort.

| Reservation from that reported remainder | Worker-slot seconds |
| --- | ---: |
| Conditional 72-game health reservation | 108,000 (30 h) |
| Worst-case new 36-game pilot: 36 × 1,500 wall seconds | 54,000 (15 h) |
| Left for further overhead at that measurement point | **5,226.509 (about 1.452 h)** |

Two fully occupied slots would take up to 7.5 elapsed hours for the cell ceilings,
plus controller/setup/idle/publication costs charged at two slots. The CPU ceiling
for 36 cells remains 43,200 CPU seconds (12 CPU-hours), which is a different
quantity. Raising the trace ceiling grants no extra CPU or wall allowance.
There is no completed-game duration forecast from trace1.

The arithmetic fits the nominal remainder **only before unaccounted external
work and further overhead**. Reconcile the actual registry/overhead first; if
there is insufficient reserve, do not launch or silently shrink the schedule.
Keep the old consumed ID, closure records and cumulative charges. A source/plan
change must never reset HOME, move the registry, delete its lock or reuse trace1.

## Verification and decision

The new quota-policy test fails against 64 MiB, then passes at 128 MiB. Existing
small-record boundary tests still require refusal before writing any part of an
over-quota next record; no 128-MiB test allocation or pilot is needed to check
that contract. The frozen plan binds the exact quota, and an old 64-MiB plan is
refused by the new policy. The plan/trace slice passed 29 tests. Final composed adapter/v2/pin verification
passed 396 distinct tests in one local invocation, with no failures/errors/skips;
see the runbook for runtime and warning scope. This is not a new pilot result.

Approval of this patch would allow **reviewing a new plan**, not executing one.
No new plan or pilot is issued here. See the
[trace1 diagnosis](archetype-v3-trace1-diagnosis-20261116.md) and
[operator runbook](archetype-v3-adapter-20261116.md).
