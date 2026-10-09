"""Actual agent decisions on restored, authorized loyalty continuation menus."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pytest
import test_loyalty_entry_lifecycle as e
from ai.agent import AIAgent
from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action

facts = e.facts


def decide(state, seat):
    state = e.cold(state)
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    move = AIAgent(archetype='Midrange').choose_action(state, moves, seat).action
    assert serialize_match_snapshot(state) == before
    result = checked_action(state, RulesEngine(), seat, move)
    assert serialize_match_snapshot(state) == before
    return e.cold(result), move


def setup(seat, phase='cards'):
    state = e.position(seat)
    e.raw_card(state, e.AURAS['Colossal Dreadmaw'], seat, Zone.BATTLEFIELD)
    if phase == 'attachment':
        card = e.raw_card(state, e.AURAS['Octopus Umbra'], seat, Zone.HAND)
    elif phase == 'land':
        card = e.raw_card(state, e.SHOCK, seat, Zone.HAND)
    else:
        card = e.raw_card(state, e.SEED['Teferi, Hero of Dominaria'], seat, Zone.HAND)
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': 1})
    if phase != 'cards':
        state = e.action(e.cold(state), seat, card_ids=[card.id])
    return state, card.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 3])
def test_actual_ai_hand_selection_respects_zero_subset_max_and_private_receipts(seat, count):
    state = e.position(seat)
    ids = [e.raw_card(state, e.SEED[name], seat, Zone.HAND).id
           for name in ('Forest', 'Teferi, Hero of Dominaria', 'Breeding Pool')]
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': count})
    before = deepcopy(state.pending_mechanic_choice)
    state, move = decide(state, seat)
    assert move['type'] == 'choose_mechanic'
    assert len(move['card_ids']) == count and len(set(move['card_ids'])) == count
    assert set(move['card_ids']) <= set(ids)
    assert set(move) == {'type', 'card_ids'}
    assert set(before['option_references']) == set(ids)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_aura_attachment_uses_offered_choice_id(seat):
    state, aura = setup(seat, 'attachment')
    offered = state.pending_mechanic_choice['options'][:]
    state, move = decide(state, seat)
    assert set(move) == {'type', 'choice_id'} and move['choice_id'] in offered
    assert state.cards[aura].attached_to == move['choice_id']
    assert state.cards[aura].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_hand_selection_does_not_follow_stale_incarnation(seat):
    state, stale = setup(seat)
    valid = e.raw_card(state, e.SEED['Forest'], seat, Zone.HAND)
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': 2})
    state.cards[stale].move_to_zone(Zone.GRAVEYARD)
    state.cards[stale].move_to_zone(Zone.HAND)
    state, move = decide(state, seat)
    assert move['card_ids'] == [valid.id]
    assert state.cards[stale].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_attachment_uses_live_offered_target_not_returned_object(seat):
    state = e.position(seat)
    stale = e.raw_card(state, e.AURAS['Colossal Dreadmaw'], seat, Zone.BATTLEFIELD).id
    valid = e.raw_card(state, e.AURAS['Colossal Dreadmaw'], seat, Zone.BATTLEFIELD)
    aura = e.raw_card(state, e.AURAS['Octopus Umbra'], seat, Zone.HAND).id
    state = e.hand_entry(state, seat, [aura])
    assert state.pending_mechanic_choice['options'] == [stale, valid.id]
    state.cards[stale].move_to_zone(Zone.GRAVEYARD)
    state.cards[stale].move_to_zone(Zone.BATTLEFIELD)
    state, move = decide(state, seat)
    assert move['choice_id'] == valid.id and state.cards[aura].attached_to == valid.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('phase', ['cards', 'attachment', 'land'])
def test_actual_ai_choices_ignore_unobserved_opponent_names_and_metadata(seat, phase):
    state, _ = setup(seat, phase)
    hidden = e.raw_card(state, e.AURAS['Colossal Dreadmaw'], 3-seat, Zone.HAND)
    library = e.raw_card(state, e.SEED['Forest'], 3-seat, Zone.LIBRARY)
    other = e.cold(state)
    for cid in (hidden.id, library.id):
        other.cards[cid].name = 'Unobserved alternate identity'
        other.cards[cid].oracle_text = 'Destroy all creatures.'
        other.cards[cid].types = ['Sorcery']
        other.cards[cid].mana_cost = '{9}'
    view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    assert view.cards[hidden.id].name == view.cards[library.id].name == ''
    _, first = decide(state, seat)
    _, second = decide(other, seat)
    assert first == second
    assert hidden.id not in first.get('card_ids', []) and library.id not in first.get('card_ids', [])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [1, 20])
def test_actual_ai_restored_land_choice_only_uses_available_payment(seat, life):
    state = e.position(seat)
    state.players[seat].life = life
    spell = e.raw_card(state, e.SEED['Monastery Swiftspear'], seat, Zone.HAND)
    card = e.raw_card(state, e.SHOCK, seat, Zone.HAND)
    state = e.hand_entry(state, seat, [card.id])
    offered = state.pending_mechanic_choice['options'][:]
    state, move = decide(state, seat)
    assert move['choice_id'] in offered
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.players[seat].life in (life, life-2)
    assert state.players[seat].life > 0
    if life == 20:
        assert move['choice_id'] == 'pay_two_life' and state.players[seat].life == 18
        offered_cast = next(m for m in RulesEngine().legal_moves(state, seat)
                            if m['type'] == 'cast_spell' and m['card_id'] == spell.id)
        result = checked_action(state, RulesEngine(), seat, offered_cast)
        assert result.cards[spell.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_observes_public_emblem_and_selects_real_draw_trigger_target(seat):
    state = e.position(seat)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    target = e.raw_card(state, e.AURAS['Colossal Dreadmaw'], 3-seat, Zone.BATTLEFIELD)
    e.raw_card(state, e.SEED['Forest'], seat, Zone.LIBRARY)
    resolve_effect(state, seat, 'loyalty_emblem', {'kind':'draw_exile',
        'text':'Whenever you draw a card, exile target permanent an opponent controls.'})
    emblem = state.emblems[-1]
    view, _ = decision_view(state, 3-seat, [])
    assert view.cards[emblem].name == 'Emblem' and view.cards[emblem].oracle_text == state.cards[emblem].oracle_text
    resolve_effect(state, seat, 'draw_cards', {'amount':1})
    for _ in range(24):
        state = e.cold(state)
        if state.pending_trigger_order:
            state, _ = decide(state, state.pending_trigger_order['current_controller'])
        elif state.stack:
            state = e.paid.act(state, state.priority_player, {'type':'pass_priority'})
        else:break
    else:raise AssertionError('24 actual continuation actions')
    assert state.cards[target.id].zone == Zone.EXILE and state.cards[emblem].zone == Zone.COMMAND


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_ugin_restored_ai_continuation_enters_mixed_permanents(facts, seat, request):
    rows = deepcopy(facts); rows.update(deepcopy(e.AURAS)); rows.update(deepcopy(e.COUNTER_ROWS))
    for name in ('Ugin, the Spirit Dragon', 'Breeding Pool', "Jetmir's Garden", 'Teferi, Hero of Dominaria'):
        rows[name] = deepcopy(e.SEED[name])
    state = e.paid.g.position(rows, seat)
    e.paid.g.add(state, rows, 'Doubling Season', seat)
    target = e.paid.g.add(state, rows, 'Colossal Dreadmaw', seat)
    chosen = [e.paid.g.add(state, rows, name, seat, Zone.HAND) for name in
        ('Breeding Pool', "Jetmir's Garden", 'Octopus Umbra', 'Teferi, Hero of Dominaria')]
    source = e.paid.g.add(state, rows, 'Ugin, the Spirit Dragon', seat, Zone.HAND)
    state, _ = e.paid.paid(state, seat, source, {'C':8})
    while state.stack:state = e.paid.act(state, state.priority_player, {'type':'pass_priority'})
    state = e.paid.priority(state, seat)
    state = e.paid.act(state, seat, {'type':'activate_loyalty','card_id':source,'ability_index':2,'targets':{}})
    receipts=[]
    for _ in range(96):
        state = e.cold(state)
        if state.pending_mechanic_choice:
            kind = state.pending_mechanic_choice['kind']
            state, move = decide(state, state.pending_mechanic_choice['player_id'])
            receipts.append({'kind':kind,'action':move})
        elif state.pending_replacement_choice:
            state, _ = decide(state, state.pending_replacement_choice['player_id'])
        elif state.pending_trigger_order:
            state, _ = decide(state, state.pending_trigger_order['current_controller'])
        elif state.stack:state = e.paid.act(state, state.priority_player, {'type':'pass_priority'})
        else:break
    else:raise AssertionError('96 actual continuation actions')
    assert {'loyalty_cards','loyalty_attachment','land_entry'} <= {x['kind'] for x in receipts}
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in chosen)
    assert state.cards[chosen[2]].attached_to == target
    assert state.cards[chosen[1]].tapped
    assert state.players[seat].lands_played_this_turn == 0
    (Path(os.environ['GAP6_EVIDENCE'])/(request.node.name+'.json')).write_text(json.dumps({
        'node':request.node.nodeid,'actual_ai_choices':receipts,'snapshot':serialize_match_snapshot(state)},indent=2)+'\n')


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_all_stale_optional_hand_offers_choose_zero(seat):
    state, stale = setup(seat)
    state.cards[stale].move_to_zone(Zone.GRAVEYARD)
    state.cards[stale].move_to_zone(Zone.HAND)
    state, move = decide(state, seat)
    assert move == {'type':'choose_mechanic', 'card_ids':[]}
    assert state.cards[stale].zone == Zone.HAND
    assert state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalidated', ['source', 'target'])
def test_actual_ai_no_live_aura_receipt_fails_explicitly_without_root_mutation(seat, invalidated):
    state, source = setup(seat, 'attachment')
    cid = source if invalidated == 'source' else state.pending_mechanic_choice['options'][0]
    zone = state.cards[cid].zone
    state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    state.cards[cid].move_to_zone(zone)
    state = e.cold(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ValueError, match='No live offered loyalty'):
        AIAgent().choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert state.pending_mechanic_choice['kind'] == 'loyalty_attachment'
