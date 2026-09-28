# Combat Trigger Timing Audit (2026-09-28)

## Rule and reproduced gap

The [2026 Comprehensive Rules, 510.3a](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf) require abilities triggered by combat damage and by the state-based actions afterward to be put on the stack before the active player receives priority; their trigger times do not prescribe separate stack groups.

An isolated real-card fixture has Ohran Frostfang and Grim Haruspex on Player A's battlefield. Grizzly Bears hits Player B while Centaur Courser and Hill Giant deal lethal combat damage to each other. The engine produces both Frostfang's player-hit trigger and Haruspex's creature-death trigger, but `pending_trigger_order` is `None`: they were inserted separately. The strict expected-failure regression is `test_damage_and_death_triggers_share_one_order_choice` in `backend/tests/test_combat_damage_assignment.py`. Grim Haruspex is face up; this fixture does not exercise its currently unsupported Morph ability.

From `backend`, reproduce with `./.venv/bin/python -m pytest -q -rx tests/test_combat_damage_assignment.py -k damage_and_death_triggers_share_one_order_choice`. It should report `1 xfailed` until the staging fix is implemented; an unexpected pass fails because the marker is strict.

Validation in a disposable tracked-source checkout: the focused combat file reports 22 passed and 1 xfailed; the full backend suite reports 994 passed and 1 xfailed. The failure was also observed without the marker in an isolated reproduction (`pending_trigger_order` was `None`, with both triggered abilities already on the stack). These checks do not cover a browser continuation for the mixed trigger group.

## Current path

- `rules_engine/combat.py:_combat_damage_step` batches damage events and immediately inserts their triggers.
- `rules_engine/combat.py:_resolve_damage_step` then calls `_remove_dead_creatures`, which emits leave/death events separately. A pending damage-trigger order can be bypassed or superseded by later choices.
- `rules_engine/state_based_actions.py` has another lethal-creature batch path, so a combat-only ordering workaround would diverge from ordinary state-based actions.
- `game_state/state.py` and `game_state/serializers.py` persist pending choices, but not a durable cross-event trigger-staging transaction for this boundary. A human death-replacement choice can interrupt removal, so a local temporary list alone would lose context on restart.

## Required fix and gate

Stage triggers from the damage event and all resulting state-based-action passes, including leave/death events, without inserting any on the stack early. After all applicable replacement choices and state-based actions finish, offer one APNAP trigger-order window per controller, then insert the ordered triggers and grant priority. The staged state must survive snapshots, backend restart and human replacement choices. Reuse one mechanism for combat and other state-based-action entry points rather than special-casing Ohran Frostfang or Grim Haruspex.

Acceptance must remove the `xfail` marker and pass its fixture, plus tests for both controllers' triggers, multiple lethal creatures, a human death-replacement pause/resume, snapshot restart, targeted death triggers, first/double-strike damage windows, and no stack insertion or priority before state-based actions finish. A full backend suite, browser choice path and deterministic replay should then pass. The current two-game replay and 994-test suite are not evidence for this rule boundary.
