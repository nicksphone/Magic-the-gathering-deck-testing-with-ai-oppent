from types import SimpleNamespace
from threading import RLock

import pytest

from game_state.state import CardInstance, MatchFactory, Step, Zone
from main import ACTIVE_MATCHES, _human_priority_pause, autoplay_tick, get_legal_moves
from rules_engine.engine import RulesEngine


def match_at(step, seat=1):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=35)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 3
    state.step = step
    state.active_player = state.priority_player = seat
    state.players[seat].hand.clear()
    return SimpleNamespace(state=state, rules=RulesEngine(), revision=0,
                           controllers={1: "human", 2: "human"}, mode="player_vs_ai", match_complete=False,
                           mutation_lock=RLock(), mutation_receipts={})


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("step", [Step.UPKEEP, Step.DRAW, Step.END_STEP])
def test_empty_windows_ignore_bare_mana_and_restricted_hints(seat, step):
    match = match_at(step, seat)
    match.rules = SimpleNamespace(legal_moves=lambda *_: [
        {"type": "pass_priority"}, {"type": "activate_mana_ability"},
        {"type": "attack_restricted"}, {"type": "cast_spell_restricted"},
    ])
    assert not _human_priority_pause(match, seat)


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("kind", ["cast_spell", "activate_ability", "attack", "block", "play_land",
                                 "choose_mechanic", "choose_trigger_target", "choose_optional_effect"])
def test_actual_decisions_stop_even_outside_configured_steps(seat, kind):
    match = match_at(Step.DRAW, seat)
    match.state.priority_stops[seat] = set()
    match.rules = SimpleNamespace(legal_moves=lambda *_: [{"type": "pass_priority"}, {"type": kind, "blockers": [{"id": "body"}]}])
    assert _human_priority_pause(match, seat)


def test_no_available_blockers_does_not_require_human_confirmation():
    match = match_at(Step.DECLARE_BLOCKERS)
    match.rules = SimpleNamespace(legal_moves=lambda *_: [
        {"type": "pass_priority"}, {"type": "block", "blockers": []},
    ])
    assert not _human_priority_pause(match, 1)


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("pooled", [True, False])
def test_payable_end_step_instant_preserves_control_window(seat, pooled):
    match = match_at(Step.END_STEP, seat)
    match.state.active_player = 3 - seat
    match.state.players[seat].mana_pool["U"] = 2 if pooled else 0
    if not pooled:
        for index in range(2):
            land = CardInstance(id=f"island-{index}", name="Island", owner=seat, controller=seat,
                                zone=Zone.BATTLEFIELD, types=["Land"], type_line="Basic Land - Island")
            match.state.cards[land.id] = land
            match.state.players[seat].battlefield.append(land.id)
    card = CardInstance(id="think", name="Think Twice", owner=seat, controller=seat,
                        zone=Zone.HAND, types=["Instant"], mana_cost="{1}{U}",
                        oracle_text="Draw a card.")
    match.state.cards[card.id] = card
    match.state.players[seat].hand.append(card.id)
    assert any(m["type"] == "cast_spell" for m in match.rules.legal_moves(match.state, seat))
    assert _human_priority_pause(match, seat)


def test_autoplay_runs_untap_upkeep_draw_then_stops_at_legal_land(monkeypatch):
    match = match_at(Step.UNTAP)
    ACTIVE_MATCHES[match.state.id] = match
    monkeypatch.setattr("main._post_step_finalize", lambda *_: None)
    monkeypatch.setattr("main._remember_public_types", lambda *_: None)
    monkeypatch.setattr("main._persist_active_match", lambda *_: None)
    monkeypatch.setattr("main._serialize_match_controller", lambda m: m.state)
    try:
        before = len(match.state.players[1].library)
        assert get_legal_moves(match.state.id)["can_auto_pass"]
        autoplay_tick(match.state.id, ticks=20, repo=None)
        assert match.state.step == Step.PRECOMBAT_MAIN
        assert len(match.state.players[1].library) == before - 1
        assert len(match.state.players[1].hand) == 1
        assert not get_legal_moves(match.state.id)["can_auto_pass"]
    finally:
        ACTIVE_MATCHES.pop(match.state.id, None)
