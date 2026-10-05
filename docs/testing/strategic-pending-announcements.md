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

Frozen `b8f59fb` passes 8,294 tests in all 334 recursive backend files with 653
matching hashes and absent initial databases, plus the full browser harness in
all three BO3 modes. This qualifies the bounded implementation, not AI strength.
The first paired-seat sample casts on turn 9 instead of passing, but declines
the payable body on later turns; wider trace review remains necessary.

A separate turn-11 reconstruction validates 289 checked prefixes and exposes
absolute stack-score double counting. Return a response delta relative to the
current projected position; both-seat no-response/score-offset fixtures and
real harmful counter responses cover the shared arithmetic. Seven initial
failures are repaired, 129 selected checks pass, and nine expanded contracts
pass (overlapping selections). Exact `4aaf87a` qualifies 8,303 backend tests in
all 335 files once with 656 matching hashes/absent initial databases, plus the
complete browser gate in all three BO3 modes. The completed forward sample
develops four creatures rather than one and still loses to Tribal; there are
no invalid-cost/target diagnostic lines. Broader pair/seat and cross-archetype
trace review is unfinished, not implied by qualification. No card-specific
forcing or balance adjustment is used.

Effects with unresolved choices or unknown future card
contents remain conservative, not fully strategic. One observed Tribal upkeep
decision takes roughly 19 seconds without profiling; a fresh-agent cProfile
reconstruction matches the recorded action but incurs profiling overhead.
Strategic stack search is its dominant cost. Further optimization needs measured
decision parity and mutation-safe query reuse, not skipped legality or rule work.
