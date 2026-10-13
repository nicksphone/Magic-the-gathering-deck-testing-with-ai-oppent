"""NEW baseline: canonical profiles, genuine paid stack responses, no SQL.

Starting boards and pools are declared fixtures, not naturally paid births.
No fabricated profile tiers, spell StackItems, or hidden-card forecasts.
"""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from knowledge.profiles import derive_profile
from knowledge.service import estimate_for
from rules_engine.engine import RulesEngine
from rules_engine.targeting import spell_cant_be_countered, stack_object_kind
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.test_task23_checked_removal_baseline import add_profiled
from tests.vraska_full import test_full_vraska as rules

OBSERVATIONS = []


def base(seat):
    state = rules.bare(seat)
    state.turn = 5
    state.active_player = state.priority_player = 3 - seat
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    add_profiled(state, rules.BEAR, seat, rules.Zone.BATTLEFIELD)
    counter = add_profiled(state, RAW['Counterspell'], seat, rules.Zone.HAND)
    state.players[seat].mana_pool = {'U': 2}
    return state, counter.id


def announced(seat, name):
    state, counter = base(seat)
    raw = RAW[name]
    source = add_profiled(state, raw, 3 - seat, rules.Zone.HAND)
    state.players[3 - seat].mana_pool = {'B': 1, 'C': 1} if name == 'Zulaport Cutthroat' else {'G': 1}
    assert source.oracle_text == raw['oracle_text'] and source.mana_cost == raw['mana_cost']
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': source.id})
    assert len(state.stack) == 1 and state.stack[-1].source_card_id == source.id
    assert stack_object_kind(state, state.stack[-1]) == 'spell'
    assert state.stack[-1].payload['mana_spent'] == (2 if name == 'Zulaport Cutthroat' else 1)
    state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
    assert state.priority_player == seat
    return state, counter, source.id


def replay(state, enabled):
    snapshot = serialize_match_snapshot(state)
    if enabled:
        state = deserialize_match_snapshot(deepcopy(snapshot))
    assert serialize_match_snapshot(state) == snapshot
    return state


def decide(state, seat, archetype):
    before = serialize_match_snapshot(state)
    actor = AIAgent(difficulty='strong', archetype=archetype)
    moves = RulesEngine().legal_moves(state, seat)
    decision = actor.choose_action(state, moves, seat)
    OBSERVATIONS.append({'seat': seat, 'archetype': archetype,
        'source': state.cards[state.stack[-1].source_card_id].name if state.stack else None,
        'printed_tier': estimate_for(state.cards[state.stack[-1].source_card_id]).tier if state.stack else None,
        'stack_score': actor._stack_item_threat_score(state, state.stack[-1].id, seat) if state.stack else None,
        'action_type': decision.action['type'],
        'chosen_card': state.cards[decision.action['card_id']].name if decision.action.get('card_id') else None,
        'targets': deepcopy(decision.action.get('targets')),
        'knowledge_usage': decision.knowledge_usage})
    assert serialize_match_snapshot(state) == before
    return decision, moves


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
@pytest.mark.parametrize('archetype', ['Control', 'Counter-heavy'])
def test_actual_tier_three_stack_threat_gets_paid_counter(seat, roundtrip, archetype):
    state, counter, source = announced(seat, 'Zulaport Cutthroat')
    state = replay(state, roundtrip)
    profile = derive_profile(RAW['Zulaport Cutthroat'])
    assert profile.threat_level == estimate_for(state.cards[source]).tier == 3
    assert 'counter_spell' in profile.answerable_by
    before = serialize_match_snapshot(state)
    decision, moves = decide(state, seat, archetype)
    assert any(move['type'] == 'cast_spell' and move['card_id'] == counter for move in moves)
    assert decision.action['type'] == 'cast_spell' and decision.action['card_id'] == counter
    assert decision.action['targets']['target_stack_id'] == state.stack[-1].id
    result = rules.act(state, seat, decision.action)
    assert len(result.stack) == 2 and result.stack[-1].source_card_id == counter
    assert result.stack[-1].payload['mana_spent'] == 2
    assert sum(result.players[seat].mana_pool.values()) == 0
    result = rules.settle(result)
    assert result.cards[source].zone == rules.Zone.GRAVEYARD
    assert result.cards[counter].zone == rules.Zone.GRAVEYARD and not result.stack
    assert result.winner is None and result.players[seat].life == 20
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
@pytest.mark.parametrize('archetype', ['Control', 'Counter-heavy'])
def test_stable_tier_one_one_one_holds_real_castable_counter(seat, roundtrip, archetype):
    state, counter, source = announced(seat, 'Llanowar Elves')
    state = replay(state, roundtrip)
    assert state.cards[source].power == state.cards[source].toughness == 1
    assert derive_profile(RAW['Llanowar Elves']).threat_level == estimate_for(state.cards[source]).tier == 1
    before = serialize_match_snapshot(state)
    decision, moves = decide(state, seat, archetype)
    assert any(move['type'] == 'cast_spell' and move['card_id'] == counter for move in moves)
    assert decision.action['type'] == 'pass_priority', 'Stable low threat should preserve the payable counter'
    result = rules.act(state, seat, decision.action)
    result = rules.settle(result)
    assert result.cards[source].zone == rules.Zone.BATTLEFIELD
    assert result.cards[counter].zone == rules.Zone.HAND
    assert result.players[seat].mana_pool == {'U': 2}
    assert result.players[seat].life == 20 and result.winner is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_real_veil_uncounterable_window_preserves_counter_and_real_removal_exists(seat, roundtrip):
    state, counter = base(seat)
    veil = add_profiled(state, RAW['Veil of Summer'], 3 - seat, rules.Zone.HAND)
    source = add_profiled(state, RAW['Zulaport Cutthroat'], 3 - seat, rules.Zone.HAND)
    removal = add_profiled(state, RAW['Lightning Bolt'], seat, rules.Zone.HAND)
    state.players[3 - seat].mana_pool = {'G': 1, 'B': 1, 'C': 1}
    state.players[seat].mana_pool = {'U': 2, 'R': 1}
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': veil.id})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = rules.settle(state)
    assert state.cards[veil.id].zone == rules.Zone.GRAVEYARD
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': source.id})
    assert state.stack[-1].payload['mana_spent'] == 2
    state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
    state = replay(state, roundtrip)
    assert spell_cant_be_countered(state, state.stack[-1])
    estimate = estimate_for(state.cards[source.id])
    # Printed routes are advice: actual Veil changes current counterability.
    assert 'counter_spell' in {route.effect_key for route in estimate.routes}
    assert estimate.tier == 3
    before = serialize_match_snapshot(state)
    decision, _ = decide(state, seat, 'Control')
    assert decision.action.get('card_id') != counter, 'Do not waste a counter on an uncounterable spell'
    actual = rules.act(state, seat, decision.action)
    if decision.action['type'] == 'cast_spell':
        assert actual.stack[-1].source_card_id == removal.id
        assert actual.stack[-1].payload['mana_spent'] == 1
    actual = rules.settle(actual)
    assert actual.cards[source.id].zone == rules.Zone.BATTLEFIELD
    assert actual.cards[counter].zone == rules.Zone.HAND and actual.winner is None

    # Genuine checked alternative: hold red removal until its creature target exists.
    result = rules.act(state, seat, {'type': 'pass_priority'})
    result = rules.settle(result)
    if result.priority_player != seat:
        result = rules.act(result, result.priority_player, {'type': 'pass_priority'})
    assert result.priority_player == seat and result.cards[source.id].zone == rules.Zone.BATTLEFIELD
    answer, moves = decide(result, seat, 'Control')
    assert any(move['type'] == 'cast_spell' and move['card_id'] == removal.id for move in moves)
    assert answer.action['type'] == 'cast_spell' and answer.action['card_id'] == removal.id
    assert answer.action['targets']['target_card_id'] == source.id
    result = rules.act(result, seat, answer.action)
    assert result.stack[-1].payload['mana_spent'] == 1
    result = rules.settle(result)
    assert result.cards[source.id].zone == rules.Zone.GRAVEYARD
    assert result.cards[counter].zone == rules.Zone.HAND and result.winner is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_opponent_hand_cannot_change_same_public_counter_decision(seat):
    state, counter, source = announced(seat, 'Llanowar Elves')
    hidden = add_profiled(state, RAW['Lightning Bolt'], 3 - seat, rules.Zone.HAND)
    other, _, _ = announced(seat, 'Llanowar Elves')
    replacement = add_profiled(other, RAW['Counterspell'], 3 - seat, rules.Zone.HAND)
    assert replacement.id == hidden.id
    views = []
    actions = []
    for current in (state, other):
        before = serialize_match_snapshot(current)
        public, moves = decision_view(current, seat, RulesEngine().legal_moves(current, seat))
        assert is_unknown(public.cards[hidden.id]) and not public.cards[hidden.id].knowledge_snapshot
        views.append(serialize_match_snapshot(public))
        actions.append(decide(current, seat, 'Control')[0].action)
        assert serialize_match_snapshot(current) == before
    assert views[0] == views[1] and actions[0] == actions[1]


@pytest.mark.parametrize('seat', [1, 2])
def test_tier_three_advice_never_creates_unpayable_counter_permission(seat):
    state, counter, source = announced(seat, 'Zulaport Cutthroat')
    state.players[seat].mana_pool = {'U': 1}
    before = serialize_match_snapshot(state)
    decision, moves = decide(state, seat, 'Control')
    assert not any(move['type'] == 'cast_spell' and move['card_id'] == counter for move in moves)
    assert decision.action['type'] == 'pass_priority'
    result = rules.act(state, seat, decision.action)
    result = rules.settle(result)
    assert result.cards[source].zone == rules.Zone.BATTLEFIELD
    assert result.cards[counter].zone == rules.Zone.HAND and result.winner is None
    assert serialize_match_snapshot(state) == before
