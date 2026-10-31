"""Canonical resource-access goldens with deliberately adverse synthetic Q.

These independently constructed positions are not TRAIN rows or fitted-model
evaluation. No archived game snapshot, hand or preferred action is imported.
"""
from copy import deepcopy

import pytest

from ai import learned_policy, learned_qv
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position
from tests.test_burn_core_native_outcomes import add as add_full_canonical
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _expanded, _field


@pytest.mark.parametrize('seat', [1, 2])
def test_known_spell_access_beats_redundant_color_under_adverse_q(monkeypatch, seat):
    state, cards, opponents, _ = position(
        seat, ['Island', 'Plains'],
        ['Island', 'Island'], ['Grizzly Bears'])
    cards['Swords to Plowshares'] = add_full_canonical(state, 'Swords to Plowshares', seat)
    player = state.players[seat]
    player.lands_played_this_turn = player.land_plays_recorded_on_turn = 0
    player.last_land_play_turn = state.turn
    rules = RulesEngine()
    cast = {'type': 'cast_spell', 'card_id': cards['Swords to Plowshares'],
            'targets': {'target_card_id': opponents['Grizzly Bears']}}
    for name in ('Island', 'Plains'):
        developed = checked_action(state, rules, seat,
                                   {'type': 'play_land', 'card_id': cards[name]})
        if name == 'Island':
            with pytest.raises(ActionRejected):
                checked_action(developed, rules, seat, cast)
        else:
            paid = checked_action(developed, rules, seat, cast)
            assert paid.stack[-1].source_card_id == cards['Swords to Plowshares']
    binding = _binding(learned_policy)
    agent = AIAgent(difficulty='master', archetype='Control', learned_binding=binding)
    proposals = [{'type': 'play_land', 'card_id': cards[name]}
                 for name in ('Island', 'Plains')] + [{'type': 'pass_priority'}]
    monkeypatch.setattr(agent, '_strategic_top_actions', lambda *_: deepcopy(proposals))
    scored = []

    class AdverseScores:
        def predict(self, pack):
            kind = _field(pack['root'], 'type')['value']
            card = _field(_expanded(pack), 'card_id') if kind == 'play_land' else None
            name = _field(_field(card, 'intrinsic'), 'name')['value'] if card else ''
            scored.append((kind, name))
            return {'q': .8 if name == 'Island' else .1 if name == 'Plains' else -.8,
                    'v': 0.0}

    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda *_: AdverseScores())
    before = serialize_match_snapshot(state)
    moves = rules.legal_moves(state, seat)
    view, supplied = decision_view(state, seat, moves)
    action = learned_policy.choose_learned_action(
        binding, agent, view, supplied, seat,
        admit=lambda chosen: checked_action(state, rules, seat, chosen))
    assert serialize_match_snapshot(state) == before
    assert ('play_land', 'Island') in scored and ('play_land', 'Plains') in scored
    assert action['type'] == 'play_land' and action['card_id'] == cards['Plains'], action

    developed = checked_action(state, rules, seat, action)
    paid = checked_action(developed, rules, seat, cast)
    assert paid.stack[-1].source_card_id == cards['Swords to Plowshares']
