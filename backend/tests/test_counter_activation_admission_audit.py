"""Strict counter-payment admissions; real canonical body, no injected ability."""
from copy import deepcopy
import json

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected
from rules_engine.costs import activated_cost_available, parse_activated_cost
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from tests.test_batch_graveyard_publication_audit import assert_private
from tests.test_generic_protection_damage import BALLISTA, position, raw_card
from tests.test_kozilek_graveyard_trigger_audit import passes
from tests.test_self_graveyard_replacement_audit import act, restart, snap


def board(seat, counters=3, *, funded=False):
    state, target = position(seat, 'White Knight')
    source = raw_card(state, BALLISTA, seat, Zone.BATTLEFIELD)
    source.counters['+1/+1'] = counters  # Controlled retained position, NOT cast/entry support.
    state.players[seat].mana_pool = {'C': 4} if funded else {}
    return state, source.id, target


def literal_cost(state, source):
    return state.cards[source].oracle_text.splitlines()[-1].split(':', 1)[0]


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_canonical_remove_ability_retains_index_and_complete_body(seat):
    state, source, _ = board(seat)
    before = snap(state)
    abilities = extract_activated_abilities(state.cards[source])
    assert snap(state) == before
    assert [ability['index'] for ability in abilities] == [0, 1]
    assert abilities[0]['mana_cost'] == '{4}'
    assert abilities[1]['mana_cost'].lower() == literal_cost(state, source).lower()
    assert abilities[1]['text'] == BALLISTA['oracle_text'].splitlines()[-1].split(': ', 1)[1]


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_source_counter_cost_is_supported_and_payable_without_mana(seat):
    state, source, _ = board(seat)
    before = snap(state)
    cost = literal_cost(state, source)
    assert parse_activated_cost(cost).supported
    assert activated_cost_available(state, seat, source, cost, ability_index=1)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_real_payment_and_colorless_damage_repeated_snapshot(seat, tmp_path):
    state, source, target = board(seat)
    action = {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
              'targets': {'target_card_id': target}}
    # This must actually execute; an unsupported ActionRejected is an ordinary RED.
    result = act(state, seat, action)
    assert result.cards[source].counters['+1/+1'] == 2
    assert result.cards[target].counters.get('__damage_marked', 0) == 0
    assert result.stack[-1].source_card_id == source
    assert result.stack[-1].effect_key == 'deal_damage'
    assert result.stack[-1].payload['__announced_targets'] == action['targets']
    result = passes(restart(result, tmp_path, 'real-counter-paid-stack'))
    assert result.cards[target].counters['__damage_marked'] == 1
    assert result.cards[source].zone == Zone.BATTLEFIELD
    assert result.cards[source].counters['+1/+1'] == 2
    assert_private(result)
    restart(result, tmp_path, 'real-counter-paid-resolution')


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_last_counter_real_stack_survives_source_departure(seat, tmp_path):
    state, source, _ = board(seat, counters=1)
    old_reference = object_incarnation(state.cards[source])
    old_sequence = state.cards[source].zone_change_sequence
    result = act(state, seat, {'type': 'activate_ability', 'card_id': source,
                    'ability_index': 1, 'targets': {'target_player': 3-seat}})
    card = result.cards[source]
    assert card.zone == Zone.GRAVEYARD
    assert card.zone_change_sequence == old_sequence + 1
    assert result.players[seat].graveyard.count(source) == 1
    item = next(item for item in result.stack if item.source_card_id == source)
    assert item.controller == seat and item.effect_key == 'deal_damage'
    assert item.payload['__source_lki']['battlefield_incarnation'] == old_reference
    assert item.payload['__source_lki']['color_names'] == []
    assert item.payload['__source_lki']['counters'].get('+1/+1', 0) == 0
    result = passes(restart(result, tmp_path, 'departed-source-real-stack'))
    assert result.players[3-seat].life == 19
    assert result.cards[source].zone == Zone.GRAVEYARD
    assert not result.stack
    assert_private(result)
    restart(result, tmp_path, 'departed-source-resolved')


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_canonical_four_mana_index_zero_still_executes(seat, tmp_path):
    state, source, _ = board(seat, funded=True)
    offered = [move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == source]
    assert any(move['type'] == 'activate_ability' and move['ability_index'] == 0 for move in offered)
    result = act(state, seat, {'type': 'activate_ability', 'card_id': source,
                              'ability_index': 0, 'targets': {}})
    assert not sum(result.players[seat].mana_pool.values())
    assert result.cards[source].counters['+1/+1'] == 3
    result = passes(restart(result, tmp_path, 'existing-four-paid'))
    assert result.cards[source].counters['+1/+1'] == 4
    assert result.cards[source].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_real_counter_ability_body_compiles_without_cost_or_dispatch_guesses(seat):
    state, source, target = board(seat)
    card = state.cards[source]
    proxy = deepcopy(card)
    # Analysis of the exact canonical body, NOT an injected executable ability.
    proxy.oracle_text = card.oracle_text.splitlines()[-1].split(': ', 1)[1]
    proxy.card_faces = []
    spec = build_ability_spec(state, proxy, seat, {'target_card_id': target}, report_unsupported=False)
    assert spec.effect.key == 'deal_damage'
    assert spec.effect.payload == {'amount': 1, 'target_card_id': target}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wrong', ['index', 'target', 'actor'])
def test_checked_invalid_candidate_preserves_entire_root(seat, wrong):
    state, source, _ = board(seat)
    action = {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
              'targets': {'target_player': 3-seat}}
    actor = seat
    if wrong == 'index':
        action['ability_index'] = 99
    elif wrong == 'target':
        action['targets'] = {'target_card_id': 'absent-card'}
    else:
        actor = 3-seat
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, actor, action)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('problem', ['empty', 'different_counter', 'departed'])
def test_counter_cost_resource_negative_queries_are_root_pure(seat, problem):
    state, source, _ = board(seat)
    card = state.cards[source]
    if problem == 'empty':
        card.counters.clear()  # Controlled zero-toughness QUERY seam, not priority legality.
    elif problem == 'different_counter':
        card.counters = {'charge': 3}
    else:
        state.players[seat].battlefield.remove(source)
        card.move_to_zone(Zone.HAND)
        state.players[seat].hand.append(source)
    before = snap(state)
    assert not activated_cost_available(state, seat, source, literal_cost(state, source), ability_index=1)
    assert snap(state) == before


@pytest.mark.parametrize('text', [
    'Remove any number of +1/+1 counters from this creature',
    'Remove a +1/+1 counter from a creature you control',
    'Remove a charge counter from this artifact',
    'Remove a +1/+1 counter from this creature and pay 2 life',
])
def test_bounded_source_counter_proposal_does_not_guess_other_costs(text):
    # Pure proposed grammar boundaries, never fabricated gameplay Oracle/card rows.
    if text == 'Remove a charge counter from this artifact':
        from rules_engine.costs import ActivatedCost, apply_activated_costs
        from tests.test_paid_counter_family_audit import board as family_board
        assert parse_activated_cost(text) == ActivatedCost(remove_source_counters=1,
                                                          remove_counter_kind='charge')
        state, source, _ = family_board(1, 'Lux Cannon')
        before = snap(state)
        assert activated_cost_available(state, 1, source, text)
        assert snap(state) == before
        assert apply_activated_costs(state, 1, source, text)
        assert state.cards[source].counters['charge'] == 2 and not state.cards[source].tapped
        assert not state.stack
        return
    assert not parse_activated_cost(text).supported
