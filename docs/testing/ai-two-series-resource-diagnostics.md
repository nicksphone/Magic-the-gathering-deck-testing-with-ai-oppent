# Two-Series Resource Diagnostics

This is a diagnostic on exact source
`2d106588ace24587b7b04f3719ba90606ab47017`, not a completed matchup matrix or
AI-strength result. The once-only execution started at 2026-10-15 11:07:24 UTC
and ended at 11:25:17 UTC with exit 3. No restart, resource-cap increase,
forced outcome, learned-data promotion or policy-weight change occurred.

## Scope And Results

Both selected rows retain Strong, best-of-three, 6,000 ticks, fixed boards,
original physical seats/seeds and all fourteen resource limits. Each BO3 has
one shared 600-second cooperative deadline, not a new budget for each game.

| Series | Physical Seats | Root Seed | Actual Result |
| --- | --- | --- | --- |
| 45 | Ramp / Dimir Control | 590217180 | Game 1 stops at `game_log`: 1,130 accepted ticks, turn 39, 439.179 seconds; no winner. |
| 55 | Midrange / Drain Deck | 1706798304 | Game 1 ends naturally with seat 2 winning after 421 ticks and 113.178 seconds. Game 2 stops at `deadline` after 261 accepted ticks and 490.667 seconds. No series winner. |

Both series remain resource-limited. The original matrix denominator stays
110; the other 108 rows are outside this diagnostic, not discarded or newly
resolved. Partial-game quality is unavailable, not zero. The current result
does not retroactively establish causes for the older `2b9f3a60` matrix.

## Measured Boundaries

The bounded observer produces nine aggregate stage buckets and no pending
stage. Series 55 game 2 records 451.051 seconds in action selection, versus
34.296 in checked action application and 2.278 in legal-move generation.
Its longest action-selection call is 40.382 seconds. These aggregates locate
a stage, not an individual hot function; they do not prove a DB or host-load
cause. Observer overhead is included, and this is not matched A/B timing.

The accepted series 45 log contains 4,127,410 logical UTF-8 bytes. The
4,194,304-byte game-log limit also reserves 65,536 bytes for action growth and
the proposed trace. Escaped JSON receipt bytes and the duplicated private
record wrapper are different measures, not violations of that logical cap.
Speeding up an otherwise identical accepted trace cannot alone prevent the
same log-cap stop. Any trace-layout or accounting change needs explicit
lossless-output and finite-budget validation, not an unreported exemption.

The shared deadline is cooperative: series 55's measured 604.108 seconds
includes an overrun before the next check and evidence work. This is not a
fresh game-2 budget or a hard per-call preemption guarantee.

## Preservation

All three private game receipts match their original raw-log JSON byte slices,
lengths and hashes. No body is published. All 3,317 source files and 4,160
runtime files remain unchanged. The single setup-only memory SQL connection
closes before games; no physical database, application startup, provider or
network access occurs. Terminal metadata reports zero open writers, live
threads or policy denials. Known supervised processes and their group end;
direct checks of all seven existing runtime files find no open handles.

## Completed Function Profile

A separate once-only profile ran from 12:04:44 to 12:15:52 UTC on October 15,
with the same source, limits and shared BO3 clock. The first game's hash,
winner, 421 accepted ticks and turn 14 exactly match the reference above.
Only second-game action selection was profiled. That game stops on the
deadline after 247 accepted ticks, without a winner; exit 3 remains diagnostic,
not a resolved series or a completed matrix.

The 248 measured chooser calls consume 489.153 seconds. Nested cumulative
measurements identify `_winning_self_removal_action` (454.800 seconds),
`simulation_checked_action` (430.069), `_spell_payment_plan` (389.994),
`_plan_payment` (389.931) and `deepcopy` (356.322). These overlapping times
must not be summed. The exported profile contains only 30 pinned function
locations, counts and timings, with no arguments, locals, binary profile or
call graph. Profiling overhead is included, so this is not a matched
uninstrumented speed comparison or evidence of improved AI strength.

Source and dependency inventories remain unchanged, setup SQL closes and
terminal metadata records no writers, live threads or denials. The supervised
processes end and direct checks of six actual output files find no handles.
Private game evidence is archived privately, not committed as public fixtures.

The next implementation target is unnecessary work inside recursive payment
planning, with exact payment decisions and event traces preserved. The separate
trace audit also found that trace count/positions participate in decision-view
memoization: silently dropping entries is not a representation-only change.
Neither finding authorizes higher caps, pruned payment candidates, changed
winners, learning from partial games or Phase 3 sign-off.
