"""Real, canonical tap triggers must work for costs and effects alike."""
import pytest

from effects.handlers import tap_card
from rules_engine.casting_resources import apply_resource_payment, resource_payment
from tests.test_cast_resource_payments import ROWS, add, cost, position
from tests.test_ai_recurring_engines import resolve


@pytest.mark.parametrize('seat', [1, 2])
def test_convoke_emits_self_tap_trigger_once(seat):
    state, spell = position(seat, 'March of the Multitudes')
    emmara = add(state, 'Emmara, Soul of the Accord', seat, cards=ROWS)
    payment = resource_payment(state, seat, spell, cost(spell, 1), {
        'convoke': [{'card_id': emmara.id, 'pay_as': 'W'}]})
    assert apply_resource_payment(state, seat, spell, payment)
    assert len(state.stack) == 1
    tap_card(state, 3-seat, {'target_card_id': emmara.id})
    assert len(state.stack) == 1
    state = resolve(state)
    tokens = [state.cards[cid] for cid in state.players[seat].battlefield if cid != emmara.id]
    assert len(tokens) == 1
    token = tokens[0]
    assert (token.name, token.power, token.toughness, token.colors) == ('Soldier', 1, 1, ['W'])
    assert 'lifelink' in [keyword.lower() for keyword in token.keywords]


@pytest.mark.parametrize('seat', [1, 2])
def test_effect_tap_is_not_a_new_event_when_already_tapped(seat):
    state, _ = position(seat, 'Siege Wurm')
    emmara = add(state, 'Emmara, Soul of the Accord', seat, cards=ROWS)
    tap_card(state, 3-seat, {'target_card_id': emmara.id})
    assert len(state.stack) == 1
    tap_card(state, 3-seat, {'target_card_id': emmara.id})
    assert len(state.stack) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_tap_cost_trigger_waits_for_original_spell(seat):
    from rules_engine.events import flush_staged_triggers
    from rules_engine.stack_engine import add_to_stack
    state, spell = position(seat, 'March of the Multitudes')
    emmara = add(state, 'Emmara, Soul of the Accord', seat, cards=ROWS)
    state.trigger_staging = True
    state.trigger_staging_event = 'casting_cost'
    payment = resource_payment(state, seat, spell, cost(spell, 1), {
        'convoke': [{'card_id': emmara.id, 'pay_as': 'W'}]})
    assert apply_resource_payment(state, seat, spell, payment)
    assert not state.stack and len(state.staged_triggers) == 1
    add_to_stack(state, spell.id, seat, spell.name, 'create_token', {'amount': 1})
    flush_staged_triggers(state)
    assert [item.source_card_id for item in state.stack] == [spell.id, emmara.id]


@pytest.mark.parametrize('seat', [1, 2])
def test_attack_and_crew_both_emit_tap_event(seat):
    from game_state.state import Step
    from rules_engine.combat import declare_attackers
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    import json
    from pathlib import Path
    cards = {row['name']: row for row in json.loads(
        (Path(__file__).parent / 'fixtures/type_effect_lifecycle.json').read_text())}
    state, _ = position(seat, 'Siege Wurm')
    emmara = add(state, 'Emmara, Soul of the Accord', seat, cards=ROWS)
    emmara.summoning_sick = False
    state.step = Step.DECLARE_ATTACKERS
    declare_attackers(state, [emmara.id])
    assert len(state.stack) == 1 and state.stack[-1].source_card_id == emmara.id
    state, _ = position(seat, 'Siege Wurm')
    emmara = add(state, 'Emmara, Soul of the Accord', seat, cards=ROWS)
    vehicle = add(state, "Smuggler's Copter", seat, cards=cards)
    result = checked_action(state, RulesEngine(), seat, {
        'type': 'crew', 'card_id': vehicle.id, 'crew_card_ids': [emmara.id]})
    assert [item.source_card_id for item in result.stack] == [vehicle.id, emmara.id]
    assert result.cards[emmara.id].tapped and not result.trigger_staging
