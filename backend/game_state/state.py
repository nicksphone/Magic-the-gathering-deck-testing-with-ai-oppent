from __future__ import annotations

import random
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum


class Zone(str, Enum):
    LIBRARY = "library"
    HAND = "hand"
    BATTLEFIELD = "battlefield"
    GRAVEYARD = "graveyard"
    EXILE = "exile"
    STACK = "stack"
    CEASED = "ceased"


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

COUNTER_PERSISTENCE_RE = re.compile(
    r"\bcounters remain on .+? as it moves to any zone other than a player's hand or library\b",
    re.IGNORECASE,
)


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
    entered_turn: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    counter_timestamps: dict[str, int] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    keyword_effects: list[dict] = field(default_factory=list)
    base_stat_effects: list[dict] = field(default_factory=list)
    type_effects: list[dict] = field(default_factory=list)
    type_effect_base: list[str] | None = None
    oracle_text: str = ""
    type_line: str = ""
    image_uri: str | None = None
    attached_to: str | None = None
    static_order: int = 0
    # Monotonic timestamp for continuous/replacement effects. static_order is
    # retained as a compatibility alias for older snapshots and tests.
    effect_timestamp: int = 0
    battlefield_incarnation: int | None = None
    instance_order: int = 0
    zone_change_sequence: int = 0
    card_faces: list[dict] = field(default_factory=list)
    layout: str = ""
    selected_face_index: int | None = None
    chosen_creature_type: str | None = None
    printed_characteristics: dict = field(default_factory=dict)
    bestow_characteristics: dict = field(default_factory=dict)
    colors: list[str] | None = None
    is_token: bool = False
    last_known_battlefield: dict = field(default_factory=dict)
    exile_face_down: bool = False
    foretell_record: dict = field(default_factory=dict)
    granted_flashback: dict = field(default_factory=dict)
    was_foretold: bool = False
    was_kicked: bool = False
    printed_power: str | None = None
    printed_toughness: str | None = None

    def reset_zone_counters(self, zone: Zone) -> None:
        from rules_engine.type_effects import clear_type_effects
        clear_type_effects(self)
        self.keyword_effects.clear()
        self.base_stat_effects.clear()
        if zone not in {Zone.HAND, Zone.LIBRARY} and COUNTER_PERSISTENCE_RE.search(self.oracle_text or ""):
            self.counters = {key: value for key, value in self.counters.items() if not key.startswith("__")}
            self.counter_timestamps = {key: value for key, value in self.counter_timestamps.items() if self.counters.get(key, 0) > 0}
        else:
            self.counters.clear()
            self.counter_timestamps.clear()

    def move_to_zone(self, zone: Zone) -> None:
        if zone != self.zone and self.zone == Zone.BATTLEFIELD:
            from rules_engine.type_effects import clear_type_effects
            clear_type_effects(self)
        if zone != self.zone and not (self.zone == Zone.STACK and zone == Zone.BATTLEFIELD):
            self.was_kicked = False
        if zone not in {Zone.STACK, Zone.BATTLEFIELD} and self.bestow_characteristics:
            from rules_engine.bestow import end_bestow
            end_bestow(self)
        if zone != self.zone:
            self.foretell_record.clear()
            self.granted_flashback.clear()
            if not (self.zone == Zone.STACK and zone == Zone.BATTLEFIELD):
                self.was_foretold = False
            self.zone_change_sequence += 1
        # Battlefield deaths defer this reset until their die triggers have
        # consumed last-known counters and combat state.
        if zone != self.zone and (zone in {Zone.HAND, Zone.LIBRARY, Zone.EXILE}
                                  or zone == Zone.GRAVEYARD and self.zone != Zone.BATTLEFIELD):
            self.reset_zone_counters(zone)
        if zone != Zone.EXILE:
            self.exile_face_down = False
        self.zone = zone


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
    poison: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    library: list[str] = field(default_factory=list)
    hand: list[str] = field(default_factory=list)
    battlefield: list[str] = field(default_factory=list)
    graveyard: list[str] = field(default_factory=list)
    exile: list[str] = field(default_factory=list)
    exile_play_until: dict[str, int] = field(default_factory=dict)
    mana_pool: dict[str, int] = field(default_factory=lambda: {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0})
    snow_mana_pool: dict[str, int] = field(default_factory=lambda: {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0})
    restricted_mana_pool: list[dict] = field(default_factory=list)
    prevent_damage_shield: int = 0
    max_land_plays_this_turn: int = 1
    lands_played_this_turn: int = 0
    last_land_play_turn: int = 0
    land_plays_recorded_on_turn: int = 0


@dataclass
class MatchState:
    id: str
    players: dict[int, PlayerState]
    cards: dict[str, CardInstance]
    stack: list[StackItem]
    rng: random.Random = field(default_factory=random.Random)
    starting_decks: dict[int, list[dict]] = field(default_factory=dict)
    card_observations: dict[int, dict[str, dict]] = field(default_factory=dict)
    turn: int = 1
    active_player: int = 1
    priority_player: int = 1
    step: Step = Step.UNTAP
    passed_priority: set[int] = field(default_factory=set)
    attackers: list[str] = field(default_factory=list)
    attack_targets: dict[str, str] = field(default_factory=dict)
    attack_bands: list[list[str]] = field(default_factory=list)
    blocks: dict[str, list[str]] = field(default_factory=dict)
    attackers_declared: bool = False
    blockers_declared: bool = False
    combat_damage_resolved: bool = False
    combat_damage_stage: str = "none"
    first_strike_damage_ids: set[str] = field(default_factory=set)
    combat_damage_assignments: dict[str, dict[str, int]] = field(default_factory=dict)
    combat_assignment_queue: list[str] = field(default_factory=list)
    cleanup_pending: bool = False
    cleanup_repeat_required: bool = False
    cleanup_deferred_triggers: list[dict] = field(default_factory=list)
    delayed_triggers: list[dict] = field(default_factory=list)
    foretells_this_turn: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    winner: int | None = None
    failed_draw_players: set[int] = field(default_factory=set)
    best_of: int = 3
    score: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    pregame_pending: bool = True
    mulligan_count: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    kept_hands: set[int] = field(default_factory=set)
    mulligan_declarations: dict[int, str] = field(default_factory=dict)
    mulligan_bottomed: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    loyalty_activated_this_turn: set[str] = field(default_factory=set)
    trigger_once_seen_this_turn: set[str] = field(default_factory=set)
    priority_stops: dict[int, set[Step]] = field(
        default_factory=lambda: {
            1: {Step.UPKEEP, Step.PRECOMBAT_MAIN, Step.BEGIN_COMBAT, Step.DECLARE_ATTACKERS, Step.POSTCOMBAT_MAIN, Step.END_STEP},
            2: {Step.UPKEEP, Step.BEGIN_COMBAT, Step.DECLARE_BLOCKERS, Step.END_STEP},
        }
    )
    log: list[str] = field(default_factory=list)
    next_static_order: int = 1
    next_effect_timestamp: int = 1
    next_object_id: int = 1
    # Day/night is a game-wide state. Keep the previous turn's spell count so
    # the upkeep transition is deterministic and survives snapshot restore.
    day_night: str = "none"
    spells_cast_this_turn: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    kicked_spells_cast_this_turn: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    declared_attackers_this_turn: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    spells_cast_last_turn: int = 0
    draws_in_current_draw_step: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    draws_this_turn: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    surveils_this_turn: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    discards_this_turn: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    players_with_permanent_departure: set[int] = field(default_factory=set)
    temporary_control_changes: dict[str, dict[str, int]] = field(default_factory=dict)
    linked_exiles: list[dict] = field(default_factory=list)
    # Delayed entry modifications created by resolving effects such as Saga
    # chapters. Entries are consumed by the next matching spell this turn.
    pending_entry_counters: list[dict] = field(default_factory=list)
    adventure_permissions: dict[str, int] = field(default_factory=dict)
    # Restrictions created by resolving spells that last through cleanup.
    turn_cant_gain_life: set[int] = field(default_factory=set)
    combat_cost_effects: list[dict] = field(default_factory=list)
    turn_damage_cant_be_prevented: bool = False
    # Human-controlled matches can pause resolution when multiple replacement
    # effects apply. AI/replay runs keep deterministic automatic selection.
    replacement_choice_required: bool = False
    replacement_choice_players: set[int] = field(default_factory=set)
    mechanic_choice_players: set[int] = field(default_factory=set)
    pending_replacement_choice: dict | None = None
    trigger_order_choice_required: bool = False
    trigger_order_choice_players: set[int] = field(default_factory=set)
    trigger_staging: bool = False
    trigger_staging_event: str = "state_based_actions"
    staged_triggers: list[dict] = field(default_factory=list)
    pending_trigger_order: dict | None = None
    pending_mechanic_choice: dict | None = None

    def allocate_object_id(self) -> str:
        """Stable gameplay identities without consuming the shuffle RNG."""
        occupied = set(self.cards) | {item.id for item in self.stack}
        while True:
            identifier = str(uuid.UUID(int=self.next_object_id))
            self.next_object_id += 1
            if identifier not in occupied:
                return identifier


def pregame_actor(state: MatchState) -> int | None:
    """Pending pregame choice owner, otherwise the next undeclared player."""
    if state.pending_mechanic_choice and state.pending_mechanic_choice["kind"] in {"mulligan_bottom", "opening_hand", "opening_hand_exile"}:
        return state.pending_mechanic_choice["player_id"]
    return next((pid for pid in (state.active_player, 3 - state.active_player)
                 if pid not in state.kept_hands and pid not in state.mulligan_declarations), None)


class MatchFactory:
    @staticmethod
    def from_decks(
        deck_a: list[dict],
        deck_b: list[dict],
        player_a_name: str = "Player A",
        player_b_name: str = "Player B",
        seed: int | None = None,
    ) -> MatchState:
        cards: dict[str, CardInstance] = {}
        p1 = PlayerState(id=1, name=player_a_name)
        p2 = PlayerState(id=2, name=player_b_name)
        rng = random.Random(seed) if seed is not None else random
        for owner, deck, player in [(1, deck_a, p1), (2, deck_b, p2)]:
            expanded = []
            for item in deck:
                for _ in range(item["quantity"]):
                    expanded.append(item)
            rng.shuffle(expanded)
            for copy_index, raw_item in enumerate(expanded, start=1):
                card_name = raw_item["card_name"]
                cid = f"p{owner}-{copy_index:03d}"
                type_line = raw_item.get("type_line", "")
                # Scryfall combines double-faced type lines with `//`. Until
                # a face is selected, only the front face defines types.
                front_type_line = str(type_line).split("//", 1)[0].strip()
                if raw_item.get("layout") == "split" and raw_item.get("card_faces"):
                    front_type_line = " // ".join(str(face.get("type_line") or "") for face in raw_item["card_faces"])
                types = _infer_types(
                    card_name,
                    type_line=front_type_line,
                    mana_cost=raw_item.get("mana_cost", "") or "",
                    oracle_text=raw_item.get("oracle_text", "") or "",
                )
                card = CardInstance(
                    id=cid,
                    name=card_name,
                    owner=owner,
                    controller=owner,
                    zone=Zone.LIBRARY,
                    types=types,
                    mana_cost=raw_item.get("mana_cost", ""),
                    power=_infer_power(card_name, raw_item.get("power"), types),
                    toughness=_infer_toughness(card_name, raw_item.get("toughness"), types),
                    printed_power=str(raw_item['power']) if raw_item.get('power') is not None else None,
                    printed_toughness=str(raw_item['toughness']) if raw_item.get('toughness') is not None else None,
                    loyalty=_infer_loyalty(card_name, raw_item.get("loyalty"), types),
                    summoning_sick="Creature" in types,
                    keywords=_infer_keywords(raw_item.get("oracle_text", "") or ""),
                    oracle_text=raw_item.get("oracle_text", "") or "",
                    type_line=type_line,
                    image_uri=raw_item.get("image_uri"),
                    card_faces=list(raw_item.get("card_faces") or []),
                    layout=str(raw_item.get("layout") or ""),
                    selected_face_index=raw_item.get("selected_face_index"),
                    instance_order=copy_index,
                    colors=raw_item.get("colors"),
                )
                if card.card_faces and card.layout in {'transform', 'modal_dfc'}:
                    from rules_engine.card_faces import apply_transform_face
                    previous_selection = card.selected_face_index
                    apply_transform_face(card, 0)
                    card.selected_face_index = previous_selection
                    card.printed_characteristics['selected_face_index'] = previous_selection
                cards[cid] = card
                player.library.append(cid)

        match = MatchState(id=str(uuid.uuid4()), players={1: p1, 2: p2}, cards=cards, stack=[])
        match.starting_decks = {1: deepcopy(deck_a), 2: deepcopy(deck_b)}
        match.rng = rng if seed is not None else random.Random()
        for pid in [1, 2]:
            for _ in range(7):
                draw_card(match, pid)
        match.log.append("Game start. Both players draw 7 and decide on London mulligans.")
        return match


def draw_card(state: MatchState, player_id: int, count: int = 1) -> None:
    from rules_engine.events import emit_event
    from rules_engine.draw_restrictions import can_draw_card

    player = state.players[player_id]
    for _ in range(count):
        if player_id in state.failed_draw_players:
            return
        if not can_draw_card(state, player_id):
            return
        if not player.library:
            state.failed_draw_players.add(player_id)
            state.log.append(f"{player.name} attempted to draw from empty library.")
            return
        cid = player.library.pop()
        card = state.cards[cid]
        card.move_to_zone(Zone.HAND)
        player.hand.append(cid)
        if not state.pregame_pending:
            state.draws_this_turn[player_id] = state.draws_this_turn.get(player_id, 0) + 1
        if state.step == Step.DRAW and state.active_player == player_id:
            state.draws_in_current_draw_step[player_id] = state.draws_in_current_draw_step.get(player_id, 0) + 1
        emit_event(state, "draw_card", {"player_id": player_id, "card_id": cid})


def assign_static_order_on_battlefield_entry(state: MatchState, card_id: str) -> None:
    card = state.cards.get(card_id)
    if not card:
        return
    card.last_known_battlefield.clear()
    # Printed counter-persistence text is the exception; damage and temporary
    # modifiers still belong to the old object, not the entering permanent.
    card.reset_zone_counters(Zone.BATTLEFIELD)
    assign_effect_timestamp(state, card_id)
    card.battlefield_incarnation = card.effect_timestamp


def object_incarnation(card) -> int:
    value = getattr(card, "battlefield_incarnation", None)
    return int(value if value is not None else getattr(card, "effect_timestamp", 0) or getattr(card, "static_order", 0) or 0)


def allocate_effect_timestamp(state: MatchState) -> int:
    timestamp = max(
        int(getattr(state, "next_effect_timestamp", 1) or 1),
        int(getattr(state, "next_static_order", 1) or 1),
    )
    state.next_effect_timestamp = timestamp + 1
    state.next_static_order = timestamp + 1
    return timestamp


def assign_effect_timestamp(state: MatchState, card_id: str) -> None:
    card = state.cards[card_id]
    card.effect_timestamp = allocate_effect_timestamp(state)
    card.static_order = card.effect_timestamp


def _infer_types(name: str, type_line: str = "", mana_cost: str = "", oracle_text: str = "") -> list[str]:
    if type_line:
        from rules_engine.card_types import printed_card_types
        # The factory supplies both halves only for split-card identity.
        return list(dict.fromkeys(kind for face in type_line.split('//')
                                  for kind in printed_card_types(face)))
    n = name.lower()
    if not (mana_cost or "").strip() and n in {
        "plains", "island", "swamp", "mountain", "forest", "wastes",
        "hallowed fountain",
        "sacred foundry",
        "watery grave",
        "blood crypt",
        "overgrown tomb",
        "breeding pool",
        "stomping ground",
        "steam vents",
        "godless shrine",
        "temple garden",
    }:
        return ["Land"]
    if any(k in n for k in ["teferi", "nissa", "ugin", "emperor"]):
        return ["Planeswalker"]
    if any(
        k in n
        for k in [
            "counterspell",
            "bolt",
            "push",
            "spike",
            "consider",
            "deluge",
            "ritual",
            "growth spiral",
            "march of otherworldly light",
            "go for the throat",
            "drown in the loch",
            "skullcrack",
            "boros charm",
            "searing blaze",
            "spell pierce",
            "unholy heat",
            "deadly dispute",
            "village rites",
            "abrupt decay",
        ]
    ):
        return ["Instant"]
    if any(k in n for k in ["fable", "wedding", "massacre", "festival", "shark typhoon", "kumano", "ossification", "intangible virtue"]):
        return ["Enchantment"]
    if any(
        k in n
        for k in [
            "verdict",
            "farewell",
            "procession",
            "migration path",
            "cultivate",
            "lay down arms",
            "light up the stage",
            "lava spike",
            "storm the festival",
            "expressive iteration",
            "secure the wastes",
            "raise the alarm",
            "march of the multitudes",
            "claim the firstborn",
            "collected company",
        ]
    ):
        return ["Sorcery"]
    if "witch's oven" in n:
        return ["Artifact"]
    return ["Creature"]


def _infer_power(
    name: str,
    power: str | int | None = None,
    types: list[str] | None = None,
) -> int | None:
    if power is not None:
        return int(power) if re.fullmatch(r'[+-]?\d+', str(power)) else None
    if types is not None and "Creature" not in types:
        return None
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
    return None


def _infer_toughness(
    name: str,
    toughness: str | int | None = None,
    types: list[str] | None = None,
) -> int | None:
    if toughness is not None:
        return int(toughness) if re.fullmatch(r'[+-]?\d+', str(toughness)) else None
    if types is not None and "Creature" not in types:
        return None
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
    return None


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
    from rules_engine.oracle_text import without_reminder_text
    text = without_reminder_text(oracle_text or "").lower()
    out: list[str] = []
    if re.search(r"(?:^|[\n,])\s*training\b", text):
        out.append("training")
    # "Bands with other" is distinct from ordinary banding even though card
    # data sources may classify both under the broad Banding keyword.
    if re.search(r"(?:^|\n)\s*banding\b|,\s*banding\b", text):
        out.append("banding")
    for kw in [
        "trample",
        "first strike",
        "double strike",
        "haste",
        "flash",
        "lifelink",
        "deathtouch",
        "infect",
        "wither",
        "flying",
        "reach",
        "menace",
        "vigilance",
        "defender",
        "indestructible",
        "hexproof",
        "shroud",
        "shadow",
        "fear",
        "intimidate",
        "islandwalk",
        "swampwalk",
        "mountainwalk",
        "forestwalk",
        "plainswalk",
        "nonbasic landwalk",
        "snow landwalk",
        "desertwalk",
        "wasteswalk",
        "legendary landwalk",
    ]:
        if re.search(r'(?:^|[,\n])\s*' + re.escape(kw) + r'(?=\s*(?:[,\n.]|$))', text):
            out.append(kw)
    from rules_engine.protection import extract_protection_keywords
    for clause in re.findall(r"(?:^|[,\n])\s*protection from ([^.;,\n]+)", text):
        out.extend(extract_protection_keywords('protection from ' + clause))
    return out
