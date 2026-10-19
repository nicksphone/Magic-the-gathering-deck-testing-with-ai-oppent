"""Pure grammar controls and checked-action lifecycle fixtures, not natural games."""
from copy import deepcopy
import json

import pytest

from game_state.state import MatchFactory, Step, Zone
from rules_engine import end_step_ownership_draw as family
from rules_engine.spree import parse
from tests.test_end_step_ownership_draw import (
    ROWS, FACTS, HERE, action, end_step, paid_spell, position, raw_card,
    resolve_real_top, snap, deserialize_match_snapshot,
)

CLAUSE = ROWS['Agent of Treachery']['oracle_text'].splitlines()[1]
RAY = json.loads((HERE / 'fixtures/temporary_control_audit/ray-of-command.json').read_bytes())


def small_position(seat, text):
    island = FACTS['Island']
    deck = [{**island, 'card_name': island['name'], 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=9813)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    row = {**ROWS['Agent of Treachery'], 'name': 'Synthetic clause boundary', 'oracle_text': text}
    source = raw_card(state, row, seat, Zone.BATTLEFIELD)
    return state, source


@pytest.mark.parametrize('criterion', ['an artifact', 'a creature'])
@pytest.mark.parametrize('seat', [1, 2])
def test_unrelated_conditional_end_step_keeps_existing_route(seat, criterion):
    # This preserves dispatch, not a rules qualification of the unrelated condition.
    text = f'At the beginning of your end step, if you control {criterion}, draw a card.'
    state, source = small_position(seat, text)
    assert family.collect(state, source, text) is None
    state = end_step(state, source.id)
    trigger = [item for item in state.stack if item.source_card_id == source.id]
    assert len(trigger) == 1 and trigger[0].effect_key == 'draw_cards'
    assert trigger[0].payload['amount'] == 1


@pytest.mark.parametrize('threshold,amount', [('three', 'three'), ('2', '1'), ('one', 'a'), ('ten', 'two')])
def test_complete_numeric_clause_is_generic(threshold, amount):
    text = CLAUSE.replace('three or more', threshold + ' or more').replace('draw three cards', 'draw ' + amount + ' cards')
    values = {'three': 3, '2': 2, '1': 1, 'one': 1, 'a': 1, 'ten': 10, 'two': 2}
    assert family.compile_clause(text) == {'threshold': values[threshold], 'amount': values[amount]}


@pytest.mark.parametrize('text', [
    CLAUSE + ' Unknown instruction.', CLAUSE + ' (Unknown instruction.)',
    CLAUSE.replace('three or more', 'many or more'),
    CLAUSE.replace('permanents', 'creatures'),
    'You may ' + CLAUSE, CLAUSE.replace('your end step', 'each end step'),
])
def test_incomplete_or_unknown_clause_never_compiles_partial_draw(text):
    assert family.compile_clause(text) is None


@pytest.mark.parametrize('suffix', [' Unknown instruction.', ' (Unknown instruction.)'])
def test_unknown_ownership_tail_is_explicitly_unsupported_before_reminder_stripping(suffix):
    state, source = small_position(1, CLAUSE + suffix)
    state = end_step(state, source.id)
    trigger = [item for item in state.stack if item.source_card_id == source.id]
    assert len(trigger) == 1 and trigger[0].effect_key == 'noop'
    assert trigger[0].payload['__unsupported_trigger_instruction'] == CLAUSE + suffix


@pytest.mark.parametrize('seat', [1, 2])
def test_ownership_predicate_is_pure_and_never_double_counts_a_physical_object(seat):
    state, source = small_position(seat, CLAUSE)
    own = raw_card(state, FACTS['Forest'], seat, Zone.BATTLEFIELD)
    foreign = raw_card(state, FACTS['Forest'], 3-seat, Zone.BATTLEFIELD)
    # Explicit structural-corruption control; not an invented valid game history.
    state.players[3-seat].battlefield.remove(foreign.id)
    foreign.controller = seat
    state.players[seat].battlefield.extend([foreign.id, foreign.id, own.id])
    before = snap(state)
    assert family.condition_holds(state, seat, 1)
    assert not family.condition_holds(state, seat, 2)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_source_control_change_does_not_retarget_retained_trigger(seat):
    state, source, _ = position(seat, 3)
    state = end_step(state, source)
    trigger = state.stack[-1].id
    state, _ = paid_spell(state, 3-seat, RAY, {'target_card_id': source})
    assert state.cards[source].controller == 3-seat and state.cards[source].owner == seat
    assert state.stack[-1].id == trigger and state.stack[-1].controller == seat
    before = {pid: len(player.hand) for pid, player in state.players.items()}
    state = resolve_real_top(state)
    assert len(state.players[seat].hand) == before[seat] + 3
    assert len(state.players[3-seat].hand) == before[3-seat]


@pytest.mark.parametrize('seat', [1, 2])
def test_own_end_step_means_source_controller_not_owner(seat):
    state, source, _ = position(seat, 3)
    state, _ = paid_spell(state, 3-seat, RAY, {'target_card_id': source})
    for _ in range(2):
        target = raw_card(state, FACTS['Elvish Mystic'], seat, Zone.BATTLEFIELD)
        state, _ = paid_spell(state, 3-seat, RAY, {'target_card_id': target.id})
    assert state.cards[source].owner == seat and state.cards[source].controller == 3-seat
    assert family.condition_holds(state, 3-seat, 3), 'Wrong-turn guard must not pass merely on a false condition'
    state = end_step(state, source)
    assert not any(item.source_card_id == source for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_predicate_runs_once_at_resolution_not_after_each_replacement_resume(seat, monkeypatch):
    state, source, _ = position(seat, 3)
    reflection = next(row for row in json.loads((HERE / 'fixtures/draw_forecast.json').read_bytes())
                      if row['name'] == 'Thought Reflection')
    refs = [raw_card(state, reflection, seat, Zone.BATTLEFIELD).id for _ in range(2)]
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    calls = []
    original = family.condition_holds

    def observe(current, controller, threshold):
        result = original(current, controller, threshold)
        calls.append((controller, threshold, result))
        return result

    monkeypatch.setattr(family, 'condition_holds', observe)
    state = end_step(state, source)
    assert calls == [(seat, 3, True)]
    hand = len(state.players[seat].hand)
    trigger = state.stack[-1].id
    for _ in range(2):
        state = action(state, state.priority_player, {'type': 'pass_priority'})
    assert state.pending_replacement_choice and calls == [(seat, 3, True)] * 2
    choices = 0
    while state.pending_replacement_choice and choices < 12:
        state = deserialize_match_snapshot(deepcopy(snap(state)))
        pending = state.pending_replacement_choice
        assert pending['resume_kind'] == 'draw_event' and pending['resolving_item']['id'] == trigger
        selected = next(option['source_id'] for option in pending['options'] if option['source_id'] in refs)
        state = action(state, seat, {'type': 'choose_replacement', 'replacement_source_id': selected})
        choices += 1
    assert choices > 1 and not state.pending_replacement_choice
    assert calls == [(seat, 3, True)] * 2
    assert len(state.players[seat].hand) == hand + 12


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_paid_ability_copy_rechecks_for_actual_copy_controller(seat):
    state, source, _ = position(seat, 3)
    state = end_step(state, source)
    original = state.stack[-1].id
    copier = 3-seat
    for _ in range(2):
        raw_card(state, FACTS['Mountain'], copier, Zone.BATTLEFIELD)
    directory = HERE.parents[1] / 'audit/gate2-spree-http/fixtures/spree_http'
    favor = json.loads((directory / 'canonical.json').read_bytes())['Return the Favor']
    spell = raw_card(state, favor, copier, Zone.HAND)
    mode = parse(favor['oracle_text'])[0].text
    if state.priority_player != copier:
        state = action(state, state.priority_player, {'type': 'pass_priority'})
    state = action(state, copier, {'type': 'cast_spell', 'card_id': spell.id,
        'cost_choice': {'id': 'base'}, 'targets': {'mode_texts': [mode],
            'mode_targets': {mode: {'target_stack_id': original}}}})
    assert state.stack[-1].payload['mana_spent'] == 3
    state = resolve_real_top(state)
    copied = state.stack[-1]
    assert copied.id != original and copied.payload['__copied_from_stack_id'] == original
    assert copied.source_card_id == source and copied.controller == copier
    assert copied.effect_key == 'ownership_end_step_draw'
    before = {pid: len(player.hand) for pid, player in state.players.items()}
    state = resolve_real_top(state)
    assert all(len(state.players[pid].hand) == count for pid, count in before.items())
    assert state.stack[-1].id == original and state.stack[-1].controller == seat
    state = resolve_real_top(state)
    assert len(state.players[seat].hand) == before[seat] + 3
    assert len(state.players[copier].hand) == before[copier]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['false', 'true', 'unsupported'])
def test_separate_legacy_end_step_paragraph_is_not_consumed_by_ownership_family(seat, case):
    from rules_engine.events import _trigger_from_oracle
    legacy = 'At the beginning of your end step, draw a card.'
    ownership = CLAUSE + (' Unknown instruction.' if case == 'unsupported' else '')
    state, source = small_position(seat, legacy + '\n' + ownership)
    if case == 'true':
        # Declared ownership board for this synthetic grammar/control fixture.
        for _ in range(3):
            card = raw_card(state, FACTS['Forest'], 3-seat, Zone.BATTLEFIELD)
            state.players[3-seat].battlefield.remove(card.id)
            card.controller = seat
            state.players[seat].battlefield.append(card.id)
    counterfactual = _trigger_from_oracle(state, source.id, seat, source.oracle_text.lower(),
        'Existing unchanged dispatch', 'begin_step', {'step': 'end_step', 'active_player': seat})
    assert counterfactual['effect_key'] == 'draw_cards' and counterfactual['payload']['amount'] == 1
    hand = len(state.players[seat].hand)
    state = end_step(state, source.id)
    for _ in range(3):
        if not state.stack:
            break
        state = resolve_real_top(state)
    assert not state.stack
    assert len(state.players[seat].hand) == hand + (4 if case == 'true' else 1)


@pytest.mark.parametrize('ownership_first', [False, True])
def test_compound_single_paragraph_is_not_split_or_partially_rewarded(ownership_first):
    legacy = 'At the beginning of your end step, draw a card.'
    text = CLAUSE + ' ' + legacy if ownership_first else legacy + ' ' + CLAUSE
    state, source = small_position(1, text)
    hand = len(state.players[1].hand)
    state = end_step(state, source.id)
    assert len(state.stack) == 1
    assert state.stack[-1].effect_key == 'noop'
    assert '__unsupported_trigger_instruction' in state.stack[-1].payload
    state = resolve_real_top(state)
    assert len(state.players[1].hand) == hand
