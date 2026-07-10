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
        if opp in {"control", "counter-heavy"}:
            profile["proactive_bias"] += 0.8
        elif opp in {"tempo", "aggro", "burn"}:
            profile["holdup_bias"] += 0.5
            profile["risk_tolerance"] -= 0.1
        elif opp in {"tokens", "tribal", "drain", "aristocrats"}:
            profile["proactive_bias"] += 0.4
            profile["risk_tolerance"] += 0.2
    if own in {"aggro", "burn", "tribal", "tokens"}:
        profile["proactive_bias"] += 0.9
        profile["risk_tolerance"] += 0.5
    if own in {"ramp", "midrange"} and opp in {"control", "counter-heavy"}:
        profile["proactive_bias"] += 0.8
    if own in {"ramp", "midrange"} and opp in {"aggro", "burn", "tempo"}:
        profile["holdup_bias"] += 0.5
        profile["risk_tolerance"] -= 0.2
    if own in {"tempo"} and opp in {"ramp", "midrange"}:
        profile["holdup_bias"] += 0.3
        profile["proactive_bias"] += 0.4
    if own in {"tempo"} and opp in {"control", "counter-heavy"}:
        profile["proactive_bias"] += 0.5
        profile["risk_tolerance"] += 0.2
    return profile
