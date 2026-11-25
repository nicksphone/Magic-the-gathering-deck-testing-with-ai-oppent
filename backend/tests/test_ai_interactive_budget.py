from copy import deepcopy
from types import SimpleNamespace

import pytest

from ai import interactive_budget as budget
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import fixture


def position():
    state = fixture()
    seat = state.priority_player
    return state, seat, RulesEngine().legal_moves(state, seat)


def test_default_and_under_budget_return_the_native_decision(monkeypatch):
    monkeypatch.delenv('MTG_AI_INTERACTIVE_NODES', raising=False)
    monkeypatch.delenv('MTG_AI_INTERACTIVE_MS', raising=False)
    state, seat, offers = position()
    expected = SimpleNamespace(action={'type': 'pass_priority'})

    def choose(*args):
        assert args == (state, offers, seat)
        budget.checkpoint()
        return expected

    agent = SimpleNamespace(choose_action=choose)
    assert budget.choose_for_autoplay(agent, state, offers, seat) is expected
    monkeypatch.setenv('MTG_AI_INTERACTIVE_NODES', '1')
    assert budget.choose_for_autoplay(agent, state, offers, seat) is expected


@pytest.mark.parametrize('mode', ['nodes', 'deadline'])
def test_exhausted_search_discards_adaptation_and_returns_checked_fallback(monkeypatch, mode):
    monkeypatch.delenv('MTG_AI_INTERACTIVE_NODES', raising=False)
    monkeypatch.delenv('MTG_AI_INTERACTIVE_MS', raising=False)
    state, seat, offers = position()
    before = serialize_match_snapshot(state)
    seen = []
    clock = [0.0]
    agent = SimpleNamespace(_main_pass_signature_counts={'existing': 1})

    def choose(*args):
        budget.checkpoint()
        agent._main_pass_signature_counts['aborted'] = 2
        clock[0] = 0.1
        budget.checkpoint()
        seen.append('past boundary')
        raise AssertionError('Expired search continued')

    agent.choose_action = choose
    monkeypatch.setattr(budget, 'monotonic', lambda: clock[0])
    monkeypatch.setenv('MTG_AI_INTERACTIVE_NODES' if mode == 'nodes' else 'MTG_AI_INTERACTIVE_MS',
                       '1' if mode == 'nodes' else '50')
    decision = budget.choose_for_autoplay(agent, state, offers, seat)
    assert decision.action == {'type': 'pass_priority'}
    assert 'budget' in decision.reasoning
    assert seen == [] and agent._main_pass_signature_counts == {'existing': 1}
    assert serialize_match_snapshot(state) == before
    budget.checkpoint()  # the next caller has no leaked scope


def test_no_checked_candidate_pauses_instead_of_inventing_an_action(monkeypatch):
    monkeypatch.setenv('MTG_AI_INTERACTIVE_NODES', '0')
    monkeypatch.delenv('MTG_AI_INTERACTIVE_MS', raising=False)
    state, seat, _ = position()
    before = serialize_match_snapshot(state)
    agent = SimpleNamespace(choose_action=lambda *args: pytest.fail('Zero budget entered search'))
    offers = [{'type': 'cast_spell', 'card_id': 'missing'}]
    assert budget.choose_for_autoplay(agent, state, deepcopy(offers), seat) is None
    assert serialize_match_snapshot(state) == before


def test_real_search_copy_boundary_charges_the_node_budget(monkeypatch):
    from ai.pending_effects import planning_copy

    monkeypatch.setenv('MTG_AI_INTERACTIVE_NODES', '1')
    monkeypatch.delenv('MTG_AI_INTERACTIVE_MS', raising=False)
    state, seat, offers = position()
    called = []

    def choose(current, *_):
        planning_copy(current)
        called.append(True)
        planning_copy(current)
        pytest.fail('Second planning copy exceeded the allowance')

    agent = SimpleNamespace(choose_action=choose)
    assert budget.choose_for_autoplay(agent, state, offers, seat).action == {'type': 'pass_priority'}
    assert called == [True]


def test_autoplay_pause_keeps_unresolved_choice_and_revision(monkeypatch):
    import main
    from fastapi import HTTPException
    from threading import RLock

    monkeypatch.setenv('MTG_AI_INTERACTIVE_NODES', '0')
    monkeypatch.delenv('MTG_AI_INTERACTIVE_MS', raising=False)
    state, seat, _ = position()
    match = SimpleNamespace(state=state, match_complete=False,
                            controllers={seat: 'ai'}, revision=11,
                            mutation_lock=RLock(), mutation_receipts={},
                            ai={seat: SimpleNamespace()}, rules=SimpleNamespace(
                                advance_no_priority_step=lambda _: False,
                                legal_moves=lambda *_: [{'type': 'cast_spell', 'card_id': 'missing'}],
                            ))
    before = serialize_match_snapshot(state)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {state.id: match})
    monkeypatch.setattr(main, '_load_saved_match', lambda *_: match)
    monkeypatch.setattr(main, '_default_player_for_state', lambda _: seat)
    monkeypatch.setattr(main, '_force_ai_land_action', lambda *_: None)
    monkeypatch.setattr(main, 'checked_action', lambda *_: pytest.fail('Autoplay committed an invented action'))
    monkeypatch.setattr(main, '_post_step_finalize', lambda *_: None)
    monkeypatch.setattr(main, '_persist_active_match', lambda *_: pytest.fail('Paused request was persisted'))
    request = SimpleNamespace(headers={'Idempotency-Key': 'test', 'X-Match-Revision': '11'})
    with pytest.raises(HTTPException) as failure:
        main.autoplay_tick(state.id, ticks=1, repo=None, request=request)
    assert failure.value.status_code == 503
    assert failure.value.detail == {'code': 'ai_decision_budget_exhausted'}
    assert match.revision == 11 and match.mutation_receipts == {}
    assert serialize_match_snapshot(match.state) == before


def test_forced_land_search_uses_same_budget_and_returns_checked_offer(monkeypatch):
    import main
    from game_state.state import Zone

    monkeypatch.setenv('MTG_AI_INTERACTIVE_NODES', '0')
    monkeypatch.delenv('MTG_AI_INTERACTIVE_MS', raising=False)
    state, seat, _ = position()
    player = state.players[seat]
    cid = player.library.pop()
    state.cards[cid].move_to_zone(Zone.HAND)
    player.hand.append(cid)
    offers = RulesEngine().legal_moves(state, seat)
    agent = SimpleNamespace(choose_action=lambda *_: pytest.fail('Zero budget entered land search'))
    match = SimpleNamespace(state=state, ai={seat: agent})
    move = main._force_ai_land_action(match, seat, offers)
    assert move in offers and move['type'] == 'play_land' and move['card_id'] == cid
