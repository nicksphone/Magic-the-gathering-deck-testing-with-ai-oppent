"""Canonical additional-cost contracts, not claims of whole-card coverage."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import (collect_cost_options, additional_cost_candidates,
                                apply_additional_costs, casting_method)
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.spell_cost_clauses import spell_additional_costs
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import add
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/spell_additional_costs.json').read_text())}


def card(state, name, seat):
    return raw_add(state, name, seat, Zone.HAND, cards=ROWS)


@pytest.mark.parametrize('name,discard,sacrifice,kind', [
    ('Cathartic Reunion', 2, 0, 'creature'), ('Tormenting Voice', 1, 0, 'creature'),
    ('Raze', 0, 1, 'land'), ('Deadly Dispute', 0, 1, 'artifact_or_creature'),
    ('Ruthless Disposal', 1, 1, 'creature'),
])
@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_counts_and_types(name, discard, sacrifice, kind, seat):
    state = board(seat)
    option, = collect_cost_options(state, seat, card(state, name, seat))
    assert (option.discard_cards, option.sacrifice_creatures, option.sacrifice_kind) == (discard, sacrifice, kind)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('free', [False, True])
def test_counted_discard_cast_and_rejection_are_atomic(seat, free):
    state = board(seat)
    spell = card(state, 'Cathartic Reunion', seat)
    first = add(state, 'Island', seat, Zone.HAND)
    second = add(state, 'Swamp', seat, Zone.HAND)
    state.players[seat].mana_pool.update(R=1, C=1)
    if free:
        from effects.registry import resolve_effect
        state.players[seat].hand.remove(spell.id)
        state.players[seat].graveyard.append(spell.id)
        spell.move_to_zone(Zone.GRAVEYARD)
        state.mechanic_choice_players = {seat}
        resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    action = {'type': 'cast_spell', 'card_id': spell.id, 'from_graveyard': free,
              'cost_choice': {'id': 'base', 'discard_card_ids': [first.id]}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    action['cost_choice']['discard_card_ids'].append(second.id)
    state = checked_action(state, RulesEngine(), seat, action)
    assert state.cards[first.id].zone == state.cards[second.id].zone == Zone.GRAVEYARD
    assert state.cards[spell.id].zone == Zone.STACK
    assert state.players[seat].mana_pool['R'] == (1 if free else 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_land_cost_candidates_and_actual_cast(seat):
    state = board(seat)
    spell = card(state, 'Raze', seat)
    land = add(state, 'Island', seat)
    target = add(state, 'Swamp', 3-seat)
    creature = add(state, 'Grizzly Bears', seat)
    state.players[seat].mana_pool['R'] = 1
    option, = collect_cost_options(state, seat, spell)
    assert additional_cost_candidates(state, seat, spell.id, option)['sacrifice_card_ids'] == [land.id]
    action = {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': target.id},
              'cost_choice': {'id': 'base', 'sacrifice_card_ids': [land.id]}}
    state = checked_action(state, RulesEngine(), seat, action)
    assert state.cards[land.id].zone == Zone.GRAVEYARD
    assert state.cards[creature.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_combined_costs_consume_selected_resources(seat):
    state = board(seat)
    spell = card(state, 'Ruthless Disposal', seat)
    discarded = add(state, 'Island', seat, Zone.HAND)
    sacrificed = add(state, 'Grizzly Bears', seat)
    option, = collect_cost_options(state, seat, spell)
    assert apply_additional_costs(state, seat, option, spell.id, choice={
        'discard_card_ids': [discarded.id], 'sacrifice_card_ids': [sacrificed.id]})
    assert state.cards[discarded.id].zone == state.cards[sacrificed.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payment', ['life', 'sacrifice'])
def test_life_or_sacrifice_cast_preserves_other_resource(seat, payment):
    state = board(seat)
    spell = card(state, 'Final Payment', seat)
    offered = add(state, 'Grizzly Bears', seat)
    target = add(state, 'Grizzly Bears', 3-seat)
    state.players[seat].mana_pool.update(W=1, B=1)
    options = collect_cost_options(state, seat, spell)
    assert {option.id for option in options} == {'base_life', 'base_sacrifice'}
    cost = {'id': 'base_' + payment}
    if payment == 'sacrifice':
        cost['sacrifice_card_ids'] = [offered.id]
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
                           'cost_choice': cost, 'targets': {'target_card_id': target.id}})
    assert state.players[seat].life == (15 if payment == 'life' else 20)
    assert state.cards[offered.id].zone == (Zone.BATTLEFIELD if payment == 'life' else Zone.GRAVEYARD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_ai_avoids_lethal_life_payment_branch(seat, difficulty):
    state = board(seat)
    spell = card(state, 'Final Payment', seat)
    add(state, 'Grizzly Bears', seat)
    add(state, 'Grizzly Bears', 3-seat)
    state.players[seat].mana_pool.update(W=1, B=1)
    state.players[seat].life = 5
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    action = AIAgent(difficulty=difficulty)._materialize_action(state, move, seat)
    assert action['cost_choice']['id'] == 'base_sacrifice'
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.players[seat].life == 5


@pytest.mark.parametrize('seat', [1, 2])
def test_qualified_cost_requires_an_eligible_permanent(seat):
    state = board(seat)
    spell = card(state, 'Goblin Grenade', seat)
    state.players[seat].mana_pool['R'] = 1
    assert 'unsupported spell additional cost' not in known_unsupported_mechanics(spell.oracle_text, card_name=spell.name)
    from rules_engine.costs import check_cost_option_available
    option, = collect_cost_options(state, seat, spell)
    assert not check_cost_option_available(state, seat, spell, option)
    assert not any(move.get('card_id') == spell.id for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('clause', [
    'discard X cards', 'sacrifice a nonland permanent', 'reveal a card',
    'sacrifice a creature and sacrifice a land', 'exile a card from your graveyard',
])
def test_unmodeled_grammar_fails_closed(clause):
    assert spell_additional_costs('As an additional cost to cast this spell, ' + clause + '.') is None


def test_effect_words_do_not_pollute_cost_and_oxford_comma_is_supported():
    assert spell_additional_costs('As an additional cost to cast this spell, sacrifice a land.\n'
                                 'Discard a card. Destroy target creature or artifact.') == [
                                     {'sacrifice_creatures': 1, 'sacrifice_kind': 'land'}]
    assert spell_additional_costs('As an additional cost to cast this spell, pay 2 life, discard a card, '
                                 'and sacrifice a creature.') == [
        {'pay_life': 2, 'discard_cards': 1, 'sacrifice_creatures': 1, 'sacrifice_kind': 'creature'}]


@pytest.mark.parametrize('method', ['base', 'escape', 'flashback', 'prototype', 'bestow', 'kicker'])
def test_additional_branch_keeps_casting_method(method):
    assert casting_method(method + '_sacrifice') == method


@pytest.mark.parametrize('seat', [1, 2])
def test_http_counted_cost_options_and_rejected_payment(game, seat):
    client, controller = game
    state = board(seat)
    state.id = controller.state.id
    controller.state = state
    spell = card(state, 'Cathartic Reunion', seat)
    first = add(state, 'Island', seat, Zone.HAND)
    second = add(state, 'Swamp', seat, Zone.HAND)
    state.players[seat].mana_pool.update(R=1, C=1)
    persist(controller)
    response = client.get(f'/matches/{state.id}/legal-moves', params={'player_id': seat})
    assert response.status_code == 200
    move = next(move for move in response.json()['moves'] if move.get('card_id') == spell.id)
    option, = move['cost_options']
    assert option['discard_cards'] == 2
    assert set(option['discard_card_ids']) == {first.id, second.id}
    rejected(client, controller, {'type': 'cast_spell', 'card_id': spell.id,
                                 'cost_choice': {'id': 'base', 'discard_card_ids': [first.id]}}, seat)


def test_distinct_branch_ids_and_bounded_combination():
    state = board()
    spell = card(state, 'Cathartic Reunion', 1)
    # Grammar fixture only: no invented card enters a game or deck.
    from types import SimpleNamespace
    syntax = SimpleNamespace(**vars(spell))
    syntax.oracle_text = 'As an additional cost to cast this spell, discard a card or discard two cards.'
    options = collect_cost_options(state, 1, syntax)
    assert len({option.id for option in options}) == 2
    assert {option.discard_cards for option in options} == {1, 2}
    clause = 'As an additional cost to cast this spell, discard a card or discard two cards.\n'
    assert spell_additional_costs(clause * 6) is None
