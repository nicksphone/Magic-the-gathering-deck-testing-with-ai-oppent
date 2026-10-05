"""UI-only scenario setup. Load ONLY beside a disposable backend source copy.

No rules are replaced. Canonical metadata comes from existing backend goldens;
all actions after setup run through the real API, rules and local persistence.
"""
from pathlib import Path
import main

if (Path(main.__file__).resolve().parents[1] / ".git").exists():
    raise RuntimeError("UI fixtures require a disposable backend source copy")

from tests.browser_fixture_server import app, publish, ACTIVE_MATCHES, Session, engine, Repository, _persist_active_match, get_match
import tests.casting_trigger_browser_fixture  # Register the connected casting fixture routes.
from tests.test_ai_recurring_engines import fixture, add
from game_state.state import Zone


@app.post("/fixture/direct-combat")
def direct_combat(seat: int = 1):
    from fastapi import HTTPException
    from tests.test_attack_bands import _state
    if seat not in (1, 2):
        raise HTTPException(422, "Expected seat one or two")
    state = _state()
    if seat == 2:
        state.players[1], state.players[2] = state.players[2], state.players[1]
        for player_id, player in state.players.items():
            player.id = player_id
        for card in state.cards.values():
            card.owner, card.controller = 3-card.owner, 3-card.controller
        state.active_player = state.priority_player = 2
    return publish(state, [{"quantity": 60, "card_name": "Island"}])


@app.post("/fixture/auto-progress")
def auto_progress(window: str = "empty"):
    from tests.test_human_auto_progress import match_at
    from game_state.state import CardInstance, Step
    if window not in {"empty", "end_step", "draw"}:
        from fastapi import HTTPException
        raise HTTPException(422, "Unsupported test window")
    state = match_at(Step.UNTAP if window == "empty" else Step(window)).state
    land = CardInstance(id="blue-source", name="Island", owner=1, controller=1,
                        zone=Zone.BATTLEFIELD, types=["Land"], type_line="Basic Land - Island")
    state.cards[land.id] = land
    state.players[1].battlefield.append(land.id)
    if window != "empty":
        state.active_player = 2
        state.players[1].mana_pool["U"] = 2
        spell = CardInstance(id="think", name="Think Twice", owner=1, controller=1,
                             zone=Zone.HAND, types=["Instant"], mana_cost="{1}{U}",
                             oracle_text="Draw a card.")
        state.cards[spell.id] = spell
        state.players[1].hand.append(spell.id)
    publish(state, [{"quantity": 60, "card_name": "Island"}])
    controller = ACTIVE_MATCHES[state.id]
    controller.controllers = {1: "human", 2: "ai"}
    controller.mode = "player_vs_ai"
    with Session(engine) as session:
        _persist_active_match(Repository(session), controller)
    return get_match(state.id)


@app.post("/fixture/table")
def table(seat: int = 1, crowded: bool = True, ai_opponent: bool = False):
    if seat not in (1, 2):
        raise ValueError("Expected seat one or two")
    state = fixture()
    state.active_player = state.priority_player = seat
    for player in (1, 2):
        state.players[player].mana_pool = {color: 10 for color in "WUBRGC"}
        state.players[player].snow_mana_pool = {color: 0 for color in "WUBRGC"}
        state.players[player].name = f"Player {player} · UI fixture"
        for index in range(14 if crowded else 2):
            card = add(state, ["Grizzly Bears", "Llanowar Elves", "Torrential Gearhulk"][index % 3], player)
            card.summoning_sick = index == 0
            card.tapped = index % 4 == 2
            if index == 1:
                card.counters["+1/+1"] = 1
                card.counters["__damage_marked"] = 1
        for index in range(9):
            land = add(state, "Swamp", player)
            land.tapped = index < 3
        for index in range(15 if crowded else 4):
            add(state, ["Grizzly Bears", "Go for the Throat", "Naturalize", "Swamp"][index % 4], player, Zone.HAND)
        add(state, "Grizzly Bears", player, Zone.GRAVEYARD)
    state.log.append("UI stress fixture: canonical cards; constructed board, not a played match or competitive deck.")
    result = publish(state, [{"quantity": 60, "card_name": "Swamp"}])
    if ai_opponent:
        controller = ACTIVE_MATCHES[state.id]
        controller.controllers = {1: "human", 2: "ai"}
        controller.mode = "player_vs_ai"
        with Session(engine) as session:
            _persist_active_match(Repository(session), controller)
        return get_match(state.id)
    return result
