from __future__ import annotations

from decks.sideboard import apply_sideboard_swaps


def test_sideboard_swap_moves_cards_between_zones() -> None:
    main = [{"card_name": "Island", "quantity": 56}, {"card_name": "Counterspell", "quantity": 4}]
    side = [{"card_name": "Negate", "quantity": 3}, {"card_name": "Dispel", "quantity": 2}]

    new_main, new_side = apply_sideboard_swaps(
        main,
        side,
        cards_out=[{"card_name": "Counterspell", "quantity": 2}],
        cards_in=[{"card_name": "Negate", "quantity": 2}],
    )

    main_map = {x["card_name"]: x["quantity"] for x in new_main}
    side_map = {x["card_name"]: x["quantity"] for x in new_side}
    assert main_map["Counterspell"] == 2
    assert main_map["Negate"] == 2
    assert side_map["Negate"] == 1
    assert side_map["Counterspell"] == 2
