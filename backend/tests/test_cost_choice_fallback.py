from __future__ import annotations

import json
from pathlib import Path

from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.extra_sequence_support import position
from tests.test_linked_damage_targets import raw_card


def test_cast_uses_available_alternate_cost_when_no_cost_choice_provided() -> None:
    state = position(1)
    raw = json.loads((Path(__file__).parent / "fixtures/cost_choice_fallback/bringer-red-dawn.json").read_text())
    spell = raw_card(state, raw, 1, Zone.HAND)
    player = state.players[1]
    player.mana_pool = {color: 1 for color in "WUBRG"}
    assert spell.mana_cost == "{7}{R}{R}"
    assert spell.oracle_text == raw["oracle_text"]

    # The normal nine-mana cost is unavailable; the five-colour alternative is payable.
    RulesEngine().take_action(state, 1, {"type": "cast_spell", "card_id": spell.id})

    assert spell.id not in player.hand
    assert spell.zone == Zone.STACK
    assert all(player.mana_pool.get(color, 0) == 0 for color in "WUBRG")
