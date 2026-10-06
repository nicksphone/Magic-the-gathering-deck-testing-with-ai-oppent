from __future__ import annotations
import re

from rules_engine.type_effects import effective_types

from game_state.state import MatchState


def chosen_creature_type(card) -> str:
    return str(getattr(card, "chosen_creature_type", "") or "").strip().lower()


def creature_types(card, state=None) -> set[str]:
    """Type-line subtypes plus current printed changeling, not layer-six grants."""
    from rules_engine.card_types import CREATURE_SUBTYPES
    from rules_engine.oracle_text import without_reminder_text
    from rules_engine.type_effects import active_type_effects

    type_line = str(getattr(card, "type_line", "") or "")
    if state is not None:
        from rules_engine.land_types import effective_type_line
        type_line = effective_type_line(state, card)
    subtypes = {part.lower() for part in type_line.split("—", 1)[1].split()} if "—" in type_line else set()
    subtypes.update(kind for kind in CREATURE_SUBTYPES if ' ' in kind
                    and re.search(r'\b' + re.escape(kind) + r'\b', type_line.lower()))
    oracle = without_reminder_text(getattr(card, "oracle_text", "") or "")
    if (state is None or not any('creature_subtypes' in effect for effect in
                                active_type_effects(card))) and (
            {"Creature", "Kindred", "Tribal"}.intersection(getattr(card, "types", []) or [])
            and any(re.fullmatch(r"changeling\.?", line.strip(), re.I) for line in oracle.splitlines())):
        # CR 702.73a/613: the copied/printed CDA applies in layer four,
        # before losing abilities in layer six, and functions in every zone.
        subtypes.update(CREATURE_SUBTYPES)
    return subtypes


def top_library_creature_for_type(state: MatchState, player_id: int):
    from rules_engine.continuous import printed_abilities_suppressed
    player = state.players[player_id]
    if not player.library:
        return None
    top_id = player.library[-1]
    top = state.cards.get(top_id)
    if top is None or "Creature" not in (effective_types(state, top) or []):
        return None
    for source_id in player.battlefield:
        source = state.cards.get(source_id)
        if source is None or "Creature" not in (effective_types(state, source) or []):
            continue
        if printed_abilities_suppressed(state, source_id):
            continue
        oracle = (getattr(source, "oracle_text", "") or "").lower()
        if "cast creature spells of the chosen type from the top of your library" not in oracle:
            continue
        chosen = chosen_creature_type(source)
        if chosen and (chosen in creature_types(top, state) or "changeling" in {k.lower() for k in (getattr(top, "keywords", []) or [])}):
            return top
    return None


def choose_type_for_realmwalker(state: MatchState, player_id: int) -> str:
    counts: dict[str, int] = {}
    player = state.players[player_id]
    for cid in [*player.library, *player.hand, *player.battlefield]:
        card = state.cards.get(cid)
        for kind in creature_types(card, state):
            counts[kind] = counts.get(kind, 0) + 1
    return max(counts, key=lambda kind: (counts[kind], kind)) if counts else "creature"
