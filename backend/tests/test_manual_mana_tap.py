from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_tap_lands_bulk_adds_mana_and_taps_requested_count() -> None:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    p1 = state.players[1]

    # Stage exactly three Mountains as untapped battlefield lands.
    p1.battlefield = []
    for _ in range(3):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.name = "Mountain"
        card.types = ["Land"]
        card.tapped = False

    engine.take_action(state, 1, {"type": "tap_lands_bulk", "land_name": "Mountain", "count": 2})

    tapped = sum(1 for cid in p1.battlefield if state.cards[cid].tapped)
    assert tapped == 2
    assert p1.mana_pool["R"] == 2
