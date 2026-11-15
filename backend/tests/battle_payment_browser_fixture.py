"""Declared canonical midgame for browser Battle/Pact acceptance, not history."""
import json
from pathlib import Path

from card_data.seed_cards import seed_card_payload
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry


def midgame(seat):
    if type(seat) is not int or seat not in (1, 2):
        raise ValueError("Expected seat one or two")
    pact = "Summoner's Pact"
    fixtures = Path(__file__).parent / "fixtures"
    battle_raw = json.loads((fixtures / "battle_full_printing/invasion-of-zendikar-mom-194.json").read_text())
    bears = json.loads((fixtures / "library_canonical_88/grizzly-bears-scryfall-raw.json").read_text())
    deck = [{**battle_raw, "card_name": battle_raw["name"], "quantity": 1},
            {**bears, "card_name": bears["name"], "quantity": 4},
            {**seed_card_payload("Forest"), "card_name": "Forest", "quantity": 53},
            {**seed_card_payload(pact), "card_name": pact, "quantity": 2}]
    state = MatchFactory.from_decks(deck, deck, seed=71203)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    state.priority_stops = {player: set(Step) for player in (1, 2)}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
        player.lands_played_this_turn = player.land_plays_recorded_on_turn = 1
        player.last_land_play_turn = state.turn
    def place(name, zone):
        player = state.players[seat]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        card = state.cards[cid]
        card.move_to_zone(zone)
        getattr(player, zone.value).append(cid)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, cid)
            card.summoning_sick = False
        return cid

    for _ in range(6):
        place("Forest", Zone.BATTLEFIELD)
    attackers = [place("Grizzly Bears", Zone.BATTLEFIELD) for _ in range(3)]
    battle = place(battle_raw["card_faces"][0]["name"], Zone.HAND)
    pacts = [place(pact, Zone.HAND) for _ in range(2)]
    state.log.append("Declared canonical midgame: initial lands and creatures are fixture inputs, not played history.")
    return state, {"battle": battle, "attackers": attackers, "pacts": pacts}


def unsupported_midgame(seat):
    """Explicit UI negative input; this is not a supported Oracle instruction."""
    state, ids = midgame(seat)
    state.pending_mechanic_choice = {
        "kind": "diagnostic_unknown", "player_id": seat, "count": 1,
        "options": ["unimplemented"], "label": "Diagnostic unsupported choice",
    }
    return state, ids
