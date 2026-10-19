"""Review P2 regressions, using real native menus and explicit bad-input copies."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from knowledge.service import estimate_for
from rules_engine.engine import RulesEngine
from tests.test_task43_vanilla_controls import RAW, VANILLA, rules, add_profiled


@pytest.mark.parametrize('missing', [('power',), ('toughness',), ('power', 'toughness')])
def test_missing_printed_creature_pt_never_mints_scalar_but_keeps_legacy_tier_routes(missing):
    raw = deepcopy(VANILLA['Watchwolf'])
    for field in missing:
        raw.pop(field)  # Explicit bad copied input, not an official intake claim.
    state = rules.bare(1)
    card = add_profiled(state, raw, 1, rules.Zone.HAND)
    estimate = estimate_for(card)
    assert estimate is not None and estimate.tier == 1 and estimate.routes
    assert estimate.play_value is None and estimate.context is None
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m['type'] == 'cast_spell' and m['card_id'] == card.id)
    assert AIAgent()._profile_cast_advice(state, move, 1) == 0.0


@pytest.mark.parametrize('name,want', [('Lightning Bolt', 5.2), ('Supreme Verdict', 4.25)])
def test_real_noncreature_none_pt_retains_actual_estimator_value(name, want):
    state = rules.bare(1)
    card = add_profiled(state, RAW[name], 1, rules.Zone.HAND)
    assert card.power is None and card.toughness is None
    estimate = estimate_for(card)
    assert estimate.play_value == want and estimate.context is not None
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m['type'] == 'cast_spell' and m['card_id'] == card.id)
    assert AIAgent()._profile_cast_advice(state, move, 1) != 0.0


@pytest.mark.parametrize('choice', [None, {'id': 'base'}, {'id': 'kicker_1'}])
def test_full_canonical_archangel_real_four_option_menu_is_neutral_even_before_selection(choice):
    state = rules.bare(1)
    card = add_profiled(state, RAW['Archangel of Wrath'], 1, rules.Zone.HAND)
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m['type'] == 'cast_spell' and m['card_id'] == card.id)
    assert [option['id'] for option in move['cost_options']] == ['base', 'kicker_1', 'kicker_2', 'kicker_1_2']
    assert estimate_for(card).play_value == 5.05
    if choice is not None:
        move['cost_choice'] = choice
    assert AIAgent()._profile_cast_advice(state, move, 1) == 0.0


@pytest.mark.parametrize('fault', ['missing_header', 'selected_extra_field', 'from_exile', 'from_library', 'resource_payment'])
def test_actual_move_header_choice_origin_and_resource_context_must_be_closed(fault):
    state = rules.bare(1)
    card = add_profiled(state, VANILLA['Watchwolf'], 1, rules.Zone.HAND)
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m['type'] == 'cast_spell' and m['card_id'] == card.id)
    assert [option['id'] for option in move['cost_options']] == ['base']
    if fault == 'missing_header':
        move.pop('cost_options')
    elif fault == 'selected_extra_field':
        move['cost_choice'] = {'id': 'base', 'discard_card_ids': []}
    elif fault == 'resource_payment':
        move['resource_payment'] = {'delve': [], 'convoke': [], 'improvise': []}
    else:
        move[fault] = True
    assert AIAgent()._profile_cast_advice(state, move, 1) == 0.0


@pytest.mark.parametrize('choice', [None, {'id': 'base'}])
def test_real_closed_single_base_choice_retains_positive_advice(choice):
    state = rules.bare(1)
    card = add_profiled(state, VANILLA['Watchwolf'], 1, rules.Zone.HAND)
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m['type'] == 'cast_spell' and m['card_id'] == card.id)
    if choice is not None:
        move['cost_choice'] = choice
    assert AIAgent()._profile_cast_advice(state, move, 1) == pytest.approx(0.735)
