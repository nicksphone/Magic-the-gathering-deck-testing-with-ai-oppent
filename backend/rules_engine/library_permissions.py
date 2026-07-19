from __future__ import annotations

from game_state.state import MatchState


def chosen_creature_type(card) -> str:
    return str(getattr(card, "chosen_creature_type", "") or "").strip().lower()


def creature_types(card) -> set[str]:
    type_line = str(getattr(card, "type_line", "") or "")
    if "—" not in type_line:
        return set()
    return {part.lower() for part in type_line.split("—", 1)[1].split()}


def top_library_creature_for_type(state: MatchState, player_id: int):
    player = state.players[player_id]
    if not player.library:
        return None
    top_id = player.library[-1]
    top = state.cards.get(top_id)
    if top is None or "Creature" not in (getattr(top, "types", []) or []):
        return None
    for source_id in player.battlefield:
        source = state.cards.get(source_id)
        if source is None or "Creature" not in (getattr(source, "types", []) or []):
            continue
        oracle = (getattr(source, "oracle_text", "") or "").lower()
        if "cast creature spells of the chosen type from the top of your library" not in oracle:
            continue
        chosen = chosen_creature_type(source)
        if chosen and (chosen in creature_types(top) or "changeling" in {k.lower() for k in (getattr(top, "keywords", []) or [])}):
            return top
    return None


def choose_type_for_realmwalker(state: MatchState, player_id: int) -> str:
    counts: dict[str, int] = {}
    player = state.players[player_id]
    for cid in [*player.library, *player.hand, *player.battlefield]:
        card = state.cards.get(cid)
        for kind in creature_types(card):
            counts[kind] = counts.get(kind, 0) + 1
    return max(counts, key=lambda kind: (counts[kind], kind)) if counts else "creature"
