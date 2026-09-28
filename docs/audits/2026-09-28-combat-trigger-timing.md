# Combat Trigger Timing Audit (2026-09-28)

## Rule and reproduced gap

The [2026 Comprehensive Rules, 510.3a](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf) require abilities triggered by combat damage and by the state-based actions afterward to be put on the stack before the active player receives priority; their trigger times do not prescribe separate stack groups.

An isolated real-card fixture has Ohran Frostfang and Grim Haruspex on Player A's battlefield. Grizzly Bears hits Player B while Centaur Courser and Hill Giant deal lethal combat damage to each other. The engine produces both Frostfang's player-hit trigger and Haruspex's creature-death trigger, but `pending_trigger_order` is `None`: they were inserted separately. The strict expected-failure regression is `test_damage_and_death_triggers_share_one_order_choice` in `backend/tests/test_combat_damage_assignment.py`. Grim Haruspex is face up; this fixture does not exercise its currently unsupported Morph ability.

From `backend`, run `./.venv/bin/python -m pytest -q tests/test_combat_damage_assignment.py -k damage_and_death_triggers_share_one_order_choice`. The original missing order choice is now a passing regression after persisted combat trigger staging.

Original validation in a disposable tracked-source checkout: the focused combat file reported 22 passed and 1 xfailed; the full backend suite reported 994 passed and 1 xfailed. The failure was also observed without the marker in an isolated reproduction (`pending_trigger_order` was `None`, with both triggered abilities already on the stack). Current focused combat coverage passes the former expected failure, APNAP ordering and staged snapshot round-trip; browser and real death-replacement continuation remain open.

## Current path

- `rules_engine/combat.py:_combat_damage_step` batches damage events into a persisted staging window rather than immediately inserting triggers.
- `rules_engine/combat.py:_resolve_damage_step` calls `_remove_dead_creatures`, then applies state-based actions. Event collection preserves damage and leave/death triggers for one flush after the immediate actions.
- `rules_engine/state_based_actions.py` has another lethal-creature batch path, so a combat-only ordering workaround would diverge from ordinary state-based actions.
- `game_state/state.py` and `game_state/serializers.py` now persist staged triggers. The state survives a snapshot round-trip; the complete human death-replacement pause/resume has not yet been verified with a canonical supported card fixture.

## Required fix and gate

The first staging implementation collects damage and immediate leave/death triggers, then offers one APNAP order window. The remaining gate is to prove that all applicable replacement choices and repeated state-based-action passes finish before flushing, including process restart during a real human death-replacement choice. Reuse the staging mechanism for other state-based-action entry points rather than special-casing the two fixture cards.

The `xfail` marker is removed, and focused mixed-trigger, both-controller APNAP and snapshot tests pass. Remaining acceptance requires multiple lethal creatures, a canonical human death-replacement pause/resume, backend process restart, targeted death triggers, first/double-strike windows, and no stack insertion or priority before all state-based actions finish. The full backend suite, browser choice path and deterministic replay must then pass; the original 994-test suite was not evidence for this rule boundary.
