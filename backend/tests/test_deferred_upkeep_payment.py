"""Real zero-cost Pact casts, native turns, payments and durable continuations.

Removing resolution-time scheduling makes the first Pact case miss its choice.
Removing payment dispatch makes the paid cases fail to spend four real sources.
Removing owner filtering makes the obligation appear at the opponent's upkeep.
"""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.serializers import serialize_match, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import fixture, add as fixture_add
from tests.test_combat_keyword_triggers import CARDS as COMBAT
from tests.test_conditional_player_draw import act, cold, seed_add, cast, finish, advance
from tests.test_forge_negative_life_diagnostic import canonical_entry
from tests.test_land_type_layers import add as restricted_land
from tests.test_linked_damage_targets import raw_card
from tests.mana_canonical_76 import entry as mana_entry
from tests.test_announced_target_reference_product import EXTRA as COPY_PRINTINGS
from tests.stage_metadata import mark as _stage_metadata


def mark(label):
    _stage_metadata(label)


def position(seat, *, sources=0, creature=True, spell="Summoner's Pact"):
    state = fixture()
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        player.mana_pool = {}
    cid = seed_add(state, spell, seat)
    if creature:
        fixture_add(state, 'Grizzly Bears', seat, Zone.LIBRARY, full_printing=True)
    for _ in range(sources):
        raw_card(state, mana_entry('Forest'), seat, Zone.BATTLEFIELD)
    return state, cid


def own_draw(state, seat, after_turn):
    for _ in range(96):
        if state.turn > after_turn and state.active_player == seat and state.step == Step.DRAW:
            return state
        assert state.winner is None and not state.pending_mechanic_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native turn progression did not reach the next own draw')


def due_trigger(state, seat, after_turn):
    opponent_upkeep = False
    for _ in range(96):
        if state.turn > after_turn and state.step == Step.UPKEEP:
            if state.active_player == seat and state.stack:
                assert opponent_upkeep
                return state
            if state.active_player != seat:
                opponent_upkeep = True
                assert not state.stack and not state.pending_mechanic_choice
        if state.turn > after_turn and state.active_player == seat and state.step == Step.DRAW:
            mark('resolved-pact-reached-next-own-draw-without-payment-trigger')
            raise AssertionError('Resolved Pact omitted its next-own-upkeep trigger')
        assert state.winner is None and not state.pending_mechanic_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native turn progression did not reach the payment trigger')


def offer(state):
    return advance(state, lambda s: bool(s.pending_mechanic_choice))


def choose(state, seat, option):
    return act(state, seat, {'type': 'choose_mechanic', 'card_ids': [option]})


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_nondelayed_search_survives_upkeeps(seat):
    state, spell = position(seat, spell='Cultivate', creature=False)
    state.players[seat].mana_pool = {'G': 1, 'C': 2}
    start = state.turn
    state, _ = cast(state, seat, spell, 3)
    state = finish(state)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert len(state.players[seat].battlefield) == 1
    assert state.cards[state.players[seat].battlefield[0]].tapped
    assert len(state.players[seat].hand) == 1
    state = own_draw(cold(state, True), seat, start)
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_zero_cost_pact_decline_loses_at_next_own_upkeep(seat, restored):
    state, spell = position(seat)
    start = state.turn
    assert state.cards[spell].mana_cost == '{0}'
    state, _ = cast(cold(state, restored), seat, spell, 0)
    state = finish(state)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert any(state.cards[cid].name == 'Grizzly Bears' for cid in state.players[seat].hand)
    state = offer(due_trigger(cold(state, restored), seat, start))
    assert state.pending_mechanic_choice['options'] == ['decline']
    state = choose(cold(state, restored), seat, 'decline')
    assert state.winner == 3-seat and state.step == Step.UPKEEP
    assert state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_payment_spends_four_real_lands_and_never_repeats(seat, restored):
    state, spell = position(seat, sources=4)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = offer(due_trigger(cold(finish(state), restored), seat, start))
    assert state.pending_mechanic_choice['options'] == ['pay', 'decline']
    assert all(not state.cards[cid].tapped for cid in state.players[seat].battlefield)
    state = choose(cold(state, restored), seat, 'pay')
    assert state.winner is None and state.pending_mechanic_choice is None
    assert all(state.cards[cid].tapped for cid in state.players[seat].battlefield)
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = own_draw(state, seat, state.turn)
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_affordable_payment_can_be_declined(seat):
    state, spell = position(seat, sources=4)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = offer(due_trigger(finish(state), seat, start))
    state = choose(state, seat, 'decline')
    assert state.winner == 3-seat
    assert all(not state.cards[cid].tapped for cid in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fail_to_find', [False, True])
def test_paused_search_resumes_before_obligation_and_can_fail_to_find(seat, fail_to_find):
    state, spell = position(seat)
    state.mechanic_choice_players = {seat}
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = offer(state)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    selected = [] if fail_to_find else state.pending_mechanic_choice['options'][:1]
    state = act(cold(state, True), seat, {'type': 'choose_mechanic', 'card_ids': selected})
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert len(state.players[seat].hand) == (0 if fail_to_find else 1)
    state = offer(due_trigger(cold(state, True), seat, start))
    assert choose(state, seat, 'decline').winner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_search_still_creates_payment(seat):
    state, spell = position(seat, creature=False)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = finish(state)
    assert not state.players[seat].hand
    state = offer(due_trigger(state, seat, start))
    assert choose(state, seat, 'decline').winner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_real_counterspell_prevents_obligation(seat):
    state, spell = position(seat)
    counter = seed_add(state, 'Counterspell', 3-seat)
    state.players[3-seat].mana_pool = {'U': 2}
    start = state.turn
    state, target = cast(state, seat, spell, 0)
    state = act(state, seat, {'type': 'pass_priority'})
    state, _ = cast(state, 3-seat, counter, 2, {'target_stack_id': target})
    state = finish(state)
    assert state.cards[spell].zone == Zone.GRAVEYARD and not state.players[seat].hand
    assert own_draw(cold(state, True), seat, start).winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_real_stifle_counters_delayed_trigger_without_recurrence(seat):
    state, spell = position(seat)
    stifle = fixture_add(state, 'Stifle', 3-seat, Zone.HAND, cards=COMBAT).id
    raw_card(state, mana_entry('Island'), 3-seat, Zone.BATTLEFIELD)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = due_trigger(cold(finish(state), True), seat, start)
    target = state.stack[-1].id
    if state.priority_player != 3-seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': stifle,
                              'targets': {'target_stack_id': target}})
    state = finish(state)
    assert state.cards[stifle].zone == Zone.GRAVEYARD
    assert own_draw(state, seat, state.turn).winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_source_exile_does_not_cancel_obligation(seat):
    state, spell = position(seat)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = finish(state)
    resolve_effect(state, 3-seat, 'exile_from_graveyard', {'target_card_id': spell})
    assert state.cards[spell].zone == Zone.EXILE
    state = offer(due_trigger(cold(state, True), seat, start))
    assert choose(state, seat, 'decline').winner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_multiple_resolutions_require_independent_payments(seat):
    state, first = position(seat, sources=4)
    second = seed_add(state, "Summoner's Pact", seat)
    start = state.turn
    state, _ = cast(state, seat, first, 0)
    state = finish(state)
    state, _ = cast(state, seat, second, 0)
    state = finish(state)
    state = offer(due_trigger(cold(state, True), seat, start))
    state = choose(state, seat, 'pay')
    state = offer(state)
    assert state.pending_mechanic_choice['options'] == ['decline']
    assert choose(state, seat, 'decline').winner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_real_copy_owes_its_controller_while_countered_original_owes_nothing(seat):
    state, spell = position(seat)
    copy = raw_card(state, COPY_PRINTINGS['twincast'], 3-seat, Zone.HAND).id
    fixture_add(state, 'Grizzly Bears', 3-seat, Zone.LIBRARY, full_printing=True)
    state.players[3-seat].mana_pool = {'U': 4}
    counter = seed_add(state, 'Counterspell', 3-seat)
    start = state.turn
    state, target = cast(state, seat, spell, 0)
    state = act(state, seat, {'type': 'pass_priority'})
    state, _ = cast(state, 3-seat, copy, 2, {'target_stack_id': target})
    state = advance(state, lambda s: len(s.stack) == 1)
    if state.priority_player != 3-seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    state, _ = cast(state, 3-seat, counter, 2, {'target_stack_id': target})
    state = finish(state)
    assert not state.players[seat].hand
    assert any(state.cards[cid].name == 'Grizzly Bears' for cid in state.players[3-seat].hand)
    # The copy controller's very next upkeep is the opponent's next turn.
    state = advance(state, lambda s: s.turn > start and s.step == Step.UPKEEP and bool(s.stack))
    assert state.active_player == 3-seat
    state = offer(cold(state, True))
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    assert choose(state, 3-seat, 'decline').winner == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_loss_prohibition_prevents_decline_loss_without_repeating(seat):
    state, spell = position(seat)
    raw_card(state, canonical_entry('Platinum Angel'), seat, Zone.BATTLEFIELD)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = offer(due_trigger(finish(state), seat, start))
    state = choose(state, seat, 'decline')
    assert state.winner is None
    assert own_draw(cold(state, True), seat, state.turn).winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_cast_only_sources_cannot_pay_effect_cost(seat):
    state, spell = position(seat)
    for _ in range(4):
        restricted_land(state, 'Ancient Ziggurat', seat)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = offer(due_trigger(finish(state), seat, start))
    assert state.pending_mechanic_choice['options'] == ['decline']
    assert choose(state, seat, 'decline').winner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_spell_tax_does_not_tax_fixed_upkeep_payment(seat):
    state, spell = position(seat, sources=4)
    seed_add(state, 'Thalia, Guardian of Thraben', 3-seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 1}
    start = state.turn
    state, _ = cast(state, seat, spell, 1)
    state = offer(due_trigger(finish(state), seat, start))
    assert state.pending_mechanic_choice['options'] == ['pay', 'decline']
    state = choose(state, seat, 'pay')
    assert state.winner is None and sum(state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('affordable', [False, True])
def test_public_choice_is_bounded_and_ai_executes_array_choice(seat, affordable):
    state, spell = position(seat, sources=4 if affordable else 0)
    start = state.turn
    state, _ = cast(state, seat, spell, 0)
    state = offer(due_trigger(finish(state), seat, start))
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    view = serialize_match(state)
    assert set(moves[0]) == {'type', 'kind', 'player_id', 'options', 'count', 'label', 'option_labels'}
    assert set(view['pending_mechanic_choice']) == set(moves[0]) - {'type'}
    decision = AIAgent().choose_action(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action == {'type': 'choose_mechanic', 'card_ids': ['pay' if affordable else 'decline']}
    state = act(cold(state, True), seat, decision.action)
    assert state.winner == (None if affordable else 3-seat)


@pytest.mark.parametrize('bad', ['wrong-actor', 'pay-unaffordable', 'duplicate', 'scalar'])
def test_invalid_payment_choice_preserves_caller_snapshot(bad):
    state, spell = position(1)
    start = state.turn
    state, _ = cast(state, 1, spell, 0)
    state = offer(due_trigger(finish(state), 1, start))
    before = serialize_match_snapshot(state)
    action = {'type': 'choose_mechanic', 'card_ids': ['decline']}
    actor = 2 if bad == 'wrong-actor' else 1
    if bad == 'pay-unaffordable':
        action['card_ids'] = ['pay']
    elif bad == 'duplicate':
        action['card_ids'] = ['decline', 'decline']
    elif bad == 'scalar':
        action = {'type': 'choose_mechanic', 'choice_id': 'decline'}
    rejected = False
    try:
        act(state, actor, action)
    except ActionRejected:
        rejected = True
    assert rejected and serialize_match_snapshot(state) == before


@pytest.mark.parametrize('tail', [
    'At the beginning of your next upkeep, pay {2}{G}{G}. If you don\'t, you lose the game.',
    'At the beginning of your next upkeep, pay {0}. If you don\'t, you lose the game.',
])
def test_complete_fixed_payment_tail_compiles(tail):
    from rules_engine.deferred_upkeep_payment import compile_instruction
    result = compile_instruction('Draw a card. ' + tail)
    assert result['immediate_text'] == 'Draw a card.'
    assert result['mana_cost'] in {'{2}{G}{G}', '{0}'}


@pytest.mark.parametrize('tail', [
    'At the beginning of your next upkeep, pay {X}. If you don\'t, you lose the game.',
    'At the beginning of your next upkeep, pay {G/P}. If you don\'t, you lose the game.',
    'At the beginning of your next upkeep, pay {2}{G}{G}. If you don\'t, you lose the game. Draw a card.',
    'At the beginning of your next upkeep, pay {2}{G}{G}.',
])
def test_partial_or_unsupported_payment_tail_fails_closed(tail):
    from rules_engine.deferred_upkeep_payment import compile_instruction
    text = 'Draw a card. ' + tail
    assert compile_instruction(text) == {'__unsupported_instruction': text}
