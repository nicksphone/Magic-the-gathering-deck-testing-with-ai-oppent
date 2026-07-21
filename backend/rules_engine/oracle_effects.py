from __future__ import annotations

import re
from typing import Any

from game_state.state import CardInstance, MatchState, Zone
from rules_engine.mana import choose_mana_color_for_player, parse_mana_cost


DAMAGE_RE = re.compile(r"deals?\s+(\d+)\s+damage")
X_DAMAGE_RE = re.compile(r"deals?\s+x\s+damage")
DRAW_RE = re.compile(r"draw\s+(a|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?", re.IGNORECASE)
X_DRAW_RE = re.compile(r"draw\s+x\s+card")
GAIN_RE = re.compile(r"gain\s+(\d+)\s+life")
LOSE_RE = re.compile(r"loses?\s+(\d+)\s+life")
LOSE_COUNT_RE = re.compile(r"loses?\s+life\s+equal\s+to\s+the\s+number\s+of\s+([a-z-]+)\s+you\s+control", re.IGNORECASE)
GAIN_CONTROL_RE = re.compile(r"gain control of\s+target\s+(creature|artifact|enchantment|permanent|planeswalker|land)", re.IGNORECASE)
PREVENT_RE = re.compile(r"prevent(?:s)? the next (\d+) damage")
SAC_RE = re.compile(r"sacrifice\s+(a|\d+)\s+creature")
COUNTER_RE = re.compile(r"put\s+(a|an|one|two|three|four|five|\d+)\s+\+1/\+1\s+counters?\s+on\s+(?:up to one )?target\s+(creature|land|permanent)")
MANA_SYMBOL_RE = re.compile(r"\{([WUBRGC])\}")
TOKEN_PT_RE = re.compile(r"create[^.]*?(\d+)\/(\d+)")
TOKEN_COUNT_RE = re.compile(r"create\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)", re.IGNORECASE)
TOKEN_NAME_RE = re.compile(
    r"create\s+(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+\d+/\d+\s+([a-z ]+?)\s+creature\s+tokens?",
    re.IGNORECASE,
)
CHOOSE_ONE_RE = re.compile(r"choose one\s*[—-]\s*(.+)", re.IGNORECASE | re.DOTALL)
CHOOSE_TWO_RE = re.compile(r"choose two(?:\s*[—-]\s*(.+))?", re.IGNORECASE | re.DOTALL)
DIVIDE_RE = re.compile(r"divide[^.]*damage[^.]*among[^.]*targets", re.IGNORECASE)
UP_TO_RE = re.compile(r"up to\s+(\d+)\s+target", re.IGNORECASE)
SEARCH_UP_TO_RE = re.compile(r"search your library for up to\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+[^.]*?cards?", re.IGNORECASE)
SEARCH_MV_MAX_RE = re.compile(r"mana value\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+or less", re.IGNORECASE)
TARGET_MV_MAX_RE = re.compile(r"mana value\s+(?:less than or equal to\s+)?(\d+)\s+or less", re.IGNORECASE)
TARGET_MV_GRAVEYARD_RE = re.compile(
    r"mana value\s+(?:less than or equal to\s+)?the number of cards in (?:its controller's|your) graveyard",
    re.IGNORECASE,
)
TARGET_MV_CONTROLLED_TYPE_RE = re.compile(
    r"mana value\s+(?:less than or equal to\s+)?the number of\s+([a-z]+)s?\s+you control",
    re.IGNORECASE,
)
COPY_STACK_RE = re.compile(r"copy target (spell|activated ability|triggered ability)", re.IGNORECASE)
COPY_SPELL_RE = COPY_STACK_RE
SPLIT_NAME_RE = re.compile(r"^(.+?)\s*//\s*(.+)$")
LOYALTY_ABILITY_RE = re.compile(r"([+-]?(?:\d+|X)):\s*([^\n]+)")
SAGA_CHAPTER_RE = re.compile(r"^\s*(I{1,3}|IV|V|VI|VII|VIII|IX|X)\s*[—-]\s*(.+?)\s*$", re.IGNORECASE)
ACTIVATED_ABILITY_RE = re.compile(
    r"(?m)((?:\{[^{}]+\})(?:\s*,\s*(?:\{[^{}]+\}|[^:\n]+))*)\s*:\s*([^\n]+)"
)
CREW_RE = re.compile(r"\bcrew\s+(\d+)\b", re.IGNORECASE)
LOOK_TOP_RE = re.compile(r"look at the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?", re.IGNORECASE)
LOOK_TOP_CHOICE_RE = re.compile(
    r"look at the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?.*?"
    r"(?:put\s+)?one(?: of them)? into your hand.*?"
    r"(?:put\s+)?one(?: of them)? on the bottom.*?"
    r"(?:put\s+)?(?:exile\s+)?one(?: of them)?(?: into exile)?",
    re.IGNORECASE,
)
LOOK_CREATURE_TO_HAND_RE = re.compile(
    r"look at the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?.*?creature card with power\s+(\d+)\s+or less.*?put it into your hand",
    re.IGNORECASE,
)
PUT_CREATURES_FROM_TOP_RE = re.compile(
    r"put up to\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+creature cards?\s+with mana value\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+or less[^.]*onto the battlefield",
    re.IGNORECASE,
)
PUT_PERMANENTS_FROM_TOP_RE = re.compile(
    r"put up to\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+permanent cards?\s+with mana value\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+or less[^.]*onto the battlefield",
    re.IGNORECASE,
)
LOOT_RE = re.compile(r"draw\s+(a|\d+)\s+card[s]?\s*,?\s*then\s*discard\s+(a|\d+)\s+card", re.IGNORECASE)
SAC_AT_EOT_RE = re.compile(r"sacrifice (?:it|that token) at the beginning of the next end step", re.IGNORECASE)
SHARK_TOKEN_RE = re.compile(
    r"create (?:a|an) (?:blue )?x/x(?: blue)? shark creature token with flying",
    re.IGNORECASE,
)
EXILE_TOP_PLAYABLE_RE = re.compile(r"exile the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?.*?may play those cards", re.IGNORECASE)
REVEAL_DEFENDING_TOP_LAND_RE = re.compile(r"defending player reveals the top card of their library.*?if it's a land card", re.IGNORECASE)
LAND_FROM_HAND_RE = re.compile(
    r"put (?:a|one) land card from your hand onto the battlefield tapped",
    re.IGNORECASE,
)
CAST_INSTANT_FROM_GRAVEYARD_RE = re.compile(
    r"cast target (instant|sorcery) card from your graveyard without paying its mana cost",
    re.IGNORECASE,
)
COUNTER_UNLESS_PAY_RE = re.compile(
    r"counter target (?P<kind>noncreature )?spell unless its controller pays\s+(?P<cost>\{[^}]+\}(?:\{[^}]+\})*)",
    re.IGNORECASE,
)


def infer_effect_from_oracle(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    action_targets = action_targets or {}
    # A real planeswalker card's loyalty lines are activated later, not cast as
    # one combined spell effect. Loyalty proxies intentionally do not carry
    # the Planeswalker type and continue through the normal parser below.
    if "Planeswalker" in (getattr(card, "types", []) or []):
        return "noop", {}
    card, oracle, name = _resolve_effective_card_surface(card, action_targets)
    mode_text = action_targets.get("mode_text")
    mode_texts = action_targets.get("mode_texts") or []
    x_value = int(action_targets.get("x_value", 0) or 0)
    if "exile this saga" in oracle and "return it to the battlefield transformed" in oracle:
        target = action_targets.get("target_card_id") or action_targets.get("source_card_id")
        if target:
            return "transform_card", {"target_card_id": target, "face_index": 1}
    if mode_text:
        oracle = mode_text.lower()
    elif mode_texts:
        oracle = " ; ".join(str(x).lower() for x in mode_texts)
    split_match = SPLIT_NAME_RE.match(name)
    if split_match and not mode_text and not mode_texts:
        # Split cards are represented as a single cached record with aliases in
        # the repo. Keep the original oracle intact, but preserve the split-card
        # signal for downstream consumers that need to render or validate them specially.
        pass

    unless_match = COUNTER_UNLESS_PAY_RE.search(oracle)
    if unless_match:
        target_stack_id = action_targets.get("target_stack_id") or (state.stack[-1].id if state.stack else None)
        return "counter_spell_unless_pay", {
            "target_stack_id": target_stack_id,
            "unless_cost": unless_match.group("cost").upper(),
            "target_kind": "noncreature" if unless_match.group("kind") else "any",
            "pay_unless_counter": action_targets.get("pay_unless_counter"),
        }
    if "counter target spell" in oracle:
        target_stack_id = action_targets.get("target_stack_id") or (state.stack[-1].id if state.stack else None)
        return "counter_spell", {"target_stack_id": target_stack_id}
    if "counter target activated ability" in oracle or "counter target triggered ability" in oracle:
        target_stack_id = action_targets.get("target_stack_id") or (state.stack[-1].id if state.stack else None)
        return "counter_ability", {"target_stack_id": target_stack_id}
    copy_match = COPY_STACK_RE.search(oracle)
    if copy_match and state.stack:
        target_stack_id = action_targets.get("target_stack_id") or state.stack[-1].id
        kind = str(copy_match.group(1) or "spell").strip().lower()
        effect_key = "copy_spell" if kind == "spell" else "copy_ability"
        return effect_key, {"target_stack_id": target_stack_id, "copy_kind": kind}
    topdeck_creatures = _infer_topdeck_creature_put_effect(oracle, action_targets)
    if topdeck_creatures is not None:
        return topdeck_creatures
    topdeck_permanents = _infer_topdeck_permanent_put_effect(oracle, action_targets)
    if topdeck_permanents is not None:
        return topdeck_permanents
    creature_to_hand = LOOK_CREATURE_TO_HAND_RE.search(oracle)
    if creature_to_hand:
        return "topdeck_reveal_creature_to_hand", {
            "top_n": _parse_count_token(creature_to_hand.group(1)),
            "power_max": int(creature_to_hand.group(2)),
        }
    exile_playable = EXILE_TOP_PLAYABLE_RE.search(oracle)
    if exile_playable:
        return "exile_top_cards_playable", {"amount": _parse_count_token(exile_playable.group(1))}
    if REVEAL_DEFENDING_TOP_LAND_RE.search(oracle):
        return "reveal_defending_top_land", {
            "target_player": action_targets.get("target_player", 1 if controller == 2 else 2),
        }
    top_choice = LOOK_TOP_CHOICE_RE.search(oracle)
    if top_choice:
        payload = {"top_n": _parse_count_token(top_choice.group(1)), "play_exiled_until": state.turn}
        for key in ("top_choice_hand_id", "top_choice_exile_id", "top_choice_bottom_ids"):
            if key in action_targets:
                payload[key] = action_targets[key]
        return "look_top_choose", payload
    search_effect = _infer_search_effect(oracle, action_targets)
    if search_effect is not None:
        return search_effect

    clauses = _split_clauses(oracle)
    effects: list[tuple[str, dict[str, Any]]] = []
    for clause in clauses:
        inferred = _infer_clause_effect(state, card, controller, clause, action_targets, x_value)
        if inferred is not None:
            if (
                inferred[0] == "add_counters"
                and inferred[1].get("target_card_id")
                and "becomes a 0/0" in oracle
                and "target land" in oracle
            ):
                inferred[1]["animate_land"] = True
            effects.append(inferred)
    effects.extend(_infer_turn_restriction_effects(oracle, controller))
    if len(effects) >= 2:
        return "effect_sequence", {"effects": [{"effect_key": k, "payload": v} for k, v in effects]}
    if len(effects) == 1:
        return effects[0]

    if any(k in name for k in ["bolt", "spike", "shock", "skewer"]):
        opp = action_targets.get("target_player", 1 if controller == 2 else 2)
        return "deal_damage", {"target_player": opp, "amount": 3}
    if any(k in name for k in ["consider", "deluge"]):
        return "draw_cards", {"amount": 1}
    if "counterspell" in name and state.stack:
        return "counter_spell", {"target_stack_id": state.stack[-1].id}

    # Static-only/keyword text often has no explicit resolver-side action.
    # Treat those as no-op without warning to keep logs focused on real misses.
    if _looks_static_or_keyword_only(card.oracle_text or "") or _is_event_layer_resolved(card.oracle_text or ""):
        return "noop", {}
    # Fallback: log uninferrable oracle text instead of silent no-op.
    state.log.append(f"Oracle effect not inferred for {card.name} (controller={controller}). Text: {card.oracle_text[:120]}")
    return "noop", {}


def _infer_turn_restriction_effects(oracle: str, controller: int) -> list[tuple[str, dict[str, Any]]]:
    """Parse restrictions that apply after a resolving spell for this turn."""
    effects: list[tuple[str, dict[str, Any]]] = []
    opponent = 1 if controller == 2 else 2
    if re.search(r"players? (?:can't|cannot) gain life this turn", oracle):
        effects.append(("set_turn_restriction", {"kind": "cant_gain_life", "all_players": True}))
    elif re.search(r"you (?:can't|cannot) gain life this turn", oracle):
        effects.append(("set_turn_restriction", {"kind": "cant_gain_life", "players": [controller]}))
    elif re.search(r"your opponents? (?:can't|cannot) gain life this turn", oracle):
        effects.append(("set_turn_restriction", {"kind": "cant_gain_life", "players": [opponent]}))
    if re.search(r"(?:damage|combat damage) (?:can't|cannot) be prevented this turn", oracle):
        effects.append(("set_turn_restriction", {"kind": "damage_cant_be_prevented"}))
    return effects


def _resolve_effective_card_surface(card: CardInstance, action_targets: dict[str, Any]) -> tuple[CardInstance, str, str]:
    faces = list(getattr(card, "card_faces", []) or [])
    if not faces:
        return card, (card.oracle_text or "").lower(), card.name.lower()
    raw_index = action_targets.get("selected_face_index", getattr(card, "selected_face_index", None))
    if raw_index is None:
        return card, (card.oracle_text or "").lower(), card.name.lower()
    try:
        index = int(raw_index)
    except Exception:
        return card, (card.oracle_text or "").lower(), card.name.lower()
    if index < 0 or index >= len(faces):
        return card, (card.oracle_text or "").lower(), card.name.lower()
    face = faces[index] or {}
    oracle = str(face.get("oracle_text") or card.oracle_text or "").lower()
    name = str(face.get("name") or card.name or "").lower()
    return card, oracle, name


def _looks_static_or_keyword_only(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    # A planeswalker card's loyalty lines are not one cast-time effect. They
    # are parsed and resolved only when the player activates a loyalty action.
    if re.search(r"(?:^|\n)\s*[+-]\d+\s*:", t):
        return True
    if re.search(r"\{[^}]+\}(?:\{[^}]+\})*:\s*", t) and not any(
        marker in t for marker in ("when ", "whenever ", "at the beginning")
    ):
        return True
    action_verbs = [
        "draw", "destroy", "exile", "counter", "deals", "deal", "create", "return", "search",
        "sacrifice", "tap target", "untap", "gain", "lose", "discard", "mill", "put ",
    ]
    if any(v in t for v in action_verbs):
        return False
    if "whenever " in t and " attacks" in t:
        # Trigger wiring may still be missing; keep this visible.
        return False
    static_markers = [
        "haste", "flying", "trample", "vigilance", "first strike", "double strike",
        "deathtouch", "lifelink", "menace", "reach", "ward", "hexproof",
        "can't be blocked", "cannot be blocked", "can't attack", "can't block",
        "prowess", "lands you control have", "add two mana of any one color",
    ]
    return any(m in t for m in static_markers)


def _is_event_layer_resolved(text: str) -> bool:
    """Identify event patterns resolved by rules_engine.events, not casts."""
    t = (text or "").strip().lower()
    return any(
        pattern in t
        for pattern in (
            "at the beginning of your upkeep, look at the top card",
            "whenever you cast a noncreature spell, put a +1/+1 counter",
            "would deal noncombat damage to a creature",
            "when this creature dies, it deals damage equal to its power",
            "when this creature enters the battlefield, cast target instant card from your graveyard",
        )
    )


def _infer_topdeck_creature_put_effect(oracle: str, action_targets: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    look_match = LOOK_TOP_RE.search(oracle)
    put_match = PUT_CREATURES_FROM_TOP_RE.search(oracle)
    if not (look_match and put_match):
        return None
    top_n = _parse_count_token(look_match.group(1))
    max_creatures = _parse_count_token(put_match.group(1))
    mv_max = _parse_count_token(put_match.group(2))
    # Optional overrides for future UI/testing hooks.
    top_n = int(action_targets.get("top_n", top_n) or top_n)
    max_creatures = int(action_targets.get("max_creatures", max_creatures) or max_creatures)
    mv_max = int(action_targets.get("mv_max", mv_max) or mv_max)
    payload = {
        "top_n": max(1, top_n),
        "max_creatures": max(1, max_creatures),
        "mv_max": max(0, mv_max),
    }
    if action_targets.get("topdeck_card_ids") is not None:
        payload["selected_card_ids"] = list(action_targets.get("topdeck_card_ids") or [])
    return "topdeck_put_creatures_battlefield", payload


def _infer_search_effect(oracle: str, action_targets: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    if "search your library for" not in oracle:
        return None
    contains = action_targets.get("search_contains")
    count = action_targets.get("search_count")
    mv_max = action_targets.get("search_mv_max")
    if not contains:
        if "basic land" in oracle:
            contains = "basic_land"
        elif "creature card" in oracle:
            contains = "creature"
        elif "artifact card" in oracle:
            contains = "artifact"
        elif "enchantment card" in oracle:
            contains = "enchantment"
        elif "planeswalker card" in oracle:
            contains = "planeswalker"
        elif "instant card" in oracle:
            contains = "instant"
        elif "sorcery card" in oracle:
            contains = "sorcery"
        elif "land card" in oracle or "lands" in oracle:
            contains = "land"
        elif "permanent card" in oracle:
            contains = "permanent"
    if count is None:
        count_match = SEARCH_UP_TO_RE.search(oracle)
        if count_match:
            count = _parse_count_token(count_match.group(1))
    if mv_max is None:
        mv_match = SEARCH_MV_MAX_RE.search(oracle)
        if mv_match:
            mv_max = _parse_count_token(mv_match.group(1))
    destination = "battlefield" if "onto the battlefield" in oracle else "hand"
    payload: dict[str, Any] = {"contains": contains, "destination": destination}
    if "onto the battlefield tapped" in oracle:
        payload["tapped"] = True
    if "shuffle" in oracle:
        payload["shuffle"] = True
    if count is not None:
        payload["count"] = int(count)
    if mv_max is not None:
        payload["mv_max"] = int(mv_max)
    selected = action_targets.get("search_card_ids")
    if selected is not None:
        payload["selected_card_ids"] = list(selected or [])
    return "search_library", payload


def search_card_matches(card: CardInstance, contains: str | None, mv_max: int | None = None) -> bool:
    """Return whether a card satisfies a structured library-search filter."""
    if not contains:
        return False
    needle = str(contains).strip().lower()
    card_types = {str(t).lower() for t in (getattr(card, "types", []) or [])}
    type_line = str(getattr(card, "type_line", "") or "").lower()
    type_line_parts = [part.strip() for part in re.split(r"\s*[—-]\s*", type_line, maxsplit=1)]
    subtypes = set(type_line_parts[1].split()) if len(type_line_parts) > 1 else set()
    if needle == "basic_land":
        matched = "basic" in type_line_parts[0].split() and "land" in card_types
    elif needle in {"artifact", "enchantment", "creature", "instant", "sorcery", "planeswalker", "land"}:
        matched = needle in card_types
    elif needle == "permanent":
        matched = bool(card_types.intersection({"artifact", "enchantment", "creature", "land", "planeswalker", "battle"}))
    else:
        matched = needle in subtypes or needle in type_line or needle in str(getattr(card, "name", "")).lower()
    if not matched:
        return False
    if mv_max is not None:
        from rules_engine.mana import parse_mana_cost

        req = parse_mana_cost(getattr(card, "mana_cost", "") or "")
        value = int(req["generic"] + req["W"] + req["U"] + req["B"] + req["R"] + req["G"])
        if value > int(mv_max):
            return False
    return True


def _infer_topdeck_permanent_put_effect(oracle: str, action_targets: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    look_match = LOOK_TOP_RE.search(oracle)
    put_match = PUT_PERMANENTS_FROM_TOP_RE.search(oracle)
    if not (look_match and put_match):
        return None
    payload = {
        "top_n": max(1, int(action_targets.get("top_n", _parse_count_token(look_match.group(1))) or 1)),
        "max_permanents": max(1, int(action_targets.get("max_permanents", _parse_count_token(put_match.group(1))) or 1)),
        "mv_max": max(0, int(action_targets.get("mv_max", _parse_count_token(put_match.group(2))) or 0)),
    }
    if action_targets.get("topdeck_card_ids") is not None:
        payload["selected_card_ids"] = list(action_targets.get("topdeck_card_ids") or [])
    return "topdeck_put_permanents_battlefield", payload


def inspect_target_hints(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_oracle = card.oracle_text or ""
    action_targets = action_targets or {}
    selected_modes = action_targets.get("mode_texts") or []
    selected_mode = action_targets.get("mode_text") or (selected_modes[0] if len(selected_modes) == 1 else None)
    oracle = str(selected_mode or raw_oracle).lower()
    hints: dict[str, Any] = {}
    opponent = 1 if controller == 2 else 2
    graveyard_creatures = [
        {"id": cid, "name": state.cards[cid].name, "owner": state.cards[cid].owner, "controller": state.cards[cid].controller}
        for pid in state.players
        for cid in getattr(state.players[pid], "graveyard", [])
        if cid in state.cards and "Creature" in state.cards[cid].types
    ]
    faces = list(getattr(card, "card_faces", []) or [])
    split_match = SPLIT_NAME_RE.match((card.name or "").strip())
    if split_match:
        hints["split_card"] = True
        left, right = [x.strip() for x in split_match.groups()]
        hints["face_names"] = [left, right]
    elif faces:
        face_names = [str(face.get("name", "")).strip() for face in faces if str(face.get("name", "")).strip()]
        if len(face_names) > 1:
            hints["split_card"] = True
            hints["face_names"] = face_names
    modes = _extract_modes(raw_oracle)
    if modes:
        hints["modes"] = modes
    if CHOOSE_TWO_RE.search(oracle):
        hints["choose_two_modes"] = True
    # X should generally be user-supplied only when present in cast cost.
    # Do not require x_value for cards whose oracle text references X contextually
    # (e.g. "where X is..." or cycling text) unless the spell itself has {X} cost.
    if "x" in (card.mana_cost or "").lower():
        hints["requires_x_value"] = True
    up_to_match = UP_TO_RE.search(oracle)
    if up_to_match:
        hints["up_to_target_count"] = int(up_to_match.group(1))

    top_choice = LOOK_TOP_CHOICE_RE.search(oracle)
    if top_choice:
        top_n = _parse_count_token(top_choice.group(1))
        top_cards = list(reversed(state.players[controller].library[-top_n:]))
        hints["top_choice"] = {
            "top_n": top_n,
            "candidates": [
                {"id": cid, "name": state.cards[cid].name}
                for cid in top_cards
                if cid in state.cards
            ],
        }

    topdeck_effect = _infer_topdeck_creature_put_effect(oracle, {}) or _infer_topdeck_permanent_put_effect(oracle, {})
    if topdeck_effect is not None:
        _, topdeck_payload = topdeck_effect
        top_n = int(topdeck_payload.get("top_n", 1) or 1)
        max_count = int(topdeck_payload.get("max_creatures", topdeck_payload.get("max_permanents", 1)) or 1)
        mv_max = int(topdeck_payload.get("mv_max", 0) or 0)
        top_cards = list(reversed(state.players[controller].library[-top_n:]))
        candidates = []
        for cid in top_cards:
            candidate = state.cards.get(cid)
            if candidate is None:
                continue
            types = set(candidate.types or [])
            if topdeck_effect[0] == "topdeck_put_creatures_battlefield" and "Creature" not in types:
                continue
            if topdeck_effect[0] == "topdeck_put_permanents_battlefield" and not types.intersection({"Creature", "Artifact", "Enchantment", "Land", "Planeswalker"}):
                continue
            req = parse_mana_cost(candidate.mana_cost or "")
            value = int(req["generic"] + req["C"] + sum(req[color] for color in "WUBRG"))
            if value <= mv_max:
                candidates.append({"id": cid, "name": candidate.name, "mana_value": value})
        hints["topdeck_choice"] = {
            "top_n": top_n,
            "max_count": max_count,
            "allow_zero": True,
            "candidates": candidates,
        }

    if "counter target spell" in oracle or "counter target noncreature spell" in oracle or "counter target activated ability" in oracle or "counter target triggered ability" in oracle or COPY_STACK_RE.search(oracle):
        stack_targets = []
        for item in state.stack:
            source = state.cards.get(item.source_card_id)
            if source is None:
                continue
            if "counter target noncreature spell" in oracle and "Creature" in (source.types or []):
                continue
            stack_targets.append({"id": item.id, "label": item.label})
        hints["stack_targets"] = stack_targets
        if COUNTER_UNLESS_PAY_RE.search(oracle):
            match = COUNTER_UNLESS_PAY_RE.search(oracle)
            hints["unless_payment"] = {
                "cost": match.group("cost").upper(),
                "choice_key": "pay_unless_counter",
                "default": "pay_if_legal",
            }
    if "target creature" in oracle or "destroy target" in oracle or "exile target" in oracle or "tap target" in oracle or "return target" in oracle:
        hints["creature_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if "Creature" in state.cards[cid].types
        ]
    if "target land" in oracle:
        hints["land_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[controller].battlefield
            if "Land" in state.cards[cid].types
        ]
    aura_restrictions = {
        "creature": "creature" in oracle,
        "artifact": "artifact" in oracle,
        "enchantment": "enchantment" in oracle,
        "land": "land" in oracle,
        "planeswalker": "planeswalker" in oracle,
        "permanent": "permanent" in oracle,
    }
    if "enchant " in oracle and any(aura_restrictions.values()):
        allowed_players = [controller] if "you control" in oracle else [1, 2]
        aura_targets = []
        for pid in allowed_players:
            for cid in state.players[pid].battlefield:
                target = state.cards[cid]
                target_types = {str(value).lower() for value in (target.types or [])}
                if (
                    (aura_restrictions["permanent"] and target.zone == Zone.BATTLEFIELD)
                    or any(aura_restrictions[kind] and kind in target_types for kind in aura_restrictions if kind != "permanent")
                ):
                    aura_targets.append({"id": cid, "name": target.name})
        hints["aura_targets"] = aura_targets
        hints["creature_targets"] = aura_targets
    if "target permanent" in oracle or "nonland permanent" in oracle or "return target" in oracle:
        hints["permanent_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if "Land" not in state.cards[cid].types
        ]
    if "artifact" in oracle:
        hints["artifact_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if "Artifact" in state.cards[cid].types
        ]
    if "enchantment" in oracle:
        hints["enchantment_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if "Enchantment" in state.cards[cid].types
        ]
    if "artifact" in oracle and "enchantment" in oracle:
        hints["noncreature_permanent_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if ("Artifact" in state.cards[cid].types or "Enchantment" in state.cards[cid].types)
        ]
    if "graveyard" in oracle and ("return" in oracle or "put" in oracle or "reanimate" in oracle):
        hints["graveyard_creature_targets"] = graveyard_creatures
        graveyard_permanents = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in state.players
            for cid in state.players[pid].graveyard
            if any(t in {"Creature", "Artifact", "Enchantment", "Land", "Planeswalker"} for t in state.cards[cid].types)
        ]
        graveyard_artifacts = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in state.players
            for cid in state.players[pid].graveyard
            if "Artifact" in state.cards[cid].types
        ]
        graveyard_enchantments = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in state.players
            for cid in state.players[pid].graveyard
            if "Enchantment" in state.cards[cid].types
        ]
        if "artifact" in oracle:
            hints["graveyard_artifact_targets"] = graveyard_artifacts
        if "enchantment" in oracle:
            hints["graveyard_enchantment_targets"] = graveyard_enchantments
        if "permanent" in oracle or ("artifact" in oracle and "enchantment" in oracle):
            hints["graveyard_permanent_targets"] = graveyard_permanents if "permanent" in oracle else graveyard_artifacts + graveyard_enchantments
    if "cast target" in oracle and "from your graveyard" in oracle:
        hints["graveyard_spell_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[controller].graveyard
            if cid in state.cards and {"Instant", "Sorcery"}.intersection(state.cards[cid].types)
        ]
    search_effect = _infer_search_effect(oracle, {})
    if search_effect is not None:
        _, search_payload = search_effect
        contains = search_payload.get("contains")
        mv_max = search_payload.get("mv_max")
        hints["library_search"] = {
            "contains": contains,
            "destination": search_payload.get("destination", "hand"),
            "max_count": int(search_payload.get("count", 0) or 0),
            "allow_zero": bool("up to" in oracle),
            "candidates": [
                {"id": cid, "name": state.cards[cid].name}
                for cid in state.players[controller].library
                if cid in state.cards and search_card_matches(state.cards[cid], contains, mv_max)
            ],
        }
    if "any target" in oracle or "target player" in oracle or "deals" in oracle:
        hints["player_targets"] = [
            {"id": 1, "name": state.players[1].name},
            {"id": 2, "name": state.players[2].name},
        ]
    if DIVIDE_RE.search(oracle):
        hints["supports_divide"] = True
    if "any target" in oracle or "target creature or planeswalker" in oracle:
        hints["planeswalker_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if "Planeswalker" in state.cards[cid].types
        ]
    restrictions = infer_target_restrictions(state, oracle, controller)
    if restrictions:
        hints["target_restrictions"] = restrictions
        for key in (
            "creature_targets", "planeswalker_targets", "permanent_targets", "land_targets",
            "artifact_targets", "enchantment_targets", "noncreature_permanent_targets",
            "aura_targets",
        ):
            if key in hints:
                hints[key] = [
                    item for item in hints[key]
                    if _target_id_matches_restrictions(state, str(item.get("id")), restrictions, controller)
                ]
    return hints


def infer_target_restrictions(state: MatchState, oracle_text: str, controller: int) -> dict[str, Any]:
    """Extract reusable restrictions for targeted permanent choices.

    This intentionally describes legality rather than naming cards. The same
    metadata supports target hints, human validation, AI materialization, and
    future stack-resolution rechecks.
    """
    oracle = (oracle_text or "").lower()
    restrictions: dict[str, Any] = {}
    if "nonartifact" in oracle:
        restrictions.setdefault("exclude_types", []).append("Artifact")
    if "nonland" in oracle:
        restrictions.setdefault("exclude_types", []).append("Land")
    if "noncreature" in oracle:
        restrictions.setdefault("exclude_types", []).append("Creature")
    if "nonenchantment" in oracle:
        restrictions.setdefault("exclude_types", []).append("Enchantment")

    if "target creature or planeswalker" in oracle:
        restrictions["allowed_types"] = ["Creature", "Planeswalker"]
    elif "target artifact or enchantment" in oracle:
        restrictions["allowed_types"] = ["Artifact", "Enchantment"]
    elif "target creature" in oracle:
        restrictions["allowed_types"] = ["Creature"]
    elif "target planeswalker" in oracle:
        restrictions["allowed_types"] = ["Planeswalker"]
    elif "target artifact" in oracle:
        restrictions["allowed_types"] = ["Artifact"]
    elif "target enchantment" in oracle:
        restrictions["allowed_types"] = ["Enchantment"]
    elif "target land" in oracle:
        restrictions["allowed_types"] = ["Land"]

    max_match = TARGET_MV_MAX_RE.search(oracle)
    if max_match:
        restrictions["mana_value_max"] = int(max_match.group(1))
    elif TARGET_MV_GRAVEYARD_RE.search(oracle):
        restrictions["mana_value_max_source"] = "controller_graveyard"
    else:
        controlled_match = TARGET_MV_CONTROLLED_TYPE_RE.search(oracle)
        if controlled_match:
            restrictions["mana_value_max_source"] = f"controlled_{controlled_match.group(1).lower()}"
    return restrictions


def _target_id_matches_restrictions(
    state: MatchState,
    card_id: str,
    restrictions: dict[str, Any],
    controller: int,
) -> bool:
    card = state.cards.get(card_id)
    if card is None:
        return False
    types = set(card.types or [])
    excluded = set(restrictions.get("exclude_types") or [])
    if types.intersection(excluded):
        return False
    allowed = set(restrictions.get("allowed_types") or [])
    if allowed and not types.intersection(allowed):
        return False
    max_value = restrictions.get("mana_value_max")
    source = restrictions.get("mana_value_max_source")
    if source == "controller_graveyard":
        max_value = len(state.players.get(card.controller, state.players[controller]).graveyard)
    elif isinstance(source, str) and source.startswith("controlled_"):
        subtype = source.removeprefix("controlled_")
        max_value = sum(
            1
            for cid in state.players[controller].battlefield
            if subtype in {str(t).lower() for t in state.cards[cid].types}
            or subtype in str(state.cards[cid].type_line or "").lower().split()
        )
    if max_value is not None:
        cost = parse_mana_cost(card.mana_cost or "")
        mana_value = int(cost.get("generic", 0) or 0) + int(cost.get("C", 0) or 0)
        mana_value += sum(int(cost.get(color, 0) or 0) for color in "WUBRG")
        if mana_value > int(max_value):
            return False
    return True


def _first_creature(state: MatchState, player_id: int) -> str | None:
    for cid in state.players[player_id].battlefield:
        if "Creature" in state.cards[cid].types:
            return cid
    return None


def _extract_modes(oracle: str) -> list[str]:
    match = CHOOSE_ONE_RE.search(oracle) or CHOOSE_TWO_RE.search(oracle)
    if not match:
        return []
    body = str(match.group(1) or "").strip()
    # Scryfall uses bullet lines for current Oracle text, while older imports
    # often use semicolons. Support both without changing the mode text itself.
    body = body.replace("\r", "")
    if "•" in body:
        candidates = re.split(r"\s*•\s*", body)
    elif "\n" in body:
        candidates = re.split(r"\n+", body)
    else:
        candidates = re.split(r"\s*;\s*", body)
    out: list[str] = []
    for candidate in candidates:
        cleaned = re.sub(r"^\s*(?:[-*]|\(?[a-z]\)|\d+[.)])\s*", "", candidate, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" ;:.")
        if cleaned:
            out.append(cleaned)
    return out


def _split_clauses(oracle: str) -> list[str]:
    cleaned = oracle.replace("\n", " ")
    parts = re.split(r"\.\s+|\s*;\s+|\s+then\s+", cleaned)
    return [p.strip(" .;") for p in parts if p.strip(" .;")]


def extract_loyalty_abilities(card: CardInstance) -> list[dict[str, Any]]:
    oracle = card.oracle_text or ""
    out: list[dict[str, Any]] = []
    for match in LOYALTY_ABILITY_RE.finditer(oracle):
        raw_delta = match.group(1).strip()
        text = match.group(2).strip()
        if raw_delta.upper().endswith("X"):
            x_sign = -1 if raw_delta.startswith("-") else 1
            out.append(
                {
                    "delta": 0,
                    "x_cost": True,
                    "x_sign": x_sign,
                    "text": text,
                    "label": f"{raw_delta.upper()}: {text}",
                }
            )
        else:
            delta = int(raw_delta)
            out.append({"delta": delta, "x_cost": False, "x_sign": 0, "text": text, "label": f"{delta:+d}: {text}"})
    return out


def extract_saga_chapters(oracle_text: str) -> list[dict[str, Any]]:
    """Parse chapter lines into ordered lore-counter triggers."""
    values = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
    chapters: list[dict[str, Any]] = []
    for line in (oracle_text or "").splitlines():
        match = SAGA_CHAPTER_RE.match(line)
        if not match:
            continue
        roman = match.group(1).upper()
        chapters.append({"number": values[roman], "text": match.group(2).strip(), "label": f"{roman} — {match.group(2).strip()}"})
    return sorted(chapters, key=lambda item: int(item["number"]))


def extract_activated_abilities(card: CardInstance) -> list[dict[str, Any]]:
    """Extract simple mana-cost activated abilities from a card surface."""
    out: list[dict[str, Any]] = []
    for index, match in enumerate(ACTIVATED_ABILITY_RE.finditer(card.oracle_text or "")):
        cost = match.group(1).strip().upper()
        text = match.group(2).strip()
        # Mana abilities are handled by the mana source model and should not
        # be duplicated as stack actions here.
        if "add " in text.lower() and "target" not in text.lower():
            continue
        out.append({"index": index, "mana_cost": cost, "text": text, "label": f"{cost}: {text}"})
    return out


def crew_value(card: CardInstance) -> int | None:
    match = CREW_RE.search(card.oracle_text or "")
    return int(match.group(1)) if match else None


def _infer_clause_effect(
    state: MatchState,
    card: CardInstance,
    controller: int,
    oracle: str,
    action_targets: dict[str, Any],
    x_value: int,
) -> tuple[str, dict[str, Any]] | None:
    opponent = 1 if controller == 2 else 2
    target_player = action_targets.get("target_player")
    target_card_id = action_targets.get("target_card_id")

    if "when you next cast a creature spell" in oracle and "additional +1/+1 counter" in oracle:
        return "set_next_creature_entry_counter", {"counter": "+1/+1", "amount": 1}

    if "exile this saga" in oracle and "return it to the battlefield transformed" in oracle:
        target = target_card_id or action_targets.get("source_card_id")
        if target:
            return "transform_card", {"target_card_id": target, "face_index": 1}

    control_match = GAIN_CONTROL_RE.search(oracle)
    if control_match:
        target = target_card_id or _choose_any_permanent_target(state, controller, action_targets, exclude_types=set())
        return "change_control", {
            "target_card_id": target,
            "new_controller": controller,
            "until_end_of_turn": "until end of turn" in oracle,
        }

    damage_match = DAMAGE_RE.search(oracle)
    if damage_match:
        amount = int(damage_match.group(1))
        if DIVIDE_RE.search(oracle):
            distribution = action_targets.get("target_distribution", {})
            return "deal_damage_multi", {"target_distribution": distribution}
        if target_card_id:
            return "deal_damage", {"target_card_id": target_card_id, "amount": amount}
        if target_player is None:
            target_player = opponent
        return "deal_damage", {"target_player": target_player, "amount": amount}

    if X_DAMAGE_RE.search(oracle):
        amount = max(0, x_value)
        if DIVIDE_RE.search(oracle):
            distribution = action_targets.get("target_distribution", {})
            return "deal_damage_multi", {"target_distribution": distribution}
        if target_card_id:
            return "deal_damage", {"target_card_id": target_card_id, "amount": amount}
        if target_player is None:
            target_player = opponent
        return "deal_damage", {"target_player": target_player, "amount": amount}

    draw_match = DRAW_RE.search(oracle)
    loot_match = LOOT_RE.search(oracle)
    if loot_match:
        draw_raw = loot_match.group(1)
        disc_raw = loot_match.group(2)
        draw_n = 1 if draw_raw == "a" else int(draw_raw)
        disc_n = 1 if disc_raw == "a" else int(disc_raw)
        return "effect_sequence", {
            "effects": [
                {"effect_key": "draw_cards", "payload": {"amount": draw_n}},
                {"effect_key": "discard_cards", "payload": {"target_player": controller, "amount": disc_n}},
            ]
        }
    if draw_match:
        raw = draw_match.group(1)
        amount = _parse_count_token(raw)
        return "draw_cards", {"amount": amount}
    if X_DRAW_RE.search(oracle):
        return "draw_cards", {"amount": max(0, x_value)}

    gain_match = GAIN_RE.search(oracle)
    if gain_match:
        amount = int(gain_match.group(1))
        if "target player" in oracle and target_player is not None:
            return "gain_life", {"amount": amount, "target_player": target_player}
        return "gain_life", {"amount": amount}

    lose_match = LOSE_RE.search(oracle)
    lose_count_match = LOSE_COUNT_RE.search(oracle)
    if lose_count_match:
        return "lose_life", {
            "target_player": target_player if target_player is not None else opponent,
            "count_type": lose_count_match.group(1).lower(),
            "count_controller": controller,
        }
    if lose_match:
        amount = int(lose_match.group(1))
        if "you lose" in oracle:
            return "lose_life", {"amount": amount, "target_player": controller}
        if "target player" in oracle and target_player is not None:
            return "lose_life", {"amount": amount, "target_player": target_player}
        return "lose_life", {"amount": amount, "target_player": opponent}

    prevent_match = PREVENT_RE.search(oracle)
    if prevent_match:
        amount = int(prevent_match.group(1))
        if "target creature" in oracle:
            target = target_card_id or _first_creature(state, controller)
            if target:
                return "prevent_damage", {"amount": amount, "target_card_id": target}
        if "target player" in oracle:
            if target_player is None:
                target_player = controller
            return "prevent_damage", {"amount": amount, "target_player": int(target_player)}

    if LAND_FROM_HAND_RE.search(oracle):
        return "put_land_from_hand", {"tapped": True}

    cast_from_graveyard = CAST_INSTANT_FROM_GRAVEYARD_RE.search(oracle)
    if cast_from_graveyard:
        target = action_targets.get("target_card_id")
        if target is None:
            for cid in state.players[controller].graveyard:
                candidate = state.cards.get(cid)
                if candidate and cast_from_graveyard.group(1).title() in candidate.types:
                    target = cid
                    break
        # Keep the effect structured even when no qualifying graveyard card
        # exists yet. Move generation and target validation decide whether the
        # action is currently legal; parsing should not depend on board state.
        return "cast_from_graveyard", {"target_card_id": target}

    if "destroy all artifacts and enchantments" in oracle or "destroy all artifact and enchantment" in oracle:
        return "destroy_all_artifacts_and_enchantments", {}
    if "destroy all artifacts" in oracle:
        return "destroy_all_artifacts", {}
    if "destroy all enchantments" in oracle:
        return "destroy_all_enchantments", {}
    if "exile all creatures" in oracle:
        return "exile_all_creatures", {}

    if "exile target" in oracle and "artifact" in oracle and "enchantment" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Artifact", "Enchantment"})
        if target:
            return "exile", {"target_card_id": target}
    if "destroy target" in oracle and "artifact" in oracle and "enchantment" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Artifact", "Enchantment"})
        if target:
            return "destroy_permanent", {"target_card_id": target}
    if "destroy target" in oracle and "nonland permanent" in oracle:
        target = _choose_any_permanent_target(state, controller, action_targets, exclude_types={"Land"})
        if target:
            return "destroy_permanent", {"target_card_id": target}
    if "destroy target artifact" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Artifact"})
        if target:
            return "destroy_permanent", {"target_card_id": target}
    if "destroy target enchantment" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Enchantment"})
        if target:
            return "destroy_permanent", {"target_card_id": target}
    if "exile target artifact" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Artifact"})
        if target:
            return "exile", {"target_card_id": target}
    if "exile target enchantment" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Enchantment"})
        if target:
            return "exile", {"target_card_id": target}
    if "exile target" in oracle and "nonland permanent" in oracle:
        target = _choose_any_permanent_target(state, controller, action_targets, exclude_types={"Land"})
        if target:
            return "exile", {"target_card_id": target}

    if "return target" in oracle and "to its owner's hand" in oracle and "nonland permanent" in oracle:
        target = _choose_any_permanent_target(state, controller, action_targets, exclude_types={"Land"})
        if target:
            return "return_permanent_to_hand", {"target_card_id": target}
    if "return target" in oracle and "to its owner's hand" in oracle and "creature" in oracle:
        target = action_targets.get("target_card_id") or _first_creature(state, opponent)
        if target:
            return "return_permanent_to_hand", {"target_card_id": target}

    if "destroy target" in oracle:
        target = target_card_id or _first_creature(state, opponent)
        return "destroy_permanent", {"target_card_id": target}

    if "destroy all creatures" in oracle:
        return "destroy_all_creatures", {}

    if "exile target" in oracle:
        target = target_card_id or _first_creature(state, opponent)
        return "exile", {"target_card_id": target}

    if "tap target" in oracle:
        if "nonland permanent" in oracle:
            target = _choose_any_permanent_target(state, controller, action_targets, exclude_types={"Land"})
        else:
            target = target_card_id or _first_creature(state, opponent)
        if target:
            return "tap", {"target_card_id": target}

    if "untap target" in oracle:
        target = target_card_id
        if target:
            return "untap", {"target_card_id": target}

    if "return target" in oracle and "graveyard" in oracle and "hand" in oracle:
        return "return_from_graveyard", {}
    if "graveyard" in oracle and "creature" in oracle and ("return" in oracle or "put" in oracle or "reanimate" in oracle):
        target = action_targets.get("target_card_id")
        if target:
            return "return_creature_from_graveyard_to_battlefield", {"target_card_id": target}
    if "graveyard" in oracle and ("return" in oracle or "put" in oracle or "reanimate" in oracle):
        if "artifact" in oracle or "enchantment" in oracle or "permanent" in oracle:
            target = action_targets.get("target_card_id")
            if target:
                return "return_permanent_from_graveyard_to_battlefield", {"target_card_id": target}

    if "search your library for" in oracle:
        contains = action_targets.get("search_contains")
        count = action_targets.get("search_count")
        mv_max = action_targets.get("search_mv_max")
        if not contains:
            if "basic land" in oracle:
                contains = "basic_land"
            elif "creature card" in oracle:
                contains = "creature"
            elif "artifact card" in oracle:
                contains = "artifact"
            elif "enchantment card" in oracle:
                contains = "enchantment"
            elif "planeswalker card" in oracle:
                contains = "planeswalker"
            elif "instant card" in oracle:
                contains = "instant"
            elif "sorcery card" in oracle:
                contains = "sorcery"
            elif "land card" in oracle:
                contains = "land"
            elif "permanent card" in oracle:
                contains = "permanent"
        if count is None:
            count_match = SEARCH_UP_TO_RE.search(oracle)
            if count_match:
                count = _parse_count_token(count_match.group(1))
        if mv_max is None:
            mv_match = SEARCH_MV_MAX_RE.search(oracle)
            if mv_match:
                mv_max = _parse_count_token(mv_match.group(1))
        destination = "battlefield" if "onto the battlefield" in oracle else "hand"
        payload: dict[str, Any] = {"contains": contains, "destination": destination}
        if "onto the battlefield tapped" in oracle:
            payload["tapped"] = True
        if "shuffle" in oracle:
            payload["shuffle"] = True
        if count is not None:
            payload["count"] = int(count)
        if mv_max is not None:
            payload["mv_max"] = int(mv_max)
        return "search_library", payload

    if SHARK_TOKEN_RE.search(oracle):
        payload = {"source_card_id": action_targets.get("source_card_id")}
        if "x_value" in action_targets:
            payload["x_value"] = max(0, int(action_targets.get("x_value", 0) or 0))
        return "create_shark_token", payload

    exile_playable = EXILE_TOP_PLAYABLE_RE.search(oracle)
    if exile_playable:
        return "exile_top_cards_playable", {"amount": _parse_count_token(exile_playable.group(1))}

    token_match = TOKEN_PT_RE.search(oracle)
    if "token" in oracle and token_match:
        count_match = TOKEN_COUNT_RE.search(oracle)
        token_count = _parse_count_token(count_match.group(1)) if count_match else 1
        token_name_match = TOKEN_NAME_RE.search(oracle)
        token_name = "Token"
        if token_name_match:
            token_name = token_name_match.group(1).strip().title()
        token_keywords = _extract_keywords_from_text(oracle)
        out = {
            "name": token_name,
            "power": int(token_match.group(1)),
            "toughness": int(token_match.group(2)),
            "amount": token_count,
            "keywords": token_keywords,
        }
        if SAC_AT_EOT_RE.search(oracle):
            out["sacrifice_next_end_step"] = True
        return "create_token", out

    counters_match = COUNTER_RE.search(oracle)
    if counters_match:
        amount = _parse_count_token(counters_match.group(1))
        target = target_card_id
        if target is None and counters_match.group(2).lower() == "land":
            target = next(
                (cid for cid in state.players[controller].battlefield if "Land" in state.cards[cid].types),
                None,
            )
        if target is None:
            target = _first_creature(state, controller)
        if target:
            return "add_counters", {
                "target_card_id": target,
                "counter": "+1/+1",
                "amount": amount,
                "animate_land": counters_match.group(2).lower() == "land" and "becomes a 0/0" in oracle,
            }

    if "put a green creature card from your hand onto the battlefield" in oracle:
        return "put_green_creature_from_hand", {}

    if "creatures you control get +1/+1" in oracle:
        return "continuous_buff", {"amount": 1}

    if "add one mana of any color" in oracle or "add mana of any color" in oracle or "add one mana of any one color" in oracle:
        color = choose_mana_color_for_player(state, controller)
        return "add_mana", {"color": color, "amount": 1}

    if "add " in oracle and "{" in oracle and "}" in oracle:
        symbols = MANA_SYMBOL_RE.findall(oracle.upper())
        if symbols:
            counts: dict[str, int] = {}
            for sym in symbols:
                counts[sym] = counts.get(sym, 0) + 1
            if len(counts) == 1:
                color, amount = next(iter(counts.items()))
                return "add_mana", {"color": color, "amount": amount}
            return "effect_sequence", {"effects": [{"effect_key": "add_mana", "payload": {"color": c, "amount": a}} for c, a in counts.items()]}

    sac_match = SAC_RE.search(oracle)
    if sac_match:
        raw = sac_match.group(1)
        amount = 1 if raw == "a" else int(raw)
        target = target_card_id
        if target:
            return "sacrifice", {"target_card_id": target}
        own_creatures = [cid for cid in state.players[controller].battlefield if "Creature" in state.cards[cid].types]
        if own_creatures and amount == 1:
            return "sacrifice", {"target_card_id": own_creatures[0]}

    if "discard" in oracle and "card" in oracle:
        amount = 1
        if "two cards" in oracle:
            amount = 2
        if "three cards" in oracle:
            amount = 3
        if "you discard" in oracle:
            return "discard_cards", {"target_player": controller, "amount": amount}
        return "discard_cards", {"target_player": target_player or opponent, "amount": amount}

    return None


def _choose_noncreature_permanent_target(
    state: MatchState,
    controller: int,
    action_targets: dict[str, Any],
    allowed_types: set[str],
) -> str | None:
    target_card_id = action_targets.get("target_card_id")
    if target_card_id in state.cards:
        target_card = state.cards[target_card_id]
        if allowed_types.intersection(set(target_card.types or [])):
            return target_card_id
    opponent = 1 if controller == 2 else 2
    candidates: list[str] = []
    for cid in state.players[opponent].battlefield:
        card = state.cards.get(cid)
        if not card:
            continue
        if allowed_types.intersection(set(card.types or [])):
            candidates.append(cid)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda cid: (
            0 if "Artifact" in state.cards[cid].types else 1,
            0 if "Enchantment" in state.cards[cid].types else 1,
            str(state.cards[cid].name).lower(),
            cid,
        ),
    )[0]


def _choose_any_permanent_target(
    state: MatchState,
    controller: int,
    action_targets: dict[str, Any],
    exclude_types: set[str] | None = None,
) -> str | None:
    exclude_types = exclude_types or set()
    target_card_id = action_targets.get("target_card_id")
    if target_card_id in state.cards:
        target_card = state.cards[target_card_id]
        if not exclude_types.intersection(set(target_card.types or [])):
            return target_card_id
    opponent = 1 if controller == 2 else 2
    candidates: list[str] = []
    for cid in state.players[opponent].battlefield:
        card = state.cards.get(cid)
        if not card:
            continue
        if exclude_types.intersection(set(card.types or [])):
            continue
        candidates.append(cid)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda cid: (
            0 if "Creature" in state.cards[cid].types else 1,
            0 if "Artifact" in state.cards[cid].types else 1,
            0 if "Enchantment" in state.cards[cid].types else 1,
            str(state.cards[cid].name).lower(),
            cid,
        ),
    )[0]


def _parse_count_token(token: str) -> int:
    mapping = {
        "a": 1,
        "an": 1,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    t = (token or "").strip().lower()
    if t in mapping:
        return mapping[t]
    try:
        return int(t)
    except Exception:
        return 1


def _extract_keywords_from_text(text: str) -> list[str]:
    lower = (text or "").lower()
    found: list[str] = []
    for kw in ["trample", "first strike", "double strike", "haste", "flash", "lifelink", "deathtouch", "vigilance", "flying", "menace"]:
        if kw in lower:
            found.append(kw)
    return found
