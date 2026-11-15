"""Paid canonical duplicate casts; synthetic scores only exercise routing."""
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.extra_sequence_support import position
from tests.test_ai_friendly_material_conservation import CARDS
from tests.test_ai_legend_keeper_value import ROWS
from tests.test_linked_damage_targets import raw_card
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _expanded, _field


def duplicate_position(seat, name, reverse=False):
    state = position(seat)
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {}
    row = CARDS.get(name, ROWS.get(name))
    if reverse:
        fresh = raw_card(state, row, seat, Zone.HAND)
    old = raw_card(state, row, seat, Zone.BATTLEFIELD)
    if not reverse:
        fresh = raw_card(state, row, seat, Zone.HAND)
    old.summoning_sick = False
    for _ in range(3):
        raw_card(state, CARDS['Plains'], seat, Zone.BATTLEFIELD)
    return state, old, fresh


def settle_duplicate(state, seat, action):
    from ai.pending_effects import _settle_announced_stack
    projected = checked_action(state, RulesEngine(), seat, action)
    chooser = AIAgent('master', 'Aggro')
    assert _settle_announced_stack(projected, player_id=seat,
        own_choice_action=lambda s, m, p: chooser.choose_action(s, m, p).action)
    return projected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('name', ['Isamaru, Hound of Konda', 'Adeline, Resplendent Cathar'])
def test_no_payoff_duplicate_is_not_a_candidate(seat, reverse, name):
    state, old, fresh = duplicate_position(seat, name, reverse)
    officer = raw_card(state, CARDS['Recruitment Officer'], seat, Zone.HAND)
    rules = RulesEngine()
    view, moves = decision_view(state, seat, rules.legal_moves(state, seat))
    move = next(m for m in moves if m.get('card_id') == fresh.id)
    before, offered = serialize_match_snapshot(view), deepcopy(moves)
    rng = random.getstate(), view.rng.getstate()
    action = {'type': 'cast_spell', 'card_id': fresh.id, 'targets': {}}
    projected = settle_duplicate(view, seat, action)
    assert projected.cards[old.id].zone == Zone.BATTLEFIELD
    assert not projected.cards[old.id].summoning_sick
    assert projected.cards[fresh.id].zone == Zone.GRAVEYARD
    assert fresh.id not in projected.players[seat].hand
    assert any(projected.cards[cid].tapped for cid in view.players[seat].battlefield
               if view.cards[cid].name == 'Plains')
    agent = AIAgent('master', 'Aggro')
    assert agent._materialize_action(view, move, seat).get('_invalid_ai_choice') is True
    candidates = agent._strategic_top_actions(view, moves, seat, 8)
    assert not any(a.get('card_id') == fresh.id for a in candidates)
    assert any(a.get('card_id') == officer.id for a in candidates)
    assert serialize_match_snapshot(view) == before and moves == offered
    assert (random.getstate(), view.rng.getstate()) == rng


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lethal', [False, True])
def test_real_death_payoff_stays_available(seat, lethal):
    state, old, fresh = duplicate_position(seat, 'Isamaru, Hound of Konda')
    raw_card(state, CARDS['Blood Artist'], seat, Zone.BATTLEFIELD)
    state.players[3-seat].life = 1 if lethal else 20
    rules = RulesEngine()
    view, moves = decision_view(state, seat, rules.legal_moves(state, seat))
    move = next(m for m in moves if m.get('card_id') == fresh.id)
    action = AIAgent('master', 'Aggro')._materialize_action(view, move, seat)
    assert not action.get('_invalid_ai_choice')
    result = settle_duplicate(view, seat, action)
    assert result.players[3-seat].life == (0 if lethal else 19)
    assert result.players[seat].life == 21
    assert result.winner == (seat if lethal else None)


@pytest.mark.parametrize('seat', [1, 2])
def test_useful_body_upgrade_is_not_a_blanket_duplicate_ban(seat):
    state, old, fresh = duplicate_position(seat, 'Isamaru, Hound of Konda')
    old.counters['-1/-1'] = 1
    rules = RulesEngine()
    view, moves = decision_view(state, seat, rules.legal_moves(state, seat))
    move = next(m for m in moves if m.get('card_id') == fresh.id)
    action = AIAgent('master', 'Aggro')._materialize_action(view, move, seat)
    assert not action.get('_invalid_ai_choice')
    result = settle_duplicate(view, seat, action)
    assert result.cards[fresh.id].zone == Zone.BATTLEFIELD
    assert result.cards[old.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_duplicate_veto_precedes_synthetic_learned_preference(monkeypatch, seat):
    from ai import learned_policy, learned_qv
    state, _, fresh = duplicate_position(seat, 'Isamaru, Hound of Konda')
    rules = RulesEngine()
    view, moves = decision_view(state, seat, rules.legal_moves(state, seat))

    class Scores:
        def predict(self, pack):
            kind = _field(_expanded(pack), 'type')['value']
            return {'q': 0.9 if kind == 'cast_spell' else 0.0, 'v': 0.0}

    binding = _binding(learned_policy)
    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda _policy, _pack: Scores())
    agent = AIAgent('master', 'Aggro', learned_binding=binding)
    before = serialize_match_snapshot(view)
    chosen = learned_policy.choose_learned_action(binding, agent, view, moves, seat,
        admit=lambda a: checked_action(view, rules, seat, a))
    assert chosen is not None and chosen['type'] == 'pass_priority'
    assert fresh.id in view.players[seat].hand
    assert serialize_match_snapshot(view) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('benefit', ['opponent_tap', 'granted_ability', 'entry_counters',
                                    'player_protection', 'extra_turn', 'unsupported'])
def test_synthetic_settlement_protocol_does_not_erase_unpriced_changes(monkeypatch, seat, benefit):
    """Boundary fault injection, not a claim that these cards cause the change."""
    from ai import pending_effects
    state, old, fresh = duplicate_position(seat, 'Isamaru, Hound of Konda')
    opposing = raw_card(state, CARDS['Plains'], 3-seat, Zone.BATTLEFIELD)
    original = pending_effects._settle_announced_stack

    def settle(projected, **kwargs):
        assert original(projected, **kwargs)
        if benefit == 'opponent_tap':
            projected.cards[opposing.id].tapped = True
        elif benefit == 'granted_ability':
            projected.cards[old.id].activated_ability_effects.append({'synthetic_protocol': True})
        elif benefit == 'entry_counters':
            projected.pending_entry_counters.append({'synthetic_protocol': True})
        elif benefit == 'player_protection':
            projected.turn_spell_protection.add(seat)
        elif benefit == 'extra_turn':
            projected.extra_turns.append({'synthetic_protocol': True})
        else:
            projected.log.append('Unsupported synthetic settlement instruction')
        return True

    monkeypatch.setattr(pending_effects, '_settle_announced_stack', settle)
    action = {'type': 'cast_spell', 'card_id': fresh.id, 'targets': {}}
    assert not AIAgent('master', 'Aggro')._empty_duplicate_legend_cast(state, action, seat)
