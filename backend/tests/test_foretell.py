"""Canonical keyword, special-action payment and durable casting permissions."""
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.card_faces import exile_permission
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.foretell import hand_costs, can_look, record
from tests.test_ai_recurring_engines import add as raw_add, resolve
from tests.test_variable_mana import clean
from tests.test_api_input_contracts import game, persist

CARDS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/foretell.json').read_text())}
PRINTED = [name for name, card in CARDS.items() if 'Foretell' in (card['keywords'] or [])]


def add(state, name, seat, zone=Zone.HAND):
    return raw_add(state, name, seat, zone, cards=CARDS)


def setup(name='Behold the Multiverse', seat=1):
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, name, seat)
    state.players[seat].mana_pool = {'C': 2}
    return state, source.id


@pytest.mark.parametrize('name', PRINTED)
@pytest.mark.parametrize('seat', [1, 2])
def test_printed_foreTell_special_action_preserves_identity_and_retains_priority(name, seat):
    state, cid = setup(name, seat)
    snapshot = serialize_match_snapshot(state)
    options = hand_costs(state, state.cards[cid], seat)
    assert options[0] and not options[1]
    assert serialize_match_snapshot(state) == snapshot
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    assert not state.stack and state.priority_player == seat
    assert state.cards[cid].exile_face_down and state.cards[cid].zone == Zone.EXILE
    assert state.cards[cid].name == name and state.cards[cid].oracle_text == CARDS[name]['oracle_text']
    assert can_look(state.cards[cid], seat) and not can_look(state.cards[cid], 3 - seat)
    assert record(state.cards[cid])['fixed_costs'] == options[0]
    assert not exile_permission(state, seat, cid)
    assert state.foretells_this_turn[seat] == 1 and state.spells_cast_this_turn[seat] == 0
    assert not any(name in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
def test_exile_views_need_actual_look_permission_and_reveal_foretold_cards_at_game_end(seat):
    state, cid = setup(seat=seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_match(state)['players'][seat]['exile'] == []
    assert serialize_match(state, look_players=[3-seat])['players'][seat]['exile'] == []
    assert serialize_match(state, look_players=[seat])['players'][seat]['exile'][0]['id'] == cid
    state.winner = 3-seat
    assert serialize_match(state)['players'][seat]['exile'][0]['name'] == 'Behold the Multiverse'


@pytest.mark.parametrize('seat', [1, 2])
def test_later_turn_cast_uses_foreTell_cost_and_saved_provenance(seat):
    state, cid = setup(seat=seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state.turn += 1
    state.players[seat].mana_pool = {'C': 1, 'U': 1}
    options = collect_cost_options(state, seat, state.cards[cid])
    assert [(option.id, option.mana_cost) for option in options] == [('foretell_0', '{1}{U}')]
    before = len(state.players[seat].hand)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': cid,
                          'from_exile': True, 'cost_choice': {'id': options[0].id}})
    assert state.cards[cid].was_foretold and not state.cards[cid].foretell_record
    assert state.stack[-1].payload['__was_foretold']
    state = resolve(state)
    assert state.pending_mechanic_choice['kind'] == 'scry'
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': []})
    if state.pending_mechanic_choice:
        state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic',
                              'card_ids': state.pending_mechanic_choice['options']})
    assert len(state.players[seat].hand) == before + 2
    assert state.cards[cid].zone == Zone.GRAVEYARD and not state.cards[cid].was_foretold


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('chargers,price', [(1, 1), (2, 0)])
def test_foreTell_modifiers_allow_opposing_turn_and_accumulate(chargers, price, seat):
    state, cid = setup(seat=seat)
    state.active_player = 3-seat
    for _ in range(chargers):
        add(state, 'Cosmos Charger', seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': price}
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move['type'] == 'foretell')
    assert move['mana_cost'] == '{' + str(price) + '}'
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    assert state.priority_player == seat and state.players[seat].mana_pool['C'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('modifier', ['Cosmos Charger', 'Dream Devourer'])
def test_source_removal_does_not_remove_saved_foreTell_permission(modifier, seat):
    state, cid = setup(seat=seat)
    source = add(state, modifier, seat, Zone.BATTLEFIELD)
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    source = state.cards[source.id]
    state.players[seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(source.id)
    state.turn += 1
    assert exile_permission(state, seat, cid)
    assert collect_cost_options(state, seat, state.cards[cid])[0].mana_cost == '{1}{U}'


@pytest.mark.parametrize('seat', [1, 2])
def test_exile_zone_departure_clears_permission_even_after_return_to_exile(seat):
    state, cid = setup(seat=seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    card = state.cards[cid]
    card.move_to_zone(Zone.HAND)
    card.move_to_zone(Zone.EXILE)
    card.exile_face_down = True
    state.turn += 1
    assert not can_look(card, seat) and not exile_permission(state, seat, cid)


@pytest.mark.parametrize('seat', [1, 2])
def test_bad_foreTell_attempts_leave_complete_snapshot_unchanged(seat):
    state, cid = setup(seat=seat)
    state.active_player = 3-seat
    snapshot = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    assert serialize_match_snapshot(state) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_foreTell_reaches_http_contract_and_saved_private_views(game, seat):
    client, match = game
    state, cid = setup(seat=seat)
    state.id = match.state.id
    match.state = state
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': 'foretell', 'card_id': cid}})
    assert response.status_code == 200, response.text
    assert response.json()['players'][str(seat)]['exile'][0]['id'] == cid
    assert not match.state.stack
    import main
    main.ACTIVE_MATCHES.pop(state.id)
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = client.get(f'/matches/{state.id}')
    assert restored.status_code == 200, restored.text
    assert restored.json()['players'][str(seat)]['exile'][0]['id'] == cid
    assert main.ACTIVE_MATCHES[state.id].state.cards[cid].foretell_record['player_id'] == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', ['Dream Devourer', 'Bohn, Beguiling Balladeer'])
def test_granted_cost_survives_source_removal_and_uses_actual_printed_mana(grant, seat):
    state = clean()
    state.active_player = state.priority_player = seat
    spell = raw_add(state, 'Damnation', seat, Zone.HAND)
    source = add(state, grant, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': spell.id})
    state = resolve(state)
    source = state.cards[source.id]
    state.players[seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(source.id)
    state.turn += 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    options = collect_cost_options(state, seat, state.cards[spell.id])
    assert [(option.id, option.mana_cost) for option in options] == [('foretell_0', '{B}{B}')]
    state.players[seat].mana_pool = {'B': 2}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
                          'from_exile': True, 'cost_choice': {'id': 'foretell_0'}})
    assert state.stack[-1].payload['__was_foretold']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('blink', [False, True])
def test_foreTell_self_reward_uses_the_stack_and_original_object(seat, blink):
    from rules_engine.continuous import effective_power
    state, cid = setup(seat=seat)
    source = add(state, 'Dream Devourer', seat, Zone.BATTLEFIELD)
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    assert len(state.stack) == 1 and effective_power(state, source.id) == 0
    source = state.cards[source.id]
    if blink:
        source.move_to_zone(Zone.EXILE)
        source.move_to_zone(Zone.BATTLEFIELD)
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert effective_power(state, source.id) == (0 if blink else 2)


@pytest.mark.parametrize('seat', [1, 2])
def test_ranar_first_action_is_free_but_not_the_second(seat):
    state, cid = setup(seat=seat)
    add(state, 'Ranar the Ever-Watchful', seat, Zone.BATTLEFIELD)
    second = add(state, 'Behold the Multiverse', seat)
    state.players[seat].mana_pool.clear()
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    assert not any(move['type'] == 'foretell' for move in RulesEngine().legal_moves(state, seat))
    state.players[seat].mana_pool = {'C': 2}
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': second.id})
    assert state.foretells_this_turn[seat] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_special_action_can_be_taken_with_a_split_second_spell_on_stack(seat):
    from game_state.state import StackItem
    state, cid = setup(seat=seat)
    # Use canonical Krosan Grip from the existing rules fixture, not altered Oracle text.
    rows = json.loads((Path(__file__).parent / 'fixtures/surveil_mill.json').read_text())
    grip = next(row for row in rows if row['name'] == 'Krosan Grip')
    source = raw_add(state, grip['name'], 3-seat, Zone.HAND, cards={grip['name']: grip})
    state.players[3-seat].hand.remove(source.id)
    source.move_to_zone(Zone.STACK)
    state.stack.append(StackItem(id=state.allocate_object_id(), source_card_id=source.id,
                                controller=3-seat, label=source.name, effect_key='destroy_permanent', payload={}))
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    assert len(state.stack) == 1 and state.priority_player == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Midrange', 'Control', 'Tempo', 'Ramp', 'Drain',
                                 'Aristocrats', 'Reanimator', 'Tokens', 'Tribal', 'Combo-lite',
                                 'Counter-heavy', 'Removal-heavy'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_every_ai_style_banks_idle_mana_without_mutating_decision_state(seat, style, difficulty):
    from ai.agent import AIAgent
    state, cid = setup(seat=seat)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty=difficulty, archetype=style)
    decision = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action == {'type': 'foretell', 'card_id': cid}
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_keeps_affordable_counter_in_hand_and_mana_available(seat):
    from ai.agent import AIAgent
    from ai.foretell_policy import idle_foretell_action
    state, cid = setup('Saw It Coming', seat)
    state.players[seat].mana_pool = {'U': 3}
    agent = AIAgent(archetype='Control')
    assert idle_foretell_action(agent, state, RulesEngine().legal_moves(state, seat), seat) is None
    state, cid = setup(seat=seat)
    add(state, 'Saw It Coming', seat)
    state.players[seat].mana_pool = {'U': 3}
    assert idle_foretell_action(agent, state, RulesEngine().legal_moves(state, seat), seat) is None


@pytest.mark.parametrize('name', ['Haunting Voyage', 'Ethereal Valkyrie', 'The Foretold Soldier'])
def test_unimplemented_foreTell_clauses_remain_explicit_diagnostics(name):
    from rules_engine.coverage import known_unsupported_mechanics
    assert 'foretell-related effect fidelity' in known_unsupported_mechanics(CARDS[name]['oracle_text'], card_name=name)


@pytest.mark.parametrize('seat', [1, 2])
def test_irrelevant_board_does_not_invoke_foretell_layer_work(seat):
    from unittest.mock import patch
    state = clean()
    card = raw_add(state, 'Grizzly Bears', seat, Zone.HAND)
    raw_add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    with patch('rules_engine.continuous.printed_abilities_suppressed', side_effect=AssertionError('irrelevant suppression')):
        with patch('rules_engine.type_effects.effective_types', side_effect=AssertionError('irrelevant types')):
            assert hand_costs(state, card, seat) == ([], [])
