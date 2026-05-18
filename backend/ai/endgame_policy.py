from __future__ import annotations


def should_force_closure(turn: int, own_archetype: str, opp_archetype: str | None) -> bool:
    own = (own_archetype or "").strip().lower()
    opp = (opp_archetype or "").strip().lower()
    if turn >= 14 and own in {"control", "counter-heavy"} and opp in {"control", "counter-heavy"}:
        return True
    if turn >= 16 and own in {"ramp", "midrange"} and opp in {"control", "counter-heavy"}:
        return True
    return turn >= 20


def should_force_inevitability_line(turn: int, own_archetype: str, opp_archetype: str | None) -> bool:
    own = (own_archetype or "").strip().lower()
    opp = (opp_archetype or "").strip().lower()
    if own not in {"control", "counter-heavy"}:
        return False
    if opp in {"control", "counter-heavy"}:
        return turn >= 9
    return turn >= 12
