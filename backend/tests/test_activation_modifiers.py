"""Canonical activation taxes/reductions; fixtures are not competitive decks."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.activation_modifiers import activation_cost_view, payable_crew_group
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.costs import activated_cost_available, apply_activated_costs
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands, nonland_mana_outputs
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve
from tests.test_combat_domain_temporary_costs import add as combat_add, zero_mana
from tests.test_api_input_contracts import game, persist, rejected, snapshot

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/activation_modifiers.json').read_text())}


def add(state, name, seat=1, zone=Zone.BATTLEFIELD):
    card = raw_add(state, name, seat, zone, cards=ROWS)
    card.summoning_sick = False
    return card


def board(seat=1):
    state = fixture()
    zero_mana(state)
    state.priority_player = state.active_player = seat
    return state


def requirement(state, source, cost, kind='activated'):
    return activation_cost_view(state, source.controller, source.id, cost, ability_kind=kind)['requirements'][0]


@pytest.mark.parametrize('seat', [1, 2])
def test_controller_reductions_colored_floor_stacking_and_source_departure(seat):
    state = board(seat)
    mage = add(state, 'Azure Mage', seat)
    other = add(state, 'Azure Mage', 3-seat)
    grounds = add(state, 'Training Grounds', seat)
    assert requirement(state, mage, '{3}{U}')['generic'] == 1
    assert requirement(state, other, '{3}{U}')['generic'] == 3
    add(state, 'Heartstone', 3-seat)
    assert requirement(state, mage, '{3}{U}')['generic'] == 0
    assert requirement(state, mage, '{3}{U}')['U'] == 1
    assert requirement(state, other, '{3}{U}')['generic'] == 2
    assert requirement(state, mage, '')['generic'] == 0
    grounds.zone = Zone.GRAVEYARD  # Stale battlefield-list entries do not apply.
    assert requirement(state, mage, '{3}{U}')['generic'] == 2
    resumed = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert requirement(resumed, resumed.cards[mage.id], '{3}{U}')['generic'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_nonmana_tax_prices_zero_but_does_not_tax_mana_or_spells(seat):
    state = board(seat)
    elf = add(state, 'Llanowar Elves', seat)
    add(state, 'Suppression Field', 3-seat)
    assert requirement(state, elf, '')['generic'] == 2
    assert requirement(state, elf, '', 'mana')['generic'] == 0
    assert nonland_mana_outputs(state, elf.id, elf) == {'G': 1}
    assert not activated_cost_available(state, seat, elf.id, '')
    assert can_pay_with_pool_and_lands(state, seat, '{G}', payment_kind='spell')


@pytest.mark.parametrize('seat', [1, 2])
def test_taxed_mana_source_never_funds_its_own_cost_and_manual_payment_works(seat):
    state = board(seat)
    elf = add(state, 'Llanowar Elves', seat)
    rays = add(state, 'Oppressive Rays', 3-seat)
    rays.attached_to = elf.id
    assert nonland_mana_outputs(state, elf.id, elf) == {}
    assert not can_pay_with_pool_and_lands(state, seat, '{G}')
    action = {'type': 'tap_nonland_for_mana', 'card_id': elf.id, 'color': 'G'}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    state.players[seat].mana_pool['C'] = 3
    assert nonland_mana_outputs(state, elf.id, elf, free_only=False) == {'G': 1}
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.cards[elf.id].tapped
    assert result.players[seat].mana_pool['C'] == 0
    assert result.players[seat].mana_pool['G'] == 1


def test_attached_artifact_reduction_and_tap_sacrifice_source_reservation():
    state = board()
    stone = add(state, 'Mind Stone')
    assert not activated_cost_available(state, 1, stone.id, '{1}, {T}, Sacrifice this artifact')
    assert not apply_activated_costs(state, 1, stone.id, '{1}, {T}, Sacrifice this artifact')
    assert not stone.tapped and stone.zone == Zone.BATTLEFIELD
    aura = add(state, 'Power Artifact')
    aura.attached_to = stone.id
    assert requirement(state, stone, '{3}')['generic'] == 1
    assert requirement(state, stone, '{1}')['generic'] == 1
    assert requirement(state, stone, '')['generic'] == 0
    combat_add(state, 'Forest')
    assert activated_cost_available(state, 1, stone.id, '{1}, {T}, Sacrifice this artifact')
    assert apply_activated_costs(state, 1, stone.id, '{1}, {T}, Sacrifice this artifact')
    assert stone.zone == Zone.GRAVEYARD


def test_creature_reduction_does_not_apply_to_hand_abilities_but_global_tax_does():
    state = board()
    mage = add(state, 'Azure Mage', zone=Zone.HAND)
    add(state, 'Training Grounds')
    assert requirement(state, mage, '{3}{U}', 'cycling')['generic'] == 3
    add(state, 'Suppression Field', 2)
    assert requirement(state, mage, '{3}{U}', 'cycling')['generic'] == 5
    assert requirement(state, mage, '{2}', 'ninjutsu')['generic'] == 4


def test_floored_and_unfloored_reductions_can_reach_zero_without_removing_colors():
    from rules_engine.mana import _payment_requirements
    assert _payment_requirements('{3}', False, 0, 1, 0, floored_reductions=[(1, 2)])[0]['generic'] == 0
    assert _payment_requirements('{0}', False, 0, 0, 0, floored_reductions=[(1, 2)])[0]['generic'] == 0
    req = _payment_requirements('{X}{U}{C}{S}', False, 3, 0, 2, floored_reductions=[(1, 9)])[0]
    assert req['generic'] == 0 and req['U'] == req['C'] == req['S'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_draw_ability_is_priced_resolves_and_preserves_original(seat):
    state = board(seat)
    mage = add(state, 'Azure Mage', seat)
    add(state, 'Training Grounds', seat)
    state.players[seat].mana_pool.update({'C': 1, 'U': 1})
    original = serialize_match_snapshot(state)
    action = {'type': 'activate_ability', 'card_id': mage.id, 'ability_index': 0, 'targets': {}}
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == original
    assert result.players[seat].mana_pool['C'] == result.players[seat].mana_pool['U'] == 0
    assert len(result.stack) == 1
    assert len(resolve(result).players[seat].hand) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_http_tax_rejection_and_payment_are_atomic_and_resume(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = board(seat)
    mage = add(state, 'Azure Mage', seat)
    add(state, 'Suppression Field', 3-seat)
    state.players[seat].mana_pool.update({'C': 3, 'U': 1})
    state.id = match.state.id
    match.state = state
    persist(match)
    action = {'type': 'activate_ability', 'card_id': mage.id, 'ability_index': 0, 'targets': {}}
    rejected(client, match, action, seat)
    match.state.players[seat].mana_pool['C'] = 5
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert match.state.players[seat].mana_pool['C'] == match.state.players[seat].mana_pool['U'] == 0
    committed = snapshot(match)[0]
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id])[0] == committed


def test_coverage_recognizes_supported_clauses_but_not_unknown_scopes_or_floors():
    for name, row in ROWS.items():
        assert 'activation cost modifiers' not in known_unsupported_mechanics(row['oracle_text'], card_name=name)
    for text in (
        'Activated abilities of creatures with magnet counters cost {2} less to activate.',
        "Activated abilities cost {2} less to activate. This effect can't reduce the mana in that cost to less than two mana.",
    ):
        assert 'activation cost modifiers' in known_unsupported_mechanics(text)


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_ai_crew_suggestion_reserves_crew_creatures_for_mana_payment(difficulty):
    from ai.agent import AIAgent
    from tests.test_vehicles import _vehicle_state
    state = _vehicle_state()
    zero_mana(state)
    add(state, 'Suppression Field', 2)
    elf = add(state, 'Llanowar Elves')
    state.players[1].mana_pool['C'] = 1
    assert payable_crew_group(state, 1, 'vehicle', 1, ['crew', elf.id]) == ['crew']
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move['type'] == 'crew')
    action = AIAgent(difficulty)._materialize_action(state, move, 1)
    assert action['crew_card_ids'] == ['crew']
    result = checked_action(state, RulesEngine(), 1, action)
    assert result.cards['crew'].tapped and result.cards[elf.id].tapped
    assert result.players[1].mana_pool['C'] == result.players[1].mana_pool['G'] == 0
    assert 'Creature' in resolve(result).cards['vehicle'].types


def test_crew_tax_cannot_tap_same_mana_creature_for_both_costs():
    from tests.test_vehicles import _vehicle_state
    state = _vehicle_state()
    zero_mana(state)
    state.cards['crew'].tapped = True
    add(state, 'Suppression Field', 2)
    elf = add(state, 'Llanowar Elves')
    state.players[1].mana_pool['C'] = 1
    assert payable_crew_group(state, 1, 'vehicle', 1, [elf.id]) is None
    assert not any(move['type'] == 'crew' for move in RulesEngine().legal_moves(state, 1))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'crew', 'card_id': 'vehicle', 'crew_card_ids': [elf.id]})
    assert serialize_match_snapshot(state) == before


def test_loyalty_tax_is_paid_separately_from_loyalty_counter_cost():
    from tests.test_declaration_limits import add as limit_add
    state = board()
    walker = limit_add(state, 'Ugin, the Spirit Dragon')
    walker.loyalty = 7
    add(state, 'Suppression Field', 2)
    assert not any(move['type'] == 'activate_loyalty' for move in RulesEngine().legal_moves(state, 1))
    state.players[1].mana_pool['C'] = 2
    result = checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty', 'card_id': walker.id,
        'ability_index': 0, 'targets': {'target_player': 2}})
    assert result.cards[walker.id].loyalty == 9
    assert result.players[1].mana_pool['C'] == 0
    assert resolve(result).players[2].life == 17


def test_cycling_tax_is_charged_on_the_real_hand_action():
    from tests.test_cycling import _state_with_cycler
    state, cid = _state_with_cycler()
    zero_mana(state)
    add(state, 'Suppression Field', 2)
    # One untapped Island plus one pooled mana cannot pay the modified three.
    state.players[1].mana_pool['C'] = 1
    assert not any(move['type'] == 'cycle_card' for move in RulesEngine().legal_moves(state, 1))
    state.players[1].mana_pool['C'] = 2
    result = checked_action(state, RulesEngine(), 1, {'type': 'cycle_card', 'card_id': cid, 'targets': {}})
    assert result.cards[cid].zone == Zone.GRAVEYARD
    assert result.players[1].mana_pool['C'] == result.players[1].mana_pool['U'] == 0
    before = len(result.players[1].hand)
    assert len(resolve(result).players[1].hand) == before+1


def test_reduction_source_ability_loss_and_unknown_floor_do_not_leak():
    from tests.test_ability_suppression import add as suppression_add
    state = board()
    mage = add(state, 'Azure Mage')
    grounds = add(state, 'Training Grounds')
    assert requirement(state, mage, '{3}{U}')['generic'] == 1
    # Removing an unsupported floor must not turn it into an unbounded discount.
    grounds.oracle_text = grounds.oracle_text.replace('one mana', 'two mana')
    assert requirement(state, mage, '{3}{U}')['generic'] == 3
    grounds.zone = Zone.GRAVEYARD
    zirda = add(state, 'Zirda, the Dawnwaker')
    assert requirement(state, mage, '{3}{U}')['generic'] == 1
    suppression_add(state, 'Humility', 2)
    assert requirement(state, mage, '{3}{U}')['generic'] == 3


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_ai_announced_x_respects_tax_and_tap_source_reservations(difficulty):
    from ai.agent import AIAgent
    state = board()
    source = combat_add(state, 'War Tax')
    add(state, 'Suppression Field', 2)
    state.players[1].mana_pool.update({'U': 1, 'C': 4})
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move['type'] == 'activate_ability')
    # Materialization cannot trust a provisional X from a printed-cost budget.
    move['targets'] = {'x_value': 4}
    action = AIAgent(difficulty)._materialize_action(state, move, 1)
    assert action['targets']['x_value'] == 2
    result = checked_action(state, RulesEngine(), 1, action)
    assert result.players[1].mana_pool['C'] == result.players[1].mana_pool['U'] == 0


def test_equip_unfloored_discount_can_follow_zirda_floor():
    equipment_rows = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/equip_costs.json').read_text())}
    state = board()
    add(state, 'Zirda, the Dawnwaker')
    add(state, 'Auriok Steelshaper')
    equipment = raw_add(state, 'Bonesplitter', cards=equipment_rows)
    target = add(state, 'Llanowar Elves')
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move['type'] == 'equip']
    assert moves
    result = checked_action(state, RulesEngine(), 1, {'type': 'equip', 'card_id': equipment.id, 'target_card_id': target.id})
    assert resolve(result).cards[equipment.id].attached_to == target.id
