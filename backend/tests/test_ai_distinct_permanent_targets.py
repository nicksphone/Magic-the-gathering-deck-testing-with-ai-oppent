"""Canonical Ghostly materialization and public AI/checked-action boundaries."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card
from tests.test_multi_target_immediate_return import case, resolve, ISLAND


def position(seat, lands_only=False):
    state, targets, spell = case(seat)
    # Explicit starting position: no competing hand spell, no prior action history.
    for cid in list(state.players[seat].hand):
        if cid != spell:
            state.players[seat].hand.remove(cid)
            state.players[seat].library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
    state.cards[targets[0]].counters['+1/+1'] = 2
    state.cards[targets[1]].tapped = True
    if lands_only:
        state.players[seat].battlefield.remove(targets[0])
        state.cards[targets[0]].move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(targets[0])
        targets[0] = raw_card(state, ISLAND, seat, Zone.BATTLEFIELD).id
        state.cards[targets[0]].tapped = True
    rules = RulesEngine()
    legal = rules.legal_moves(state, seat)
    move = next(row for row in legal if row.get('card_id') == spell
                and row['type'] == 'cast_spell')
    return state, targets, spell, rules, legal, move


def paid_result(state, seat, spell, targets, rules, action):
    before = serialize_match_snapshot(state)
    refs = {cid: (object_incarnation(state.cards[cid]), state.cards[cid].zone_change_sequence)
            for cid in targets}
    assert not action.get('_invalid_ai_choice')
    assert action['type'] == 'cast_spell' and action['card_id'] == spell
    assert set(action['targets']['target_card_ids']) == set(targets)
    assert len(action['targets']['target_card_ids']) == 2
    assert not action['targets'].get('target_card_id')
    current = checked_action(state, rules, seat, action)
    assert sum(current.players[seat].mana_pool.values()) == 0
    assert current.cards[spell].zone == Zone.STACK
    current = resolve(current)
    assert current.cards[spell].zone == Zone.GRAVEYARD
    for cid in targets:
        card = current.cards[cid]
        assert card.zone == Zone.BATTLEFIELD and card.controller == seat
        assert card.zone_change_sequence == refs[cid][1] + 2
        assert object_incarnation(card) > refs[cid][0]
        assert cid in current.players[seat].battlefield
        assert not card.tapped
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lands_only', [False, True])
def test_real_public_move_materializes_distinct_permanents_and_pays(seat, lands_only):
    state, targets, spell, rules, _, move = position(seat, lands_only)
    before = serialize_match_snapshot(state)
    hints = move['target_hints']
    assert hints['required_distinct_target_count'] == 2
    assert {row['id'] for row in hints['permanent_targets']} == set(targets)
    assert not hints.get('creature_targets') and not hints.get('ordered_counter_amounts')
    action = AIAgent(difficulty='casual')._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    paid_result(state, seat, spell, targets, rules, action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lands_only', [False, True])
def test_real_public_choose_action_materializes_checked_paid_ghostly(seat, lands_only):
    state, targets, spell, rules, legal, _ = position(seat, lands_only)
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty='casual').choose_action(state, legal, seat).action
    assert serialize_match_snapshot(state) == before
    paid_result(state, seat, spell, targets, rules, action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wrong', ['field', 'short', 'duplicate', 'three', 'one', 'missing'])
def test_candidate_field_and_count_are_not_guessed_from_oracle_or_board(seat, wrong):
    state, targets, spell, rules, _, original = position(seat)
    move = deepcopy(original)
    hints = move['target_hints']
    if wrong == 'field':
        hints['creature_targets'] = hints.pop('permanent_targets')
    elif wrong == 'short':
        hints['permanent_targets'] = hints['permanent_targets'][:1]
    elif wrong == 'duplicate':
        hints['permanent_targets'] = [hints['permanent_targets'][0]] * 2
    elif wrong == 'three':
        hints['required_distinct_target_count'] = 3
    elif wrong == 'one':
        hints['required_distinct_target_count'] = 1
    else:
        hints.pop('required_distinct_target_count')
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty='casual')._materialize_action(state, move, seat)
    if wrong in {'one', 'missing'}:
        assert len(action.get('targets', {}).get('target_card_ids', [])) != 2
        with pytest.raises(ActionRejected):
            checked_action(state, rules, seat, action)
    else:
        assert action.get('_invalid_ai_choice')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_wrong_target_count_rejects_atomically_without_ai_repair(seat):
    state, targets, _, rules, _, original = position(seat)
    move = deepcopy(original)
    move['targets'] = {'target_card_ids': targets[:1]}
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty='casual')._materialize_action(state, move, seat)
    assert action['targets']['target_card_ids'] == targets[:1]
    with pytest.raises(ActionRejected):
        checked_action(state, rules, seat, action)
    assert serialize_match_snapshot(state) == before
