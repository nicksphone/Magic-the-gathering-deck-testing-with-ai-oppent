from __future__ import annotations

from game_state.state import MatchState, TURN_STEPS


def serialize_match(state: MatchState) -> dict:
    step_order = [x.value for x in TURN_STEPS]

    def _sort_steps(steps: set) -> list[str]:
        vals = [s.value for s in steps]
        return sorted(vals, key=lambda x: step_order.index(x) if x in step_order else 999)

    return {
        "id": state.id,
        "turn": state.turn,
        "active_player": state.active_player,
        "priority_player": state.priority_player,
        "step": state.step.value,
        "winner": state.winner,
        "score": state.score,
        "pregame_pending": state.pregame_pending,
        "mulligan_count": state.mulligan_count,
        "kept_hands": sorted(list(state.kept_hands)),
        "priority_stops": {
            str(pid): _sort_steps(steps)
            for pid, steps in state.priority_stops.items()
        },
        "players": {
            pid: {
                "id": p.id,
                "name": p.name,
                "life": p.life,
                "library_count": len(p.library),
                "hand_count": len(p.hand),
                "battlefield": [
                    {
                        "id": cid,
                        "name": state.cards[cid].name,
                        "tapped": state.cards[cid].tapped,
                        "summoning_sick": state.cards[cid].summoning_sick,
                        "power": state.cards[cid].power,
                        "toughness": state.cards[cid].toughness,
                        "loyalty": state.cards[cid].loyalty,
                        "mana_cost": state.cards[cid].mana_cost,
                        "types": state.cards[cid].types,
                    }
                    for cid in p.battlefield
                ],
                "hand": [
                    {
                        "id": cid,
                        "name": state.cards[cid].name,
                        "mana_cost": state.cards[cid].mana_cost,
                        "types": state.cards[cid].types,
                    }
                    for cid in p.hand
                ],
                "graveyard_count": len(p.graveyard),
                "exile_count": len(p.exile),
                "mana_pool": p.mana_pool,
            }
            for pid, p in state.players.items()
        },
        "stack": [
            {
                "id": item.id,
                "label": item.label,
                "controller": item.controller,
                "effect_key": item.effect_key,
                "targets": item.targets,
            }
            for item in state.stack
        ],
        "attackers": state.attackers,
        "attack_targets": state.attack_targets,
        "blocks": state.blocks,
        "log": state.log[-120:],
    }
