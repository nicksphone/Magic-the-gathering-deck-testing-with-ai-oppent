"""Canonical selected-ability cost reductions, not fabricated competitive decks."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.activation_modifiers import activation_cost_view, activation_modifier_gaps
from rules_engine.action_validation import checked_action
from rules_engine.costs import activated_cost_available
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from tests.test_activation_modifiers import board, add
from tests.test_ai_recurring_engines import add as raw_add, resolve
from tests.test_ability_suppression import add as suppression_add

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/ability_cost_discounts.json').read_text())}


def source(state, name, seat):
    card = raw_add(state, name, seat, cards=ROWS)
    card.summoning_sick = False
    return card


def view(state, card):
    ability = extract_activated_abilities(card)[0]
    from rules_engine.costs import parse_activated_cost
    cost = parse_activated_cost(ability['mana_cost'])
    return activation_cost_view(state, card.controller, card.id, cost.mana_cost,
                                ability_index=ability['index'])['requirements'][0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
def test_selected_effect_excludes_cost_note_but_keeps_printed_provenance(seat, name):
    state = board(seat)
    card = source(state, name, seat)
    ability = extract_activated_abilities(card)[0]
    assert ability['cost_modifier']
    assert 'This ability costs' not in ability['text']
    assert 'This ability costs' in ability['label']
    assert card.oracle_text == ROWS[name]['oracle_text']
    assert not activation_modifier_gaps(card.oracle_text, card.name)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('units', [0, 1, 3, 8])
@pytest.mark.parametrize('name', ["Tamiyo's Logbook", 'Deepwood Denizen', 'Battlefield Butcher'])
def test_counts_are_live_controller_relative_colored_and_snapshot_safe(seat, units, name):
    state = board(seat)
    card = source(state, name, seat)
    if name == "Tamiyo's Logbook":
        for _ in range(units):
            add(state, 'Mind Stone', seat)
        for _ in range(7):
            add(state, 'Mind Stone', 3-seat)
        # The Logbook itself must not count as an 'other' artifact.
        color = 'U'
    elif name == 'Deepwood Denizen':
        add(state, 'Azure Mage', seat).counters['+1/+1'] = units
        add(state, 'Azure Mage', 3-seat).counters['+1/+1'] = 7
        add(state, 'Mind Stone', seat).counters['+1/+1'] = 7
        color = 'G'
    else:
        for _ in range(units):
            add(state, 'Azure Mage', seat, Zone.GRAVEYARD)
        add(state, 'Azure Mage', 3-seat, Zone.GRAVEYARD)
        add(state, 'Mind Stone', seat, Zone.GRAVEYARD)
        add(state, 'Azure Mage', seat, Zone.GRAVEYARD).is_token = True
        color = None
    result = view(state, card)
    assert result['generic'] == max(0, 5-units)
    if color:
        assert result[color] == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert view(restored, restored.cards[card.id]) == result
    suppression_add(state, 'Humility', 3-seat)
    if 'Creature' in card.types:
        assert view(state, card)['generic'] == 5


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Starport Security', 'Esquire of the King'])
def test_controlled_creature_conditions_are_not_global(seat, name):
    state = board(seat)
    card = source(state, name, seat)
    base = 3 if name == 'Starport Security' else 4
    assert view(state, card)['generic'] == base
    other = raw_add(state, 'Sheoldred, the Apocalypse', 3-seat)
    other.counters['+1/+1'] = 1
    assert view(state, card)['generic'] == base
    condition = raw_add(state, 'Sheoldred, the Apocalypse', seat)
    condition.counters['+1/+1'] = 1
    assert view(state, card)['generic'] == base-2
    condition.zone = Zone.GRAVEYARD
    assert view(state, card)['generic'] == base


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ["Tamiyo's Logbook", 'Deepwood Denizen', 'Battlefield Butcher'])
def test_checked_payment_and_effect_resolution_use_selected_discount(seat, name):
    state = board(seat)
    card = source(state, name, seat)
    if name == "Tamiyo's Logbook":
        for _ in range(5):
            add(state, 'Mind Stone', seat).tapped = True
        state.players[seat].mana_pool['U'] = 1
    elif name == 'Deepwood Denizen':
        card.counters['+1/+1'] = 5
        state.players[seat].mana_pool['G'] = 1
    else:
        for _ in range(5):
            add(state, 'Azure Mage', seat, Zone.GRAVEYARD)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'activate_ability' and m['card_id'] == card.id)
    assert move['activation_costs']['requirements'][0]['generic'] == 0
    result = checked_action(state, RulesEngine(), seat, move)
    assert result.cards[card.id].tapped
    assert sum(result.players[seat].mana_pool.values()) == 0
    result = resolve(result)
    if name == 'Battlefield Butcher':
        assert result.players[3-seat].life == 18
    else:
        assert len(result.players[seat].hand) == 1


def test_missing_or_unrelated_ability_index_does_not_apply_card_discount():
    state = board()
    card = source(state, 'Deepwood Denizen', 1)
    card.counters['+1/+1'] = 5
    ability = extract_activated_abilities(card)[0]
    state.players[1].mana_pool['G'] = 1
    assert activated_cost_available(state, 1, card.id, ability['mana_cost'], ability_index=ability['index'])
    assert not activated_cost_available(state, 1, card.id, ability['mana_cost'])
    assert not activated_cost_available(state, 1, card.id, ability['mana_cost'], ability_index=999)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_two_ability_card_keeps_its_discount_on_only_one_ability(seat):
    state = board(seat)
    card = source(state, "Hylda's Crown of Winter", seat)
    abilities = extract_activated_abilities(card)
    assert len(abilities) == 2
    assert abilities[0]['cost_modifier'] and abilities[1]['cost_modifier'] is None
    assert view(state, card)['generic'] == 0
    assert not activated_cost_available(state, seat, card.id, abilities[1]['mana_cost'], ability_index=abilities[1]['index'])
    state.active_player = 3-seat
    assert view(state, card)['generic'] == 1
    assert not activated_cost_available(state, seat, card.id, abilities[0]['mana_cost'], ability_index=abilities[0]['index'])
    state.players[seat].mana_pool['C'] = 1
    assert activated_cost_available(state, seat, card.id, abilities[0]['mana_cost'], ability_index=abilities[0]['index'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Starport Security', 'Esquire of the King', "Hylda's Crown of Winter"])
def test_conditional_discount_checked_activation_and_real_effect(seat, name):
    from rules_engine.continuous import effective_power
    state = board(seat)
    card = source(state, name, seat)
    qualifier = raw_add(state, 'Sheoldred, the Apocalypse', seat)
    qualifier.counters['+1/+1'] = 1
    enemy = add(state, 'Azure Mage', 3-seat)
    state.players[seat].mana_pool.update(C=0 if name == "Hylda's Crown of Winter" else 1 if name == 'Starport Security' else 2,
                                       W=0 if name == "Hylda's Crown of Winter" else 1)
    action = {'type': 'activate_ability', 'card_id': card.id, 'ability_index': 0,
              'targets': {} if name == 'Esquire of the King' else {'target_card_id': enemy.id}}
    result = resolve(checked_action(state, RulesEngine(), seat, action))
    assert sum(result.players[seat].mana_pool.values()) == 0
    if name == 'Esquire of the King':
        assert effective_power(result, card.id) == 2
    else:
        assert result.cards[enemy.id].tapped
