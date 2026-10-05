# Strategic Pending Announcements

## Observed Failure

Current canonical Drain/Tribal templates reproduce repeated passes despite a
payable creature and an empty friendly board. Replay of 236 recorded checked
actions matches hand, battlefield, turn and step at every prefix to the first
failure. A fresh Master agent returns a strategic-planner pass at that position;
spell materialization and cost legality are valid.

The strategic evaluator charges a spell's lost hand card while its useful
permanent remains on the stack. This undervalues supported pending development
at a shallow horizon, rather than proving the creature or deck is unusable.

## Shared Repair

Value supported unanswered declared effects through the existing rules-engine
projection and settlement path. Keep the real search node, its priority and
response branches intact. Unknown choices, library changes and changes to the
opponent's hidden hand reject that known forecast; no hidden card is optimized.
This is a horizon estimate, not certainty that the opponent passes or that a
temporary effect remains forever. No card name determines the policy.

## Evidence and Limits

The observed position plus six canonical creature families across five styles/
both seats initially produce 51 failures/10 passes. With shared valuation, the
latest selection passes 468 checks, including checked paid execution, actor/
prefix equivalence, real counter responses, hidden-zone guard and original-state
immutability. The unoptimized actor-reference uses the same new valuation but
retains its independent replaying recurrence; tests were not removed or loosened.

Full exact-source qualification, broad AI quality and before/after natural-game
traces are pending. Effects with unresolved choices or unknown future card
contents remain conservative, not fully strategic. One observed Tribal upkeep
decision takes roughly 19 seconds without profiling; a fresh-agent cProfile
reconstruction matches the recorded action but incurs profiling overhead.
Strategic stack search is its dominant cost. Further optimization needs measured
decision parity and mutation-safe query reuse, not skipped legality or rule work.
