"""V2 visual stress positions, not played games. Disposable loopback source copy only.

Uses canonical test metadata and real mutation/persistence routes. Optional local
art must be pre-cached as v2-<slug>.jpg; this fixture never downloads card data.
"""
from pathlib import Path
import main

if (Path(main.__file__).resolve().parents[1] / ".git").exists():
    raise RuntimeError("UI fixtures require a disposable backend source copy")

from tests.ui_fixture_server import app, publish, fixture, add
from game_state.state import Zone


@app.post("/fixture/table-v2")
def table_v2(seat: int = 1, crowded: bool = True, artwork: bool = True):
    if seat not in (1, 2):
        raise ValueError("Expected seat one or two")
    state = fixture()
    state.active_player = state.priority_player = seat
    for player in (1, 2):
        state.players[player].mana_pool = {color: 0 for color in "WUBRGC"}
        state.players[player].mana_pool["G"] = 2
        state.players[player].snow_mana_pool = {color: 0 for color in "WUBRGC"}
        for index in range(15 if crowded else 3):
            card = add(state, ["Grizzly Bears", "Llanowar Elves", "Torrential Gearhulk"][index % 3], player)
            card.summoning_sick = index == 0
            card.tapped = index % 4 == 2
            if index == 1:
                card.counters["+1/+1"] = 1
                card.counters["__damage_marked"] = 1
        for index in range(20 if crowded else 5):
            card = add(state, "Swamp", player)
            card.tapped = index < 3
        for index in range(15 if crowded else 4):
            add(state, ["Grizzly Bears", "Go for the Throat", "Naturalize", "Swamp"][index % 4], player, Zone.HAND)
        add(state, "Grizzly Bears", player, Zone.GRAVEYARD)
        if artwork:
            for zone in ("battlefield", "hand", "graveyard"):
                for card_id in getattr(state.players[player], zone):
                    card = state.cards[card_id]
                    filename = "v2-" + card.name.lower().replace(" ", "-") + ".jpg"
                    if (main.CACHE_DIR / filename).is_file():
                        card.image_uri = "/card-images/" + filename
    state.log.append("V2 UI stress fixture: canonical cards; constructed position, not a played game.")
    return publish(state, [{"quantity": 60, "card_name": "Swamp"}])
