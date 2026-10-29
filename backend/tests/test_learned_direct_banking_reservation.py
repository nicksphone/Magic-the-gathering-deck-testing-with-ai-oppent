"""Canonical resource roots with controlled Q protocol, not trained-model evidence."""
from copy import deepcopy

import pytest

from ai import learned_policy, learned_qv, pending_effects
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands
from tests.test_foretell import add as foretell_add, setup as foretell_setup
from tests.test_live_learned_policy import _binding
from tests.test_suspend_lifecycle import setup as suspend_setup
from tests.test_surveil_mill import add as interaction_add
from tests.test_training_reference_context import _field

RULES = RulesEngine()
WAIT = {'type': 'pass_priority'}


def direct_bank(monkeypatch, state, seat, action, *, forecast=None, nonfinite=None,
                include_pass=True):
    scores = []

    class Scores:
        def predict(self, pack):
            kind = _field(pack['root'], 'type')['value']
            scores.append(kind)
            result = {'q': .9 if kind in {'foretell', 'suspend'} else 0.0, 'v': 0.0}
            if nonfinite and kind == nonfinite[0]:
                result[nonfinite[1]] = float('nan')
            return result

    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda *_: Scores())
    agent = AIAgent(difficulty='master', archetype='Control')
    proposals = [deepcopy(action)] + ([dict(WAIT)] if include_pass else [])
    monkeypatch.setattr(agent, '_strategic_top_actions', lambda *_: deepcopy(proposals))
    if forecast:
        monkeypatch.setattr(pending_effects, 'unanswered_action_wins',
                            lambda _view, _seat, move, **_kwargs: forecast(move)[0])
        monkeypatch.setattr(pending_effects, 'unanswered_action_loses',
                            lambda _view, _seat, move, **_kwargs: forecast(move)[1])
    before = serialize_match_snapshot(state)
    moves = RULES.legal_moves(deepcopy(state), seat)
    old_moves = deepcopy(moves)
    view, supplied = decision_view(state, seat, moves)
    before_view = serialize_match_snapshot(view)
    admitted = []

    def admit(proposed):
        admitted.append(deepcopy(proposed))
        return checked_action(state, RULES, seat, proposed)

    result = learned_policy.choose_learned_action(
        _binding(learned_policy), agent, view, supplied, seat, admit=admit)
    assert action in admitted and (WAIT in admitted) is include_pass
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(view) == before_view and moves == old_moves
    if result is not None:
        checked_action(state, RULES, seat, result)
    return result, scores


def affordable(state, seat, card_id):
    card = state.cards[card_id]
    return any(can_pay_with_pool_and_lands(
        state, seat, option.mana_cost, spell_types=card.types, source_card_id=card_id)
        for option in collect_cost_options(state, seat, card))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['foretell', 'suspend'])
@pytest.mark.parametrize('preserved', [False, True])
def test_direct_bank_keeps_other_affordable_interaction(monkeypatch, seat, family, preserved):
    if family == 'foretell':
        state, cid = foretell_setup('Behold the Multiverse', seat)
        answer = foretell_add(state, 'Saw It Coming', seat)
        state.players[seat].mana_pool = {'U': 5 if preserved else 3}
    else:
        state, cid = suspend_setup(seat, 'Ancestral Vision')
        answer = interaction_add(state, 'Counterspell', seat, Zone.HAND)
        state.players[seat].mana_pool = {'U': 3 if preserved else 2}
    state.turn = 1
    action = {'type': family, 'card_id': cid}
    assert affordable(state, seat, answer.id)
    paid = checked_action(state, RULES, seat, action)
    assert paid.cards[cid].zone == Zone.EXILE
    assert affordable(paid, seat, answer.id) is preserved
    result, scores = direct_bank(monkeypatch, state, seat, action)
    assert result == (action if preserved else WAIT)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['foretell', 'suspend'])
def test_direct_bank_cannot_hide_the_affordable_answer_itself(monkeypatch, seat, family):
    if family == 'foretell':
        state, cid = foretell_setup('Saw It Coming', seat)
        foretell_add(state, 'Ranar the Ever-Watchful', seat, Zone.BATTLEFIELD)
        state.players[seat].mana_pool = {'U': 3}
    else:
        state, cid = suspend_setup(seat, 'Rift Bolt')
        state.players[seat].mana_pool = {'R': 3}
    state.turn = 1
    action = {'type': family, 'card_id': cid}
    assert affordable(state, seat, cid)
    paid = checked_action(state, RULES, seat, action)
    assert cid not in paid.players[seat].hand
    if family == 'foretell':
        assert paid.players[seat].mana_pool == state.players[seat].mana_pool
    result, scores = direct_bank(monkeypatch, state, seat, action)
    assert result == WAIT


def reserved_bank(family, seat):
    if family == 'foretell':
        state, cid = foretell_setup('Saw It Coming', seat)
        state.players[seat].mana_pool = {'U': 3}
    else:
        state, cid = suspend_setup(seat, 'Rift Bolt')
        state.players[seat].mana_pool = {'R': 3}
    assert affordable(state, seat, cid)
    return state, {'type': family, 'card_id': cid}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['foretell', 'suspend'])
@pytest.mark.parametrize('win', [True, False, None])
def test_terminal_provider_protocol_precedes_reservation(monkeypatch, seat, family, win):
    # Provider protocol only: this native bank is NOT claimed to win the game.
    state, action = reserved_bank(family, seat)
    result, _ = direct_bank(monkeypatch, state, seat, action,
        forecast=lambda move: (win, False) if move == action else (False, False))
    assert result == (action if win is True else WAIT)


@pytest.mark.parametrize('family', ['foretell', 'suspend'])
@pytest.mark.parametrize('key', ['q', 'v'])
@pytest.mark.parametrize('bad_bank', [True, False])
def test_provider_protocol_checks_finite_outputs_even_for_vetoed_bank(
        monkeypatch, family, key, bad_bank):
    state, action = reserved_bank(family, 1)
    result, _ = direct_bank(monkeypatch, state, 1, action,
        forecast=lambda _move: (False, False),
        nonfinite=(family if bad_bank else 'pass_priority', key))
    assert result is None


@pytest.mark.parametrize('family', ['foretell', 'suspend'])
def test_provider_protocol_all_reservation_vetoes_fall_back(monkeypatch, family):
    state, action = reserved_bank(family, 1)
    result, _ = direct_bank(monkeypatch, state, 1, action,
        forecast=lambda _move: (False, False), include_pass=False)
    assert result is None
