"""Cost-specific prohibitions must not become general life-change locks."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.replacement import can_pay_life
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from tests.test_ai_search_prefix import bare_state
from tests.test_life_conversion import permanent
from tests.test_life_lock_suppression import restriction
from tests.test_linked_damage_targets import raw_card


def canonical(state, name, controller, zone=Zone.BATTLEFIELD):
    raw = json.loads((Path(__file__).parent / 'fixtures/contextual_cost_prohibitions' / (name+'.json')).read_text())
    return raw_card(state, raw, controller, zone)


def position(seat, source_controller, kind):
    state = bare_state(seat)
    angel = canonical(state, 'angel-of-jubilation', source_controller)
    if kind == 'life_activation':
        payer = restriction(state, 'erebos-god-of-the-dead', seat)
        pool = 'BC'
    elif kind == 'sacrifice_activation':
        payer = canonical(state, 'viscera-seer', seat)
        pool = ''
    else:
        payer = canonical(state, 'dismember', seat, Zone.HAND)
        pool = 'C'  # Both black Phyrexian symbols would require life.
    state.players[seat].mana_pool = {color: int(color in pool) for color in 'WUBRGC'}
    return state, angel, payer


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('own_source', [False, True])
@pytest.mark.parametrize('kind', ['life_activation', 'sacrifice_activation', 'phyrexian_spell'])
def test_global_cost_prohibition_rejects_payment_in_cast_or_activation_context(seat, own_source, kind):
    state, _, payer = position(seat, seat if own_source else 3-seat, kind)
    moves = RulesEngine().legal_moves(state, seat)
    assert not any(move.get('card_id') == payer.id and move['type'] in {'cast_spell', 'activate_ability'}
                   for move in moves)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['life_activation', 'sacrifice_activation', 'phyrexian_spell'])
def test_direct_action_cannot_bypass_cost_prohibition_or_mutate_original_state(seat, kind):
    state, angel, payer = position(seat, 3-seat, kind)
    if kind == 'phyrexian_spell':
        action = {'type': 'cast_spell', 'card_id': payer.id, 'targets': {'target_card_id': angel.id},
                  'hybrid_choices': ['P', 'P']}
    else:
        action = {'type': 'activate_ability', 'card_id': payer.id, 'ability_index': 0}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['life_activation', 'sacrifice_activation', 'phyrexian_spell'])
def test_suppressed_prohibition_source_no_longer_blocks_its_costs(seat, kind):
    state, angel, payer = position(seat, 3-seat, kind)
    add_keyword_effect(state, angel.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    assert any(move.get('card_id') == payer.id and move['type'] in {'cast_spell', 'activate_ability'}
               for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
def test_generic_creature_sacrifice_cost_can_consume_the_ability_source(seat):
    state, angel, payer = position(seat, 3-seat, 'sacrifice_activation')
    add_keyword_effect(state, angel.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'activate_ability', 'card_id': payer.id, 'ability_index': 0})
    assert len(state.stack) == 1
    assert payer.id in state.players[seat].graveyard
    assert payer.id not in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_phyrexian_spell_can_use_mana_instead_of_forbidden_life_payment(seat):
    state, _, payer = position(seat, 3-seat, 'phyrexian_spell')
    state.players[seat].mana_pool['B'] = 2
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == payer.id
               for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_ai_materializes_payable_phyrexian_branches_under_cost_prohibition(seat, style):
    from ai.agent import AIAgent
    state, _, payer = position(seat, 3-seat, 'phyrexian_spell')
    state.players[seat].mana_pool['B'] = 2
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move.get('card_id') == payer.id)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    state = checked_action(state, RulesEngine(), seat, action)
    assert len(state.stack) == 1
    assert state.players[seat].life == 20
    assert state.players[seat].mana_pool['B'] == 0
    assert state.players[seat].mana_pool['C'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_cast_activation_prohibition_does_not_block_land_entry_payment_or_life_loss(seat):
    state = bare_state(seat)
    canonical(state, 'angel-of-jubilation', 3-seat)
    land = canonical(state, 'sacred-foundry', seat, Zone.HAND)
    assert can_pay_life(state, seat, 2)  # Context-free life payment is not a cast cost.
    assert any(move['type'] == 'play_land' and move.get('card_id') == land.id
               and move.get('entry_choice') == 'pay_two_life'
               for move in RulesEngine().legal_moves(state, seat))
    state = checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': land.id,
                                                       'entry_choice': 'pay_two_life'})
    assert state.players[seat].life == 18
    resolve_effect(state, 3-seat, 'lose_life', {'target_player': seat, 'amount': 3})
    assert state.players[seat].life == 15


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['ward', 'combat'])
def test_noncasting_effect_payment_is_not_prohibited_as_a_cast_cost(seat, context):
    state = bare_state(seat)
    canonical(state, 'angel-of-jubilation', 3-seat)
    assert can_pay_with_pool_and_lands(state, seat, '{B/P}', payment_kind=context)
    assert auto_pay_cost(state, seat, '{B/P}', payment_kind=context)
    assert state.players[seat].life == 18


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_life_payment_remains_permitted_even_under_cost_prohibition(seat):
    from rules_engine.replacement import cost_payment_is_prohibited
    state = bare_state(seat)
    canonical(state, 'angel-of-jubilation', 3-seat)
    assert can_pay_life(state, seat, 0)
    assert not cost_payment_is_prohibited(state, seat, 'spell', life=0)


@pytest.mark.parametrize('seat', [1, 2])
def test_mixed_artifact_creature_sacrifice_cost_can_use_only_noncreature_artifacts(seat):
    from rules_engine.costs import activated_cost_available, _eligible_sacrifice_ids
    state = bare_state(seat)
    canonical(state, 'angel-of-jubilation', 3-seat)
    source = canonical(state, 'makeshift-munitions', seat)
    creature = permanent(state, 'platinum-emperion', seat)
    artifact = permanent(state, 'alhammarrets-archive', seat)
    state.players[seat].mana_pool['C'] = 1
    candidates = _eligible_sacrifice_ids(state, seat, 'artifact_or_creature', payment_kind='activation')
    assert artifact.id in candidates and creature.id not in candidates
    assert activated_cost_available(state, seat, source.id, '{1}, Sacrifice an artifact or creature')


@pytest.mark.parametrize('seat', [1, 2])
def test_exhaustive_sacrifice_cannot_silently_omit_forbidden_creatures(seat):
    state = bare_state(seat)
    canonical(state, 'angel-of-jubilation', 3-seat)
    canonical(state, 'viscera-seer', seat)
    spell = canonical(state, 'kaerveks-spite', seat, Zone.HAND)
    state.players[seat].mana_pool['B'] = 3
    assert not any(move['type'] == 'cast_spell' and move.get('card_id') == spell.id
                   for move in RulesEngine().legal_moves(state, seat))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
                                                    'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_exhaustive_cost_can_sacrifice_all_noncreature_permanents(seat):
    state = bare_state(seat)
    canonical(state, 'angel-of-jubilation', 3-seat)
    land = canonical(state, 'sacred-foundry', seat)
    spell = canonical(state, 'kaerveks-spite', seat, Zone.HAND)
    state.players[seat].mana_pool['B'] = 3
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
                                                      'targets': {'target_player': 3-seat}})
    assert state.cards[land.id].zone == Zone.GRAVEYARD
    assert len(state.stack) == 1
    assert state.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_cast_sacrifice_additional_cost_is_prohibited_while_source_active(seat):
    state = bare_state(seat)
    angel = canonical(state, 'angel-of-jubilation', 3-seat)
    canonical(state, 'viscera-seer', seat)
    spell = canonical(state, 'bone-splinters', seat, Zone.HAND)
    state.players[seat].mana_pool['B'] = 1
    assert not any(move['type'] == 'cast_spell' and move.get('card_id') == spell.id
                   for move in RulesEngine().legal_moves(state, seat))
    add_keyword_effect(state, angel.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == spell.id
               for move in RulesEngine().legal_moves(state, seat))
