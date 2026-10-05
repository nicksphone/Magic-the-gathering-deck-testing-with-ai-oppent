"""Canonical resource opportunity costs, independent of named deck archetypes."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_cast_resource_payments import ROWS, add, position


def materialize(state, spell, seat, archetype):
    ai = AIAgent(archetype=archetype)
    move = next(move for move in ai.engine.legal_moves(state, seat)
                if move.get('type') == 'cast_spell' and move.get('card_id') == spell.id)
    before = serialize_match_snapshot(state)
    action = ai._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    assert not action.get('_invalid_ai_choice')
    return action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('archetype', ['Aggro', 'Control', 'Tokens', 'Ramp'])
def test_convoke_preserves_large_blocker_for_any_archetype(seat, archetype):
    state, spell = position(seat, 'Siege Wurm')
    blocker = add(state, 'Hooting Mandrills', seat, cards=ROWS)
    add(state, 'Siege Wurm', 3-seat, cards=ROWS)
    for _ in range(2):
        add(state, 'Llanowar Elves', seat, cards=ROWS)
    for _ in range(5):
        add(state, 'Ornithopter', seat, cards=ROWS)
    action = materialize(state, spell, seat, archetype)
    assert action.get('resource_payment') is not None
    result = checked_action(state, RulesEngine(), seat, action)
    assert not result.cards[blocker.id].tapped
    assert result.cards[spell.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_delve_keeps_flashback_card_and_exiles_spent_cards(seat):
    state, spell = position(seat, 'Dig Through Time')
    raw = json.loads((Path(__file__).parent / 'fixtures/opaque_selection/memory-deluge.json').read_text())
    cards = {'Memory Deluge': {**raw, 'power': raw.get('power'), 'toughness': raw.get('toughness')}}
    memory = add(state, 'Memory Deluge', seat, Zone.GRAVEYARD, cards=cards)
    for _ in range(6):
        add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS)
    state.players[seat].mana_pool = {'U': 2}
    action = materialize(state, spell, seat, 'Control')
    assert action.get('resource_payment') is not None
    result = checked_action(state, RulesEngine(), seat, action)
    assert memory.id in result.players[seat].graveyard
    assert result.stack[-1].payload['mana_spent'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_improvise_keeps_repeatable_mana_source(seat):
    state, spell = position(seat, 'Reverse Engineer')
    ring = add(state, 'Sol Ring', seat, cards=ROWS)
    for _ in range(3):
        add(state, 'Ornithopter', seat, cards=ROWS)
    state.players[seat].mana_pool = {'U': 2}
    action = materialize(state, spell, seat, 'Ramp')
    result = checked_action(state, RulesEngine(), seat, action)
    assert not result.cards[ring.id].tapped
    assert len(result.stack[-1].payload['__casting_resource_payment']['improvise']) == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_convoke_values_actual_self_tap_payoff(seat):
    state, spell = position(seat, 'Siege Wurm')
    emmara = add(state, 'Emmara, Soul of the Accord', seat, cards=ROWS)
    add(state, 'Ornithopter', seat, cards=ROWS)
    state.players[seat].mana_pool = {'G': 2, 'C': 4}
    action = materialize(state, spell, seat, 'Tokens')
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.cards[emmara.id].tapped
    assert result.stack[-1].source_card_id == emmara.id


@pytest.mark.parametrize('seat', [1, 2])
def test_query_reuse_returns_independent_choices(seat):
    from rules_engine.query_context import rule_query_scope
    from ai.casting_resources import choose_resource_payment
    state, spell = position(seat, 'Dig Through Time')
    raw = json.loads((Path(__file__).parent / 'fixtures/opaque_selection/memory-deluge.json').read_text())
    add(state, 'Memory Deluge', seat, Zone.GRAVEYARD, cards={
        'Memory Deluge': {**raw, 'power': raw.get('power'), 'toughness': raw.get('toughness')}})
    for _ in range(6):
        add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS)
    state.players[seat].mana_pool = {'U': 2}
    ai = AIAgent(archetype='Control')
    base = {'type': 'cast_spell', 'card_id': spell.id}
    with rule_query_scope(state):
        first = choose_resource_payment(ai, state, base, seat)
        first['resource_payment']['delve'].clear()
        second = choose_resource_payment(ai, state, base, seat)
        assert len(second['resource_payment']['delve']) == 6


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_hidden_hand_identity_does_not_change_resource_choice(seat):
    from copy import deepcopy
    state, spell = position(seat, 'Siege Wurm')
    add(state, 'Hooting Mandrills', seat, cards=ROWS)
    for _ in range(2):
        add(state, 'Llanowar Elves', seat, cards=ROWS)
    for _ in range(5):
        add(state, 'Ornithopter', seat, cards=ROWS)
    other = deepcopy(state)
    add(state, 'Hogaak, Arisen Necropolis', 3-seat, Zone.HAND, cards=ROWS)
    add(other, 'Ornithopter', 3-seat, Zone.HAND, cards=ROWS)
    first = materialize(state, spell, seat, 'Midrange')
    second = materialize(other, spell, seat, 'Midrange')
    assert first['resource_payment'] == second['resource_payment']


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_resource_choices_are_never_overridden(seat):
    from ai.casting_resources import choose_resource_payment
    state, spell = position(seat, 'Dig Through Time')
    action = {'type': 'cast_spell', 'card_id': spell.id, 'resource_payment': {}}
    assert choose_resource_payment(AIAgent(), state, action, seat) is action


def test_keyword_query_accepts_existing_lightweight_card_views():
    from types import SimpleNamespace
    from rules_engine.casting_resources import resource_keywords
    assert resource_keywords(SimpleNamespace(types=['Creature'])) == frozenset()


@pytest.mark.parametrize('seat', [1, 2])
def test_combined_convoke_delve_with_hybrid_cost_spends_no_mana(seat):
    state, spell = position(seat, 'Hogaak, Arisen Necropolis')
    for _ in range(2):
        add(state, 'Llanowar Elves', seat, cards=ROWS)
    for _ in range(5):
        add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS)
    assert AIAgent(archetype='Reanimator')._can_pay_card_cost(state, seat, spell)
    action = materialize(state, spell, seat, 'Reanimator')
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.stack[-1].payload['mana_spent'] == 0
    assert len(result.players[seat].exile) == 5
    assert all(result.cards[cid].tapped for cid in result.players[seat].battlefield)
