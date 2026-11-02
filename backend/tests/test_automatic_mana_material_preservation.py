"""Automatic mana must not consume extra cards when ordinary lands suffice."""
from copy import deepcopy
import json

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import activate_mana_ability, mana_ability_specs
from tests.test_fixed_spell_cost_witness import add
from tests.test_spell_cost_overlap_investigation import position, unchanged_root


def payment_position(seat, family, spell_name, free_lands):
    state = position(seat)
    source = add(state, 'Skirge Familiar' if family == 'discard' else 'Phyrexian Tower', seat)
    lands = [add(state, 'Swamp', seat) for _ in range(2 if free_lands else 0)]
    victim = add(state, 'Ornithopter', seat)
    fuel = add(state, 'Island', seat, Zone.HAND) if family == 'discard' else add(state, 'Raging Goblin', seat)
    spell = add(state, spell_name, seat, Zone.HAND)
    if family == 'discard' and not free_lands and spell_name == 'Deadly Dispute':
        # One land plus the required discard activation supplies the genuine 1B.
        lands.append(add(state, 'Swamp', seat))
    action = dict(type='cast_spell', card_id=spell.id,
                  cost_choice=dict(id='base', sacrifice_card_ids=[victim.id]))
    return state, source, lands, victim, fuel, spell, action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['discard', 'sacrifice'])
@pytest.mark.parametrize('spell_name', ['Deadly Dispute', 'Village Rites'])
@pytest.mark.parametrize('free_lands', [True, False])
def test_automatic_payment_consumes_extra_cards_only_when_needed(seat, family, spell_name, free_lands):
    state, source, lands, victim, fuel, spell, action = payment_position(seat, family, spell_name, free_lands)
    original_action = deepcopy(action)
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(snapshot)))
    assert serialize_match_snapshot(restored) == snapshot
    with unchanged_root(state), unchanged_root(restored):
        paid = checked_action(state, RulesEngine(), seat, action)
        replay = checked_action(restored, RulesEngine(), seat, action)
    assert action == original_action
    assert serialize_match_snapshot(paid) == serialize_match_snapshot(replay)
    assert paid.cards[spell.id].zone == Zone.STACK
    assert paid.cards[victim.id].zone == Zone.GRAVEYARD
    assert paid.stack[-1].payload['mana_spent'] == (2 if spell_name == 'Deadly Dispute' else 1)
    if free_lands:
        expected = Zone.HAND if family == 'discard' else Zone.BATTLEFIELD
        assert paid.cards[fuel.id].zone == expected, 'Automatic payment consumed an unnecessary extra card'
        if family == 'discard':
            assert not paid.cards[source.id].tapped
        # Tower's ordinary colorless tap is free; only its sacrifice must be avoided.
        free_sources = lands + ([source] if family == 'sacrifice' else [])
        assert sum(paid.cards[land.id].tapped for land in free_sources) == (2 if spell_name == 'Deadly Dispute' else 1)
    else:
        assert paid.cards[fuel.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['discard', 'sacrifice'])
def test_explicit_resource_consuming_mana_activation_remains_allowed(seat, family):
    state, source, _, _, fuel, _, _ = payment_position(seat, family, 'Village Rites', True)
    specs = mana_ability_specs(source, state)
    index = next(index for index, cost, _ in specs if 'Discard' in cost) if family == 'discard' else next(
        index for index, cost, _ in specs if 'Sacrifice a creature' in cost)
    choices = {'discard_card_ids': [fuel.id]} if family == 'discard' else {'sacrifice_card_ids': [fuel.id]}
    assert activate_mana_ability(state, seat, source.id, index, 'B', payment_choices=choices)
    assert state.cards[fuel.id].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool['B'] == (1 if family == 'discard' else 2)
