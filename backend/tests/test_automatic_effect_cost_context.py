"""Canonical automatic-effect cost context, not client-supplied permissions."""
from copy import deepcopy
from dataclasses import asdict
import random

import pytest

from ai.agent import AIAgent
from ai import casting_resources as completion
from ai.action_contract import complete_action
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import collect_cost_options
from rules_engine.effect_casts import materialize_cast, admit_cast
from rules_engine.engine import RulesEngine
from tests.test_activation_modifiers import board
from tests.test_surveil_mill import add


def position(seat):
    state = board(seat)
    spell = add(state, 'Bone Shards', seat, Zone.GRAVEYARD)
    target = add(state, 'Grizzly Bears', 3-seat)
    fodder = add(state, 'Island', seat, Zone.HAND)
    option = next(o for o in collect_cost_options(state, seat, spell, without_mana=True)
                  if o.id == 'base_discard')
    action = dict(type='cast_spell', card_id=spell.id, from_graveyard=True,
                  targets={'target_card_id': target.id},
                  cost_choice={'id': option.id, 'discard_card_ids': [fodder.id]})
    return state, spell, fodder, action, asdict(option)


def scope(state, seat, card_id):
    factory = getattr(completion, '_automatic_effect_cost_scope', None)
    assert callable(factory), 'Trusted automatic-effect scope is missing'
    return factory(state, seat, card_id)


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_materialization_preserves_waiver_without_changing_root_rng(seat):
    state, spell, fodder, _, _ = position(seat)
    before = serialize_match_snapshot(state)
    rng = random.getstate()
    native_rng = state.rng.getstate()
    action = materialize_cast(state, seat, spell.id)
    assert not action.get('_invalid_ai_choice')
    assert action['cost_choice']['id'] == 'base_discard'
    assert serialize_match_snapshot(state) == before
    assert random.getstate() == rng and state.rng.getstate() == native_rng
    admit_cast(state, seat, action, {'target_card_id': spell.id})
    assert state.cards[spell.id].zone == Zone.STACK
    assert state.cards[fodder.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('flag', ['effect_cast', 'without_mana', 'suspend_cast'])
def test_untrusted_action_flags_do_not_supply_mana_or_grant_admission(seat, flag):
    state, spell, _, action, offered = position(seat)
    before = serialize_match_snapshot(state)
    forged = {**action, flag: True}
    result = completion.complete_fixed_cost_choice(AIAgent('strong'), state, forged, seat, offered)
    assert result.get('_invalid_ai_choice') is True
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, complete_action(action))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_trusted_scope_preserves_explicit_cost_and_does_not_grant_engine_permission(seat):
    state, spell, fodder, action, offered = position(seat)
    other = add(state, 'Island', seat, Zone.HAND)
    explicit = {'discard_card_ids': [other.id]}
    selected = deepcopy(action)
    selected['cost_choice']['discard_card_ids'] = [other.id]
    before = serialize_match_snapshot(state)
    with scope(state, seat, spell.id):
        result = completion.complete_fixed_cost_choice(AIAgent('strong'), state, selected, seat, offered, explicit)
        assert not result.get('_invalid_ai_choice')
        assert result['cost_choice']['discard_card_ids'] == [other.id]
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, complete_action(result))
    assert state.cards[fodder.id].zone == Zone.HAND
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_scope_resets_on_exception_and_does_not_cross_state_actor_or_card(seat):
    state, spell, _, action, offered = position(seat)
    agent = AIAgent('strong')
    with pytest.raises(RuntimeError):
        with scope(state, seat, spell.id):
            raise RuntimeError('synthetic unwind')
    assert completion.complete_fixed_cost_choice(agent, state, action, seat, offered).get('_invalid_ai_choice')
    other_state, other_spell, _, other_action, other_offered = position(seat)
    with scope(state, seat, spell.id):
        assert not completion._materialization_without_mana(state, 3-seat, spell.id)
        extra = add(state, 'Bone Shards', seat, Zone.GRAVEYARD)
        assert not completion._materialization_without_mana(state, seat, extra.id)
        assert completion.complete_fixed_cost_choice(agent, other_state, other_action, seat, other_offered).get('_invalid_ai_choice')
        with scope(other_state, seat, other_spell.id):
            assert completion.complete_fixed_cost_choice(agent, state, action, seat, offered).get('_invalid_ai_choice')
        assert not completion.complete_fixed_cost_choice(agent, state, action, seat, offered).get('_invalid_ai_choice')
    assert completion.complete_fixed_cost_choice(agent, state, action, seat, offered).get('_invalid_ai_choice')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('flag', ['effect_cast', 'without_mana', 'suspend_cast'])
def test_forged_move_flags_do_not_make_automatic_effect_context(seat, flag):
    from rules_engine.cast_choice import available_cast_options_and_hints
    from rules_engine.move_generator import _cost_option_view
    state, spell, _, _, _ = position(seat)
    costs, hints = available_cast_options_and_hints(state, spell, seat, without_mana=True)
    move = dict(type='cast_spell', card_id=spell.id, from_graveyard=True,
                target_hints=hints,
                cost_options=[_cost_option_view(o, state, seat, spell.id) for o in costs])
    move[flag] = True
    before = serialize_match_snapshot(state)
    result = AIAgent('strong')._materialize_action(state, move, seat)
    assert result.get('_invalid_ai_choice') is True
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_selected_cost_still_requires_and_pays_printed_mana(seat):
    state, spell, fodder, action, offered = position(seat)
    state.players[seat].graveyard.remove(spell.id)
    state.players[seat].hand.append(spell.id)
    spell.move_to_zone(Zone.HAND)
    action.pop('from_graveyard')
    ordinary = asdict(next(o for o in collect_cost_options(state, seat, spell) if o.id == 'base_discard'))
    assert completion.complete_fixed_cost_choice(AIAgent('strong'), state, action, seat, ordinary).get('_invalid_ai_choice')
    state.players[seat].mana_pool['B'] = 1
    result = completion.complete_fixed_cost_choice(AIAgent('strong'), state, action, seat, ordinary, {'discard_card_ids': [fodder.id]})
    assert not result.get('_invalid_ai_choice')
    after = checked_action(state, RulesEngine(), seat, complete_action(result))
    assert after.cards[spell.id].zone == Zone.STACK and after.cards[fodder.id].zone == Zone.GRAVEYARD
    assert after.players[seat].mana_pool['B'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_engine_pending_effect_cost_choice_keeps_native_admission(seat):
    state, spell, fodder, _, _ = position(seat)
    state.mechanic_choice_players = {seat}
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == spell.id)
    action = AIAgent('strong')._materialize_action(state, move, seat)
    assert not action.get('_invalid_ai_choice')
    after = checked_action(state, RulesEngine(), seat, complete_action(action))
    assert after.cards[spell.id].zone == Zone.STACK and after.cards[fodder.id].zone == Zone.GRAVEYARD
