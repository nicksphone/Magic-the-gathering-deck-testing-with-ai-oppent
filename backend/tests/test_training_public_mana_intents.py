"""Whole canonical public mana hints are presentation, not chosen parameters."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_training_selected_mana import (
    selected_position, filter_position, mana, forbid_database_and_network,
)


def chosen_position(seat, family):
    if family == 'tower':
        env, choices, action = selected_position(seat)
        action['payment_choices'] = {'sacrifice_card_ids': [choices[0]]}
    else:
        env, cid = filter_position(seat, 'graven-cairns', 'R')
        action = {**mana(cid, 'B', 1), 'hybrid_choices': ['R'],
                  'output_bundle': {'B': 1, 'R': 1}}
    moves = env._rules.legal_moves(deepcopy(env._state), seat)
    hint = next(move for move in moves if move['type'] == action['type']
                and move['card_id'] == action['card_id']
                and move['ability_index'] == action['ability_index'])
    assert 'required_choices' in hint
    return env, moves, hint, action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['tower', 'cairns'])
def test_actual_whole_public_intent_preserves_chosen_action_and_root(seat, family):
    env, _, hint, action = chosen_position(seat, family)
    before = env.snapshot()
    assert env.lookup_intent({**hint, **action}) == env.lookup(action)
    assert env.snapshot() == before
    # Presentation cannot provide or authorize missing authoritative choices.
    with pytest.raises(ActionRejected):
        env.lookup_intent({**hint, 'color': action['color']})
    for key in ('unknown_choice', 'output_schema', 'x_value'):
        with pytest.raises(ActionRejected, match='cannot carry'):
            env.lookup_intent({**hint, **action, key: {'chosen': 1}})
        assert env.snapshot() == before
    env.step(action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['tower', 'cairns'])
def test_canonical_hints_reused_legacy_fallback_equal_and_no_alias(seat, family, monkeypatch):
    env, moves, _, _ = chosen_position(seat, family)
    before = env.snapshot()
    canonical = env.observe(seat), env.prompts(seat)
    canonical_moves = env._view(seat)[1]
    monkeypatch.setattr(env._rules, 'legal_moves', lambda state, actor: deepcopy(moves))
    with monkeypatch.context() as patch:
        def redundant(*args, **kwargs):
            pytest.fail('canonical metadata was recomputed by training')
        patch.setattr('rules_engine.costs.activated_cost_candidates', redundant)
        patch.setattr('rules_engine.mana.hybrid_payment_symbols', redundant)
        assert env._view(seat)[1] == canonical_moves
    assert (env.observe(seat), env.prompts(seat)) == canonical
    for move in moves:
        move.pop('activation_costs', None)
        move.pop('hybrid_symbols', None)
    assert (env.observe(seat), env.prompts(seat)) == canonical
    prompts = env.prompts(seat)
    for prompt in prompts:
        if 'activation_costs' in prompt['hint']:
            prompt['hint']['activation_costs']['sacrifice_card_ids'].clear()
    assert (env.observe(seat), env.prompts(seat)) == canonical
    assert env.snapshot() == before
