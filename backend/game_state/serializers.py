from __future__ import annotations

from game_state.state import MatchState


def serialize_match(state: MatchState) -> dict:
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
                        "types": state.cards[cid].types,
                    }
                    for cid in p.battlefield
                ],
                "hand": [
                    {
                        "id": cid,
                        "name": state.cards[cid].name,
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
        "blocks": state.blocks,
        "log": state.log[-120:],
    }
