from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from enum import Enum


class Zone(str, Enum):
    LIBRARY = "library"
    HAND = "hand"
    BATTLEFIELD = "battlefield"
    GRAVEYARD = "graveyard"
    EXILE = "exile"
    STACK = "stack"


class Step(str, Enum):
    UNTAP = "untap"
    UPKEEP = "upkeep"
    DRAW = "draw"
    PRECOMBAT_MAIN = "precombat_main"
    BEGIN_COMBAT = "begin_combat"
    DECLARE_ATTACKERS = "declare_attackers"
    DECLARE_BLOCKERS = "declare_blockers"
    COMBAT_DAMAGE = "combat_damage"
    END_COMBAT = "end_combat"
    POSTCOMBAT_MAIN = "postcombat_main"
    END_STEP = "end_step"
    CLEANUP = "cleanup"


TURN_STEPS: list[Step] = [
    Step.UNTAP,
    Step.UPKEEP,
    Step.DRAW,
    Step.PRECOMBAT_MAIN,
    Step.BEGIN_COMBAT,
    Step.DECLARE_ATTACKERS,
    Step.DECLARE_BLOCKERS,
    Step.COMBAT_DAMAGE,
    Step.END_COMBAT,
    Step.POSTCOMBAT_MAIN,
    Step.END_STEP,
    Step.CLEANUP,
]


@dataclass
class CardInstance:
    id: str
    name: str
    owner: int
    controller: int
    zone: Zone
    types: list[str] = field(default_factory=list)
    mana_cost: str = ""
    power: int | None = None
    toughness: int | None = None
    loyalty: int | None = None
    tapped: bool = False
    summoning_sick: bool = True
    counters: dict[str, int] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    oracle_text: str = ""
    type_line: str = ""


@dataclass
class StackItem:
    id: str
    source_card_id: str
    controller: int
    label: str
    effect_key: str
    payload: dict
    targets: list[str] = field(default_factory=list)


@dataclass
class PlayerState:
    id: int
    name: str
    life: int = 20
    library: list[str] = field(default_factory=list)
    hand: list[str] = field(default_factory=list)
    battlefield: list[str] = field(default_factory=list)
    graveyard: list[str] = field(default_factory=list)
    exile: list[str] = field(default_factory=list)
    mana_pool: dict[str, int] = field(default_factory=lambda: {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0})
    lands_played_this_turn: int = 0


@dataclass
class MatchState:
    id: str
    players: dict[int, PlayerState]
    cards: dict[str, CardInstance]
    stack: list[StackItem]
    turn: int = 1
    active_player: int = 1
    priority_player: int = 1
    step: Step = Step.UNTAP
    passed_priority: set[int] = field(default_factory=set)
    attackers: list[str] = field(default_factory=list)
    attack_targets: dict[str, str] = field(default_factory=dict)
    blocks: dict[str, list[str]] = field(default_factory=dict)
    winner: int | None = None
    best_of: int = 3
    score: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    pregame_pending: bool = True
    mulligan_count: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    kept_hands: set[int] = field(default_factory=set)
    loyalty_activated_this_turn: set[str] = field(default_factory=set)
    priority_stops: dict[int, set[Step]] = field(
        default_factory=lambda: {
            1: {Step.UPKEEP, Step.PRECOMBAT_MAIN, Step.BEGIN_COMBAT, Step.DECLARE_ATTACKERS, Step.POSTCOMBAT_MAIN, Step.END_STEP},
            2: {Step.UPKEEP, Step.BEGIN_COMBAT, Step.DECLARE_BLOCKERS, Step.END_STEP},
        }
    )
    log: list[str] = field(default_factory=list)


class MatchFactory:
    @staticmethod
    def from_decks(deck_a: list[dict], deck_b: list[dict], player_a_name: str = "Player A", player_b_name: str = "Player B") -> MatchState:
        cards: dict[str, CardInstance] = {}
        p1 = PlayerState(id=1, name=player_a_name)
        p2 = PlayerState(id=2, name=player_b_name)
        for owner, deck, player in [(1, deck_a, p1), (2, deck_b, p2)]:
            expanded = []
            for item in deck:
                for _ in range(item["quantity"]):
                    expanded.append(item)
            random.shuffle(expanded)
            for raw_item in expanded:
                card_name = raw_item["card_name"]
                cid = str(uuid.uuid4())
                type_line = raw_item.get("type_line", "")
                types = _infer_types(card_name, type_line=type_line)
                card = CardInstance(
                    id=cid,
                    name=card_name,
                    owner=owner,
                    controller=owner,
                    zone=Zone.LIBRARY,
                    types=types,
                    mana_cost=raw_item.get("mana_cost", ""),
                    power=_infer_power(card_name, raw_item.get("power")),
                    toughness=_infer_toughness(card_name, raw_item.get("toughness")),
                    loyalty=_infer_loyalty(card_name, raw_item.get("loyalty"), types),
                    summoning_sick="Creature" in types,
                    keywords=_infer_keywords(raw_item.get("oracle_text", "") or ""),
                    oracle_text=raw_item.get("oracle_text", "") or "",
                    type_line=type_line,
                )
                cards[cid] = card
                player.library.append(cid)

        match = MatchState(id=str(uuid.uuid4()), players={1: p1, 2: p2}, cards=cards, stack=[])
        for pid in [1, 2]:
            for _ in range(7):
                draw_card(match, pid)
        match.log.append("Game start. Both players draw 7 and decide on London mulligans.")
        return match


def draw_card(state: MatchState, player_id: int, count: int = 1) -> None:
    from rules_engine.events import emit_event

    player = state.players[player_id]
    for _ in range(count):
        if not player.library:
            state.winner = 1 if player_id == 2 else 2
            state.log.append(f"{player.name} attempted to draw from empty library and loses.")
            return
        cid = player.library.pop()
        card = state.cards[cid]
        card.zone = Zone.HAND
        player.hand.append(cid)
        emit_event(state, "draw_card", {"player_id": player_id, "card_id": cid})


def _infer_types(name: str, type_line: str = "") -> list[str]:
    if type_line:
        line = type_line.lower()
        out = []
        for t in ["land", "creature", "instant", "sorcery", "enchantment", "artifact", "planeswalker"]:
            if t in line:
                out.append(t.capitalize())
        if out:
            return out
    n = name.lower()
    if any(k in n for k in ["island", "mountain", "forest", "plains", "swamp"]):
        return ["Land"]
    if any(k in n for k in ["teferi", "nissa", "ugin", "emperor"]):
        return ["Planeswalker"]
    if any(k in n for k in ["counterspell", "bolt", "push", "spike", "consider", "deluge", "ritual"]):
        return ["Instant"]
    if any(k in n for k in ["fable", "wedding", "massacre", "festival"]):
        return ["Enchantment"]
    if any(k in n for k in ["verdict", "farewell", "procession"]):
        return ["Sorcery"]
    return ["Creature"]


def _infer_power(name: str, power: str | int | None = None) -> int | None:
    if power is not None and str(power).isdigit():
        return int(power)
    n = name.lower()
    if "swiftspear" in n:
        return 1
    if "goblin guide" in n:
        return 2
    if "sheoldred" in n:
        return 4
    if "tarmogoyf" in n:
        return 4
    if "adeline" in n:
        return 4
    if any(k in n for k in ["island", "mountain", "forest", "plains", "swamp", "counterspell", "bolt", "consider"]):
        return None
    return 2


def _infer_toughness(name: str, toughness: str | int | None = None) -> int | None:
    if toughness is not None and str(toughness).isdigit():
        return int(toughness)
    n = name.lower()
    if "swiftspear" in n:
        return 2
    if "goblin guide" in n:
        return 2
    if "sheoldred" in n:
        return 5
    if "tarmogoyf" in n:
        return 5
    if "adeline" in n:
        return 4
    if any(k in n for k in ["island", "mountain", "forest", "plains", "swamp", "counterspell", "bolt", "consider"]):
        return None
    return 2


def _infer_loyalty(name: str, loyalty: str | int | None = None, types: list[str] | None = None) -> int | None:
    if loyalty is not None and str(loyalty).isdigit():
        return int(loyalty)
    if types and "Planeswalker" not in types:
        return None
    n = name.lower()
    if "teferi" in n:
        return 4
    if "nissa" in n:
        return 3
    if "ugin" in n:
        return 7
    if "emperor" in n:
        return 3
    return 4


def _infer_keywords(oracle_text: str) -> list[str]:
    text = (oracle_text or "").lower()
    out: list[str] = []
    for kw in ["trample", "first strike", "double strike", "haste", "flash", "lifelink", "deathtouch"]:
        if kw in text:
            out.append(kw)
    return out
