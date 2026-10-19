"""Real entry producers and explicitly noncanonical linked-clause boundaries."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from effects.handlers import return_creature_from_graveyard_to_battlefield
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import _trigger_from_oracle
from rules_engine.oracle_effects import without_reminder_text
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import locate, place
from tests.test_self_or_another_entry_observer_bf62 import canonical as entry_raw


OX = 'Ox of Agonas'
OX_SHA = '51783c3a2788b954d6a8fde8b82b7b7933f163db4af759460c18672e212b40ec'
CLAUSE = 'When this creature enters, discard your hand, then draw three cards.'


def canonical(name):
    if name != OX:
        return entry_raw(name)
    data = (Path(__file__).parent / 'fixtures/expanded_keyword_canonical/ox-of-agonas.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == OX_SHA
    raw = json.loads(data)
    assert raw['id'] == '00c46d18-064e-403a-bf39-ec655d78390a'
    assert raw['oracle_id'] == '22113051-c971-4108-953b-95356d21323a'
    assert raw['oracle_text'].splitlines()[0] == CLAUSE
    return raw


def board(seat, owner=None, *, suppressed=False):
    owner = seat if owner is None else owner

    def deck(pid):
        names = [OX] if pid == owner else []
        if suppressed and pid == 3 - seat:
            names.append('Humility')
        names.append('Grizzly Bears')
        counts = Counter(names)
        counts['Island'] += 60 - len(names)
        return [{**canonical(name), 'card_name': name, 'quantity': count}
                for name, count in counts.items()]

    state = MatchFactory.from_decks(deck(1), deck(2), seed=719)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = set()
    place(state, OX, Zone.GRAVEYARD, owner)
    if suppressed:
        place(state, 'Humility', Zone.BATTLEFIELD, 3 - seat)
    return state


def snapshot(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def enter_ox(state, seat, owner):
    cid = locate(state, OX, owner)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    # This is the real native graveyard-entry producer, not an injected event/stack item.
    return_creature_from_graveyard_to_battlefield(state, seat, {'target_card_id': cid})
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].controller == seat
    return cid


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cast_mode', ['hand', 'escape'])
def test_real_paid_ox_cast_uses_full_entry_discard_and_three_draws(seat, cast_mode):
    state = board(seat)
    cid = locate(state, OX, seat)
    fuel = []
    if cast_mode == 'hand':
        place(state, OX, Zone.HAND, seat)
        state.players[seat].mana_pool.update(C=3, R=2)
    else:
        fuel = [value for value in state.players[seat].library
                if state.cards[value].name == 'Island'][:8]
        for value in fuel:
            state.players[seat].library.remove(value)
            state.cards[value].move_to_zone(Zone.GRAVEYARD)
            state.players[seat].graveyard.append(value)
        state.players[seat].mana_pool['R'] = 2
    hand = [value for value in state.players[seat].hand if value != cid]
    library = list(state.players[seat].library)
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move['card_id'] == cid)
    state = checked_action(state, engine, seat, move)
    assert state.cards[cid].zone == Zone.STACK
    assert state.players[seat].mana_pool.get('C', 0) == state.players[seat].mana_pool['R'] == 0
    assert state.players[seat].exile == fuel
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].counters.get('+1/+1', 0) == (cast_mode == 'escape')
    assert len(state.stack) == 1 and state.stack[-1].source_card_id == cid
    assert state.stack[-1].effect_key == 'discard_cards'
    state = snapshot(state)
    assert resolve_top_of_stack(state)
    assert state.players[seat].hand == list(reversed(library[-3:]))
    assert set(state.players[seat].graveyard) == set(hand)
    assert state.discards_this_turn[seat] == len(hand)
    assert state.draws_this_turn[seat] == 3
    assert not state.stack
    snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign_owner', [False, True])
def test_real_core_entry_discards_entire_controllers_hand_before_three_draws(seat, foreign_owner):
    owner = 3 - seat if foreign_owner else seat
    state = board(seat, owner)
    hand = list(state.players[seat].hand)
    other_hand = list(state.players[3 - seat].hand)
    library = list(state.players[seat].library)
    cid = enter_ox(state, seat, owner)
    assert len(state.stack) == 1
    trigger = state.stack[-1]
    assert trigger.source_card_id == cid and trigger.controller == seat
    assert trigger.effect_key == 'discard_cards'
    assert trigger.payload['all_hand'] is True
    assert trigger.payload['followup_effect'] == {
        'effect_key': 'draw_cards', 'payload': {'amount': 3}}
    assert trigger.payload['__trigger_full_clause'] == CLAUSE
    state = snapshot(state)
    assert resolve_top_of_stack(state)
    assert state.players[seat].hand == list(reversed(library[-3:]))
    assert set(state.players[seat].graveyard) == set(hand)
    assert state.players[3 - seat].hand == other_hand
    assert state.discards_this_turn[seat] == len(hand)
    assert state.draws_this_turn[seat] == 3
    assert not state.stack
    assert state.cards[cid].owner == owner
    assert state.cards[cid].oracle_text == canonical(OX)['oracle_text']
    snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_entry_human_discard_then_draw_resumes_across_two_snapshots(seat):
    state = board(seat)
    hand = list(state.players[seat].hand)
    library = list(state.players[seat].library)
    state.mechanic_choice_players = {seat}
    enter_ox(state, seat, seat)
    state = snapshot(state)
    assert resolve_top_of_stack(state) is False
    assert state.pending_mechanic_choice['kind'] == 'discard'
    assert state.pending_mechanic_choice['options'] == hand
    assert state.pending_mechanic_choice['count'] == len(hand)
    assert state.players[seat].hand == hand
    assert state.players[seat].library == library
    state = snapshot(state)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': hand})
    assert state.pending_mechanic_choice is None
    assert state.players[seat].hand == list(reversed(library[-3:]))
    assert set(state.players[seat].graveyard) == set(hand)
    assert state.discards_this_turn[seat] == len(hand)
    assert state.draws_this_turn[seat] == 3
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_real_entry_empty_hand_still_draws_fixed_three(seat):
    state = board(seat)
    for cid in list(state.players[seat].hand):
        card = state.cards[cid]
        state.players[seat].hand.remove(cid)
        card.move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(cid)
    library = list(state.players[seat].library)
    enter_ox(state, seat, seat)
    assert resolve_top_of_stack(state)
    assert state.players[seat].hand == list(reversed(library[-3:]))
    assert state.discards_this_turn.get(seat, 0) == 0
    assert state.draws_this_turn[seat] == 3
    snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_other_real_entry_does_not_trigger_existing_ox(seat):
    state = board(seat)
    place(state, OX, Zone.BATTLEFIELD, seat)
    target = place(state, 'Grizzly Bears', Zone.GRAVEYARD, seat)
    hand = list(state.players[seat].hand)
    return_creature_from_graveyard_to_battlefield(state, seat, {'target_card_id': target})
    assert not state.stack
    assert state.players[seat].hand == hand


@pytest.mark.parametrize('seat', [1, 2])
def test_real_entry_under_humility_has_no_linked_trigger(seat):
    state = board(seat, suppressed=True)
    hand = list(state.players[seat].hand)
    enter_ox(state, seat, seat)
    assert not state.stack
    assert state.players[seat].hand == hand


@pytest.mark.parametrize('text', [
    CLAUSE + ' Gain 2 life.',
    CLAUSE + ' (Gain 2 life.)',
    CLAUSE + ' (Then draw a card.)',
    CLAUSE + '\nWhen this creature enters, draw a card.',
    CLAUSE + '\n' + CLAUSE,
    CLAUSE.replace('three cards.', 'three cards unless you pay {1}.'),
    CLAUSE.replace('discard your hand', 'if you control a Forest, discard your hand'),
    CLAUSE.replace('discard your hand', 'you may discard your hand'),
    CLAUSE.replace('then draw', 'then (gain 2 life) draw'),
])
def test_noncanonical_complete_clause_boundaries_never_compile_partial_rewards(text):
    state = board(1)
    # Deliberate unprinted compiler protocol: no canonical-facts claim or bound-stock mutation.
    card = CardInstance(id='clause-protocol', name='Linked entry boundary protocol', owner=1,
                        controller=1, zone=Zone.BATTLEFIELD, types=['Creature'], oracle_text=text)
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    result = _trigger_from_oracle(state, card.id, 1, without_reminder_text(text).lower(),
                                 'entry protocol', 'enters_battlefield',
                                 {'card_id': card.id, 'controller': 1}, raw_entry_oracle=text)
    assert result['effect_key'] == 'noop'
    assert result['payload']['__unsupported_trigger_instruction']


@pytest.mark.parametrize('reference', ['this creature', 'this permanent', 'Linked entry boundary protocol'])
def test_exact_source_reference_compiles_complete_all_hand_instruction(reference):
    state = board(1)
    text = CLAUSE.replace('this creature', reference)
    card = CardInstance(id='reference-protocol', name='Linked entry boundary protocol', owner=1,
                        controller=1, zone=Zone.BATTLEFIELD, types=['Creature'], oracle_text=text)
    state.cards[card.id] = card
    result = _trigger_from_oracle(state, card.id, 1, text.lower(), 'entry protocol',
                                 'enters_battlefield', {'card_id': card.id, 'controller': 1},
                                 raw_entry_oracle=text)
    assert result['effect_key'] == 'discard_cards'
    assert result['payload']['all_hand'] is True
    assert result['payload']['__trigger_full_clause'] == text
