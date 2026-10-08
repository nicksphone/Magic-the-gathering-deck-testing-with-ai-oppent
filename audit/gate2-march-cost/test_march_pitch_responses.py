"""Pitch payment persists across real responses and paid zero-MV token cause."""
import json
from pathlib import Path

import pytest

import inventory as inv
import domain_paid_support as g
from test_march_pitch_paid import setup
from test_march_paid_v2 import prepare
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


@pytest.fixture(scope='module')
def facts():
    seed, selected, _ = inv.load_inputs()
    raws = {name: selected[row['scryfall_id']] for name, row in seed.items()}
    directory = inv.ROOT / 'backend/tests/fixtures/cloudshift_compound_audit'
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split()
        assert inv.sha(directory / Path(name).name) == digest
    raw = json.loads((directory / 'flicker-of-fate.json').read_bytes())
    assert raw['name'] == 'Flicker of Fate' and raw['oracle_id']
    raws[raw['name']] = raw
    return raws


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('n', [1, 2])
def test_paid_x_zero_pitch_cannot_remove_colored_white(facts, seat, n):
    state, source, target, retained = prepare(facts, seat, 0, 'artifact')
    assert state.cards[target].is_token and state.cards[target].zone == Zone.BATTLEFIELD
    selected = [retained[0]]
    if n == 2:
        selected.append(g.add(state, facts, 'Boros Charm', seat, Zone.HAND))
    state = g.act(state, seat, 'cast_spell', card_id=source,
                  cost_choice={'id': 'base', 'exile_card_ids': selected},
                  targets={'x_value': 0, 'target_card_id': target})
    assert state.stack[-1].payload['mana_spent'] == 1
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert all(state.cards[cid].zone == Zone.EXILE for cid in selected)
    state = g.restore(state)
    g.resolve(state)
    assert state.cards[target].zone == Zone.CEASED
    assert f'{state.cards[target].name} is exiled.' in state.log
    assert state.cards[source].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('response', ['counterspell', 'bounce', 'blink'])
def test_real_response_does_not_refund_selected_exiles(facts, seat, response):
    state, action, whites, *_ = setup(facts, seat)
    if response == 'blink':
        target = g.add(state, facts, 'Intangible Virtue', 3-seat)
        action['targets']['target_card_id'] = target
    source, target = action['card_id'], action['targets']['target_card_id']
    state = checked_action(state, RulesEngine(), seat, action)
    assert state.stack[-1].payload['mana_spent'] == 1
    assert all(state.cards[cid].zone == Zone.EXILE for cid in whites[:2])
    incarnation = object_incarnation(state.cards[target])
    state = g.respond(g.restore(state), 3-seat)
    name = {'counterspell': 'Counterspell', 'bounce': 'Otawara, Soaring City',
            'blink': 'Flicker of Fate'}[response]
    responder = g.add(state, facts, name, 3-seat, Zone.HAND)
    if response == 'counterspell':
        state.players[3-seat].mana_pool = {'U': 2}
        state = g.cast(state, 3-seat, responder, target_stack_id=state.stack[-1].id)
    elif response == 'bounce':
        state.players[3-seat].mana_pool = {'C': 3, 'U': 1}
        state = g.act(state, 3-seat, 'activate_ability', card_id=responder, ability_index=1,
                      targets={'target_card_id': target})
    else:
        state.players[3-seat].mana_pool = {'C': 1, 'W': 1}
        state = g.cast(state, 3-seat, responder, target_card_id=target)
    assert sum(state.players[3-seat].mana_pool.values()) == 0
    state = g.restore(state)
    g.resolve(state)
    assert state.cards[responder].zone == Zone.GRAVEYARD
    if response != 'counterspell':
        if response == 'blink':
            assert object_incarnation(state.cards[target]) != incarnation
        assert len(state.stack) == 1 and state.stack[-1].source_card_id == source
        state = g.restore(state)
        g.resolve(state)
    assert state.cards[target].zone == (Zone.HAND if response == 'bounce' else Zone.BATTLEFIELD)
    assert state.cards[source].zone == Zone.GRAVEYARD and not state.stack
    assert all(state.cards[cid].zone == Zone.EXILE for cid in whites[:2])
    assert state.cards[whites[2]].zone == Zone.HAND
