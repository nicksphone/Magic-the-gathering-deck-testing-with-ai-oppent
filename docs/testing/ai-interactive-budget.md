# Opt-in interactive AI search limits

Autoplay uses the existing search policy unless one of these environment
variables is set in the backend process:

- `MTG_AI_INTERACTIVE_NODES` limits instrumented planning copies and
  simulated actions per decision. Use a nonnegative integer.
- `MTG_AI_INTERACTIVE_MS` sets a per-decision elapsed-time budget in
  milliseconds. Use a nonnegative integer.

Both limits can be set together. The first exhausted limit ends speculative
work. The deadline is cooperative. A single rules operation, legal offer
generation, or validating the fallback can take additional time. The
limits apply per decision, so an autoplay request containing multiple
ticks can take longer.

A completed search uses its regular final decision. During search, the
root ranker and strategic planner retain their best completed, checked
candidate. Strategic scores take precedence once available. Within each
phase, the native score and tie order select the incumbent. Nested opponent
searches never publish an action for the root. A scored pass can win on its
merits. If a better-scored challenger is still being completed, the
incumbent is used only if it is a substantive play. When there is no
incumbent, only a lone checked pass or land offer can serve as a fallback.

If there is no usable action on the first tick, autoplay returns a
retryable 503 with code `ai_decision_budget_exhausted` and rolls back the
request revision and idempotency receipt. If earlier ticks already did
work, autoplay commits those ticks and stops before the current action.
Mandatory choices can require more budget on a later request.
This policy can change play quality and is separate from the exact Master
policy used by the strength harness.

## Archived decision comparison

Sampled all 19 timeout cells' most expensive recorded Master decisions
and every other decision in those cells taking at least 40 seconds.
The 36 normal controls cover each resolved deck/opponent stratum and
different points in the game. The probe restored the recorded state,
checked its snapshot, card order and legal offers, and compared complete
action dictionaries. Each decision used a fresh agent. The sample
overrepresents expensive decisions by design.

| Positions | Exact match | Different substantive play | Play replaced by pass/skip/empty | Pass/skip/empty replaced by play | Paused |
| --- | ---: | ---: | ---: | ---: | ---: |
| 30 timeout positions | 0 | 19 | 0 | 0 | 11 |
| 36 normal positions | 36 | 0 | 0 | 0 | 0 |

Unlimited Master made a substantive play in two of the paused positions
and took an empty action in the other nine. The held implementation
substituted an empty action for a substantive play in 21 of the 30
timeout positions. In a separate payment probe at the 19 positions
where the revised policy chose a different substantive play, all 19
budgeted plays debited more mana from the acting player's committed pool.
This measures immediate mana paid and omits future costs and other
resources. The timeout sample's median budgeted CPU time was 1.21
seconds, with a maximum elapsed time of 1.63 seconds. The result
identifies a cutoff availability problem at this setting. Agreement
and spending on isolated positions do not measure win rate. Keep the
setting held for playing-strength evaluation.

## Proposed playing-strength comparison

Freeze the tested revision, worker policy, decks and seeds before issuing
one new plan. Play single games with the nine admitted decks, one mirror
deck per matchup, both seat orientations, and the same shuffle seed
within each pair. Use twelve new seeds, `2026112501` through
`2026112512`, for 216 games. The candidate is Master with 128 planning
nodes and a 1,000 ms cooperative deadline per decision. The other seat is
the same Master revision with both limits disabled. Use the same engine
limits, trace, exact action replay and selected SQLite parity checks as
the strength harness. Clock expiry is part of the policy. Replay verifies
the recorded actions and state transitions using the pinned inputs.

Score wins as 1 and draws as 0.5, and report both bounds by putting all
unresolved games at 0 or 1 in the respective bound. A budget pause without
a checked action ends that game as unresolved. For the proposed gate,
require a lower score bound of at least 0.45 and a lower 95% interval
endpoint strictly above 0.40, using the adverse bound for unresolved
games. Resample whole seed labels with all nine decks and both seats
together, 2,000 times with seed `271828`. Replay or parity failures
invalidate the experiment. Report per-deck scores, terminal and unresolved
counts, cutoff counts, retained decisions, and CPU and elapsed latency.
The result applies to this fixed deck set and budget configuration.

Eight one-core workers at 2 GiB each need 16 GiB available to the workers
plus controller headroom. The 156 resolved unlimited-Master mirror games
in the earlier strength experiment averaged about 424 seconds per cell,
including verification. Applying that rate to 216 games gives 25.4
worker-hours and about 3.2 hours with ideal eight-way utilization. The
estimate excludes timed-out cells. At 600 worker-seconds/game, allow 36
worker-hours and about 4.5 ideal elapsed hours. At the 6,000 s
cell ceiling the total can reach 360 worker-hours. Check the actual
registry balance, reserve in-flight capacity and publish unresolved
counts if the approved campaign budget stops launches. This experiment
has no issued plan or run.
