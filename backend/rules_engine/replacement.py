from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from rules_engine.continuous import effect_timestamp, printed_abilities_suppressed
from rules_engine.card_types import is_token_card


def _battlefield_oracle_texts(state, controller: int | None = None, *, text_filter=None):
    ordered: list[tuple[tuple[int, int, int, str], object, str]] = []
    battlefield_index = _battlefield_position_map(state)
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            text = (card.oracle_text or '').lower()
            if text_filter is not None and not text_filter(text):
                continue
            if printed_abilities_suppressed(state, cid):
                continue
            if controller is not None and card.controller != controller:
                continue
            order_key = (
                -effect_timestamp(card),
                -int(getattr(card, "entered_turn", 0) or 0),
                -int(battlefield_index.get(cid, 0) or 0),
                -int(getattr(card, "instance_order", 0) or 0),
                str(cid),
            )
            ordered.append((order_key, card, text))
    for _, card, text in sorted(ordered, key=lambda item: item[0]):
        yield card, text


def _battlefield_position_map(state) -> dict[str, int]:
    positions: dict[str, int] = {}
    position = 0
    for pid in sorted(state.players):
        for cid in state.players[pid].battlefield:
            positions[cid] = position
            position += 1
    return positions


def _matches_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


_PLAYER_DAMAGE_PREVENTION_RE = re.compile(
    r"if a source would deal damage to (?:you|you or (?:a|an|target) (?:permanent|creature) you control|(?:a|an|target) (?:permanent|creature) you control), prevent 1 of that damage"
)
_PERMANENT_DAMAGE_PREVENTION_RE = re.compile(
    r"if a source would deal damage to (?:you or (?:a|an|target) (?:permanent|creature) you control|(?:a|an|target) (?:permanent|creature) you control|(?:a|an|target) permanent you control|(?:a|an|target) creature you control), prevent 1 of that damage"
)
_PERMANENT_DAMAGE_REDUCTION_RE = re.compile(
    r'if a source would deal damage to a creature you control, it deals that much damage minus 1 to that creature instead'
)
_DIE_EXILE_RE = re.compile(
    r"if a (?:non-token|nontoken|another )?(?:creature|permanent|artifact|enchantment|artifact or enchantment) you control would die, exile it instead"
    r"|if an? artifact or enchantment you control would die, exile it instead"
)
_SUBTYPE_DIE_EXILE_RE = re.compile(r"\bif an? ([a-z]+) you control would die, exile it instead\b")
_ANY_GRAVEYARD_EXILE = "if a card or token would be put into a graveyard from anywhere, exile it instead"
_OPPONENT_CARD_GRAVEYARD_EXILE = "if a card would be put into an opponent's graveyard from anywhere, exile it instead"
_DRAW_DOUBLE_RE = re.compile(r"(?:^|\n)if you would draw a card, draw two cards instead\.")
_DRAW_DOUBLE_EXCEPT_FIRST_RE = re.compile(
    r"(?:^|\n)if you would draw a card except the first one you draw in each of your draw steps, draw two cards instead\."
)
_LIFE_DOUBLE_RE = re.compile(r"(?:^|\n)if you would gain life, you gain twice that much life instead\.")
_OPPONENT_GAIN_LOSS_RE = re.compile(
    r"(?:^|\n)(?:[a-z][a-z '\-]*\s+\u2014\s*)?"
    r"if an opponent would gain life, that player loses that much life instead\."
)
_CANT_LOSE_GAME_RE = re.compile(
    r"(?:^|\n)you can't lose the game(?:\.| and your opponents can't win the game\.)"
)
_GLOBAL_DAMAGE_DOUBLE_RE = re.compile(
    r'if a source would deal damage to a permanent or player, '
    r'it deals double that damage to that permanent or player instead\.')


def _player_damage_candidates(state, target_player, prevention_locked=False):
    return [(card, text) for card, text in _battlefield_oracle_texts(state)
            if _GLOBAL_DAMAGE_DOUBLE_RE.search(text)
            or (not prevention_locked and card.controller == target_player
                and _PLAYER_DAMAGE_PREVENTION_RE.search(text))]


def _draw_doubler_applies(state, target_player: int, text: str) -> bool:
    if _DRAW_DOUBLE_RE.search(text):
        return True
    if not _DRAW_DOUBLE_EXCEPT_FIRST_RE.search(text):
        return False
    in_own_draw_step = getattr(state.step, "value", state.step) == "draw" and state.active_player == target_player
    return not (in_own_draw_step and state.draws_in_current_draw_step.get(target_player, 0) == 0)


def _life_gain_candidates(state, target_player: int):
    return [(card, text) for card, text in _battlefield_oracle_texts(state)
            if (card.controller == target_player and (
                "if you would gain life, draw that many cards instead" in text
                or _LIFE_DOUBLE_RE.search(text)))
            or (card.controller != target_player and _OPPONENT_GAIN_LOSS_RE.search(text))]


def player_cant_lose_game(state, player_id: int) -> bool:
    return any(_CANT_LOSE_GAME_RE.search(text)
               for _, text in _battlefield_oracle_texts(state, controller=player_id))


def replacement_source_used(used_source_ids, event: str, source_id: str) -> bool:
    used = {str(value) for value in (used_source_ids or [])}
    return source_id in used or f"{event}:{source_id}" in used


def _permanent_damage_candidates(state, target_card_id, prevention_locked=False):
    from copy import copy
    from game_state.state import Zone
    from rules_engine.named_counters import shield_applied_in_event
    target = state.cards[target_card_id]
    if target.zone != Zone.BATTLEFIELD:
        return []
    candidates = [
        (card, text) for card, text in _battlefield_oracle_texts(state)
        if _GLOBAL_DAMAGE_DOUBLE_RE.search(text)
        or (card.controller == target.controller and (
            (_PERMANENT_DAMAGE_REDUCTION_RE.search(text) and 'Creature' in effective_types(state, target))
            or (not prevention_locked and _PERMANENT_DAMAGE_PREVENTION_RE.search(text)
                and ('creature you control' not in text or 'Creature' in effective_types(state, target)))))
    ]
    if target.counters.get('shield', 0) > 0 or shield_applied_in_event(state, target_card_id):
        source = copy(target)
        source.id = f'shield-counter:{target.id}'
        source.name = f'{target.name} shield counter'
        source.effect_timestamp = target.counter_timestamps.get('shield', effect_timestamp(target))
        candidates.append((source, 'shield-counter'))
    return sorted(candidates, key=lambda pair: -effect_timestamp(pair[0]))


def replacement_options(
    state,
    event: str,
    target_player: int | None = None,
    target_card_id: str | None = None,
    source_card_id: str | None = None,
    combat: bool = False,
) -> list[dict]:
    """Return applicable replacement sources in deterministic choice order.

    The rules engine still chooses the newest source by default for AI/replay
    callers, but API and human callers can inspect the exact source IDs before
    supplying __replacement_source_id on the affected action.
    """
    event_key = str(event or "").strip().lower()
    if event_key in {"card_draw", "draw"} and target_player in state.players:
        from rules_engine.draw_restrictions import can_draw_card
        if not can_draw_card(state, target_player):
            return []
    prevention_locked = False
    if event_key in {"damage_to_player", "player_damage", "damage_to_permanent", "permanent_damage"}:
        prevention_locked = damage_cant_be_prevented(
            state,
            source_card_id=source_card_id,
            target_player=target_player,
            target_card_id=target_card_id,
            combat=combat,
        )
    candidates: list[tuple[object, str]] = []
    if event_key in {"damage_to_player", "player_damage"} and target_player in state.players:
        candidates = _player_damage_candidates(state, target_player, prevention_locked)
    elif event_key in {"damage_to_permanent", "permanent_damage"} and target_card_id in state.cards:
        candidates = _permanent_damage_candidates(state, target_card_id, prevention_locked)
    elif event_key in {"life_gain", "gain_life"} and target_player in state.players:
        candidates = _life_gain_candidates(state, target_player)
    elif event_key in {"card_draw", "draw"} and target_player in state.players:
        candidates = [
            (card, text)
            for card, text in _battlefield_oracle_texts(state, controller=target_player)
            if "if you would draw a card, gain 1 life instead" in text or _draw_doubler_applies(state, target_player, text)
        ]
        from rules_engine.dredge import dredge_options
        candidates.extend((state.cards[option["card_id"]], state.cards[option["card_id"]].oracle_text) for option in dredge_options(state, target_player))
    elif event_key in {"die_zone", "dies"} and target_card_id in state.cards:
        candidates = _die_zone_candidates(state, state.cards[target_card_id])
    return [
        {
            "source_id": str(card.id),
            "name": card.name,
            "controller": int(card.controller),
            "static_order": int(getattr(card, "static_order", 0) or 0),
            "effect_timestamp": effect_timestamp(card),
        }
        for card, _ in candidates
    ]


def apply_damage_replacements(
    state,
    target_player: int | None,
    amount: int,
    replacement_source_id: str | None = None,
    max_replacements: int | None = None,
    used_source_ids=None,
    prevention_locked=False,
) -> int:
    out = int(amount)
    if target_player is None:
        return out
    candidates = _player_damage_candidates(state, target_player, prevention_locked)
    used: set[str] = set(used_source_ids or [])
    used.discard(str(replacement_source_id))
    requested = replacement_source_id
    applied = 0
    while out > 0 and (max_replacements is None or applied < max_replacements):
        available = [(card, text) for card, text in candidates if str(getattr(card, "id", "")) not in used]
        chosen = _choose_replacement_candidate(state, available, requested, "damage to player")
        if chosen is None:
            break
        used.add(str(getattr(chosen, "id", "")))
        text = next(text for card, text in available if card.id == chosen.id)
        out = out * 2 if _GLOBAL_DAMAGE_DOUBLE_RE.search(text) else max(0, out - 1)
        applied += 1
        requested = None
    return out


def apply_permanent_damage_replacements(
    state,
    target_card_id: str,
    amount: int,
    replacement_source_id: str | None = None,
    max_replacements: int | None = None,
    used_source_ids=None,
    prevention_locked=False,
) -> int:
    out = int(amount)
    if target_card_id not in state.cards:
        return out
    target = state.cards[target_card_id]
    candidates = _permanent_damage_candidates(state, target_card_id, prevention_locked)
    used: set[str] = set(used_source_ids or [])
    # A selected effect is about to be applied, not already applied.
    used.discard(str(replacement_source_id))
    requested = replacement_source_id
    applied = 0
    while out > 0 and (max_replacements is None or applied < max_replacements):
        available = [(card, text) for card, text in candidates if str(getattr(card, "id", "")) not in used]
        if requested is None:
            # Free static reductions first: they may avoid spending a counter.
            available.sort(key=lambda pair: str(pair[0].id).startswith('shield-counter:'))
        chosen = _choose_replacement_candidate(state, available, requested, f"damage to {target.name}")
        if chosen is None:
            break
        used.add(str(getattr(chosen, "id", "")))
        if str(chosen.id) == f'shield-counter:{target_card_id}':
            from rules_engine.named_counters import apply_shield_damage
            apply_shield_damage(state, target_card_id)
            if not prevention_locked:
                out = 0
        else:
            text = next(text for card, text in available if card.id == chosen.id)
            out = out * 2 if _GLOBAL_DAMAGE_DOUBLE_RE.search(text) else max(0, out - 1)
        applied += 1
        requested = None
    return out


def replace_noncombat_damage_to_creature(
    state,
    source_card_id: str | None,
    target_card_id: str | None,
    amount: int,
    *, source_lki: dict | None = None,
) -> object | None:
    """Apply source-controlled noncombat damage replacement to a creature.

    Effects such as Soul-Scar Mage replace the event rather than reducing its
    amount. The replacement is applied once, and the resulting counters are
    checked by the normal state-based action path in the caller.
    """
    if not target_card_id or target_card_id not in state.cards:
        return None
    from rules_engine.damage_results import damage_controller, queue_damage_counters
    if source_card_id not in state.cards and not source_lki:
        return None
    controller = damage_controller(state, source_card_id, source_lki)
    target = state.cards[target_card_id]
    if "Creature" not in (effective_types(state, target) or []) or controller == target.controller or amount <= 0:
        return None
    candidates = [
        (card, text)
        for card, text in _battlefield_oracle_texts(state, controller=controller)
        if (
            "would deal noncombat damage to a creature an opponent controls" in text
            or "would deal noncombat damage to a creature your opponent controls" in text
            or "would deal noncombat damage to target creature an opponent controls" in text
        )
    ]
    chosen = _choose_replacement_candidate(state, candidates, None, f"noncombat damage to {target.name}")
    if chosen is None:
        return None
    queue_damage_counters(state, controller, 'add_counters', {'target_card_id': target_card_id,
                          'counter': '-1/-1', 'amount': amount, '__counter_is_effect': True})
    state.log.append(f"{chosen.name} replaces {amount} noncombat damage to {target.name} with -1/-1 counters.")
    return chosen


def _choose_replacement_candidate(
    state,
    candidates: list[tuple[object, str]],
    requested_source_id: str | None,
    event_label: str,
) -> object | None:
    """Choose one applicable replacement; later timestamp wins by default.

    A caller can provide the affected player's explicit source choice. The
    deterministic fallback is intentional for AI and replay callers; unlike
    the old loop, it never applies multiple mutually exclusive replacements
    to the same event without re-evaluation.
    """
    if not candidates:
        return None
    chosen = next(
        (card for card, _ in candidates if requested_source_id and str(getattr(card, "id", "")) == str(requested_source_id)),
        candidates[0][0],
    )
    if len(candidates) > 1:
        state.log.append(
            f"Replacement choice for {event_label}: {getattr(chosen, 'name', 'replacement')} selected from {len(candidates)} applicable effect(s)."
        )
    return chosen


def damage_cant_be_prevented(
    state,
    source_card_id: str | None = None,
    target_player: int | None = None,
    target_card_id: str | None = None,
    combat: bool = False,
) -> bool:
    if bool(getattr(state, "turn_damage_cant_be_prevented", False)):
        return True
    source = state.cards[source_card_id] if source_card_id and source_card_id in state.cards else None
    for card, text in _battlefield_oracle_texts(state):
        if _matches_phrase(text, ("damage can't be prevented", "damage cannot be prevented")):
            return True
        if combat and _matches_phrase(text, ("combat damage can't be prevented", "combat damage cannot be prevented")):
            return True
        if (combat and source and source.controller == card.controller and 'Creature' in effective_types(state, source)
                and _matches_phrase(text, (
                    "combat damage that would be dealt by creatures you control can't be prevented",
                    "combat damage that would be dealt by creatures you control cannot be prevented",
                ))):
            return True
        if target_player == card.controller and _matches_phrase(
            text,
            (
                "damage that would be dealt to you can't be prevented",
                "damage that would be dealt to you cannot be prevented",
                "damage dealt to you can't be prevented",
                "damage dealt to you cannot be prevented",
            ),
        ):
            return True
        if target_player is not None and target_player != card.controller and _matches_phrase(
            text,
            (
                "damage that would be dealt to your opponents can't be prevented",
                "damage that would be dealt to your opponents cannot be prevented",
            ),
        ):
            return True
        if target_card_id and target_card_id in state.cards:
            target = state.cards[target_card_id]
            if target.controller == card.controller and _matches_phrase(
                text,
                (
                    "damage that would be dealt to permanents you control can't be prevented",
                    "damage that would be dealt to permanents you control cannot be prevented",
                    "damage dealt to permanents you control can't be prevented",
                    "damage dealt to permanents you control cannot be prevented",
                ),
            ):
                return True
        if source and source.controller == card.controller and _matches_phrase(
            text,
            (
                "damage that would be dealt by sources you control can't be prevented",
                "damage that would be dealt by sources you control cannot be prevented",
            ),
        ):
            return True
        if source and source.id == card.id and _matches_phrase(
            text,
            (
                "damage dealt by this creature can't be prevented",
                "damage dealt by this creature cannot be prevented",
                "damage dealt by this source can't be prevented",
                "damage dealt by this source cannot be prevented",
            ),
        ):
            return True
    return False


def replace_gain_life(
    state,
    target_player: int,
    amount: int,
    replacement_source_id: str | None = None,
    used_source_ids: list[str] | None = None,
) -> tuple[str, dict] | None:
    used = {str(value) for value in (used_source_ids or [])}
    candidates = [
        (card, text)
        for card, text in _life_gain_candidates(state, target_player)
        if not replacement_source_used(used, "life_gain", str(getattr(card, "id", "")))
    ]
    card = _choose_replacement_candidate(state, candidates, replacement_source_id, "life gain")
    if card is not None:
        next_used = sorted(used | {f"life_gain:{card.id}"})
        if _OPPONENT_GAIN_LOSS_RE.search((card.oracle_text or "").lower()):
            return ("lose_life", {"target_player": target_player, "amount": int(amount),
                                  "__replacement_source": card.name,
                                  "__used_replacement_source_ids": next_used})
        if _LIFE_DOUBLE_RE.search((card.oracle_text or "").lower()):
            return (
                "gain_life",
                {
                    "target_player": target_player,
                    "amount": int(amount) * 2,
                    "__replacement_source": card.name,
                    "__used_replacement_source_ids": next_used,
                },
            )
        return (
            "draw_cards",
            {
                "target_player": target_player,
                "amount": int(amount),
                "__replacement_source": card.name,
                "__replacement_source_id": card.id,
                "__used_replacement_source_ids": next_used,
            },
        )
    return None


def replace_draw_cards(
    state,
    target_player: int,
    amount: int,
    replacement_source_id: str | None = None,
    used_source_ids: list[str] | None = None,
) -> tuple[str, dict] | None:
    from rules_engine.dredge import dredge_options
    if any(option["card_id"] == replacement_source_id for option in dredge_options(state, target_player)):
        return ("dredge", {"target_player": target_player, "dredge_card_id": replacement_source_id})
    used = {str(value) for value in (used_source_ids or [])}
    candidates = [
        (card, text)
        for card, text in _battlefield_oracle_texts(state, controller=target_player)
        if not replacement_source_used(used, "card_draw", str(getattr(card, "id", "")))
        and ("if you would draw a card, gain 1 life instead" in text or _draw_doubler_applies(state, target_player, text))
    ]
    card = _choose_replacement_candidate(state, candidates, replacement_source_id, "card draw")
    if card is not None:
        next_used = sorted(used | {f"card_draw:{card.id}"})
        if _draw_doubler_applies(state, target_player, (card.oracle_text or "").lower()):
            return (
                "draw_cards",
                {
                    "target_player": target_player,
                    "amount": 2,
                    "__replacement_source": card.name,
                    "__used_replacement_source_ids": next_used,
                },
            )
        return (
            "gain_life",
            {
                "target_player": target_player,
                "amount": int(amount),
                "__replacement_source": card.name,
                "__replacement_source_id": card.id,
                "__used_replacement_source_ids": next_used,
            },
        )
    return None


def replace_die_zone(
    state,
    controller: int,
    card_id: str,
    replacement_source_id: str | None = None,
) -> str:
    """Return destination zone for a dying permanent: 'graveyard' or 'exile'."""
    target = state.cards.get(card_id)
    candidates = _die_zone_candidates(state, target) if target else []
    if _choose_replacement_candidate(state, candidates, replacement_source_id, "die zone") is not None:
        return "exile"
    return "graveyard"


def graveyard_destination(state, target) -> str:
    """Resolve supported replacements for a non-death graveyard move."""
    return "exile" if any(
        _graveyard_exile_applies(card, text, target)
        for card, text in _battlefield_oracle_texts(state)
    ) else "graveyard"


def _graveyard_exile_applies(source, text: str, target) -> bool:
    if _ANY_GRAVEYARD_EXILE in text:
        return True
    return (
        not is_token_card(target)
        and source.controller != target.owner
        and _OPPONENT_CARD_GRAVEYARD_EXILE in text
    )


def _die_zone_candidates(state, target) -> list[tuple[object, str]]:
    return [
        (card, text)
        for card, text in _battlefield_oracle_texts(state)
        if _graveyard_exile_applies(card, text, target)
        or (card.controller == target.controller and _die_exile_applies(text, target))
    ]


def _die_exile_applies(text: str, target) -> bool:
    is_token = is_token_card(target)
    if is_token and ("nontoken" in text or "non-token" in text):
        return False
    if _DIE_EXILE_RE.search(text) or _matches_phrase(text, (
        "if a permanent would die, exile it instead",
        "if a non-token permanent you control would die, exile it instead",
        "if a nontoken permanent you control would die, exile it instead",
        "if another creature you control would die, exile it instead",
        "if a non-token creature you control would die, exile it instead",
        "if a nontoken creature you control would die, exile it instead",
    )):
        return True
    match = _SUBTYPE_DIE_EXILE_RE.search(text)
    if not match:
        return False
    subtype_text = re.split(r"\s+[—-]\s+", str(getattr(target, "type_line", "") or ""), maxsplit=1)
    subtypes = set(re.findall(r"[a-z]+", subtype_text[1].lower())) if len(subtype_text) > 1 else set()
    return match.group(1) in subtypes


def player_life_total_cant_change(state, target_player: int) -> bool:
    for card, text in _battlefield_oracle_texts(state, text_filter=lambda text: 'life total' in text):
        if any(clause in text for clause in (
            "players' life totals can't change", "players' life totals cannot change",
            "each player's life total can't change", "each player's life total cannot change",
        )):
            return True
        if card.controller == target_player and any(clause in text for clause in (
            "your life total can't change", "your life total cannot change",
        )):
            return True
        if card.controller != target_player and any(clause in text for clause in (
            "your opponents' life totals can't change", "your opponents' life totals cannot change",
            "your opponent's life total can't change", "your opponent's life total cannot change",
        )):
            return True
    return False


def can_pay_life(state, player_id: int, amount: int) -> bool:
    if amount < 0:
        return False
    return amount == 0 or (state.players[player_id].life >= amount and not player_cant_lose_life(state, player_id))


def pay_life(state, player_id: int, amount: int) -> bool:
    if not can_pay_life(state, player_id, amount):
        return False
    if amount:
        state.players[player_id].life -= amount
        from rules_engine.events import emit_event
        emit_event(state, "life_paid", {"player_id": player_id, "amount": amount})
    return True


def player_cant_gain_life(state, target_player: int) -> bool:
    if player_life_total_cant_change(state, target_player):
        return True
    if int(target_player) in set(getattr(state, "turn_cant_gain_life", set()) or set()):
        return True
    for card, text in _battlefield_oracle_texts(state, text_filter=lambda text: 'gain life' in text):
        if "players can't gain life" in text or "players cannot gain life" in text:
            return True
        if "you can't gain life" in text or "you cannot gain life" in text:
            if card.controller == target_player:
                return True
        if card.controller == target_player:
            continue
        if "your opponents can't gain life" in text or "your opponents cannot gain life" in text:
            return True
        if "your opponent can't gain life" in text or "your opponent cannot gain life" in text:
            return True
    return False


def player_cant_lose_life(state, target_player: int) -> bool:
    if player_life_total_cant_change(state, target_player):
        return True
    for card, text in _battlefield_oracle_texts(state, text_filter=lambda text: 'lose life' in text):
        if "players can't lose life" in text or "players cannot lose life" in text:
            return True
        if card.controller == target_player and ("you can't lose life" in text or "you cannot lose life" in text):
            return True
        if card.controller != target_player and (
            "your opponents can't lose life" in text
            or "your opponents cannot lose life" in text
            or "your opponent can't lose life" in text
            or "your opponent cannot lose life" in text
        ):
            return True
    return False
