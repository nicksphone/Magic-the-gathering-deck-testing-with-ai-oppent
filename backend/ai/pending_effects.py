"""Project announced stack effects without guessing choices or new responses."""
from __future__ import annotations

from copy import deepcopy
import re

from game_state.state import MatchState, Zone
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.oracle_text import without_reminder_text


def pending_removal_destinations(state: MatchState, player_id: int) -> dict | None:
    """Project destinations of opposing permanents with own effects pending."""
    candidates = set(state.players[3 - player_id].battlefield)
    if not candidates or not any(item.controller == player_id for item in state.stack):
        return {}
    # Resolution does not read historical logs; avoid copying growing traces.
    projected = deepcopy(state, {id(state.log): []})
    projected.mechanic_choice_players = {1, 2}
    projected.replacement_choice_players = {1, 2}
    projected.trigger_order_choice_players = {1, 2}
    rules = RulesEngine()
    # ponytail: bounded projection; unknown choices/loops keep backup options.
    for _ in range(128):
        if projected.pending_mechanic_choice or projected.pending_replacement_choice or projected.pending_trigger_order or projected.winner is not None:
            return None
        if not projected.stack:
            remaining = set().union(*(set(player.battlefield) for player in projected.players.values()))
            return {cid: projected.cards[cid].zone for cid in candidates - remaining if cid in projected.cards}
        rules.take_action(projected, projected.priority_player, {"type": "pass_priority"}, reject_invalid=True)
    return None


def covered_removal_targets(state: MatchState, card, player_id: int, targets: dict) -> set[str] | None:
    """Conserve simple removal, but retain secondary value and zone upgrades."""
    if not state.stack or not set(card.types).intersection({"Instant", "Sorcery"}):
        return set()
    text = "\n".join(targets.get("mode_texts") or []) or targets.get("mode_text") or card.oracle_text
    if re.search(r"\b(draw|gain|gains|lose|loses|create|scry|surveil|discard|mill|search|deals?|cast|play|put|add|untap|sacrifice)\b", without_reminder_text(text), re.I):
        return set()
    key, _ = infer_effect_from_oracle(state, card, player_id, targets, report_unsupported=False)
    if key not in {"destroy_permanent", "exile", "return_permanent_to_hand"}:
        return set()
    destinations = pending_removal_destinations(state, player_id)
    if destinations is None:
        return None
    return {
        cid for cid, destination in destinations.items()
        if (destination in {Zone.GRAVEYARD, Zone.EXILE, Zone.CEASED}
            and not (key == "exile" and destination == Zone.GRAVEYARD))
        or (key == "return_permanent_to_hand" and destination == Zone.HAND)
    }
