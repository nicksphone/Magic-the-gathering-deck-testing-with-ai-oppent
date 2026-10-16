"""Actual paid routes, detached identity and atomic continuation controls."""
from collections import Counter
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.copiable_values import values
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import place
from tests.test_entry_copy_native_936 import raw as native_raw
from tests.test_entry_unadapted_two_families_641 import (
    action, board, copy_spell, loyalty_return, paid_cast, query_pure, raw, roundtrip,
)
from tests.test_graveyard_batch_boundaries_bf62 import replacement_action


def waiting_copy(seat):
    state, steel, target, original, copied = copy_spell(seat, 3-seat)
    resolve_top_of_stack(state)
    assert (state.pending_mechanic_choice or {}).get('kind') == 'entry_copy'
    return state, steel, target, original, copied


@pytest.mark.parametrize('seat', [1, 2])
def test_detached_copy_reserves_once_and_emits_exactly_one_real_etb(seat, monkeypatch):
    import rules_engine.stack_engine as stack
    emitted = []
    real_emit = stack.emit_event
    def observe(state, event, payload):
        emitted.append((event, deepcopy(payload)))
        return real_emit(state, event, payload)
    monkeypatch.setattr(stack, 'emit_event', observe)
    state, steel, target, original, copied = waiting_copy(seat)
    pending = state.pending_mechanic_choice
    plan = pending['effect_payload']['__entry_copy_plan']
    row, = plan['entries']
    receipt = row['candidate']
    cid = row['id']
    assert cid != steel and cid not in state.cards
    assert all(cid not in getattr(p, zone) for p in state.players.values()
               for zone in ('hand', 'library', 'battlefield', 'graveyard', 'exile'))
    assert receipt['card']['zone'] == 'stack' and receipt['card']['is_token'] is True
    assert pending['resolving_item'] == plan['frame']
    assert plan['frame']['id'] == copied.id and plan['frame']['source_card_id'] == steel
    assert plan['frame']['controller'] == seat
    assert not any(event == 'enters_battlefield' and payload['card_id'] == cid for event, payload in emitted)
    allocator = state.next_object_id
    stock = deepcopy(state.sideboard_facts['inventory'])
    query_pure(state, seat)
    state = action(roundtrip(state), seat, type='choose_mechanic', choice_id=target)
    assert state.next_object_id == allocator
    assert state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].name == 'Sol Ring'
    assert state.cards[cid].is_token and state.cards[cid].owner == state.cards[cid].controller == seat
    assert len([c for c in state.cards.values() if c.is_token]) == 1
    assert sum(event == 'enters_battlefield' and payload['card_id'] == cid for event, payload in emitted) == 1
    assert state.stack == [original] and state.cards[steel].name == 'Sculpting Steel'
    assert roundtrip(state).sideboard_facts['inventory'] == stock


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['id', 'allocation', 'body', 'controller', 'source'])
def test_candidate_and_native_frame_tamper_reject_before_clear_or_registration(seat, mutation):
    state, steel, target, _, _ = waiting_copy(seat)
    pending = state.pending_mechanic_choice
    data = pending['effect_payload']
    plan = data['__entry_copy_plan']
    row = plan['entries'][0]
    receipt = row['candidate']
    if mutation == 'id':
        row['id'] = receipt['card']['id'] = '00000000-0000-0000-0000-000000ffffff'
        pending['entry_card_id'] = row['id']
    elif mutation == 'allocation':
        receipt['allocation_next'] += 1
    elif mutation == 'body':
        receipt['card']['oracle_text'] += '\nDraw a card.'
    elif mutation == 'controller':
        row['controller'] = receipt['card']['controller'] = 3-seat
    else:
        data['entry_item']['source_card_id'] = row['id']
        plan['frame']['source_card_id'] = row['id']
        pending['resolving_item']['source_card_id'] = row['id']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, type='choose_mechanic', choice_id=target)
    assert serialize_match_snapshot(state) == before
    assert state.cards[steel].zone == Zone.STACK and not any(c.is_token for c in state.cards.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_original_spell_can_copy_the_completed_copy_without_copying_token_status(seat):
    state, steel, target, _, _ = waiting_copy(seat)
    state = action(roundtrip(state), seat, type='choose_mechanic', choice_id=target)
    token, = [c for c in state.cards.values() if c.is_token]
    assert not resolve_top_of_stack(state)
    assert token.id in state.pending_mechanic_choice['options']
    state = action(roundtrip(state), seat, type='choose_mechanic', choice_id=token.id)
    assert values(state.cards[steel]) == values(state.cards[token.id])
    assert state.cards[steel].name == 'Sol Ring' and not state.cards[steel].is_token
    assert 'Token' not in state.cards[steel].types
    assert state.cards[steel].characteristic_record['physical']['name'] == 'Sculpting Steel'
    assert len([c for c in state.cards.values() if c.is_token]) == 1
    assert not state.stack and roundtrip(state).cards[steel].owner == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['cost', 'controller'])
def test_daretti_paid_context_is_still_required_before_copy_choice_clear(seat, mutation):
    state, steel, cost, ring, _, _, _ = loyalty_return(seat)
    assert not resolve_top_of_stack(state)
    state = action(roundtrip(state), seat, type='choose_mechanic', card_ids=[cost])
    assert (state.pending_mechanic_choice or {}).get('kind') == 'entry_copy'
    data = state.pending_mechanic_choice['effect_payload']
    if mutation == 'cost':
        data['__loyalty_return_context']['paid_cost']['paid'] = False
    else:
        data['__loyalty_return_context']['controller'] = 3-seat
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, type='choose_mechanic', choice_id=ring)
    assert serialize_match_snapshot(state) == before
    assert state.cards[steel].zone == Zone.GRAVEYARD and state.cards[cost].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first,expected', [('add', 8), ('double', 7)])
def test_copy_candidate_survives_real_selectable_counter_preparation_without_early_entry(seat, first, expected):
    names = ['Lithoform Engine', 'Sculpting Steel', 'Triskelion', 'Hardened Scales', 'Doubling Season']
    def facts(name):
        return raw(name) if name in {'Lithoform Engine', 'Sculpting Steel', 'Island'} else native_raw(name)
    counts = Counter(names)
    counts['Island'] = 60-sum(counts.values())
    deck = [{**facts(name), 'card_name': name, 'quantity': count} for name, count in counts.items()]
    state = MatchFactory.from_decks(deck, deck, seed=1207)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].mana_pool = dict(C=30, W=10, U=10, B=10, R=10, G=10)
    target = place(state, 'Triskelion', Zone.BATTLEFIELD, 3-seat)
    for name in ('Hardened Scales', 'Doubling Season'):
        place(state, name, Zone.BATTLEFIELD, seat)
    state, engine = paid_cast(state, seat, 'Lithoform Engine')
    assert resolve_top_of_stack(state)
    state, steel = paid_cast(state, seat, 'Sculpting Steel')
    original = deepcopy(state.stack[-1])
    state = action(state, seat, type='activate_ability', card_id=engine, ability_index=2,
                   targets={'target_stack_id': original.id})
    assert resolve_top_of_stack(state)
    resolve_top_of_stack(state)
    assert (state.pending_mechanic_choice or {}).get('kind') == 'entry_copy'
    cid = state.pending_mechanic_choice['entry_card_id']
    state = action(roundtrip(state), seat, type='choose_mechanic', choice_id=target)
    pending = state.pending_replacement_choice
    assert pending is not None and pending['player_id'] == seat
    assert {o['operation'] for o in pending['options']} == {'add', 'double'}
    assert cid not in state.cards and state.cards[steel].zone == Zone.STACK
    option = next(o for o in pending['options'] if o['operation'] == first)
    state = replacement_action(roundtrip(state), seat, option['source_id'])
    assert state.pending_replacement_choice is None
    assert state.cards[cid].name == 'Triskelion' and state.cards[cid].counters['+1/+1'] == expected
    assert state.cards[cid].is_token and state.stack == [original]
    assert len([c for c in state.cards.values() if c.is_token]) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_noncopy_permanent_spell_copy_keeps_native_vanilla_behavior(seat):
    state = board(seat)
    state, engine = paid_cast(state, seat, 'Lithoform Engine')
    assert resolve_top_of_stack(state)
    state, ring = paid_cast(state, seat, 'Sol Ring')
    original = deepcopy(state.stack[-1])
    state = action(state, seat, type='activate_ability', card_id=engine, ability_index=2,
                   targets={'target_stack_id': original.id})
    assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    token, = [c for c in state.cards.values() if c.is_token]
    assert token.name == 'Sol Ring' and token.controller == token.owner == seat
    assert state.cards[ring].zone == Zone.STACK and state.stack == [original]
    assert resolve_top_of_stack(state) and state.cards[ring].zone == Zone.BATTLEFIELD
    assert roundtrip(state).cards[token.id].oracle_text == raw('Sol Ring')['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['owner', 'controller', 'is_token', 'zone_change_sequence'])
def test_candidate_native_scalar_types_cannot_alias_equal_python_values(seat, field):
    state, steel, target, _, _ = waiting_copy(seat)
    data = state.pending_mechanic_choice['effect_payload']
    card = data['__entry_copy_plan']['entries'][0]['candidate']['card']
    card[field] = (float(seat) if field in {'owner', 'controller'} else
                   1 if field == 'is_token' else False)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, type='choose_mechanic', choice_id=target)
    assert serialize_match_snapshot(state) == before
    assert state.cards[steel].zone == Zone.STACK and not any(c.is_token for c in state.cards.values())
