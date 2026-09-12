from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from analytics.decision_quality import (
    DECISION_QUALITY_METRICS,
    UNAVAILABLE_REASON,
    DecisionQualityAccumulator,
)


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
    return _step_key(payload.get("step")) in {"precombat_main", "postcombat_main"} and payload.get("legal_non_pass") is True


def _number(value: object) -> float | None:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _nonnegative_int(value: object) -> int | None:
    number = _number(value)
    return None if number is None else max(0, int(number))


def _dict_items(value: object) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _can_snapshot_block(attacker: dict, blocker: dict) -> bool:
    """Apply the common evasion checks needed for legacy quality diagnostics."""
    if bool(blocker.get("tapped", False)):
        return False
    attacker_keywords = {str(value).lower() for value in (attacker.get("keywords") or [])}
    blocker_keywords = {str(value).lower() for value in (blocker.get("keywords") or [])}
    if "flying" in attacker_keywords and not ({"flying", "reach"} & blocker_keywords):
        return False
    if "shadow" in attacker_keywords and "shadow" not in blocker_keywords:
        return False
    if "horsemanship" in attacker_keywords and "horsemanship" not in blocker_keywords:
        return False
    return True


def summarize_card_play_logic(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"games.jsonl not found: {path}")
    with path.open("r", encoding="utf-8") as lines:
        return _summarize_card_play_lines(lines)


def _summarize_card_play_lines(lines: Iterable[str]) -> dict:
    total_games = 0
    timeouts = 0
    winners = Counter()
    action_types = Counter()
    cast_by_card = Counter()
    play_land_count = Counter()
    pass_with_options = Counter()
    pass_with_meaningful_options = Counter()
    main_phase_passes = Counter()
    main_phase_land_not_first = Counter()
    attack_actions = Counter()
    attack_with_blockers = Counter()
    obvious_bad_attacks = Counter()
    lethal_attack_opportunities = Counter()
    legacy_lethal_attack_misses = Counter()
    block_actions = Counter()
    profitable_blocks = Counter()
    engine_protection_passes = Counter()
    resource_preservation_passes = Counter()
    reason_codes = Counter()
    pass_reason_codes = Counter()
    per_player_actions = defaultdict(Counter)
    pass_examples: list[dict] = []
    decision_accumulator = DecisionQualityAccumulator()

    for line in lines:
        if not isinstance(line, str) or not line.strip():
            if not isinstance(line, str):
                decision_accumulator.invalidate_all()
            continue
        try:
            row = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            decision_accumulator.invalidate_all()
            continue
        if not isinstance(row, dict):
            decision_accumulator.invalidate_all()
            continue

        total_games += 1
        winner = row.get("winner")
        winners[str(winner)] += 1
        if winner is None:
            timeouts += 1
        payloads = decision_accumulator.consume_row(row)

        for payload in payloads:
            pid = str(payload.get("pid"))
            action = payload.get("action")
            if not isinstance(action, dict):
                continue
            raw_type = action.get("type")
            atype = raw_type if isinstance(raw_type, str) and raw_type else "unknown"
            action_types[atype] += 1
            per_player_actions[pid][atype] += 1
            reason_code = str(payload.get("reason_code") or "unknown")
            reason_codes[reason_code] += 1
            if atype == "pass_priority":
                pass_reason_codes[reason_code] += 1

            battlefield = _dict_items(payload.get("battlefield"))
            opp_battlefield = _dict_items(payload.get("opp_battlefield"))
            if atype == "cast_spell":
                cast_by_card[str(action.get("card_name") or "unknown_card")] += 1
            elif atype == "play_land":
                play_land_count[pid] += 1
            elif atype == "attack":
                attackers = [item for item in (action.get("attackers") or []) if isinstance(item, str)] if isinstance(action.get("attackers") or [], list) else []
                attack_actions[pid] += 1
                attacking_cards = [item for item in battlefield if item.get("id") in attackers]
                blockers = [
                    item for item in opp_battlefield
                    if "Creature" in (item.get("types") or [])
                    and any(_can_snapshot_block(attacker, item) for attacker in attacking_cards)
                ]
                if blockers:
                    attack_with_blockers[pid] += 1
                    attacker_powers = [
                        _nonnegative_int(item.get("power")) for item in attacking_cards
                    ]
                    blocker_powers = [_nonnegative_int(item.get("power")) for item in blockers]
                    if (
                        any(value is None for value in attacker_powers)
                        or any(value is None for value in blocker_powers)
                    ):
                        decision_accumulator.invalidate_metric(pid, "lethal_misses")
                    else:
                        attacker_power = sum(
                            value for value in attacker_powers if value is not None
                        )
                        largest_blocker = max(
                            (value for value in blocker_powers if value is not None),
                            default=0,
                        )
                        if (
                            attackers
                            and attacker_power < largest_blocker
                            and len(attackers) <= len(blockers)
                        ):
                            obvious_bad_attacks[pid] += 1
                elif attackers:
                    # Kept as a legacy descriptive key only; authoritative misses come from shared evidence.
                    attack_powers = [_nonnegative_int(item.get("power")) for item in attacking_cards]
                    life = payload.get("life") if isinstance(payload.get("life"), dict) else {}
                    opponent_life = _number(life.get("opp"))
                    if any(value is None for value in attack_powers) or opponent_life is None:
                        decision_accumulator.invalidate_metric(pid, "lethal_misses")
                    elif sum(attack_powers) >= int(opponent_life):
                        lethal_attack_opportunities[pid] += 1
            elif atype == "block":
                block_actions[pid] += 1
                block_map = action.get("blocks")
                if isinstance(block_map, dict):
                    for attacker_id, assigned in block_map.items():
                        assigned_ids = assigned if isinstance(assigned, list) else [assigned]
                        attacker = next((item for item in opp_battlefield if item.get("id") == attacker_id), None)
                        if not attacker:
                            continue
                        blockers_for_attack = [item for item in battlefield if item.get("id") in assigned_ids]
                        if not blockers_for_attack:
                            continue
                        attacker_power = _nonnegative_int(attacker.get("power"))
                        attacker_toughness = _nonnegative_int(attacker.get("toughness"))
                        blocker_powers = [
                            _nonnegative_int(item.get("power")) for item in blockers_for_attack
                        ]
                        blocker_toughnesses = [
                            _nonnegative_int(item.get("toughness")) for item in blockers_for_attack
                        ]
                        if (
                            attacker_power is None
                            or attacker_toughness is None
                            or any(value is None for value in blocker_powers)
                            or any(value is None for value in blocker_toughnesses)
                        ):
                            decision_accumulator.invalidate_metric(pid, "bad_blocks")
                            continue
                        blocker_power = sum(value for value in blocker_powers if value is not None)
                        blocker_toughness = sum(
                            value for value in blocker_toughnesses if value is not None
                        )
                        if blocker_power >= attacker_toughness and attacker_power < blocker_toughness:
                            profitable_blocks[pid] += 1
            elif atype == "pass_priority" and payload.get("legal_non_pass") is True:
                pass_with_options[pid] += 1
                if _is_main_phase_window(payload):
                    pass_with_meaningful_options[pid] += 1
                    main_phase_passes[pid] += 1
                    if len(pass_examples) < 5:
                        pass_examples.append({
                            "game_index": total_games,
                            "player": pid,
                            "turn": payload.get("turn"),
                            "step": payload.get("step"),
                            "hand": payload.get("hand"),
                            "opp_hand": payload.get("opp_hand"),
                            "battlefield_size": len(battlefield),
                            "opp_battlefield_size": len(opp_battlefield),
                            "graveyard_count": payload.get("graveyard_count"),
                            "opp_graveyard_count": payload.get("opp_graveyard_count"),
                            "library_count": payload.get("library_count"),
                            "opp_library_count": payload.get("opp_library_count"),
                        })
                    hand = payload.get("hand") if isinstance(payload.get("hand"), list) else []
                    hand_names = {str(name).lower() for name in hand}
                    if any(any(tag in name for tag in ("engine", "walker", "planeswalker", "anthem", "lord")) for name in hand_names):
                        engine_protection_passes[pid] += 1
                    if any(tag in reason_code for tag in ("hold", "interaction", "response", "strategic")):
                        resource_preservation_passes[pid] += 1

            if (
                not isinstance(payload.get("lethal_attack_available"), bool)
                and atype != "attack"
                and _step_key(payload.get("step")) == "declare_attackers"
                and "attack" in (payload.get("legal_action_types") or [])
                and not [item for item in opp_battlefield if "Creature" in (item.get("types") or [])]
            ):
                life = payload.get("life") if isinstance(payload.get("life"), dict) else {}
                possible_powers = [
                    _nonnegative_int(item.get("power"))
                    for item in battlefield
                    if "Creature" in (item.get("types") or []) and not item.get("tapped")
                ]
                opponent_life = _number(life.get("opp"))
                if (
                    any(value is None for value in possible_powers)
                    or opponent_life is None
                ):
                    decision_accumulator.invalidate_metric(pid, "lethal_misses")
                elif sum(value for value in possible_powers if value is not None) >= int(
                    opponent_life
                ):
                    legacy_lethal_attack_misses[pid] += 1

            if payload.get("legal_has_land") is True and atype not in {"play_land", "pass_priority"} and _is_main_phase_window(payload):
                main_phase_land_not_first[pid] += 1

    decision_summary = decision_accumulator.finish()
    overall_metrics = {
        metric: (
            sum(decision_summary["counts"][pid][metric] for pid in ("1", "2"))
            if all(decision_summary["availability"][pid][metric] for pid in ("1", "2"))
            else None
        )
        for metric in DECISION_QUALITY_METRICS
    }
    explicit_decision_quality = {
        "metrics": overall_metrics,
        "per_player": decision_summary["counts"],
        "availability": decision_summary["availability"],
        "unavailable_metrics": {
            metric: UNAVAILABLE_REASON for metric, value in overall_metrics.items() if value is None
        },
    }

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
        "missed_land_windows": {
            pid: values["missed_land_drops"] for pid, values in decision_summary["counts"].items()
            if decision_summary["availability"][pid]["missed_land_drops"] and values["missed_land_drops"]
        },
        "unused_mana_with_options": {
            pid: values["unused_mana_passes"] for pid, values in decision_summary["counts"].items()
            if decision_summary["availability"][pid]["unused_mana_passes"] and values["unused_mana_passes"]
        },
        "main_phase_land_not_first": dict(main_phase_land_not_first),
        "combat_quality": {
            "attack_actions": dict(attack_actions),
            "attacks_with_blockers": dict(attack_with_blockers),
            "obvious_bad_attacks": dict(obvious_bad_attacks),
            "lethal_attack_opportunities": dict(lethal_attack_opportunities),
            "lethal_attack_misses": {
                pid: values["lethal_misses"] + legacy_lethal_attack_misses[pid]
                for pid, values in decision_summary["counts"].items()
                if values["lethal_misses"] + legacy_lethal_attack_misses[pid]
            },
            "block_actions": dict(block_actions),
            "profitable_blocks": dict(profitable_blocks),
            "losing_blocks": {
                pid: values["bad_blocks"] for pid, values in decision_summary["counts"].items()
                if decision_summary["availability"][pid]["bad_blocks"] and values["bad_blocks"]
            },
        },
        "resource_quality": {
            "engine_protection_passes": dict(engine_protection_passes),
            "resource_preservation_passes": dict(resource_preservation_passes),
        },
        "top_cast_cards": [{"card": card, "count": count} for card, count in cast_by_card.most_common(50)],
        "land_plays": dict(play_land_count),
        "pass_examples": pass_examples,
        "decision_quality": explicit_decision_quality,
    }


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
