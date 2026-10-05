"""Immutable combat batches: exact uncached parity and mutation-boundary controls."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from card_data.fallback_cards import fallback_card_payload
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine import combat, continuous
from rules_engine.query_context import query_cache, rule_query_scope
from rules_engine.state_based_actions import apply_state_based_actions


CARDS = {}
for filename in ('conditional_static.json', 'devotion.json', 'ability_suppression.json',
                 'combat_ability_provenance.json'):
    CARDS.update({row['name']: row for row in json.loads(
        (Path(__file__).parent / 'fixtures' / filename).read_text())})


def board(seat):
    deck = [{**fallback_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=701)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.COMBAT_DAMAGE
    return state


def add(state, name, seat):
    row = CARDS.get(name) or fallback_card_payload(name)
    assert row and (row.get('id') or row.get('scryfall_id'))
    sample = MatchFactory.from_decks([{**row, 'card_name': name, 'quantity': 1}], [], seed=1)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.BATTLEFIELD)
    card.summoning_sick = False
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def grant(state, card, keyword):
    resolve_effect(state, card.controller, 'grant_keyword', {'target_card_id': card.id, 'keyword': keyword})


def snapshot(state):
    return serialize_match_snapshot(state)


def run_reference(function, state, *args):
    # Disable only the new combat-local batches, preserving all existing scopes.
    with patch.object(combat, 'rule_query_scope', side_effect=lambda _: nullcontext()):
        return function(state, *args)


@pytest.mark.parametrize('seat', [1, 2])
def test_assignment_batches_reduce_real_query_work_without_changing_choices(seat):
    state = board(seat)
    attackers = [add(state, 'Grizzly Bears', seat) for _ in range(4)]
    blockers = [add(state, 'Palace Guard', 3-seat) for _ in range(4)]
    state.attackers = [card.id for card in attackers]
    state.blocks = {card.id: [blocker.id for blocker in blockers] for card in attackers}
    state.mechanic_choice_players = {1, 2}
    state.combat_damage_stage = 'regular'
    reference = deepcopy(state)
    original = continuous._printed_suppression_result
    with patch.object(continuous, '_printed_suppression_result', wraps=original) as queries:
        run_reference(combat._prepare_damage_step, reference)
        baseline_calls = queries.call_count
    with patch.object(continuous, '_printed_suppression_result', wraps=original) as queries:
        combat._prepare_damage_step(state)
        batched_calls = queries.call_count
    assert snapshot(state) == snapshot(reference)
    assert baseline_calls > 0 and batched_calls < baseline_calls / 2
    assert state.combat_assignment_queue and state.pending_mechanic_choice
    assert query_cache(state) is None
    # No retained cache when a counter changes the offered damage after the batch.
    source = state.pending_mechanic_choice['source_id']
    for current in (state, reference):
        resolve_effect(current, seat, 'add_counters', {'target_card_id': source, 'counter': '+1/+1', 'amount': 2})
    combat._offer_damage_assignment(state)
    run_reference(combat._offer_damage_assignment, reference)
    assert state.pending_mechanic_choice['count'] == 4
    assert snapshot(state) == snapshot(reference)


@pytest.mark.parametrize('seat', [1, 2])
def test_scope_contains_only_immutable_queries_and_ends_before_damage_or_sba(seat):
    state = board(seat)
    attacker = add(state, 'Serra Ascendant', seat)
    state.players[seat].life = 29
    state.attackers = [attacker.id]
    state.attack_targets = {attacker.id: f'player:{3-seat}'}
    grant(state, attacker, 'double strike')
    scopes = []

    @contextmanager
    def audited_scope(position):
        before = snapshot(position)
        with rule_query_scope(position):
            yield
            assert snapshot(position) == before
        assert query_cache(position) is None
        scopes.append(before)

    def guarded(function):
        def execute(position, *args, **kwargs):
            assert query_cache(position) is None
            return function(position, *args, **kwargs)
        return execute

    with patch.object(combat, 'rule_query_scope', audited_scope), \
            patch.object(combat, '_deal_unblocked_damage', guarded(combat._deal_unblocked_damage)), \
            patch.object(combat, '_remove_dead_creatures', guarded(combat._remove_dead_creatures)), \
            patch.object(combat, 'emit_event_batch', guarded(combat.emit_event_batch)):
        combat.begin_combat_damage(state)
        assert state.players[seat].life == 30
        combat.finish_combat_damage(state)
    assert len(scopes) >= 5
    assert state.players[3-seat].life == 13
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_regular_damage_requeries_life_threshold_and_new_counters_after_first_strike(seat):
    state = board(seat)
    attacker = add(state, 'Serra Ascendant', seat)
    state.players[seat].life = 29
    state.attackers = [attacker.id]
    state.attack_targets = {attacker.id: f'player:{3-seat}'}
    grant(state, attacker, 'double strike')
    reference = deepcopy(state)
    combat.begin_combat_damage(state)
    run_reference(combat.begin_combat_damage, reference)
    assert snapshot(state) == snapshot(reference)
    assert state.players[seat].life == 30 and state.players[3-seat].life == 19
    for current in (state, reference):
        resolve_effect(current, seat, 'add_counters', {'target_card_id': attacker.id, 'counter': '+1/+1', 'amount': 2})
    combat.finish_combat_damage(state)
    run_reference(combat.finish_combat_damage, reference)
    assert state.players[3-seat].life == 11  # regular damage uses 6 + 2, not cached 1
    assert state.players[seat].life == 38
    assert snapshot(state) == snapshot(reference)


@pytest.mark.parametrize('seat', [1, 2])
def test_first_strike_survival_and_ability_loss_do_not_reuse_previous_keywords(seat):
    state = board(seat)
    attacker = add(state, 'Rakdos Pit Dragon', seat)
    blocker = add(state, 'Grizzly Bears', 3-seat)
    # Hellbent activates the canonical conditional double strike.
    for cid in list(state.players[seat].hand):
        state.cards[cid].move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(cid)
    state.players[seat].hand.clear()
    grant(state, attacker, 'trample')
    state.attackers = [attacker.id]
    state.blocks = {attacker.id: [blocker.id]}
    state.attack_targets = {attacker.id: f'player:{3-seat}'}
    reference = deepcopy(state)
    combat.begin_combat_damage(state)
    run_reference(combat.begin_combat_damage, reference)
    assert state.combat_damage_stage == 'first'
    assert state.cards[blocker.id].zone == Zone.GRAVEYARD
    assert state.cards[attacker.id].zone == Zone.BATTLEFIELD
    assert snapshot(state) == snapshot(reference)
    life = state.players[3-seat].life
    for current in (state, reference):
        resolve_effect(current, 3-seat, 'temporary_ability_loss', {'target_card_id': attacker.id})
    combat.finish_combat_damage(state)
    run_reference(combat.finish_combat_damage, reference)
    assert state.players[3-seat].life == life
    assert snapshot(state) == snapshot(reference)


@pytest.mark.parametrize('seat', [1, 2])
def test_assignment_power_refreshes_after_printed_ability_loss_source_departure(seat):
    state = board(seat)
    attacker = add(state, 'Rakdos Pit Dragon', seat)
    blockers = [add(state, 'Grizzly Bears', 3-seat) for _ in range(2)]
    source = add(state, 'Humility', 3-seat)
    state.attackers = [attacker.id]
    state.blocks = {attacker.id: [card.id for card in blockers]}
    state.mechanic_choice_players = {1, 2}
    state.combat_damage_stage = 'regular'
    reference = deepcopy(state)
    combat._prepare_damage_step(state)
    run_reference(combat._prepare_damage_step, reference)
    assert state.pending_mechanic_choice['count'] == 1
    for current in (state, reference):
        resolve_effect(current, seat, 'destroy_permanent', {'target_card_id': source.id})
    combat._offer_damage_assignment(state)
    run_reference(combat._offer_damage_assignment, reference)
    assert state.pending_mechanic_choice['count'] == 3
    assert snapshot(state) == snapshot(reference)


@pytest.mark.parametrize('seat', [1, 2])
def test_changing_devotion_types_between_damage_windows_removes_combatant(seat):
    state = board(seat)
    god = add(state, 'Nylea, God of the Hunt', seat)
    support = [add(state, 'Burning-Tree Emissary', seat) for _ in range(2)]
    assert 'Creature' in combat.effective_types(state, god.id)
    grant(state, god, 'double strike')
    state.attackers = [god.id]
    state.attack_targets = {god.id: f'player:{3-seat}'}
    reference = deepcopy(state)
    combat.begin_combat_damage(state)
    run_reference(combat.begin_combat_damage, reference)
    assert state.players[3-seat].life == 14
    for current in (state, reference):
        resolve_effect(current, 3-seat, 'destroy_permanent', {'target_card_id': support[0].id})
        apply_state_based_actions(current)
    assert 'Creature' not in combat.effective_types(state, god.id)
    assert god.id not in state.attackers
    combat.finish_combat_damage(state)
    run_reference(combat.finish_combat_damage, reference)
    assert state.players[3-seat].life == 14
    assert snapshot(state) == snapshot(reference)


@pytest.mark.parametrize('seat', [1, 2])
def test_block_eligibility_scope_ends_before_payment_and_trigger_publication(seat):
    state = board(seat)
    attackers = [add(state, 'Grizzly Bears', seat) for _ in range(3)]
    blocker = add(state, 'Palace Guard', 3-seat)
    state.attackers = [card.id for card in attackers]
    assignments = {card.id: [blocker.id] for card in attackers}
    reference = deepcopy(state)
    run_reference(combat.declare_blockers, reference, assignments)
    from rules_engine.combat_payments import block_payment_state
    original_event = combat.emit_event_batch

    def payment(position, *args, **kwargs):
        assert query_cache(position) is None
        return block_payment_state(position, *args, **kwargs)

    def event(position, *args, **kwargs):
        assert query_cache(position) is None
        return original_event(position, *args, **kwargs)

    with patch('rules_engine.combat_payments.block_payment_state', payment), \
            patch.object(combat, 'emit_event_batch', event):
        combat.declare_blockers(state, assignments)
    assert state.blocks == assignments
    assert snapshot(state) == snapshot(reference)
    assert query_cache(state) is None


def test_query_scope_is_released_when_an_assignment_query_raises():
    state = board(1)
    attacker = add(state, 'Grizzly Bears', 1)
    state.attackers = [attacker.id]
    state.mechanic_choice_players = {1, 2}
    state.combat_damage_stage = 'regular'
    with patch.object(combat, '_assignment_options', side_effect=RuntimeError('query failure')):
        with pytest.raises(RuntimeError, match='query failure'):
            combat._prepare_damage_step(state)
    assert query_cache(state) is None
