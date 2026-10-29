# Large-Board Conditional Combat Forecast

The strategic planner previously valued some declared large-board attacks at
their tapped, pre-damage prefix. Attacker selection could correctly propose an
attack while the complex-board planner preferred passing because its combat
horizon was unavailable.

`AIAgent._forecast_strategic_combat` now reuses the existing blocker heuristic
when the board exceeds the exhaustive search's four-attacker/five-blocker
cardinality limits. This fallback is limited to sixteen attackers and eight
blockers. It does not expand the exhaustive tree or replace small-board search
exhaustion with a guessed optimum. Its block declaration passes through
`simulation_checked_action`; illegal assignments, including unpayable taxes,
leave the forecast unknown rather than being silently trimmed by the engine.

This is a **conditional heuristic projection**, not an exhaustive-blocking,
unanswered-win, safety, or lethal certificate. Different legal blocks and
intervening responses may change its outcome. Existing unsupported-rule,
pending-choice, stack, hidden-zone-change and bounded-resolution checks remain.
Defender restrictions and declaration/payment legality still belong to the
authoritative rules engine. No card-name, archetype-name or power-sum exception
was added, and no action is forced merely because attackers outnumber blockers.

The shared strategic position scorer uses this horizon; the complex-board
planner is not bypassed. The learned Q route still validates and ranks its
checked subset independently. Its declared-combat terminal guard only completes
already-declared defending-side combat; it does not turn this attack-side
heuristic into a terminal label. Existing Q predictions, activation authority,
training data and checkpoints are unchanged. An existing checkpoint is not
qualified for the changed engine by this patch.

`backend/tests/test_ai_large_board_combat.py` uses public canonical Factory
births and explicitly posed boards, not archived private game snapshots. It
covers both seats, larger boards, root/input purity, opaque library order,
cardinality limits, no large-board exhaustive enumeration, small-search failure,
unsupported/pending boundaries, invalid heuristic declarations, unlimited
blocking capacity, legitimate Control waiting, defender restrictions and actual
resolved attack/block taxes. These are bounded mechanism regressions, not full
game or playing-strength certification.
