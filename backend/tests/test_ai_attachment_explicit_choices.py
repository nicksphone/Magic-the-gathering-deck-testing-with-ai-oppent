"""Canonical Aura choices survive AI projection and native checked payment."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from tests.test_ai_search_prefix import bare_state
from tests.test_linked_damage_targets import raw_card
from tests.browser_positive83_canonical import raw_card as canonical_raw
from tests.test_training_choice_coverage import FIXTURES


def aura_position(seat, *, second_host=False):
    state = bare_state(seat)
    folder = FIXTURES / 'color_state_forwarding'
    record = next(row for row in json.loads((folder / 'provenance.json').read_text())['cards']
                  if row['name'] == 'Favor of the Overbeing')
    encoded = (folder / record['file']).read_bytes()
    assert sha256(encoded).hexdigest() == record['sha256']
    aura_raw = json.loads(encoded)
    assert aura_raw['object'] == 'card' and aura_raw['mana_cost'] == '{1}{G/U}'
    aura = raw_card(state, aura_raw, seat, Zone.HAND)
    host_raw = canonical_raw('Grizzly Bears')
    hosts = [raw_card(state, host_raw, seat, Zone.BATTLEFIELD)
             for _ in range(2 if second_host else 1)]
    for host in hosts:
        assign_static_order_on_battlefield_entry(state, host.id)
    for card, original in [(aura, aura_raw), *((host, host_raw) for host in hosts)]:
        assert (card.name, card.mana_cost, card.oracle_text, card.type_line) == tuple(
            original[key] for key in ('name', 'mana_cost', 'oracle_text', 'type_line'))
    state.players[seat].mana_pool = {'C': 1, 'G': 1, 'U': 1}
    agent = AIAgent(difficulty='strong', archetype='Midrange')
    move = next(move for move in agent.engine.legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move['card_id'] == aura.id)
    return state, agent, move, aura, hosts


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('branch', ['G', 'U'])
def test_explicit_hybrid_branch_preserves_full_checked_execution(seat, branch):
    state, agent, move, aura, hosts = aura_position(seat)
    supplied = {**move, 'cost_choice': {'id': 'base'}, 'hybrid_choices': [branch],
                'targets': {'target_card_id': hosts[0].id}}
    original, before = deepcopy(supplied), serialize_match_snapshot(state)
    expected = complete_action(supplied)
    native = checked_action(state, agent.engine, seat, expected)
    actual = complete_action(agent._materialize_action(state, supplied, seat))
    projected = checked_action(state, agent.engine, seat, actual)
    assert actual['hybrid_choices'] == [branch]
    assert actual['cost_choice'] == expected['cost_choice']
    assert actual['targets'] == expected['targets']
    assert projected.cards[aura.id].zone == Zone.STACK
    assert projected.players[seat].mana_pool[branch] == 0
    assert projected.players[seat].mana_pool['U' if branch == 'G' else 'G'] == 1
    assert serialize_match_snapshot(projected) == serialize_match_snapshot(native)
    assert serialize_match_snapshot(state) == before and supplied == original


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_attachment_target_is_not_reranked(seat):
    state, agent, move, _, hosts = aura_position(seat, second_host=True)
    supplied = {**move, 'cost_choice': {'id': 'base'}, 'hybrid_choices': ['G'],
                'targets': {'target_card_id': hosts[0].id}}
    original, before = deepcopy(supplied), serialize_match_snapshot(state)
    native = checked_action(state, agent.engine, seat, complete_action(supplied))
    actual = complete_action(agent._materialize_action(state, supplied, seat))
    assert actual['targets'] == supplied['targets']
    projected = checked_action(state, agent.engine, seat, actual)
    assert serialize_match_snapshot(projected) == serialize_match_snapshot(native)
    assert serialize_match_snapshot(state) == before and supplied == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['wrong_branch', 'empty_branches', 'unpayable_branch',
                                 'unknown_cost', 'unknown_target'])
def test_explicit_invalid_attachment_choices_are_not_repaired(seat, bad):
    state, agent, move, _, hosts = aura_position(seat)
    supplied = {**move, 'cost_choice': {'id': 'base'}, 'hybrid_choices': ['G'],
                'targets': {'target_card_id': hosts[0].id}}
    if bad == 'wrong_branch':
        supplied['hybrid_choices'] = ['B']
    elif bad == 'empty_branches':
        supplied['hybrid_choices'] = []
    elif bad == 'unpayable_branch':
        state.players[seat].mana_pool = {'C': 1, 'G': 1}
        supplied['hybrid_choices'] = ['U']
    elif bad == 'unknown_cost':
        supplied['cost_choice'] = {'id': 'not-an-offered-cost'}
    else:
        supplied['targets'] = {'target_card_id': 'not-an-offered-target'}
    original, before = deepcopy(supplied), serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, agent.engine, seat, complete_action(supplied))
    actual = agent._materialize_action(state, supplied, seat)
    with pytest.raises(ActionRejected):
        checked_action(state, agent.engine, seat, complete_action(actual))
    assert serialize_match_snapshot(state) == before and supplied == original
