"""Execute in disposable source: API lifespan uses a source-local database."""
import pytest

from ai.agent import AIAgent, AIDecision
from game_state.state import Step, Zone
from tests.test_api_input_contracts import game, add_card, persist, snapshot
from tests.test_match_recovery import headers


@pytest.mark.parametrize("intent", [None, [], {}, {"type": "play_land", "card_id": "stale"}])
def test_forced_land_with_malformed_ai_preference_uses_only_an_offered_land(game, monkeypatch, intent):
    client, match = game
    match.controllers = {1: "ai", 2: "ai"}
    persist(match)
    before = set(match.state.players[1].hand)
    monkeypatch.setattr(AIAgent, "choose_action", lambda *args: AIDecision(intent, "malformed preference"))
    response = client.post(f"/matches/{match.state.id}/autoplay", headers=headers())
    assert response.status_code == 200, response.text
    player = match.state.players[1]
    assert player.lands_played_this_turn == 1
    assert len(player.battlefield) == 1 and player.battlefield[0] in before
    assert match.state.cards[player.battlefield[0]].types == ['Land']


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("action", [
    None, {}, {"type": "invented_action"},
    {"type": "cast_spell"},
    {"type": "cast_spell", "card_id": "stale", "targets": {"target_player": 2}},
    {"type": "pass_priority", "_invalid_ai_choice": True},
])
def test_invalid_ai_action_rejects_without_memory_database_or_receipt_mutation(game, monkeypatch, seat, action):
    client, match = game
    match.controllers = {1: "ai", 2: "ai"}
    match.state.active_player = match.state.priority_player = seat
    match.state.step = Step.END_STEP
    persist(match)
    before = snapshot(match)
    monkeypatch.setattr(AIAgent, "choose_action", lambda *args: AIDecision(action, "injected invalid action"))
    response = client.post(f"/matches/{match.state.id}/autoplay", headers=headers())
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "illegal_ai_action"
    assert response.json()["detail"]["player_id"] == seat
    assert snapshot(match) == before


@pytest.mark.parametrize("seat", [1, 2])
def test_invalid_target_does_not_pay_mana_or_move_ai_spell(game, monkeypatch, seat):
    client, match = game
    match.controllers = {1: "ai", 2: "ai"}
    match.state.active_player = match.state.priority_player = seat
    match.state.step = Step.END_STEP
    add_card(match, "bolt", "Lightning Bolt", Zone.HAND, ["Instant"], "{R}",
             "Lightning Bolt deals 3 damage to any target.", owner=seat)
    match.state.players[seat].mana_pool["R"] = 1
    persist(match)
    before = snapshot(match)
    action = {"type": "cast_spell", "card_id": "bolt", "targets": {"target_player": 99}}
    monkeypatch.setattr(AIAgent, "choose_action", lambda *args: AIDecision(action, "injected invalid target"))
    response = client.post(f"/matches/{match.state.id}/autoplay", headers=headers())
    assert response.status_code == 422, response.text
    assert snapshot(match) == before


def test_later_tick_rejection_rolls_back_earlier_priority_and_retry_receipt(game, monkeypatch):
    client, match = game
    match.controllers = {1: "ai", 2: "ai"}
    match.state.step = Step.END_STEP
    persist(match)
    before = snapshot(match)
    actions = iter([{"type": "pass_priority"}, {"type": "cast_spell", "card_id": "stale"}])
    monkeypatch.setattr(AIAgent, "choose_action", lambda *args: AIDecision(next(actions), "injected sequence"))
    response = client.post(f"/matches/{match.state.id}/autoplay?ticks=2", headers=headers())
    assert response.status_code == 422, response.text
    assert snapshot(match) == before


@pytest.mark.parametrize("seat", [1, 2])
def test_valid_ai_spell_uses_checked_boundary_and_idempotent_retry(game, monkeypatch, seat):
    client, match = game
    match.controllers = {1: "ai", 2: "ai"}
    match.state.active_player = match.state.priority_player = seat
    match.state.step = Step.END_STEP
    add_card(match, "bolt", "Lightning Bolt", Zone.HAND, ["Instant"], "{R}",
             "Lightning Bolt deals 3 damage to any target.", owner=seat)
    match.state.players[seat].mana_pool["R"] = 1
    persist(match)
    action = {"type": "cast_spell", "card_id": "bolt", "targets": {"target_player": 3 - seat}}
    monkeypatch.setattr(AIAgent, "choose_action", lambda *args: AIDecision(action, "controlled legal choice"))
    path = f"/matches/{match.state.id}/autoplay"
    response = client.post(path, headers=headers())
    assert response.status_code == 200, response.text
    assert match.state.cards["bolt"].zone == Zone.STACK
    assert match.state.players[seat].mana_pool["R"] == 0
    assert len(match.state.stack) == 1
    after = snapshot(match)
    repeated = client.post(path, headers=headers())
    assert repeated.status_code == 200, repeated.text
    assert snapshot(match) == after
