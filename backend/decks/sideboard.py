from __future__ import annotations

from collections import Counter


class SideboardError(Exception):
    pass


def apply_sideboard_swaps(
    mainboard: list[dict],
    sideboard: list[dict],
    cards_out: list[dict],
    cards_in: list[dict],
) -> tuple[list[dict], list[dict]]:
    main = _to_counter(mainboard)
    side = _to_counter(sideboard)
    out_counts = _to_counter(cards_out)
    in_counts = _to_counter(cards_in)

    if sum(out_counts.values()) != sum(in_counts.values()):
        raise SideboardError("Sideboard swaps must have equal cards in and out.")

    for name, qty in out_counts.items():
        if main[name] < qty:
            raise SideboardError(f"Cannot remove {qty}x {name}; only {main[name]} in mainboard.")
    for name, qty in in_counts.items():
        if side[name] < qty:
            raise SideboardError(f"Cannot bring in {qty}x {name}; only {side[name]} in sideboard.")

    for name, qty in out_counts.items():
        main[name] -= qty
        side[name] += qty
    for name, qty in in_counts.items():
        side[name] -= qty
        main[name] += qty

    if sum(main.values()) < 60:
        raise SideboardError("Mainboard cannot be below 60 cards after sideboarding.")

    return _from_counter(main), _from_counter(side)


def _to_counter(deck_items: list[dict]) -> Counter:
    c = Counter()
    for item in deck_items:
        name = item["card_name"]
        qty = int(item["quantity"])
        if qty <= 0:
            continue
        c[name] += qty
    return c


def _from_counter(counter: Counter) -> list[dict]:
    return [{"card_name": n, "quantity": q} for n, q in sorted(counter.items()) if q > 0]
