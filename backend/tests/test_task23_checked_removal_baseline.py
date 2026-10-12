"""Actual current-policy baseline; trusted old boards/pools, no scoring changes."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from knowledge.profiles import derive_profile, merge_profile_payload
from knowledge.service import estimate_for, snapshot_for
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.mana import mana_value
from rules_engine.targeting import stack_object_kind
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.vraska_full import test_full_vraska as rules


DIVINATION = json.loads((Path(rules.__file__).parent / 'fixtures/divination.json').read_bytes())


def add_profiled(state, raw, seat, zone):
    card = rules.add(state, raw, seat, zone, old_board=zone == rules.Zone.BATTLEFIELD)
    row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
                          profiles_json=json.dumps(merge_profile_payload({'card_data': raw}, derive_profile(raw))))
    hydrated = {'layout': raw.get('layout', 'normal'), 'card_faces': deepcopy(raw.get('card_faces', [])),
                **{key: raw.get(key, '') for key in ('oracle_text', 'type_line', 'mana_cost')}}
    card.knowledge_snapshot = snapshot_for(row, raw['name'], hydrated)
    assert card.knowledge_snapshot and estimate_for(card) is not None
    return card


def position(seat, protection=None, response=False):
    state = rules.bare(seat)
    state.turn = 6
    state.players[seat].life = 6  # Declared current lethal pressure, not a forced endpoint.
    state.players[seat].mana_pool = {'B': 1, 'U': 1, 'C': 3}
    removal = add_profiled(state, RAW['Go for the Throat'], seat, rules.Zone.HAND)
    value = add_profiled(state, DIVINATION, seat, rules.Zone.HAND)
    threat = add_profiled(state, RAW['Atraxa, Grand Unifier'], 3 - seat, rules.Zone.BATTLEFIELD)
    small = add_profiled(state, RAW['Llanowar Elves'], 3 - seat, rules.Zone.BATTLEFIELD)
    if protection:
        # Genuine object-bound existing layer seam; NOT a paid grant certificate.
        add_keyword_effect(state, threat.id, [protection])
        assert has_keyword(state, threat.id, protection)
    reply = add_profiled(state, RAW['Counterspell'], 3 - seat, rules.Zone.HAND) if response else None
    return state, removal.id, value.id, threat.id, small.id, reply.id if reply else None


def paid_decision(state, seat):
    legal = RulesEngine().legal_moves(state, seat)
    original = serialize_match_snapshot(state)
    decision = AIAgent(difficulty='strong', archetype='Control').choose_action(state, legal, seat)
    assert serialize_match_snapshot(state) == original
    assert decision.action['type'] == 'cast_spell', 'Baseline must report an actual policy failure, not force a cast'
    source = state.cards[decision.action['card_id']]
    before = sum(state.players[seat].mana_pool.values())
    result = checked_action(state, RulesEngine(), seat, decision.action)
    expected = mana_value(source.mana_cost)
    assert result.stack[-1].payload['mana_spent'] == expected
    assert before - sum(result.players[seat].mana_pool.values()) == expected
    assert stack_object_kind(result, result.stack[-1]) == 'spell'
    return result, decision, original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('protection', [None, 'hexproof', 'protection from black', 'indestructible'])
def test_full_legal_menu_current_choice_and_checked_paid_complete_resolution(seat, protection):
    root, removal, value, threat, small, _ = position(seat, protection)
    legal = RulesEngine().legal_moves(root, seat)
    offered = {move['card_id'] for move in legal if move['type'] == 'cast_spell'}
    assert {removal, value} <= offered  # Competing canonical value cast remains offered.
    estimate = estimate_for(root.cards[threat])
    assert any(route.effect_key == 'destroy_permanent' for route in estimate.routes)
    # Printed advice remains constant even when a genuine live effect changes answerability.
    hints = next(move for move in legal if move.get('card_id') == removal and move['type'] == 'cast_spell')['target_hints']
    targets = {item['id'] for item in hints.get('creature_targets', [])}
    assert small in targets
    if protection in {'hexproof', 'protection from black'}:
        assert threat not in targets
    else:
        assert threat in targets
    result, decision, original = paid_decision(root, seat)
    if protection is None:
        assert decision.action['card_id'] == removal and decision.action['targets']['target_card_id'] == threat
    else:
        assert not (decision.action['card_id'] == removal and decision.action['targets'].get('target_card_id') == threat)
    source = decision.action['card_id']
    result = rules.settle(result)
    assert not result.stack and result.cards[source].zone == rules.Zone.GRAVEYARD
    assert result.winner is None
    if protection is None:
        assert result.cards[threat].zone == rules.Zone.GRAVEYARD
    else:
        assert result.cards[threat].zone == rules.Zone.BATTLEFIELD
    assert serialize_match_snapshot(root) == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('protection', ['hexproof', 'protection from black'])
def test_explicit_illegal_source_sensitive_removal_rejects_full_root_atomically(seat, protection):
    state, source, _, target, _, _ = position(seat, protection)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
                       {'type': 'cast_spell', 'card_id': source, 'targets': {'target_card_id': target}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_opponent_counter_response_retains_original_threat(seat):
    root, removal, value, threat, _, response = position(seat, response=True)
    legal = RulesEngine().legal_moves(root, seat)
    assert {removal, value} <= {move['card_id'] for move in legal if move['type'] == 'cast_spell'}
    result, decision, original = paid_decision(root, seat)
    assert decision.action['card_id'] == removal and decision.action['targets']['target_card_id'] == threat
    result = rules.act(result, seat, {'type': 'pass_priority'})
    assert result.priority_player == 3 - seat
    offered = RulesEngine().legal_moves(result, 3 - seat)
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == response for move in offered)
    target = result.stack[-1].id
    result = rules.act(result, 3 - seat,
                       {'type': 'cast_spell', 'card_id': response, 'targets': {'target_stack_id': target}})
    assert result.stack[-1].payload['mana_spent'] == 2
    assert stack_object_kind(result, result.stack[-1]) == 'spell'
    result = rules.settle(result)
    assert not result.stack and result.winner is None
    assert result.cards[threat].zone == rules.Zone.BATTLEFIELD
    assert result.cards[removal].zone == result.cards[response].zone == rules.Zone.GRAVEYARD
    assert serialize_match_snapshot(root) == original
