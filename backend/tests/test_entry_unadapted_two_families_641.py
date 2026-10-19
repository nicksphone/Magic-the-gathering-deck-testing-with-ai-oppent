"""Full RAW, real paid producers; strict missing-entry witnesses, not injected frames."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_object_kind
from tests.graveyard_batch_native_support_bf62 import place


HERE = Path(__file__).parent / 'fixtures'
SOURCES = json.loads((HERE/'entry_unadapted_two641/SOURCES.json').read_text())
NAMES = ['Lithoform Engine', 'Sculpting Steel', 'Sol Ring',
         'Daretti, Scrap Savant', 'Counterspell']


def raw(name):
    row = SOURCES[name]
    data = (HERE/row['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['file_sha256']
    value = json.loads(data.splitlines()[row['line']-1]) if row['line'] else json.loads(data)
    assert value['object'] == 'card' and value['name'] == name
    assert hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == row['raw_row_sha256']
    for provenance in row['provenance']:
        assert hashlib.sha256((HERE/provenance['file']).read_bytes()).hexdigest() == provenance['sha256']
    return deepcopy(value)


def board(seat):
    counts = Counter(NAMES)
    counts['Island'] = 60-sum(counts.values())
    deck = [{**raw(name), 'card_name': name, 'quantity': count} for name, count in counts.items()]
    state = MatchFactory.from_decks(deck, deck, seed=1207)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        player.mana_pool = dict(C=30, W=10, U=10, B=10, R=10, G=10)
    return state


def action(state, seat, **payload):
    return checked_action(state, RulesEngine(), seat, payload)


def paid_cast(state, seat, name, **targets):
    assert state.priority_player == seat
    cid = place(state, name, Zone.HAND, seat)
    before = sum(state.players[seat].mana_pool.values())
    state = action(state, seat, type='cast_spell', card_id=cid,
                   **({'targets': targets} if targets else {}))
    assert sum(state.players[seat].mana_pool.values()) < before
    assert state.stack[-1].source_card_id == cid and state.stack[-1].controller == seat
    assert stack_object_kind(state, state.stack[-1]) == 'spell'
    return state, cid


def roundtrip(state):
    saved = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(saved)
    assert serialize_match_snapshot(restored) == saved
    return restored


def query_pure(state, seat):
    before = serialize_match_snapshot(state)
    RulesEngine().legal_moves(state, seat)
    serialize_match(state)
    assert serialize_match_snapshot(state) == before


def copy_spell(seat, target_owner):
    state = board(seat)
    target = place(state, 'Sol Ring', Zone.BATTLEFIELD, target_owner)
    state, engine = paid_cast(state, seat, 'Lithoform Engine')
    assert resolve_top_of_stack(state)
    state, steel = paid_cast(state, seat, 'Sculpting Steel')
    original = deepcopy(state.stack[-1])
    before = sum(state.players[seat].mana_pool.values())
    state = action(state, seat, type='activate_ability', card_id=engine,
                   ability_index=2, targets={'target_stack_id': original.id})
    assert state.cards[engine].tapped and sum(state.players[seat].mana_pool.values()) == before-4
    assert state.stack[-1].source_card_id == engine
    assert resolve_top_of_stack(state)
    assert len(state.stack) == 2
    copied = state.stack[-1]
    assert copied.id != original.id and copied.controller == seat
    assert copied.source_card_id == steel == original.source_card_id
    assert copied.payload['__stack_copy_kind'] == 'spell'
    assert copied.payload['__copied_from_stack_id'] == original.id
    assert copied.payload is not state.stack[0].payload
    assert state.stack[0] == original
    assert state.cards[steel].zone == Zone.STACK
    return state, steel, target, original, deepcopy(copied)


def loyalty_return(seat, target_name='Sculpting Steel'):
    state = board(seat)
    target = place(state, target_name, Zone.GRAVEYARD, seat)
    state, engine = paid_cast(state, seat, 'Lithoform Engine')
    assert resolve_top_of_stack(state)
    if target_name != 'Sol Ring':
        state, ring = paid_cast(state, seat, 'Sol Ring')
        assert resolve_top_of_stack(state)
    else:
        ring = None
    enemy_ring = place(state, 'Sol Ring', Zone.BATTLEFIELD, 3-seat)
    state, daretti = paid_cast(state, seat, 'Daretti, Scrap Savant')
    assert resolve_top_of_stack(state) and state.cards[daretti].loyalty == 3
    incarnation = object_incarnation(state.cards[daretti])
    state = action(state, seat, type='activate_loyalty', card_id=daretti,
                   ability_index=1, targets={'target_card_id': target})
    assert state.cards[daretti].loyalty == 1
    frame = deepcopy(state.stack[-1])
    assert frame.source_card_id == daretti and frame.controller == seat
    assert stack_object_kind(state, frame) == 'activated'
    assert object_incarnation(state.cards[daretti]) == incarnation
    return state, target, engine, ring, enemy_ring, daretti, frame


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['lithoform', 'daretti'])
def test_full_raw_admission_creates_actual_independent_paid_producer_frames(seat, family):
    if family == 'lithoform':
        state, steel, target, original, copied = copy_spell(seat, 3-seat)
        state = roundtrip(state)
        assert state.stack[0] == original and state.stack[1] == copied
        assert state.cards[steel].name == 'Sculpting Steel' and state.cards[target].name == 'Sol Ring'
    else:
        from rules_engine.closed_loyalty import compile_body
        body = raw('Daretti, Scrap Savant')
        compiled = compile_body(body['oracle_text'], body['name'])
        assert compiled is not None
        assert compiled['abilities'][1]['instructions'][0]['effect_key'] == 'loyalty_sacrifice_return'
        state, target, _, _, _, source, frame = loyalty_return(seat)
        state = roundtrip(state)
        assert state.stack[-1] == frame
        assert state.cards[target].zone == Zone.GRAVEYARD
        assert state.cards[source].oracle_text == body['oracle_text']
    query_pure(state, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('decline', [False, True])
def test_copied_spell_prepares_deliberate_copy_or_decline_before_token_entry(seat, foreign, decline):
    state, steel, target, original, copied = copy_spell(seat, 3-seat if foreign else seat)
    stock = deepcopy(state.sideboard_facts['inventory'])
    source_reference = (object_incarnation(state.cards[steel]), state.cards[steel].zone_change_sequence)
    query_pure(state, seat)
    state = roundtrip(state)
    resolve_top_of_stack(state)
    assert (state.pending_mechanic_choice or {}).get('kind') == 'entry_copy', 'Copied permanent spell bypassed as-entry copy preparation'
    assert target in state.pending_mechanic_choice['options']
    assert state.pending_mechanic_choice['player_id'] == seat
    assert state.cards[steel].zone == Zone.STACK and state.stack[0] == original
    query_pure(state, seat)
    state = action(roundtrip(state), seat, type='choose_mechanic',
                   **({'card_ids': []} if decline else {'choice_id': target}))
    token, = [c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD]
    assert token.id not in stock and token.id != steel
    assert token.owner == token.controller == seat
    assert token.name == ('Sculpting Steel' if decline else 'Sol Ring')
    assert token.oracle_text == raw(token.name)['oracle_text']
    assert state.cards[steel].name == 'Sculpting Steel' and state.stack == [original]
    assert copied.id != original.id
    assert (object_incarnation(state.cards[steel]), state.cards[steel].zone_change_sequence) == source_reference
    assert roundtrip(state).sideboard_facts['inventory'] == stock


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_counter_of_physical_original_does_not_rebind_waiting_copy(seat):
    state, steel, target, original, copied = copy_spell(seat, 3-seat)
    reference = state.cards[steel].zone_change_sequence
    state = action(state, seat, type='pass_priority')
    state, counter = paid_cast(state, 3-seat, 'Counterspell', target_stack_id=original.id)
    assert resolve_top_of_stack(state)
    assert state.cards[counter].zone == state.cards[steel].zone == Zone.GRAVEYARD
    assert state.cards[steel].zone_change_sequence > reference
    assert len(state.stack) == 1 and state.stack[0] == copied
    state = roundtrip(state)
    resolve_top_of_stack(state)
    assert (state.pending_mechanic_choice or {}).get('kind') == 'entry_copy', 'Genuine copied spell lost its independent entry choice after original departure'
    state = action(roundtrip(state), seat, type='choose_mechanic', choice_id=target)
    token, = [c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD]
    assert token.name == 'Sol Ring' and token.owner == token.controller == seat
    assert state.cards[steel].zone == Zone.GRAVEYARD and not state.stack
    assert roundtrip(state).sideboard_facts['inventory'][steel]['stock_key'] == 'Sculpting Steel'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('decline', [False, True])
def test_daretti_paid_return_prepares_copy_or_decline_after_real_sacrifice(seat, foreign, decline):
    state, steel, cost, ring, enemy_ring, source, frame = loyalty_return(seat)
    target = enemy_ring if foreign else ring
    stock = deepcopy(state.sideboard_facts['inventory'])
    old_incarnation = object_incarnation(state.cards[steel])
    source_incarnation = object_incarnation(state.cards[source])
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'loyalty_cards'
    retained = pending['resolving_item']
    assert retained == pending['effect_payload']['__resolving_item']
    assert all(retained[key] == getattr(frame, key)
               for key in ('id', 'source_card_id', 'controller', 'label', 'effect_key', 'targets'))
    assert retained['payload']['__ability_target_text'] == frame.payload['__ability_target_text']
    assert cost in pending['options'] and state.cards[steel].zone == Zone.GRAVEYARD
    query_pure(state, seat)
    state = action(roundtrip(state), seat, type='choose_mechanic', card_ids=[cost])
    assert state.cards[cost].zone == Zone.GRAVEYARD
    assert (state.pending_mechanic_choice or {}).get('kind') == 'entry_copy', 'Daretti return bypassed as-entry copy preparation'
    assert state.cards[steel].zone == Zone.GRAVEYARD and target in state.pending_mechanic_choice['options']
    query_pure(state, seat)
    state = action(roundtrip(state), seat, type='choose_mechanic',
                   **({'card_ids': []} if decline else {'choice_id': target}))
    assert state.cards[steel].name == ('Sculpting Steel' if decline else 'Sol Ring')
    assert state.cards[steel].owner == state.cards[steel].controller == seat
    assert state.cards[steel].zone == Zone.BATTLEFIELD and not state.cards[steel].is_token
    assert object_incarnation(state.cards[steel]) != old_incarnation
    assert object_incarnation(state.cards[source]) == source_incarnation
    assert state.cards[source].loyalty == 1 and state.cards[cost].zone == Zone.GRAVEYARD
    assert roundtrip(state).sideboard_facts['inventory'] == stock


@pytest.mark.parametrize('seat', [1, 2])
def test_independent_vanilla_daretti_return_completes_with_real_cost_and_stock(seat):
    state, target, cost, _, _, source, _ = loyalty_return(seat, 'Sol Ring')
    stock = deepcopy(state.sideboard_facts['inventory'])
    assert not resolve_top_of_stack(state)
    state = action(roundtrip(state), seat, type='choose_mechanic', card_ids=[cost])
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[cost].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.BATTLEFIELD and state.cards[target].owner == seat
    assert state.cards[source].loyalty == 1
    assert roundtrip(state).sideboard_facts['inventory'] == stock


@pytest.mark.parametrize('seat', [1, 2])
def test_lithoform_stale_original_stack_id_rejects_without_payment_or_mutation(seat):
    state = board(seat)
    state, engine = paid_cast(state, seat, 'Lithoform Engine')
    assert resolve_top_of_stack(state)
    state, _ = paid_cast(state, seat, 'Sculpting Steel')
    old_id = state.stack[-1].id
    assert not resolve_top_of_stack(state)
    state = action(roundtrip(state), seat, type='choose_mechanic', card_ids=[])
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, type='activate_ability', card_id=engine,
               ability_index=2, targets={'target_stack_id': old_id})
    assert serialize_match_snapshot(state) == before
    assert not state.cards[engine].tapped
