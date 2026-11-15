"""Declared canonical midgame for browser Battle/Pact acceptance, not history."""
from card_data.seed_cards import seed_card_payload
from game_state.state import MatchFactory, Step, Zone
from tests.test_battle_entry import BATTLE, place, row


def midgame(seat):
    if type(seat) is not int or seat not in (1, 2):
        raise ValueError("Expected seat one or two")
    pact = "Summoner's Pact"
    deck = [row(BATTLE, 1), row("Grizzly Bears", 4), row("Forest", 53),
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
    for _ in range(6):
        place(state, seat, "Forest", Zone.BATTLEFIELD)
    attackers = [place(state, seat, "Grizzly Bears", Zone.BATTLEFIELD) for _ in range(3)]
    battle = place(state, seat, BATTLE, Zone.HAND)
    pacts = [place(state, seat, pact, Zone.HAND) for _ in range(2)]
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
