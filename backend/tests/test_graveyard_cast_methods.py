"""Permissions inspect the actual announced spell, not just graveyard data."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.costs import casting_method
from tests.test_graveyard_play_permissions import position, ROWS, moves
from tests.test_limited_graveyard_permissions import LIMITED
from tests.test_bestow import ROWS as BESTOW
from tests.test_ai_recurring_engines import add

DIRECTORY = Path(__file__).parent / 'fixtures/graveyard_cast_methods'
RAW = json.loads((DIRECTORY / 'goring-warplow.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
def test_prototype_graveyard_permission_checks_announced_mana_value(seat):
    provenance = json.loads((DIRECTORY / 'goring-warplow.json.provenance.json').read_text())
    assert hashlib.sha256((DIRECTORY / 'goring-warplow.json').read_bytes()).hexdigest() == provenance['sha256']
    state = position(seat)
    state.players[seat].mana_pool = {'B': 2}
    add(state, 'Lurrus of the Dream-Den', seat, cards=LIMITED)
    card = add(state, RAW['name'], seat, Zone.GRAVEYARD, cards={RAW['name']: RAW})
    available = moves(state, seat, card.id)
    assert available
    options = available[0]['cost_options']
    assert {casting_method(option['id']) for option in options} == {'prototype'}
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id,
        'from_graveyard': True, 'cost_choice': {'id': options[0]['id']}})
    assert serialize_match_snapshot(state) == before
    assert result.cards[card.id].mana_cost == '{1}{B}'
    assert result.cards[card.id].colors == ['B']
    assert len(result.graveyard_permission_uses) == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(result))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(result)
    from rules_engine.zone_actions import move_spell_from_stack
    move_spell_from_stack(restored, restored.stack.pop())
    assert restored.cards[card.id].mana_cost == RAW['mana_cost']
    assert restored.cards[card.id].colors == RAW['colors']


@pytest.mark.parametrize('seat', [1, 2])
def test_free_cast_can_choose_prototype_without_a_second_alternative_cost(seat):
    from rules_engine.costs import collect_cost_options
    state = position(seat)
    card = add(state, RAW['name'], seat, Zone.HAND, cards={RAW['name']: RAW})
    options = collect_cost_options(state, seat, card, without_mana=True)
    assert {option.id: option.mana_cost for option in options} == {'base': '', 'prototype': ''}


@pytest.mark.parametrize('seat', [1, 2])
def test_bestow_uses_only_announced_enchantment_permission_and_real_target(seat):
    state = position(seat)
    state.players[seat].mana_pool = {'G': 4}
    add(state, 'Muldrotha, the Gravetide', seat, cards=LIMITED)
    target = add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    card = add(state, 'Leafcrown Dryad', seat, Zone.GRAVEYARD, cards=BESTOW)
    available = next((move for move in moves(state, seat, card.id) if move.get('cast_variant') == 'bestow'), None)
    assert available
    assert all(option['id'].endswith(':Enchantment') for option in available['cost_options'])
    result = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id,
        'from_graveyard': True, 'cost_choice': {'id': available['cost_options'][0]['id']},
        'targets': {'target_card_id': target.id}})
    assert result.cards[card.id].types == ['Enchantment']
    assert next(iter(result.graveyard_permission_uses)).endswith(':Enchantment')
    assert result.stack[-1].payload['mana_spent'] == 4


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Ramp', 'Tempo', 'Tokens', 'Reanimator'])
def test_ai_preserves_a_different_permanent_type_for_known_followup(seat, style):
    from ai.agent import AIAgent
    from tests.test_cast_resource_payments import ROWS as RESOURCES
    state = position(seat)
    state.players[seat].mana_pool = {'C': 2}
    add(state, 'Muldrotha, the Gravetide', seat, cards=LIMITED)
    card = add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=RESOURCES)
    later = add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS)
    move = moves(state, seat, card.id)[0]
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty='master', archetype=style)._materialize_action(state, move, seat)
    assert action['cost_choice']['id'].endswith(':Creature')
    assert serialize_match_snapshot(state) == before
    result = checked_action(state, RulesEngine(), seat, action)
    result.stack.clear()
    assert moves(result, seat, later.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_preserves_broader_permission_when_a_subtype_permission_is_available(seat):
    from ai.agent import AIAgent
    state = position(seat)
    state.players[seat].mana_pool = {'B': 2, 'C': 2}
    lurrus = add(state, 'Lurrus of the Dream-Den', seat, cards=LIMITED)
    gisa = add(state, 'Gisa and Geralf', seat, cards=LIMITED)
    card = add(state, 'Diregraf Ghoul', seat, Zone.GRAVEYARD, cards=ROWS)
    later = add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS)
    action = AIAgent(difficulty='master', archetype='Midrange')._materialize_action(state, moves(state, seat, card.id)[0], seat)
    assert gisa.id in action['cost_choice']['id'] and lurrus.id not in action['cost_choice']['id']
    result = checked_action(state, RulesEngine(), seat, action)
    result.stack.clear()
    assert moves(result, seat, later.id)
