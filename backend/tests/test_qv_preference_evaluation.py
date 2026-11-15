"""Synthetic comparison groups detect misleading aggregate agreement."""
from copy import deepcopy
import importlib

import pytest

from tests.test_learned_qv import contract, number


class BiasPolicy:
    def prepare(self, state):
        return self

    def predict(self, action):
        return {'q': float(action['root']['value'] in (1, 4)), 'v': 0.0}


def corpus():
    rows = []
    for index, preferred in enumerate((1, 1, 1, 2, 3, 4, 4, 4)):
        other = ({1: 2, 2: 1, 3: 4, 4: 3})[preferred]
        rows.append({'state': number(index), 'preferred': number(preferred),
                     'alternatives': [number(other)]})
    return rows


def evaluator():
    return importlib.import_module('scripts.evaluate_qv_preferences')


def test_card_family_bias_can_pass_aggregate_but_not_conditional_contrasts():
    rows = corpus()
    before = deepcopy(rows)
    result = evaluator().evaluate_preferences(BiasPolicy(), rows, contract=contract())
    assert result['strict_top1'] == .75 and result['rows'] == 8
    assert result['contrast_groups'] == 2 and result['contrast_rows'] == 8
    assert result['contrast_groups_correct'] == 0 and result['contrast_accuracy'] == 0
    assert rows == before


def test_same_candidate_sets_can_be_ranked_differently_in_different_states():
    class ConditionalPolicy:
        def prepare(self, state):
            chosen = (1, 1, 1, 2, 3, 4, 4, 4)[state['root']['value']]

            class Decision:
                def predict(self, action):
                    return {'q': float(action['root']['value'] == chosen), 'v': 0.0}
            return Decision()

    result = evaluator().evaluate_preferences(ConditionalPolicy(), corpus(), contract=contract())
    assert result['strict_top1'] == result['contrast_accuracy'] == 1
    assert result['contrast_groups_correct'] == 2


def test_no_contrasts_is_unavailable_not_a_perfect_score_and_conflicts_reject():
    rows = corpus()[:3]
    result = evaluator().evaluate_preferences(BiasPolicy(), rows, contract=contract())
    assert result['contrast_groups'] == 0 and result['contrast_accuracy'] is None
    contradictory = [rows[0], deepcopy(rows[0])]
    contradictory[1]['preferred'], contradictory[1]['alternatives'][0] = (
        contradictory[1]['alternatives'][0], contradictory[1]['preferred'])
    with pytest.raises(ValueError, match='Conflicting'):
        evaluator().evaluate_preferences(BiasPolicy(), contradictory, contract=contract())


@pytest.mark.parametrize('score', [True, float('nan'), float('inf'), 2.0])
def test_bad_policy_scores_are_not_counted_as_success(score):
    class BadPolicy(BiasPolicy):
        def predict(self, action):
            return {'q': score}
    with pytest.raises(ValueError):
        evaluator().evaluate_preferences(BadPolicy(), corpus(), contract=contract())
