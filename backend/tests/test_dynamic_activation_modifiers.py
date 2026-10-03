"""Canonical dynamic costs; constructed boards are not tournament decklists."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.activation_modifiers import activation_modifier_gaps, parse_activation_modifier
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.costs import activated_cost_available
from rules_engine.engine import RulesEngine
from rules_engine.hooks import CostContext, apply_cost_modifiers
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from tests.test_activation_modifiers import board, add, requirement
from tests.test_ai_recurring_engines import add as raw_add, resolve
from tests.test_ability_suppression import add as suppression_add
from tests.test_api_input_contracts import game, persist, rejected, snapshot

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/dynamic_activation_modifiers.json').read_text())}


def dynamic(state, name, seat):
    card = raw_add(state, name, seat, cards=ROWS)
    card.summoning_sick = False
    return card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bonus', [-4, 0, 1, 5])
def test_source_power_is_live_controller_relative_and_preserves_colored_mana(seat, bonus):
    state = board(seat)
    source = dynamic(state, 'Agatha of the Vile Cauldron', seat)
    mage = add(state, 'Azure Mage', seat)
    source.counters['__eot_power'] = bonus
    assert requirement(state, mage, '{3}{U}')['generic'] == max(0, 3-max(0, 1+bonus))
    assert requirement(state, mage, '{3}{U}')['U'] == 1
    assert requirement(state, mage, '{3}')['generic'] == max(1, 3-max(0, 1+bonus))
    assert requirement(state, mage, '')['generic'] == 0
    other = add(state, 'Azure Mage', 3-seat)
    assert requirement(state, other, '{3}{U}')['generic'] == 3
    hand = add(state, 'Azure Mage', seat, Zone.HAND)
    assert requirement(state, hand, '{3}{U}', 'cycling')['generic'] == 3
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert requirement(restored, restored.cards[mage.id], '{3}{U}') == requirement(state, mage, '{3}{U}')


@pytest.mark.parametrize('seat', [1, 2])
def test_power_counters_source_departure_and_suppression(seat):
    state = board(seat)
    source = dynamic(state, 'Agatha of the Vile Cauldron', seat)
    mage = add(state, 'Azure Mage', seat)
    source.counters['+1/+1'] = 2
    assert requirement(state, mage, '{3}{U}')['generic'] == 0
    source.zone = Zone.GRAVEYARD
    assert requirement(state, mage, '{3}{U}')['generic'] == 3
    source.zone = Zone.BATTLEFIELD
    suppression_add(state, 'Humility', 3-seat)
    assert requirement(state, mage, '{3}{U}')['generic'] == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_attachment_power_and_changed_controller_bind_live_state(seat):
    from tests.test_aura_costs import add as aura_add
    state = board(seat)
    source = dynamic(state, 'Agatha of the Vile Cauldron', seat)
    mage = add(state, 'Azure Mage', seat)
    aura = aura_add(state, 'Rancor', seat)
    aura.attached_to = source.id
    assert requirement(state, mage, '{3}{U}')['generic'] == 0
    source.controller = 3-seat
    assert requirement(state, mage, '{3}{U}')['generic'] == 3
    source.controller = seat
    aura.zone = Zone.GRAVEYARD
    assert requirement(state, mage, '{3}{U}')['generic'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_dynamic_discount_actual_checked_payment_and_draw_resolution(seat):
    state = board(seat)
    dynamic(state, 'Agatha of the Vile Cauldron', seat).counters['+1/+1'] = 2
    mage = add(state, 'Azure Mage', seat)
    state.players[seat].mana_pool['U'] = 1
    assert activated_cost_available(state, seat, mage.id, '{3}{U}')
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'activate_ability' and m['card_id'] == mage.id)
    result = checked_action(state, RulesEngine(), seat, move)
    assert result.players[seat].mana_pool['U'] == 0
    assert len(resolve(result).players[seat].hand) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('active_is_owner', [False, True])
@pytest.mark.parametrize('kind', ['activated', 'cycling', 'crew', 'mana'])
def test_turn_tax_actor_and_mana_exception(seat, active_is_owner, kind):
    state = board(seat)
    source = dynamic(state, 'Tithe Taker', 3-seat)
    mage = add(state, 'Azure Mage', seat)
    state.active_player = source.controller if active_is_owner else seat
    expected = int(active_is_owner and kind != 'mana')
    assert requirement(state, mage, '', kind)['generic'] == expected
    assert requirement(state, source, '', kind)['generic'] == 0
    source.zone = Zone.GRAVEYARD
    assert requirement(state, mage, '', kind)['generic'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_paired_turn_spell_tax_hint_payment_and_suppression(seat):
    state = board(seat)
    owner = 3-seat
    dynamic(state, 'Tithe Taker', owner)
    state.active_player = owner
    context = apply_cost_modifiers(CostContext(player_id=seat, card_name='Azure Mage',
        mana_cost='{1}{U}', state=state, spell_types={'Creature'}))
    assert context.generic_increase == 1
    state.players[seat].mana_pool.update(C=1, U=1)
    assert not can_pay_with_pool_and_lands(state, seat, '{1}{U}', spell_types={'Creature'})
    before = serialize_match_snapshot(state)
    assert not auto_pay_cost(state, seat, '{1}{U}', spell_types={'Creature'})
    assert serialize_match_snapshot(state) == before
    state.players[seat].mana_pool['C'] = 2
    assert auto_pay_cost(state, seat, '{1}{U}', spell_types={'Creature'})
    assert state.players[seat].mana_pool['C'] == state.players[seat].mana_pool['U'] == 0
    mage = add(state, 'Azure Mage', seat)
    assert requirement(state, mage, '{3}{U}')['generic'] == 4
    suppression_add(state, 'Humility', seat)
    assert requirement(state, mage, '{3}{U}')['generic'] == 3
    assert apply_cost_modifiers(CostContext(player_id=seat, card_name='Azure Mage',
        mana_cost='{1}{U}', state=state, spell_types={'Creature'})).generic_increase == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('modifier', ['power', 'turn'])
def test_http_dynamic_payment_rejection_and_sqlite_resume(game, seat, modifier):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = board(seat)
    mage = add(state, 'Azure Mage', seat)
    if modifier == 'power':
        dynamic(state, 'Agatha of the Vile Cauldron', seat).counters['+1/+1'] = 2
        required = 0
    else:
        dynamic(state, 'Tithe Taker', 3-seat)
        state.active_player = 3-seat
        required = 4
    state.players[seat].mana_pool['C'] = max(0, required-1)
    state.id = match.state.id
    match.state = state
    persist(match)
    action = {'type': 'activate_ability', 'card_id': mage.id, 'ability_index': 0, 'targets': {}}
    rejected(client, match, action, seat)
    match.state.players[seat].mana_pool.update(C=required, U=1)
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert match.state.players[seat].mana_pool['C'] == match.state.players[seat].mana_pool['U'] == 0
    committed = snapshot(match)[0]
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id])[0] == committed


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_instant_cast_stacks_turn_taxes_and_locks_payment(seat):
    from tests.test_pending_removal import add_card
    state = board(seat)
    owner = 3-seat
    dynamic(state, 'Tithe Taker', owner)
    second = dynamic(state, 'Tithe Taker', owner)
    state.active_player = owner
    spell = add_card(state, 'Lightning Bolt', Zone.HAND, seat)
    state.players[seat].mana_pool.update(R=1, C=1)
    action = {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_player': owner}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    second.zone = Zone.GRAVEYARD
    state.players[owner].battlefield.remove(second.id)
    state.players[owner].graveyard.append(second.id)
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.players[seat].mana_pool['R'] == result.players[seat].mana_pool['C'] == 0
    assert result.cards[spell.id].mana_cost == '{R}'
    assert resolve(result).players[owner].life == 17


def test_unsupported_amount_references_and_ability_specific_discounts_stay_visible():
    clause = "activated abilities of creatures you control cost {x} less to activate, where x is another creature's power"
    assert parse_activation_modifier(clause, 'Agatha of the Vile Cauldron') is None
    assert activation_modifier_gaps(clause, 'Agatha of the Vile Cauldron')
    assert activation_modifier_gaps('{5}{U}, {T}: Draw a card. This ability costs {1} less to activate for each other artifact you control.')
    assert activation_modifier_gaps('During combat, abilities your opponents activate cost {1} more to activate.')
    for row in ROWS.values():
        assert not activation_modifier_gaps(row['oracle_text'], row['name'])
