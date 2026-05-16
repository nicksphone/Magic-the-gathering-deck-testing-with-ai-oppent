from __future__ import annotations


def profile_for(own_archetype: str, opp_archetype: str | None) -> dict[str, float]:
    own = (own_archetype or "").strip().lower()
    opp = (opp_archetype or "").strip().lower()
    profile = {
        "proactive_bias": 0.0,
        "holdup_bias": 0.0,
        "risk_tolerance": 0.0,
    }
    if own in {"control", "counter-heavy"}:
        profile["holdup_bias"] += 0.8
        if opp in {"control", "counter-heavy", "tempo"}:
            profile["proactive_bias"] += 0.7
    if own in {"aggro", "burn", "tribal", "tokens"}:
        profile["proactive_bias"] += 0.9
        profile["risk_tolerance"] += 0.5
    if own in {"ramp", "midrange"} and opp in {"control", "counter-heavy"}:
        profile["proactive_bias"] += 0.8
    if own in {"tempo"} and opp in {"ramp", "midrange"}:
        profile["holdup_bias"] += 0.3
        profile["proactive_bias"] += 0.4
    return profile

