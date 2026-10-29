"""Finite exact-deck witnesses, not whole-card or TRAIN qualification."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Step, Zone
from rules_engine.costs import collect_cost_options
from tests.test_any_player_cast_damage import checked, settle
from tests.test_linked_damage_targets import raw_card

ROOT = Path(__file__).parent / 'fixtures/ai_burn_foretell'
RAW_BYTES = (ROOT / 'CANONICAL-RAW.json').read_bytes()
RAW = json.loads(RAW_BYTES)
PROOF = json.loads((ROOT / 'CARD-PROVENANCE.json').read_bytes())
WAIT = {'type': 'pass_priority'}
assert sha256(RAW_BYTES).hexdigest() == '3072700528cfd0a7ec6878dc2a7f94cece02f3c2901221ee1ddd490c0aee214d'
assert len(RAW) == 22


def row(name):
    raw = RAW[name]
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert sha256(encoded).hexdigest() == PROOF['cards'][name]['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert len(raw) == PROOF['cards'][name]['fields']
    image = ScryfallSyncService._extract_remote_image_uri(raw)
    assert image
    result = {**deepcopy(raw), **ScryfallSyncService._normalize_payload(raw, image),
              'colors': deepcopy(raw['colors']), 'card_faces': deepcopy(raw.get('card_faces', []))}
    for key in ('oracle_text', 'mana_cost', 'type_line', 'power', 'toughness', 'colors'):
        assert result.get(key) == raw.get(key)
    return result


def position(seat):
    deck = [{**row('Island'), 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=202610290823)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
    return state


def add(state, name, seat, zone=Zone.HAND):
    card = raw_card(state, row(name), seat, zone)
    raw = RAW[name]
    assert (card.oracle_text, card.mana_cost, card.type_line, card.colors) == (
        raw['oracle_text'], raw['mana_cost'], raw['type_line'], raw['colors'])
    if raw.get('power') is not None:
        assert (card.power, card.toughness) == (int(raw['power']), int(raw['toughness']))
    return card.id


def advance(state, predicate):
    for _ in range(128):
        if predicate(state):
            return state
        assert state.winner is None and not state.pending_mechanic_choice
        state = checked(state, state.priority_player, WAIT)
    raise AssertionError('Native priority progression exceeded fixture bound')


def paid_creature(state, seat, name, mana):
    cid = add(state, name, seat)
    state.players[seat].mana_pool = dict(mana)
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': cid,
                                 'cost_choice': {'id': 'base'}})
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = settle(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].summoning_sick
    return state, cid


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('top_name,is_land', [('Island', True), ('Opt', False)])
def test_paid_guide_real_attack_reveals_and_only_moves_land(seat, top_name, is_land):
    state = position(seat)
    defender = 3-seat
    top = add(state, top_name, defender, Zone.LIBRARY)
    state, guide = paid_creature(state, seat, 'Goblin Guide', {'R': 1})
    turn = state.turn
    state = advance(state, lambda s: s.step == Step.DECLARE_ATTACKERS
                    and s.priority_player == seat)
    assert state.turn == turn and state.cards[guide].summoning_sick
    before_hand = list(state.players[defender].hand)
    before_library = list(state.players[defender].library)
    own_hand = list(state.players[seat].hand)
    assert before_library[-1] == top
    state = checked(state, seat, {'type': 'attack', 'attackers': [guide]})
    assert state.attackers == [guide] and state.cards[guide].tapped
    assert len(state.stack) == 1 and state.stack[0].source_card_id == guide
    assert state.stack[0].payload['target_player'] == defender
    state = settle(state)
    assert not state.stack
    assert state.players[defender].hand == before_hand + ([top] if is_land else [])
    assert state.players[defender].library == (before_library[:-1] if is_land else before_library)
    assert state.cards[top].zone == (Zone.HAND if is_land else Zone.LIBRARY)
    assert state.players[seat].hand == own_hand
    assert any(f'reveals {top_name} from the top of their library' in line for line in state.log)
    assert {pid: player.life for pid, player in state.players.items()} == {1: 20, 2: 20}
    print(f'ACTUAL Guide seat={seat} top={top_name} transferred={is_land} native_attack=True')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_foretold_saw_counters_actual_opponent_spell(seat):
    state = position(seat)
    saw = add(state, 'Saw It Coming', seat)
    state.players[seat].mana_pool = {'C': 2}
    state = checked(state, seat, {'type': 'foretell', 'card_id': saw})
    assert state.cards[saw].zone == Zone.EXILE and state.cards[saw].exile_face_down
    assert not state.stack and sum(state.players[seat].mana_pool.values()) == 0
    turn = state.turn
    opponent = 3-seat
    state = advance(state, lambda s: s.turn > turn and s.priority_player == opponent)
    bolt = add(state, 'Lightning Bolt', opponent)
    state.players[opponent].mana_pool = {'R': 1}
    state = checked(state, opponent, {'type': 'cast_spell', 'card_id': bolt,
                                     'targets': {'target_player': seat}})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == bolt
    target = state.stack[0].id
    assert sum(state.players[opponent].mana_pool.values()) == 0
    state = advance(state, lambda s: s.priority_player == seat)
    assert len(state.stack) == 1 and state.stack[0].id == target
    options = collect_cost_options(state, seat, state.cards[saw])
    assert [(option.id, option.mana_cost) for option in options] == [('foretell_0', '{1}{U}')]
    state.players[seat].mana_pool = {'C': 1, 'U': 1}
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': saw, 'from_exile': True,
                                 'cost_choice': {'id': 'foretell_0'},
                                 'targets': {'target_stack_id': target}})
    assert len(state.stack) == 2 and state.stack[-1].source_card_id == saw
    assert state.stack[-1].payload['__was_foretold'] is True
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = settle(state)
    assert not state.stack
    assert state.cards[saw].zone == state.cards[bolt].zone == Zone.GRAVEYARD
    assert not state.cards[saw].foretell_record
    assert {pid: player.life for pid, player in state.players.items()} == {1: 20, 2: 20}
    print(f'ACTUAL Saw seat={seat} bank_paid=2 later_paid=1U countered_bolt=True')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_serra_checked_attack_does_not_tap(seat):
    state = position(seat)
    state, angel = paid_creature(state, seat, 'Serra Angel', {'C': 3, 'W': 2})
    turn = state.turn
    state = advance(state, lambda s: s.active_player == seat and s.priority_player == seat
                    and s.step == Step.DECLARE_ATTACKERS and not s.cards[angel].summoning_sick)
    assert state.turn > turn and not state.cards[angel].tapped
    state = checked(state, seat, {'type': 'attack', 'attackers': [angel]})
    assert state.attackers == [angel] and state.cards[angel].zone == Zone.BATTLEFIELD
    assert not state.cards[angel].tapped
    assert not state.stack and state.winner is None
    print(f'ACTUAL Serra seat={seat} native_attack=True tapped=False')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_foretold_doomskar_destroys_both_boards_but_not_lands(seat):
    state = position(seat)
    creatures = [add(state, 'Serra Angel', seat, Zone.BATTLEFIELD),
                 add(state, 'Goblin Guide', 3-seat, Zone.BATTLEFIELD)]
    lands = [add(state, name, owner, Zone.BATTLEFIELD)
             for name, owner in [('Island', seat), ('Plateau', seat),
                                 ('Mountain', 3-seat), ('Plateau', 3-seat)]]
    doomskar = add(state, 'Doomskar', seat)
    state.players[seat].mana_pool = {'C': 2}
    state = checked(state, seat, {'type': 'foretell', 'card_id': doomskar})
    assert state.cards[doomskar].zone == Zone.EXILE and state.cards[doomskar].exile_face_down
    assert not state.stack and sum(state.players[seat].mana_pool.values()) == 0
    turn = state.turn
    state = advance(state, lambda s: s.turn > turn and s.active_player == seat
                    and s.priority_player == seat and s.step == Step.PRECOMBAT_MAIN)
    options = collect_cost_options(state, seat, state.cards[doomskar])
    assert [(option.id, option.mana_cost) for option in options] == [('foretell_0', '{1}{W}{W}')]
    state.players[seat].mana_pool = {'C': 1, 'W': 2}
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': doomskar,
                                 'from_exile': True, 'cost_choice': {'id': 'foretell_0'}})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == doomskar
    assert state.stack[0].payload['__was_foretold'] is True
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = settle(state)
    assert not state.stack and state.cards[doomskar].zone == Zone.GRAVEYARD
    assert not state.cards[doomskar].foretell_record
    for cid in creatures:
        assert state.cards[cid].zone == Zone.GRAVEYARD
        assert cid in state.players[state.cards[cid].owner].graveyard
        assert cid not in state.players[state.cards[cid].owner].battlefield
    for cid in lands:
        assert state.cards[cid].zone == Zone.BATTLEFIELD
        assert cid in state.players[state.cards[cid].owner].battlefield
        assert cid not in state.players[state.cards[cid].owner].graveyard
    assert {pid: player.life for pid, player in state.players.items()} == {1: 20, 2: 20}
    print(f'ACTUAL Doomskar seat={seat} bank_paid=2 later_paid=1WW creatures_destroyed=2 lands_remain=4')
