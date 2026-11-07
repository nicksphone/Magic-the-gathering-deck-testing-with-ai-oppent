"""Full canonical paid creature entry and later-turn Foretell lifecycles."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.continuous import effective_combat_stats, has_keyword
from rules_engine.costs import collect_cost_options
from rules_engine.foretell import can_look, record
from tests.test_any_player_cast_damage import checked, settle, RULES
from tests.test_linked_damage_targets import raw_card
from tests.test_variable_mana import clean


DATA = (Path(__file__).parent / 'fixtures/foretell_native_entry.json').read_bytes()
assert hashlib.sha256(DATA).hexdigest() == '4ad57f3f3b264005935bb02379fdee0062a33a8e425a181b4a169303873a4530'
RAW = json.loads(DATA)
WAIT = {'type': 'pass_priority'}


def add_hand(state, name, seat):
    raw = RAW[name]
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) >= 68
    card = raw_card(state, raw, seat, Zone.HAND)
    assert card.oracle_text == raw['oracle_text'] and card.mana_cost == raw['mana_cost']
    return card.id


def assert_private_foretell(state, cid, seat):
    assert state.cards[cid].zone == Zone.EXILE and state.cards[cid].exile_face_down
    assert cid in state.players[seat].exile and cid not in state.players[seat].hand
    assert can_look(state.cards[cid], seat) and not can_look(state.cards[cid], 3-seat)
    assert record(state.cards[cid])['player_id'] == seat
    assert not state.stack and state.priority_player == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_charger_flash_entry_enables_offturn_one_mana_raven_foretell(seat):
    state = clean()
    state.active_player = state.priority_player = 3-seat
    charger = add_hand(state, 'Cosmos Charger', seat)
    raven = add_hand(state, 'Augury Raven', seat)
    state.players[seat].mana_pool = {'C': 4, 'U': 1}
    state = checked(state, 3-seat, WAIT)
    turn = state.turn
    before = serialize_match_snapshot(state)
    assert not any(move['type'] == 'foretell' and move.get('card_id') == raven
                   for move in RULES.legal_moves(state, seat))
    assert serialize_match_snapshot(state) == before
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': charger,
                    'cost_choice': {'id': 'base'}, 'targets': {}})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == charger
    assert {color: amount for color, amount in state.players[seat].mana_pool.items()
            if amount} == {'C': 1}
    assert state.players[seat].mana_pool['U'] == 0
    state = settle(state)
    assert state.turn == turn and state.active_player == 3-seat
    assert state.cards[charger].zone == Zone.BATTLEFIELD
    assert has_keyword(state, charger, 'flying')
    if state.priority_player != seat:
        state = checked(state, state.priority_player, WAIT)
    before = serialize_match_snapshot(state)
    move = next(move for move in RULES.legal_moves(state, seat)
                if move['type'] == 'foretell' and move.get('card_id') == raven)
    assert move['mana_cost'] == '{1}'
    assert serialize_match_snapshot(state) == before
    state = checked(state, seat, {'type': 'foretell', 'card_id': raven})
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.turn == turn and state.active_player == 3-seat
    assert_private_foretell(state, raven, seat)
    assert state.cards[raven].oracle_text == RAW['Augury Raven']['oracle_text']
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_raven_foretell_then_native_later_turn_cast_enters_flying(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    raven = add_hand(state, 'Augury Raven', seat)
    state.players[seat].mana_pool = {'C': 2}
    turn = state.turn
    state = checked(state, seat, {'type': 'foretell', 'card_id': raven})
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert_private_foretell(state, raven, seat)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    for _ in range(96):
        if (state.turn > turn and state.active_player == state.priority_player == seat
                and state.step == Step.PRECOMBAT_MAIN):
            break
        assert state.winner is None
        state = checked(state, state.priority_player, WAIT)
    assert state.turn > turn and state.active_player == state.priority_player == seat
    assert state.step == Step.PRECOMBAT_MAIN
    state.players[seat].mana_pool = {'C': 1, 'U': 1}
    before = serialize_match_snapshot(state)
    options = collect_cost_options(state, seat, state.cards[raven])
    assert [(option.id, option.mana_cost) for option in options] == [('foretell_0', '{1}{U}')]
    assert serialize_match_snapshot(state) == before
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': raven,
                    'from_exile': True, 'cost_choice': {'id': 'foretell_0'}, 'targets': {}})
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert len(state.stack) == 1 and state.stack[0].source_card_id == raven
    assert state.stack[0].payload['__was_foretold'] is True
    state = settle(state)
    assert state.cards[raven].zone == Zone.BATTLEFIELD
    assert raven in state.players[seat].battlefield and raven not in state.players[seat].exile
    assert has_keyword(state, raven, 'flying') and effective_combat_stats(state, raven) == (3, 3)
    assert state.cards[raven].oracle_text == RAW['Augury Raven']['oracle_text']
    assert not state.stack and state.winner is None
