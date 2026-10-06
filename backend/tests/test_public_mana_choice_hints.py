"""Canonical controller-scoped public mana views, not training-only enrichment."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.costs import activated_cost_candidates, parse_activated_cost
from rules_engine.mana import hybrid_payment_symbols
from rules_engine.mana_abilities import mana_ability_specs, mana_ability_views
from rules_engine.engine import RulesEngine
from tests.test_mana_executor_choices import ROWS, position, add

ROWS.update({row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/affinity/permanents.json').read_text())['data']})


def select(state, source, fragment):
    spec = next(s for s in mana_ability_specs(source, state) if fragment in s[1])
    view = next(v for v in mana_ability_views(state, source) if v['ability_index'] == spec[0])
    return spec, view


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,fragment,discard,sacrifice,hybrid', [
    ('Forest', '{T}', 0, 0, 0),
    ('Phyrexian Tower', 'Sacrifice', 0, 1, 0),
    ('Bog Witch', 'Discard', 1, 0, 0),
    ('Skirk Prospector', 'Sacrifice', 0, 1, 0),
    ('Graven Cairns', '{B/R}', 0, 0, 1),
    ('Flooded Grove', '{G/U}', 0, 0, 1),
    ('Chromatic Star', 'Sacrifice', 0, 0, 0),
])
def test_public_hints_match_cost_helpers_and_forward_without_state_mutation(
        seat, name, fragment, discard, sacrifice, hybrid):
    state = position(seat)
    source = add(state, name, seat)
    goblin = add(state, 'Raging Goblin', seat)
    elf = add(state, 'Llanowar Elves', seat)
    own_hand = add(state, 'Forest', seat, Zone.HAND)
    other_hand = add(state, 'Island', 3-seat, Zone.HAND)
    other_goblin = add(state, 'Raging Goblin', 3-seat)
    state.players[seat].mana_pool.update(B=1, R=1, G=1, C=1)
    if name == 'Skirk Prospector':
        source.tapped = source.summoning_sick = True
    before = serialize_match_snapshot(state)
    spec, view = select(state, source, fragment)
    parsed = parse_activated_cost(spec[1])
    assert view['activation_costs'] == activated_cost_candidates(state, seat, source.id, parsed)
    assert view['hybrid_symbols'] == hybrid_payment_symbols(parsed.mana_cost)
    assert view['required_choices'] == {
        'payment_choices': bool(discard or sacrifice), 'hybrid_choices': bool(hybrid),
        'discard_card_count': discard, 'sacrifice_card_count': sacrifice,
        'hybrid_choice_count': hybrid}
    candidates = view['activation_costs']
    assert other_hand.id not in json.dumps(view)
    assert other_goblin.id not in candidates['sacrifice_card_ids']
    if discard:
        assert candidates['discard_card_ids'] == [own_hand.id]
    if name == 'Skirk Prospector':
        assert set(candidates['sacrifice_card_ids']) == {source.id, goblin.id}
        assert elf.id not in candidates['sacrifice_card_ids']
    if name == 'Chromatic Star':
        assert candidates['fixed_sacrifice_card_ids'] == [source.id]
        assert candidates['sacrifice_creatures'] == 1
    moves = RulesEngine().legal_moves(state, seat)
    move = next(m for m in moves if m['type'] == 'activate_mana_ability'
                and m['card_id'] == source.id and m['ability_index'] == spec[0])
    for key in ('activation_costs', 'hybrid_symbols', 'required_choices',
                'output_options', 'base_output_bundles'):
        assert move[key] == view[key]
    assert other_hand.id not in json.dumps(moves)
    assert serialize_match_snapshot(state) == before
    # Returned candidate lists never alias live player zones or subsequent views.
    view['activation_costs']['discard_card_ids'].clear()
    assert serialize_match_snapshot(state) == before
    assert select(state, source, fragment)[1]['activation_costs'] == activated_cost_candidates(
        state, seat, source.id, parsed)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,fragment,base', [
    ('Graven Cairns', '{B/R}', [{'B': 2}, {'B': 1, 'R': 1}, {'R': 2}]),
    ('Flooded Grove', '{G/U}', [{'G': 2}, {'G': 1, 'U': 1}, {'U': 2}]),
])
def test_public_hints_do_not_confuse_base_anchors_with_sphere_replacement(seat, name, fragment, base):
    state = position(seat)
    source = add(state, name, seat)
    add(state, 'Damping Sphere', seat)
    state.players[seat].mana_pool.update(R=1, G=1)
    before = serialize_match_snapshot(state)
    _, view = select(state, source, fragment)
    assert view['outputs'] == {'C': 1}
    assert view['base_output_bundles'] == base
    assert view['required_choices']['hybrid_choice_count'] == 1
    assert all(option['color'] in option['output_bundle'] for option in view['output_options'])
    assert not any(option['color'] == 'C' for option in view['output_options'])
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Bog Witch', 'Phyrexian Tower'])
def test_unavailable_mana_sources_do_not_advertise_cost_hints(seat, name):
    state = position(seat)
    source = add(state, name, seat)
    source.tapped = True
    add(state, 'Raging Goblin', seat)
    add(state, 'Forest', seat, Zone.HAND)
    state.players[seat].mana_pool['B'] = 1
    before = serialize_match_snapshot(state)
    assert not mana_ability_views(state, source)
    assert serialize_match_snapshot(state) == before
