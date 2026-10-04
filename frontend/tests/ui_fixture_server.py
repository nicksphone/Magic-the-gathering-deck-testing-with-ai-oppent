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
