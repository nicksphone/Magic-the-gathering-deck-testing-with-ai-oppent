"""Canonical paid casts: printed MV, announced stack X, and alternate cost."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.costs import collect_cost_options
from tests.test_any_player_cast_damage import checked, setup
from tests.test_linked_damage_targets import raw_card

FIXTURES = Path(__file__).parent / 'fixtures'
WAIT = {'type': 'pass_priority'}
RAW = {
    name: json.loads((FIXTURES / path).read_bytes())
    for name, path in {
        'Rift Bolt': 'suspend_canonical/rift-bolt.json',
        'Walking Ballista': 'graveyard_permissions/walking-ballista.json',
        'Behold the Multiverse': 'low_mana_value_cast/behold-the-multiverse.json',
    }.items()
}


def add_raw(state, name, seat):
    raw = RAW[name]
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) >= 60
    if name == 'Behold the Multiverse':
        proof = json.loads((FIXTURES / 'low_mana_value_cast/provenance.json').read_bytes())
        encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        assert sha256(encoded.encode()).hexdigest() == proof['cards'][name]['object_sha256']
    card = raw_card(state, deepcopy(raw), seat, Zone.HAND)
    assert card.oracle_text == raw['oracle_text'] and card.mana_cost == raw['mana_cost']
    return card.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case,expected_triggers', [
    ('printed-three', 1),
    ('foretold-four-paid-two', 0),
    ('double-x-one', 1),
    ('double-x-two', 0),
])
def test_paid_native_cast_uses_stack_mana_value(seat, case, expected_triggers):
    state, source_id = setup(seat)
    name = ('Rift Bolt' if case == 'printed-three' else
            'Behold the Multiverse' if case == 'foretold-four-paid-two' else
            'Walking Ballista')
    cid = add_raw(state, name, seat)
    action = {'type': 'cast_spell', 'card_id': cid,
              'cost_choice': {'id': 'base'}, 'targets': {}}
    if case == 'printed-three':
        assert RAW[name]['cmc'] == 3 and RAW[name]['mana_cost'] == '{2}{R}'
        state.players[seat].mana_pool = {'R': 1, 'C': 2}
        action['targets'] = {'target_player': 3-seat}
    elif case == 'foretold-four-paid-two':
        assert RAW[name]['cmc'] == 4 and RAW[name]['mana_cost'] == '{3}{U}'
        state.players[seat].mana_pool = {'C': 2}
        state = checked(state, seat, {'type': 'foretell', 'card_id': cid})
        assert state.cards[cid].zone == Zone.EXILE and not state.stack
        assert sum(state.players[seat].mana_pool.values()) == 0
        turn = state.turn
        for _ in range(64):
            if state.turn > turn and state.priority_player == seat:
                break
            state = checked(state, state.priority_player, WAIT)
        assert state.turn > turn and state.priority_player == seat
        state.players[seat].mana_pool = {'C': 1, 'U': 1}
        options = collect_cost_options(state, seat, state.cards[cid])
        option = next(option for option in options if option.id == 'foretell_0')
        assert option.mana_cost == '{1}{U}'
        action.update(from_exile=True, cost_choice={'id': option.id})
    else:
        x = 1 if case == 'double-x-one' else 2
        assert RAW[name]['mana_cost'] == '{X}{X}' and RAW[name]['cmc'] == 0
        state.players[seat].mana_pool = {'C': 2*x}
        action['targets'] = {'x_value': x}
    state = checked(state, seat, action)
    assert sum(state.players[seat].mana_pool.values()) == 0
    spell = next(item for item in state.stack if item.source_card_id == cid)
    assert state.cards[cid].mana_cost == RAW[name]['mana_cost']
    if name == 'Walking Ballista':
        assert spell.payload['x_value'] == x
    if name == 'Behold the Multiverse':
        assert spell.payload['__was_foretold'] is True
    triggers = [item for item in state.stack if item.source_card_id == source_id]
    assert len(triggers) == expected_triggers
    assert len(state.stack) == 1 + expected_triggers
    if triggers:
        assert state.stack[-1] == triggers[0]
        assert triggers[0].controller == seat
        assert triggers[0].payload['target_player'] == seat
        state = checked(state, state.priority_player, WAIT)
        state = checked(state, state.priority_player, WAIT)
        assert len(state.stack) == 1 and state.stack[0].source_card_id == cid
    assert state.players[seat].life == 20 - 2*expected_triggers
    assert state.players[3-seat].life == 20 and state.winner is None
