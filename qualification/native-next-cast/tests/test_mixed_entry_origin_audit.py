"""Canonical intake/real paid upstream audit. No manufactured origin frame."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.state import Zone, Step
from rules_engine.move_generator import legal_moves
from tests.test_graveyard_self_activation_product import position, FAMILIES, raw_card, act, snapshot

HERE = Path(__file__).resolve().parents[1]
INTAKE = json.loads((HERE / 'fixtures/canonical.json').read_text())
ROWS = {entry['row']['name']: entry['row'] for entry in INTAKE['matches']}


def record(request, **data):
    target = HERE / 'records' / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    with target.open('x') as f:
        json.dump({'node': request.node.nodeid, **data}, f, indent=2, sort_keys=True)


def paid_source(seat, name):
    state, _ = position(seat, FAMILIES[0])
    card = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 2 if name == 'Summon: Fenrir' else 0}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id, 'targets': {}})
    return state, card.id


def finish_priority(state, maximum=16):
    for _ in range(maximum):
        if not state.stack or state.pending_mechanic_choice or state.pending_replacement_choice:
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Actual source priority exceeded declared16 passes')


def test_full_official_bulk_intake_pins():
    assert INTAKE['sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'
    assert len(ROWS) == 3
    assert ROWS['Summon: Fenrir']['oracle_text'].splitlines()[2] == (
        'II — Heavenward Howl — When you next cast a creature spell this turn, that creature enters with an additional +1/+1 counter on it.')


@pytest.mark.parametrize('seat', [1, 2])
def test_strict_full_canonical_conditional_source_does_not_arm_unconditional_packet(request, seat):
    state, cid = paid_source(seat, 'Long List of the Ents')
    before = snapshot(state)
    state = finish_priority(state)
    record(request, scope='strict upstream conditional admission, not mixed entry ordering',
           paid_before=before, after=snapshot(state), source_id=cid,
           original_oracle=ROWS['Long List of the Ents']['oracle_text'])
    assert not state.pending_entry_counters, 'Noted-type condition was discarded into unconditional entry seed'


@pytest.mark.parametrize('seat', [1, 2])
def test_strict_full_canonical_fenrir_first_chapter_is_real_search_before_one_shot(request, seat):
    state, cid = paid_source(seat, 'Summon: Fenrir')
    state = finish_priority(state)
    # Search may pause or auto-select a real eligible library card. Either
    # route must be observable without inventing a chapter/frame/action.
    offered = legal_moves(state, seat)
    record(request, scope='strict upstream complete paid source prerequisites',
           after=snapshot(state), source_id=cid, offered=offered,
           original_oracle=ROWS['Summon: Fenrir']['oracle_text'])
    found = [card for card in state.cards.values() if card.owner == seat
             and card.zone == Zone.BATTLEFIELD and 'Basic' in card.type_line]
    pending = state.pending_mechanic_choice
    assert found or (pending and any('search' in str(value).lower() for value in pending.values())), (
        'Complete real Crescent Fang chapter did not reach its search instruction')
