# AI strength run timeout diagnosis

The pre-registered strength run accounted for 648 cells at `590f24d8`.
It resolved 629 and recorded 19 timeouts. The
[failed result](release-acceptance-status.md) stands. This analysis used the
existing result records and traces, plus two single-decision profiles
reconstructed from recorded checkpoints.

## What stopped the cells

| Limit and stage | Deck | Cells | Recorded actions | Last recorded turns |
| --- | --- | ---: | ---: | ---: |
| CPU, game | Drain Deck | 9 | 1,127–2,482 | 30–61 |
| CPU, verification | Drain Deck | 7 | 1,504–2,201 | 35–64 |
| CPU, game | Ramp | 1 | 1,898 | 64 |
| Trace quota, game | Drain Deck | 2 | 2,322–2,559 | 57–62 |

The CPU stops spent about 2,400 worker CPU seconds and took 2,402–2,409 wall
seconds, below the 3,000-second wall limit. The trace stops hit the 23 MiB quota
with game CPU use of about 2,238 and 2,329 seconds. The seven verification
stops finished gameplay and exhausted the shared CPU allowance during
verification, leaving the results unverified. They used a median 694 CPU
seconds in the verification worker. The largest attributed categories were
snapshot capture (median 336 seconds) and serialize/restore checks (median
204 seconds).

The traces advanced through turns and continued to record non-pass actions.
The evidence points to long games with expensive decisions, including some
expensive decisions that ultimately chose to pass priority. The nine Drain
Deck gameplay CPU stops spent a median 1,822 CPU seconds inside AI decisions.
Across the 18 unresolved Drain Deck traces, 2,304 activated-ability decisions
averaged 5.36 wall seconds and 391 took at least 10 seconds. The 31,739
pass-priority decisions averaged 0.41 seconds and 77 took at least 10 seconds.
The Ramp trace reached turn 64, with its slowest recorded pass taking about
123 seconds. These are counts of completed, recorded decisions. A CPU stop
can interrupt a decision before its trace row is written.

## Where the CPU went

The two selected decisions had their pre-action snapshot, card order and
legal-offer digests verified against the trace. Each profile used a fresh
agent on the reconstructed state. Both reproduced the recorded action.
The original trace timings are wall time. Profile timings are local process
CPU time with instrumentation, and nested measurements overlap.

Master's strategic continuation depth is at most two. Its candidate and stack
response searches still generate hundreds of copies and simulated actions
within that bound. Dense battlefields multiply the rules-query work in each
simulation.

- **Drain Deck mirror, turn 50, activated ability.** The recorded decision
  took 20.46 seconds. The baseline profile took 26.86 CPU seconds and made
  406 state copies and 486 simulated action calls. Stack lookahead accounted
  for 14.80 cumulative seconds. Layer-four battlefield queries ran 638,743
  times and accounted for 4.15 cumulative seconds.
- **Ramp, turn 55, pass priority.** The recorded decision took 107.74 seconds.
  The baseline profile took 152.50 CPU seconds, including 948 state copies.
  Layer-four battlefield queries ran 3,358,031 times and accounted for 35.40
  cumulative seconds. The battlefield predicate visited over 23 million
  cards, almost all of which had no live type effects to inspect.

## Change and scope

The layer-four query now skips the live-effect scan when the card has no type
effects. Cards with effects still go through the existing incarnation and
subtype checks. The regression exercises an empty list, a newly added live
effect and clearing the effect between queries. Search horizons, move ranking,
simulation budgets and serialization are outside this patch.

| Decision | Profiled CPU before | Profiled CPU after | Layer-four CPU before → after |
| --- | ---: | ---: | ---: |
| Drain Deck activated ability | 26.86 s | 26.22 s | 4.15 → 2.26 s |
| Ramp pass priority | 152.50 s | 147.43 s | 35.40 → 19.30 s |

Both selected actions and the number of state copies and layer-four calls
matched. The Ramp profile made about 6,700 live type-effect scans after the
change, down from about 23.2 million. The total profile times were 2–3%
lower. These are single-position results with profiling overhead.

No strength games were launched for this analysis. The change reduces one
measured source of CPU overhead. Whether it would bring a long game and its
verification under the cap remains unmeasured. Trace-quota stops have a
separate limit. A new pre-registration would be required for a new strength
claim, including the casual threshold the original run missed.
