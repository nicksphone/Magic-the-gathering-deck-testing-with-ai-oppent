from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize card play logic from H2H games.jsonl traces")
    p.add_argument("--games-jsonl", required=True, help="Path to games.jsonl from debug_head_to_head.py")
    p.add_argument("--out", default="", help="Optional output json path")
    return p.parse_args()


def _step_key(step: object) -> str:
    text = str(step or "")
    if "." in text:
        text = text.split(".")[-1]
    return text.strip().lower()


def _is_main_phase_window(payload: dict) -> bool:
    return _step_key(payload.get("step")) in {"precombat_main", "postcombat_main"} and bool(payload.get("legal_non_pass"))


def summarize_card_play_logic(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"games.jsonl not found: {path}")

    total_games = 0
    timeouts = 0
    winners = Counter()
    action_types = Counter()
    cast_by_card = Counter()
    play_land_count = Counter()
    pass_with_options = Counter()
    pass_with_meaningful_options = Counter()
    main_phase_passes = Counter()
    missed_land_windows = Counter()
    unused_mana_with_options = Counter()
    main_phase_land_not_first = Counter()
    attack_actions = Counter()
    attack_with_blockers = Counter()
    obvious_bad_attacks = Counter()
    lethal_attack_opportunities = Counter()
    lethal_attack_misses = Counter()
    block_actions = Counter()
    profitable_blocks = Counter()
    losing_blocks = Counter()
    engine_protection_passes = Counter()
    resource_preservation_passes = Counter()
    reason_codes = Counter()
    pass_reason_codes = Counter()
    per_player_actions = defaultdict(Counter)
    pass_examples: list[dict] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total_games += 1
            row = json.loads(line)
            winner = row.get("winner")
            winners[str(winner)] += 1
            if winner is None:
                timeouts += 1

            for log_line in row.get("log", []):
                if not log_line.startswith("AI TRACE "):
                    continue
                payload = json.loads(log_line[len("AI TRACE ") :])
                pid = str(payload.get("pid"))
                act = (payload.get("action") or {})
                atype = str(act.get("type", "unknown"))
                action_types[atype] += 1
                per_player_actions[pid][atype] += 1
                reason_code = str(payload.get("reason_code") or "unknown")
                reason_codes[reason_code] += 1
                if atype == "pass_priority":
                    pass_reason_codes[reason_code] += 1

                if atype == "cast_spell":
                    name = str(act.get("card_name") or "unknown_card")
                    cast_by_card[name] += 1
                elif atype == "play_land":
                    play_land_count[pid] += 1
                elif atype == "attack":
                    attackers = [item for item in (act.get("attackers") or []) if isinstance(item, str)]
                    attack_actions[pid] += 1
                    attacking_cards = [item for item in (payload.get("battlefield") or []) if item.get("id") in attackers]
                    blockers = [
                        item
                        for item in (payload.get("opp_battlefield") or [])
                        if "Creature" in (item.get("types") or [])
                        and any(_can_snapshot_block(attacker, item) for attacker in attacking_cards)
                    ]
                    if blockers:
                        attack_with_blockers[pid] += 1
                        attacker_power = sum(max(0, int(_number(item.get("power")))) for item in (payload.get("battlefield") or []) if item.get("id") in attackers)
                        largest_blocker = max((max(0, int(_number(item.get("power")))) for item in blockers), default=0)
                        if attackers and attacker_power < largest_blocker and len(attackers) <= len(blockers):
                            obvious_bad_attacks[pid] += 1
                    if attackers and not blockers:
                        attack_power = sum(max(0, int(_number(item.get("power")))) for item in (payload.get("battlefield") or []) if item.get("id") in attackers)
                        if attack_power >= int(_number((payload.get("life") or {}).get("opp"))):
                            lethal_attack_opportunities[pid] += 1
                elif atype == "block":
                    block_map = act.get("blocks") or {}
                    block_actions[pid] += 1
                    for attacker_id, assigned in block_map.items():
                        assigned_ids = assigned if isinstance(assigned, list) else [assigned]
                        attacker = next((item for item in (payload.get("opp_battlefield") or []) if item.get("id") == attacker_id), None)
                        if not attacker:
                            continue
                        attacker_power = max(0, int(_number(attacker.get("power"))))
                        attacker_toughness = max(0, int(_number(attacker.get("toughness"))))
                        blockers_for_attack = [item for item in (payload.get("battlefield") or []) if item.get("id") in assigned_ids]
                        if not blockers_for_attack:
                            continue
                        blocker_power = sum(max(0, int(_number(item.get("power")))) for item in blockers_for_attack)
                        blocker_toughness = sum(max(0, int(_number(item.get("toughness")))) for item in blockers_for_attack)
                        if blocker_power >= attacker_toughness and attacker_power < blocker_toughness:
                            profitable_blocks[pid] += 1
                        elif attacker_power >= blocker_toughness and blocker_power < attacker_toughness:
                            losing_blocks[pid] += 1
                elif atype == "pass_priority" and bool(payload.get("legal_non_pass")):
                    mana_pool = payload.get("mana_pool") or {}
                    pool_total = sum(max(0, int(value or 0)) for value in mana_pool.values())
                    if pool_total > 0:
                        unused_mana_with_options[pid] += 1
                    pass_with_options[pid] += 1
                    if _is_main_phase_window(payload):
                        pass_with_meaningful_options[pid] += 1
                        main_phase_passes[pid] += 1
                        if len(pass_examples) < 5:
                            pass_examples.append(
                                {
                                    "game_index": total_games,
                                    "player": pid,
                                    "turn": payload.get("turn"),
                                    "step": payload.get("step"),
                                    "hand": payload.get("hand"),
                                    "opp_hand": payload.get("opp_hand"),
                                    "battlefield_size": len(payload.get("battlefield") or []),
                                    "opp_battlefield_size": len(payload.get("opp_battlefield") or []),
                                    "graveyard_count": payload.get("graveyard_count"),
                                    "opp_graveyard_count": payload.get("opp_graveyard_count"),
                                    "library_count": payload.get("library_count"),
                                    "opp_library_count": payload.get("opp_library_count"),
                                }
                            )
                        hand_names = {str(name).lower() for name in (payload.get("hand") or [])}
                        if any(any(tag in name for tag in ("engine", "walker", "planeswalker", "anthem", "lord")) for name in hand_names):
                            engine_protection_passes[pid] += 1
                        if any(tag in reason_code for tag in ("hold", "interaction", "response", "strategic")):
                            resource_preservation_passes[pid] += 1

                if (
                    atype != "attack"
                    and _step_key(payload.get("step")) == "declare_attackers"
                    and "attack" in (payload.get("legal_action_types") or [])
                ):
                    battlefield = payload.get("battlefield") or []
                    blockers = [item for item in (payload.get("opp_battlefield") or []) if "Creature" in (item.get("types") or [])]
                    if not blockers:
                        possible_power = sum(max(0, int(_number(item.get("power")))) for item in battlefield if "Creature" in (item.get("types") or []) and not item.get("tapped"))
                        if possible_power >= int(_number((payload.get("life") or {}).get("opp"))):
                            lethal_attack_misses[pid] += 1

                if bool(payload.get("legal_has_land")) and atype != "play_land" and _is_main_phase_window(payload):
                    missed_land_windows[pid] += 1
                    if atype != "pass_priority":
                        main_phase_land_not_first[pid] += 1

    return {
        "games": total_games,
        "timeouts": timeouts,
        "winners": dict(winners),
        "actions": dict(action_types),
        "reason_codes": dict(reason_codes),
        "pass_reason_codes": dict(pass_reason_codes),
        "per_player_actions": {k: dict(v) for k, v in per_player_actions.items()},
        "pass_with_options": dict(pass_with_options),
        "pass_with_meaningful_options": dict(pass_with_meaningful_options),
        "main_phase_passes": dict(main_phase_passes),
        "missed_land_windows": dict(missed_land_windows),
        "unused_mana_with_options": dict(unused_mana_with_options),
        "main_phase_land_not_first": dict(main_phase_land_not_first),
        "combat_quality": {
            "attack_actions": dict(attack_actions),
            "attacks_with_blockers": dict(attack_with_blockers),
            "obvious_bad_attacks": dict(obvious_bad_attacks),
            "lethal_attack_opportunities": dict(lethal_attack_opportunities),
            "lethal_attack_misses": dict(lethal_attack_misses),
            "block_actions": dict(block_actions),
            "profitable_blocks": dict(profitable_blocks),
            "losing_blocks": dict(losing_blocks),
        },
        "resource_quality": {
            "engine_protection_passes": dict(engine_protection_passes),
            "resource_preservation_passes": dict(resource_preservation_passes),
        },
        "top_cast_cards": [{"card": c, "count": n} for c, n in cast_by_card.most_common(50)],
        "land_plays": dict(play_land_count),
        "pass_examples": pass_examples,
}


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _can_snapshot_block(attacker: dict, blocker: dict) -> bool:
    """Apply the common evasion checks needed for quality diagnostics."""
    attacker_keywords = {str(value).lower() for value in (attacker.get("keywords") or [])}
    blocker_keywords = {str(value).lower() for value in (blocker.get("keywords") or [])}
    if "flying" in attacker_keywords and not ({"flying", "reach"} & blocker_keywords):
        return False
    if "shadow" in attacker_keywords and "shadow" not in blocker_keywords:
        return False
    if "horsemanship" in attacker_keywords and "horsemanship" not in blocker_keywords:
        return False
    return True


def main() -> int:
    args = parse_args()
    path = Path(args.games_jsonl)
    summary = summarize_card_play_logic(path)
    out_path = Path(args.out) if args.out else path.with_name("card_play_analytics.json")
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out_path), "games": summary["games"], "timeouts": summary["timeouts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
