"""Real paid legend/death lines; only the preference scores are synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from ai.pending_effects import _unanswered_action_outcome
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.extra_sequence_support import position
from tests.test_ai_friendly_material_conservation import CARDS
from tests.test_ai_legend_keeper_value import ROWS
from tests.test_linked_damage_targets import raw_card
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _expanded, _field


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('winning_payoff', [False, True])
@pytest.mark.parametrize('prefer_pass', [False, True])
def test_public_mandatory_choice_win_outranks_synthetic_scores(
        monkeypatch, seat, winning_payoff, prefer_pass):
    from ai import learned_policy, learned_qv

    state = position(seat, Step.END_STEP)
    state.active_player = 3-seat
    state.priority_player = seat
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {}
    old = raw_card(state, ROWS['Isamaru, Hound of Konda'], seat, Zone.BATTLEFIELD)
    old.summoning_sick = False
    fresh = raw_card(state, ROWS['Isamaru, Hound of Konda'], seat, Zone.HAND)
    land = raw_card(state, CARDS['Plains'], seat, Zone.BATTLEFIELD)
    flash = json.loads((Path(__file__).parent / 'fixtures/global_flash_timing_audit/'
                        'leyline-of-anticipation.json').read_text())
    raw_card(state, flash, seat, Zone.BATTLEFIELD)
    if winning_payoff:
        raw_card(state, CARDS['Blood Artist'], seat, Zone.BATTLEFIELD)
        state.players[3-seat].life = 1
    rules = RulesEngine()
    view, moves = decision_view(state, seat, rules.legal_moves(state, seat))
    cast = {'type': 'cast_spell', 'card_id': fresh.id, 'targets': {}}
    paid = checked_action(state, rules, seat, cast)
    assert paid.cards[land.id].tapped and not state.cards[land.id].tapped
    chooser = AIAgent('master', 'Aggro')
    forecast = _unanswered_action_outcome(view, seat, cast,
        own_choice_action=lambda s, m, p: chooser.choose_action(s, m, p).action)
    assert forecast == ('win' if winning_payoff else 'neutral')
    before, offered = serialize_match_snapshot(view), deepcopy(moves)
    rng = random.getstate(), view.rng.getstate()

    class SyntheticScores:
        def predict(self, pack):
            kind = _field(_expanded(pack), 'type')['value']
            preferred = 'pass_priority' if prefer_pass else 'cast_spell'
            q = 0.9 if kind == preferred else 0.0 if kind in {'cast_spell', 'pass_priority'} else -0.9
            return {'q': q, 'v': 0.0}

    binding = _binding(learned_policy)
    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda _policy, _pack: SyntheticScores())
    agent = AIAgent('master', 'Aggro', learned_binding=binding)
    chosen = learned_policy.choose_learned_action(binding, agent, view, moves, seat,
        admit=lambda action: checked_action(view, rules, seat, action))
    assert chosen is not None
    # A synthetic high score must not force the now-qualified no-payoff duplicate.
    if winning_payoff:
        assert chosen['type'] == 'cast_spell' and chosen['card_id'] == fresh.id
        assert chosen['targets'] == {}
        checked_action(view, rules, seat, chosen)
    else:
        assert chosen['type'] == 'pass_priority'
    assert serialize_match_snapshot(view) == before and moves == offered
    assert (random.getstate(), view.rng.getstate()) == rng
