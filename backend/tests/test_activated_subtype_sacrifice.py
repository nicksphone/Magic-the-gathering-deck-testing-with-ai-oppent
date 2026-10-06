"""Canonical subtype sacrifices use the shared selected-resource payment path."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.costs import (
    activated_cost_available, activated_cost_candidates, apply_activated_costs,
    parse_activated_cost,
)
from tests.test_ai_search_prefix import bare_state
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures'


def canonical(state, name, seat):
    for filename in ('mana_resources.json', 'qualified_spell_costs.json'):
        rows = json.loads((FIXTURES / filename).read_text())
        row = next((row for row in rows if row['name'] == name), None)
        if row is not None:
            return raw_card(state, row, seat, Zone.BATTLEFIELD)
    raise AssertionError(name)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('sacrifice_source', [False, True])
def test_canonical_prospector_selected_goblin_cost_and_root_preservation(seat, sacrifice_source):
    state = bare_state(seat)
    source = canonical(state, 'Skirk Prospector', seat)
    other = canonical(state, 'Goblin Instigator', seat)
    elf = canonical(state, 'Llanowar Elves', seat)
    enemy = canonical(state, 'Goblin Instigator', 3-seat)
    cost_text = source.oracle_text.split(':', 1)[0]
    cost = parse_activated_cost(cost_text)
    assert cost.supported and cost.sacrifice_kind == 'subtype_goblin'
    assert cost.sacrifice_creatures == 1 and not cost.sacrifice_source
    candidates = activated_cost_candidates(state, seat, source.id, cost)
    assert set(candidates['sacrifice_card_ids']) == {source.id, other.id}
    selected = source if sacrifice_source else other
    choice = {'sacrifice_card_ids': [selected.id]}
    before = serialize_match_snapshot(state)
    assert activated_cost_available(state, seat, source.id, cost_text,
                                    ability_kind='mana', ability_index=0, payment_choices=choice)
    assert serialize_match_snapshot(state) == before
    paid = deepcopy(state)
    assert apply_activated_costs(paid, seat, source.id, cost_text,
                                 ability_kind='mana', ability_index=0, payment_choices=choice)
    assert selected.id in paid.players[seat].graveyard
    assert elf.id in paid.players[seat].battlefield
    assert enemy.id in paid.players[3-seat].battlefield
    assert serialize_match_snapshot(state) == before
    assert not paid.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['elf', 'enemy', 'reserved', 'duplicate', 'empty'])
def test_invalid_subtype_payment_is_rejected_before_mutation(seat, invalid):
    state = bare_state(seat)
    source = canonical(state, 'Skirk Prospector', seat)
    goblin = canonical(state, 'Goblin Instigator', seat)
    elf = canonical(state, 'Llanowar Elves', seat)
    enemy = canonical(state, 'Goblin Instigator', 3-seat)
    ids = {'elf': [elf.id], 'enemy': [enemy.id], 'reserved': [goblin.id],
           'duplicate': [goblin.id, goblin.id], 'empty': []}[invalid]
    options = {'payment_choices': {'sacrifice_card_ids': ids},
               'unavailable_resources': {goblin.id} if invalid == 'reserved' else (),
               'ability_kind': 'mana', 'ability_index': 0}
    before = serialize_match_snapshot(state)
    text = source.oracle_text.split(':', 1)[0]
    assert not activated_cost_available(state, seat, source.id, text, **options)
    assert not apply_activated_costs(state, seat, source.id, text, **options)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('text', ['Sacrifice a Goblin with flying', 'Sacrifice a madeup',
                                 'Sacrifice a Goblin, sacrifice a creature',
                                 'Sacrifice a creature, sacrifice a Goblin'])
def test_unrepresented_qualified_or_mixed_sacrifices_stay_unsupported(text):
    assert not parse_activated_cost(text).supported


@pytest.mark.parametrize('text,count,kind', [('Sacrifice a Goblin', 1, 'goblin'),
                                           ('Sacrifice two Goblins', 2, 'goblin'),
                                           ('Sacrifice an Elf', 1, 'elf')])
def test_generic_subtype_grammar_reuses_shared_cost_components(text, count, kind):
    cost = parse_activated_cost(text)
    assert cost.supported and cost.sacrifice_creatures == count
    assert cost.sacrifice_kind == 'subtype_' + kind
