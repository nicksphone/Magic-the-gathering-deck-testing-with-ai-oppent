from __future__ import annotations
from rules_engine.type_effects import effective_types

import re
from typing import Any

from game_state.state import CardInstance, MatchState, Zone, object_incarnation
from card_data.token_definitions import named_artifact_token
from rules_engine.mana import choose_mana_color_for_player, parse_mana_cost
from rules_engine.oracle_text import without_reminder_text
from rules_engine.targeting import single_player_permanent_alternative, stack_object_kind, stack_source_card, validate_hexproof_shroud_targets, validate_protection_targets


DAMAGE_RE = re.compile(r"deals?\s+(\d+)\s+damage")
X_DAMAGE_RE = re.compile(r"deals?\s+x\s+damage")
DRAW_RE = re.compile(r"draw\s+(a|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?", re.IGNORECASE)
EACH_PLAYER_DRAW_RE = re.compile(r"each player draws? (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+|x) cards?\.?", re.IGNORECASE)
X_DRAW_RE = re.compile(r"draw\s+x\s+card")
GAIN_RE = re.compile(r"gains?\s+(\d+)\s+life")
LOSE_RE = re.compile(r"loses?\s+(\d+)\s+life")
LOSE_COUNT_RE = re.compile(r"loses?\s+life\s+equal\s+to\s+the\s+number\s+of\s+([a-z-]+)\s+you\s+control", re.IGNORECASE)
GAIN_CONTROL_RE = re.compile(r"gain control of\s+target\s+(creature|artifact|enchantment|permanent|planeswalker|land)", re.IGNORECASE)
PREVENT_RE = re.compile(r"prevent(?:s)? the next (\d+) damage")
SAC_RE = re.compile(r"sacrifice\s+(a|\d+)\s+creature")
COUNTER_RE = re.compile(r"put\s+(a|an|one|two|three|four|five|\d+)\s+\+1/\+1\s+counters?\s+on\s+(?:up to one )?target\s+(?:noncreature )?(creature|land|permanent)")
SELF_COUNTER_RE = re.compile(r"^\s*put\s+(a|an|one|two|three|four|five|\d+)\s+\+1/\+1\s+counters?\s+on\s+(this (?:creature|permanent|artifact|enchantment)|[^.]+)", re.IGNORECASE)
NAMED_COUNTER_RE = re.compile(
    r'put (a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+) '
    r'([a-z][a-z -]*?) counters? on (it|this (?:creature|permanent|artifact|enchantment)|'
    r'(?:up to one )?target (?:creature|permanent|artifact|enchantment|land|planeswalker)(?: you control)?)', re.I,
)
MANA_SYMBOL_RE = re.compile(r"\{([WUBRGC])\}")
TOKEN_PT_RE = re.compile(r"create[^.]*?(\d+)\/(\d+)")
TOKEN_COUNT_RE = re.compile(r"create\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|x|\d+)\b", re.IGNORECASE)
NAMED_ARTIFACT_TOKEN_RE = re.compile(r"create\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+([a-z]+)\s+tokens?\b", re.IGNORECASE)
TOKEN_REMINDER_ABILITY_RE = re.compile(r"\b(?:it's|they're|it is|they are)\s+(?:an?\s+)?artifacts?\s+with\s+[\"\u201c]([^\"\u201d]+)[\"\u201d]", re.IGNORECASE)
SAC_TOUGHNESS_TOKEN_RE = re.compile(r"if the sacrificed creature's toughness was (\d+) or greater, create (a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+) ([a-z]+) tokens? instead", re.IGNORECASE)
TOKEN_NAME_RE = re.compile(
    r"create\s+(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|x|\d+)\s+\d+/\d+\s+([a-z ]+?)\s+creature\s+tokens?",
    re.IGNORECASE,
)
TOKEN_CREATURE_ABILITY_RE = re.compile(r"creature tokens? with [\"\u201c]([^\"\u201d]+)[\"\u201d]", re.IGNORECASE)
TOKEN_COLOR_SYMBOLS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
TOKEN_COLOR_RE = re.compile(r"^(white|blue|black|red|green|colorless)(?: and (white|blue|black|red|green))?\s+(.+)$", re.IGNORECASE)
CHOOSE_ONE_RE = re.compile(r"choose one\s*[—-]\s*(.+)", re.IGNORECASE | re.DOTALL)
CHOOSE_TWO_RE = re.compile(r"choose two(?:\s*[—-]\s*(.+))?", re.IGNORECASE | re.DOTALL)
DIVIDE_RE = re.compile(r"(?:divid[^.]*damage|damage[^.]*divid)[^.]*among[^.]*targets", re.IGNORECASE)
DIVIDED_ONE_OR_TWO_RE = re.compile(r"\bdivided\b[^.]*\bamong one or two targets\b", re.IGNORECASE)
UP_TO_RE = re.compile(r"up to\s+(\d+)\s+target", re.IGNORECASE)
SEARCH_COUNT_RE = re.compile(r"search your library for (?:up to\s+)?(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+[^.]*?cards?", re.IGNORECASE)
SEARCH_MV_MAX_RE = re.compile(r"mana value\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+or less", re.IGNORECASE)
TARGET_MV_MAX_RE = re.compile(r"mana value\s+(?:less than or equal to\s+)?(\d+)\s+or less", re.IGNORECASE)
TARGET_MV_MIN_RE = re.compile(r"\btarget[^.\n]*\bwith mana value\s+(\d+)\s+or greater\b", re.IGNORECASE)
TARGET_MV_EXACT_RE = re.compile(r"\btarget[^.\n]*\bwith mana value\s+(\d+)(?=\s*[.;]|\s*$)", re.IGNORECASE)
TARGET_MV_GRAVEYARD_RE = re.compile(
    r"mana value\s+(?:less than or equal to\s+)?the number of cards in (?:its controller's|your) graveyard",
    re.IGNORECASE,
)
TARGET_MV_CONTROLLED_TYPE_RE = re.compile(
    r"mana value\s+(?:less than or equal to\s+)?the number of\s+([a-z]+)s?\s+you control",
    re.IGNORECASE,
)
COPY_STACK_RE = re.compile(r"copy target (instant or sorcery spell|permanent spell|spell|activated or triggered ability|activated ability|triggered ability)", re.IGNORECASE)
COPY_CREATURE_TOKEN_RE = re.compile(r"create a token that's a copy of (?:another )?target (?:nonlegendary )?creature you control", re.IGNORECASE)
COPY_SPELL_RE = COPY_STACK_RE
SPLIT_NAME_RE = re.compile(r"^(.+?)\s*//\s*(.+)$")
LOYALTY_ABILITY_RE = re.compile(r"([+-]?(?:\d+|X)):\s*([^\n]+)")
SAGA_CHAPTER_RE = re.compile(r"^\s*([IVX]+(?:\s*,\s*[IVX]+)*)\s*[—-]\s*(.+?)\s*$", re.IGNORECASE)
ACTIVATED_ABILITY_RE = re.compile(
    r"(?m)((?:\{[^{}]+\})+(?:\s*,\s*(?:(?:\{[^{}]+\})+|[^:\n]+))*)\s*:\s*([^\n]+)"
)
TARGET_TYPE_UNION_RE = re.compile(
    r'\btarget ((?:nonbasic )?(?:artifact|creature|enchantment|planeswalker|land)'
    r'(?:, (?:nonbasic )?(?:artifact|creature|enchantment|planeswalker|land))*'
    r',? or (?:nonbasic )?(?:artifact|creature|enchantment|planeswalker|land))\b')
UNTARGETED_GRAVEYARD_RETURN_RE = re.compile(
    r'return (?:a|an|one) (creature|planeswalker|artifact|enchantment)'
    r'(?: or (creature|planeswalker|artifact|enchantment))? card from your graveyard to your hand')
DESTROY_CONTROLLER_SEARCH_RE = re.compile(
    r"destroy target ([^.]+)\. that player may search their library for a land card "
    r"with a basic land type, put it onto the battlefield, then shuffle\.?$")


def spell_resolution_text(card: CardInstance, oracle_text: str) -> str:
    if not set(getattr(card, "types", []) or []).intersection({"Instant", "Sorcery"}):
        return oracle_text
    from rules_engine.foretell import resolution_text
    oracle_text = resolution_text(card, oracle_text)
    return "\n".join(
        line for line in oracle_text.splitlines()
        if not ACTIVATED_ABILITY_RE.match(line.strip())
        and without_reminder_text(line).strip().lower() != 'split second'
    )
CREW_RE = re.compile(r"\bcrew\s+(\d+)\b", re.IGNORECASE)
LOOK_TOP_RE = re.compile(r"look at the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?", re.IGNORECASE)
REVEAL_TOP_DISTINCT_TYPES_RE = re.compile(
    r"reveal the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards? of your library\.\s*"
    r"for each card type, you may put a card of that type from among the revealed cards into your hand",
    re.IGNORECASE,
)
LOOK_TOP_MANA_SPENT_HAND_RE = re.compile(
    r"look at the top x cards of your library, where x is the amount of mana spent to cast this spell\.\s*"
    r"put (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+) of them into your hand "
    r"and the rest on the bottom of your library in a random order",
    re.IGNORECASE,
)
LOOK_TOP_CHOICE_RE = re.compile(
    r"look at the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?.*?"
    r"(?:put\s+)?one(?: of them)? into your hand.*?"
    r"(?:put\s+)?one(?: of them)? on the bottom.*?"
    r"(?:put\s+)?(?:exile\s+)?one(?: of them)?(?: into exile)?",
    re.IGNORECASE,
)
LOOK_CREATURE_TO_HAND_RE = re.compile(
    r"look at the top\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+cards?.*?creature card with\s+(power|mana value)\s+(\d+)\s+or less.*?put it into your hand",
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
PUT_LANDS_FROM_TOP_RE = re.compile(
    r"put up to\s+(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+land cards?\s+from among them onto the battlefield tapped",
    re.IGNORECASE,
)
LOOT_RE = re.compile(r"draw\s+(a|\d+)\s+card[s]?\s*,?\s*then\s*discard\s+(a|\d+)\s+card", re.IGNORECASE)
REVEAL_CHOOSE_HAND_RE = re.compile(
    r"target (?P<target_kind>opponent|player) reveals (?:their|his or her) hand\. "
    r"you choose a (?P<restriction>noncreature, nonland |nonland |creature or planeswalker )?card from it"
    r"(?: with mana value (?P<mv>\d+) or (?P<comparison>less|greater))?"
    r"(?:\. that player discards that card\.|(?P<exile> and exile that card\.))"
    r"(?: you lose (?P<life>\d+) life\.)?", re.IGNORECASE,
)
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
    r"counter target (?P<kind>noncreature )?(?P<objects>spell(?: or ability)?|(?:activated or triggered |activated |triggered )?ability) unless its controller pays\s+(?P<cost>\{[^}]+\}(?:\{[^}]+\})*)",
    re.IGNORECASE,
)


def _counter_unless_kinds(match):
    objects = match['objects'].lower()
    if objects == 'spell or ability':
        return ['spell', 'activated', 'triggered']
    if objects in {'ability', 'activated or triggered ability'}:
        return ['activated', 'triggered']
    return [objects.split()[0]]


COUNTER_TARGET_SPELL_RE = re.compile(
    r"\bcounter target (?:(?:noncreature|creature|artifact|enchantment|planeswalker|instant|sorcery) )?spell\b",
    re.IGNORECASE,
)
ALL_CREATURES_X_DEBUFF_RE = re.compile(r"\b(?:all creatures get|each creature gets) -x/-x until end of turn\b", re.IGNORECASE)
TARGET_PT_CHANGE_RE = re.compile(r"target creature gets ([+-]\d+)/([+-]\d+) until end of turn\.?", re.IGNORECASE)
TARGET_PT_KEYWORDS_RE = re.compile(
    r'target creature(?: you control| an opponent controls)? gets ([+-]\d+)/([+-]\d+)'
    r'(?: and gains (.+?))? until end of turn\.?', re.I)


def parse_temporary_target_buff(text):
    match = TARGET_PT_KEYWORDS_RE.fullmatch(text.strip())
    if match is None:
        return None
    from rules_engine.continuous import _attached_keywords
    keywords = _attached_keywords((match[3] or '').lower())
    if keywords is None or any(keyword.startswith('ward') for keyword in keywords):
        return None
    return {'power': int(match[1]), 'toughness': int(match[2]), 'keywords': keywords}


def infer_effect_from_oracle(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
    *,
    report_unsupported: bool = True,
) -> tuple[str, dict[str, Any]]:
    from rules_engine.kicker import spell_kicker_view
    card = spell_kicker_view(card)
    action_targets = action_targets or {}
    if set(getattr(card, 'types', []) or []).intersection({'Instant', 'Sorcery'}):
        from rules_engine.foretell import spell_variants, record
        variants = spell_variants(card.oracle_text)
        if variants:
            from copy import copy
            branches = []
            for text in variants:
                proxy = copy(card)
                proxy.oracle_text = text
                proxy.card_faces = []
                key, data = infer_effect_from_oracle(state, proxy, controller, action_targets,
                                                   report_unsupported=report_unsupported)
                branches.append({'effect_key': key, 'payload': data})
            return 'foretell_spell', {'branches': branches,
                                     'was_foretold': bool(getattr(card, 'was_foretold', False) or record(card))}
    # A real planeswalker card's loyalty lines are activated later, not cast as
    # one combined spell effect. Loyalty proxies intentionally do not carry
    # the Planeswalker type and continue through the normal parser below.
    if "Planeswalker" in (effective_types(state, card) or []):
        return "noop", {}
    card, oracle, name = _resolve_effective_card_surface(card, action_targets)
    oracle = without_reminder_text(spell_resolution_text(card, oracle))
    from rules_engine.linked_targets import linked_damage_instruction, linked_damage_effect
    if linked_damage_instruction(oracle, card.name):
        from copy import copy
        proxy = copy(card)
        proxy.oracle_text = oracle
        return linked_damage_effect(state, proxy, action_targets)
    from rules_engine.landfall import alternative_effect
    landfall = alternative_effect(oracle, action_targets)
    if landfall:
        return landfall
    damage_gain = re.fullmatch(
        rf'(?:{re.escape(card.name.lower())}|this spell) deals (\d+) damage to '
        r'(?:any target|target creature|target player|target opponent|target planeswalker) '
        r'and you gain (\d+) life\.?', oracle.strip(), re.I)
    if damage_gain:
        damage_clause, gain_clause = oracle.rsplit(' and ', 1)
        damage = _infer_clause_effect(state, card, controller, damage_clause, action_targets, 0)
        return 'effect_sequence', {'effects': [
            {'effect_key': damage[0], 'payload': damage[1], 'clause_text': damage_clause},
            {'effect_key': 'gain_life', 'payload': {'amount': int(damage_gain[2])},
             'clause_text': gain_clause},
        ]}
    from rules_engine.ordered_targets import ordered_counter_allocations, ordered_creature_modifiers
    modifiers = ordered_creature_modifiers(oracle)
    if modifiers:
        ids = action_targets.get('target_card_ids') or []
        if len(ids) != len(modifiers) or any(cid not in state.cards for cid in ids):
            return 'noop', {}
        effects = []
        for target_id, modifier in zip(ids, modifiers):
            target = state.cards[target_id]
            effects.append({'effect_key': 'temporary_pt_buff', 'payload': {
                'target_card_id': target_id, 'power': modifier['power'], 'toughness': modifier['toughness'],
                '__target_incarnation': object_incarnation(target),
                '__target_zone_sequence': target.zone_change_sequence}})
        return 'effect_sequence', {'effects': effects, '__ordered_target_instances': True}
    allocation = ordered_counter_allocations(oracle)
    if allocation:
        effects = []
        for target_id, amount in zip(action_targets.get('target_card_ids', []), allocation['amounts']):
            target = state.cards[target_id]
            effects.append({'effect_key': 'add_counters', 'payload': {
                'target_card_id': target_id, 'counter': allocation['counter'], 'amount': amount,
                '__target_incarnation': object_incarnation(target),
                '__target_zone_sequence': target.zone_change_sequence}})
        return 'effect_sequence', {'effects': effects, '__ordered_distinct_targets': True}
    sacrifice_damage = re.fullmatch(
        r"(?:as an additional cost to cast this spell, sacrifice a creature\.\s*)?"
        + re.escape(card.name.lower())
        + r" deals damage equal to the sacrificed creature's power to any target\.",
        oracle.strip(),
    )
    if sacrifice_damage:
        paid = getattr(card, 'paid_cost_context', {}).get('sacrificed_creatures', [])
        amount = max(0, int(paid[0]['power'])) if len(paid) == 1 else 0
        return 'deal_damage', {**action_targets, 'amount': amount}
    from rules_engine.keyword_triggers import next_turn_draw_instruction
    delayed_lines = [(line, next_turn_draw_instruction(line)) for line in oracle.splitlines()]
    if any(instruction is not None for _, instruction in delayed_lines):
        from copy import copy
        proxy = copy(card)
        proxy.oracle_text = '\n'.join(line for line, instruction in delayed_lines if instruction is None)
        proxy.card_faces = []
        effects = []
        if proxy.oracle_text.strip():
            key, data = infer_effect_from_oracle(state, proxy, controller, action_targets,
                                               report_unsupported=report_unsupported)
            effects.append({'effect_key': key, 'payload': data})
        effects.extend({'effect_key': 'schedule_next_turn_draw',
                        'payload': {**instruction, 'source_card_id': card.id}}
                       for _, instruction in delayed_lines if instruction is not None)
        return 'effect_sequence', {'effects': effects}
    from rules_engine.devotion import devotion_instruction
    devotion = devotion_instruction(oracle, card.name)
    if devotion is not None:
        return 'devotion_effect', {**action_targets, 'devotion': devotion,
                                   'source_incarnation': object_incarnation(card)}
    if re.search(r"choose a creature card exiled with .+? with (?:mana value|converted mana cost) x\.\s*.+? becomes a copy of that card", oracle):
        return "copy_linked_exiled_card", {
            "source_card_id": card.id, "x_value": int(action_targets.get("x_value", 0) or 0),
            "source_timestamp": object_incarnation(state.cards[card.id]),
        }
    linked_hand_exile = re.search(
        r"each opponent reveals their hand\.\s*for each opponent, exile a creature card they revealed this way until [^.]+ leaves the battlefield",
        oracle,
    )
    if linked_hand_exile:
        return "choose_revealed_exile", {
            "target_player": 1 if controller == 2 else 2,
            "allowed_types": ["Creature"], "destination": "exile",
            "linked_source_id": card.id, "linked_source_timestamp": object_incarnation(card),
        }
    linked_exile = re.search(
        r"exile each nonland permanent with mana value (\d+) or less until this (?:enchantment|permanent|creature|artifact) leaves the battlefield",
        oracle,
    )
    if linked_exile:
        return "exile_nonland_until_source_leaves", {
            "mv_max": int(linked_exile.group(1)), "source_card_id": card.id,
            "source_timestamp": object_incarnation(card),
        }
    if re.search(r"\bdeals? x damage to each creature and each player\b", oracle, re.IGNORECASE):
        return "damage_each_creature_and_player", {"amount": max(0, int(action_targets.get("x_value", 0) or 0))}
    mode_text = action_targets.get("mode_text")
    mode_texts = _printed_mode_order(oracle, action_targets.get("mode_texts") or [])
    x_value = int(action_targets.get("x_value", 0) or 0)
    if re.search(r"exile all creatures\.\s+incubate x, where x is the number of creatures exiled this way", oracle):
        return "exile_all_creatures_incubate", {}
    if "exile this saga" in oracle and "return it to the battlefield transformed" in oracle:
        target = action_targets.get("target_card_id") or action_targets.get("source_card_id")
        if target:
            return "exile_return_transformed", {"target_card_id": target}
    if mode_text:
        oracle = without_reminder_text(mode_text.lower())
    elif mode_texts:
        effects = []
        for selected_mode in mode_texts:
            mode_target = (action_targets.get("mode_targets") or {}).get(selected_mode, {})
            key, payload = infer_effect_from_oracle(
                state, card, controller,
                {**action_targets, **mode_target, "mode_text": selected_mode, "mode_texts": []},
            )
            for effect in payload["effects"] if key == "effect_sequence" else [{"effect_key": key, "payload": payload}]:
                effects.append({**effect, "mode_text": selected_mode})
        return "effect_sequence", {"effects": effects}
    from rules_engine.linked_discard import linked_discard_effect, simultaneous_discard_draw_effect
    simultaneous = simultaneous_discard_draw_effect(oracle)
    if simultaneous:
        return 'each_player_discard', simultaneous
    linked_discard = linked_discard_effect(oracle)
    if linked_discard:
        return 'discard_cards', {'self_discard': True, **linked_discard}
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
            "stack_kinds": _counter_unless_kinds(unless_match),
            "pay_unless_counter": action_targets.get("pay_unless_counter"),
        }
    if COUNTER_TARGET_SPELL_RE.search(oracle):
        target_stack_id = action_targets.get("target_stack_id") or (state.stack[-1].id if state.stack else None)
        counter_payload = {
            "target_stack_id": target_stack_id,
            "target_kind": "noncreature" if "counter target noncreature spell" in oracle else "any",
        }
        # A destination changes only a successful counter; subsequent draw or
        # selection instructions still happen when the target is uncounterable.
        tail = COUNTER_TARGET_SPELL_RE.sub('', oracle, count=1).strip(' .\t\r\n')
        destination = re.match(
            r"if that spell is countered this way, put it into its owner's "
            r"(hand|exile) instead of into (?:their|that player's) graveyard\.\s*", tail)
        if destination:
            counter_payload['destination'] = destination[1]
            tail = tail[destination.end():].strip(' .\t\r\n')
        draw = DRAW_RE.fullmatch(tail)
        selection = re.fullmatch(r'(scry|surveil) (\d+)', tail)
        if draw or selection:
            followup_key = 'draw_cards' if draw else selection[1]
            amount = _parse_count_token(draw[1]) if draw else int(selection[2])
            return 'effect_sequence', {'effects': [
                {'effect_key': 'counter_spell', 'payload': counter_payload},
                {'effect_key': followup_key, 'payload': {'amount': amount}},
            ]}
        return 'counter_spell', counter_payload
    graveyard_exile = re.fullmatch(
        r'exile target card from (?:a|your) graveyard\.'
        r'(?:\s*draw (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?\.?)?',
        oracle.strip())
    if graveyard_exile:
        exile = {'effect_key': 'exile_from_graveyard',
                 'payload': {'target_card_id': action_targets.get('target_card_id')}}
        if graveyard_exile[1]:
            return 'effect_sequence', {'effects': [exile, {
                'effect_key': 'draw_cards',
                'payload': {'amount': _parse_count_token(graveyard_exile[1])},
            }]}
        return exile['effect_key'], exile['payload']
    revealed_choice = REVEAL_CHOOSE_HAND_RE.fullmatch(oracle.strip())
    if revealed_choice:
        restriction = (revealed_choice.group("restriction") or "").lower()
        destination = "exile" if revealed_choice.group("exile") else "discard"
        effect = {"effect_key": f"choose_revealed_{destination}", "payload": {
            "target_player": action_targets.get("target_player", 1 if controller == 2 else 2),
            "excluded_types": (["Creature"] if "noncreature" in restriction else [])
                              + (["Land"] if "nonland" in restriction else []),
            "allowed_types": ["Creature", "Planeswalker"] if "creature or planeswalker" in restriction else [],
            "destination": destination,
        }}
        if revealed_choice.group("mv"):
            bound = "mv_max" if revealed_choice.group("comparison").lower() == "less" else "mv_min"
            effect["payload"][bound] = int(revealed_choice.group("mv"))
        life = revealed_choice.group("life")
        if life:
            return "effect_sequence", {"effects": [effect, {
                "effect_key": "lose_life", "payload": {"target_player": controller, "amount": int(life)},
            }]}
        return effect["effect_key"], effect["payload"]
    if ("counter target activated ability" in oracle or "counter target triggered ability" in oracle
            or "counter target activated or triggered ability" in oracle):
        target_stack_id = action_targets.get("target_stack_id") or (state.stack[-1].id if state.stack else None)
        kind = "ability" if "counter target activated or triggered ability" in oracle else (
            "activated" if "counter target activated ability" in oracle else "triggered"
        )
        return "counter_ability", {
            "target_stack_id": target_stack_id,
            "target_kind": kind,
        }
    copy_match = COPY_STACK_RE.search(oracle)
    if copy_match and state.stack:
        target_stack_id = action_targets.get("target_stack_id") or state.stack[-1].id
        kind = str(copy_match.group(1) or "spell").strip().lower()
        effect_key = "copy_spell" if kind.endswith("spell") else "copy_ability"
        return effect_key, {"target_stack_id": target_stack_id, "copy_kind": kind,
                            "may_choose_new_targets": "you may choose new targets for the copy" in oracle}
    distinct_types = REVEAL_TOP_DISTINCT_TYPES_RE.search(oracle)
    if distinct_types:
        return "look_top_distinct_types_to_hand", {
            "top_n": _parse_count_token(distinct_types.group(1)),
            "bottom_random": "bottom of your library in a random order" in oracle,
        }
    topdeck_creatures = _infer_topdeck_creature_put_effect(oracle, action_targets)
    if topdeck_creatures is not None:
        return topdeck_creatures
    topdeck_permanents = _infer_topdeck_permanent_put_effect(oracle, action_targets)
    if topdeck_permanents is not None:
        return topdeck_permanents
    creature_to_hand = LOOK_CREATURE_TO_HAND_RE.search(oracle)
    if creature_to_hand:
        payload = {
            "top_n": _parse_count_token(creature_to_hand.group(1)),
            "bottom_random": "bottom" in oracle and "random order" in oracle,
            "optional": "may reveal" in oracle,
        }
        payload["power_max" if creature_to_hand.group(2) == "power" else "mv_max"] = int(creature_to_hand.group(3))
        return "topdeck_reveal_creature_to_hand", payload
    exile_playable = EXILE_TOP_PLAYABLE_RE.search(oracle)
    if exile_playable:
        return "exile_top_cards_playable", {"amount": _parse_count_token(exile_playable.group(1))}
    if REVEAL_DEFENDING_TOP_LAND_RE.search(oracle):
        return "reveal_defending_top_land", {
            "target_player": action_targets.get("target_player", 1 if controller == 2 else 2),
        }
    mana_spent_hand = LOOK_TOP_MANA_SPENT_HAND_RE.search(oracle)
    if mana_spent_hand:
        return "look_top_select_hand", {
            "hand_count": _parse_count_token(mana_spent_hand.group(1)),
            "top_n_source": "mana_spent_to_cast",
            "bottom_random": True,
        }
    top_choice = LOOK_TOP_CHOICE_RE.search(oracle)
    if top_choice:
        return "look_top_choose", {"top_n": _parse_count_token(top_choice.group(1))}
    controller_search = DESTROY_CONTROLLER_SEARCH_RE.fullmatch(oracle.strip())
    if controller_search:
        return 'destroy_with_controller_search', {'target_card_id': action_targets.get('target_card_id'),
            'search_payload': {'contains': 'land_with_basic_type', 'destination': 'battlefield',
                               'count': 1, 'shuffle': True, 'optional': True}}
    search_effect = _infer_search_effect(oracle, action_targets)
    if search_effect is not None:
        if re.search(r"you gain 1 life for each \{s\} spent to cast this spell", oracle):
            return "effect_sequence", {"effects": [
                {"effect_key": search_effect[0], "payload": search_effect[1]},
                {"effect_key": "gain_life", "payload": {"amount_source": "snow_mana_spent"}},
            ]}
        return search_effect

    linked_return = re.fullmatch(
        r'(?:put|return) target creature card from (?:a|your) graveyard '
        r'(?:onto|to) the battlefield under your control\.\s*'
        r"you lose life equal to that card's mana value\.?", oracle.strip())
    if linked_return:
        return 'return_creature_from_graveyard_to_battlefield', {
            'target_card_id': action_targets.get('target_card_id'),
            'lose_life_equal_to_mana_value': True,
        }
    clauses = _split_clauses(oracle)
    effects: list[tuple[str, dict[str, Any], str]] = []
    for clause in clauses:
        from rules_engine.combat_payments import temporary_combat_tax
        combat_tax = temporary_combat_tax(clause)
        if combat_tax:
            effects.append(('set_combat_cost', {**combat_tax,
                            'mana_cost': combat_tax['mana_cost'].replace('{X}', f'{{{max(0, x_value)}}}'),
                            'source_name': card.name, 'clause': clause}, clause))
            continue
        effects.extend((key, payload, clause) for key, payload in _infer_turn_restriction_effects(clause, controller))
        scry_clause = re.fullmatch(r'(scry|surveil) (\d+),?', clause)
        if scry_clause:
            effects.append((scry_clause[1], {'amount': int(scry_clause[2])}, clause))
            continue
        named_counter = NAMED_COUNTER_RE.fullmatch(clause)
        if named_counter:
            target = card.id if named_counter[3].startswith('this ') else action_targets.get('target_card_id')
            if target:
                effects.append(('add_counters', {'target_card_id': target, 'counter': named_counter[2].lower(),
                                                'amount': _parse_count_token(named_counter[1])}, clause))
            continue
        inferred = _infer_clause_effect(state, card, controller, clause, action_targets, x_value)
        if inferred is not None:
            # The existing land-animation handler already performs its untap.
            if inferred[0] == "untap" and any(
                payload.get("animate_untap")
                and payload.get("target_card_id") == inferred[1].get("target_card_id")
                for _, payload, _ in effects
            ):
                continue
            if (
                inferred[0] == "add_counters"
                and inferred[1].get("target_card_id")
                and "becomes a 0/0" in oracle
                and ("target land" in oracle or "target noncreature land" in oracle)
            ):
                inferred[1]["animate_land"] = True
                inferred[1]["animate_keywords"] = [keyword for keyword in ("vigilance", "haste") if keyword in oracle]
                inferred[1]["animate_untap"] = "untap it" in oracle
            effects.append((*inferred, clause))
    if len(effects) >= 2:
        return "effect_sequence", {"effects": [{"effect_key": k, "payload": v, "clause_text": clause} for k, v, clause in effects]}
    if len(effects) == 1:
        return effects[0][0], effects[0][1]

    if not oracle and not card.oracle_text and set(effective_types(state, card)).intersection({'Instant', 'Sorcery'}):
        if report_unsupported:
            state.log.append(f'Oracle effect not inferred for {card.name}: missing spell Oracle text; no effect fabricated.')
        return 'noop', {}

    # Static-only/keyword text often has no explicit resolver-side action.
    # Treat those as no-op without warning to keep logs focused on real misses.
    if _looks_static_or_keyword_only(card.oracle_text or "") or _is_event_layer_resolved(card.oracle_text or ""):
        return "noop", {}
    # Fallback: log uninferrable oracle text instead of silent no-op.
    if report_unsupported:
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
    # Active objects/proxies already carry their current characteristics. Only
    # an explicit casting choice may replace them with a printed card face.
    raw_index = action_targets.get("selected_face_index")
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
        "sacrifice", "tap target", "tap another target", "untap", "gain", "lose", "discard", "mill", "put ",
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
        "bottom_random": "bottom of your library in a random order" in oracle,
        "bottom_any_order": "bottom of your library in any order" in oracle,
    }
    return "topdeck_put_creatures_battlefield", payload


def _infer_search_effect(oracle: str, action_targets: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    if "search your library for" not in oracle:
        return None
    contains = action_targets.get("search_contains")
    count = action_targets.get("search_count")
    mv_max = action_targets.get("search_mv_max")
    if not contains:
        colored = re.search(r'search your library for (?:a|an|one) (white|blue|black|red|green) '
                            r'(artifact|creature|enchantment|land|planeswalker|battle|permanent) card', oracle)
        if colored:
            contains = colored[1] + '_' + colored[2]
        elif "snow permanent card" in oracle and "legendary card" in oracle and "saga card" in oracle:
            contains = "snow_or_legendary_or_saga"
        elif "land card with a basic land type" in oracle:
            contains = "land_with_basic_type"
        elif "basic land" in oracle:
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
        elif re.search(r"search your library for (?:up to )?(?:a|an|one|\d+) card(?:,|\.)", oracle):
            contains = "card"
    if count is None:
        count_match = SEARCH_COUNT_RE.search(oracle)
        if count_match:
            count = _parse_count_token(count_match.group(1))
        else:
            count = 1
    if mv_max is None:
        mv_match = SEARCH_MV_MAX_RE.search(oracle)
        if mv_match:
            mv_max = _parse_count_token(mv_match.group(1))
    split_destination = ("put one onto the battlefield tapped" in oracle
                         and ("the other into your hand" in oracle or "the rest into your hand" in oracle))
    search_clause = oracle[oracle.index("search your library for"):].split(".", 1)[0]
    destination = (
        "split_battlefield_hand" if split_destination else
        "graveyard" if re.search(r"\bput (?:that card|them|it|those cards?) into your graveyard\b", search_clause) else
        "battlefield" if "onto the battlefield" in search_clause else "hand"
    )
    payload: dict[str, Any] = {"contains": contains, "destination": destination}
    if "search your library for up to " in search_clause:
        payload["up_to"] = True
    if re.search(r"\breveal\b", search_clause):
        payload["reveal"] = True
    if "onto the battlefield tapped" in oracle:
        payload["tapped"] = True
    if "shuffle" in oracle:
        payload["shuffle"] = True
    if count is not None:
        payload["count"] = int(count)
    if mv_max is not None:
        payload["mv_max"] = int(mv_max)
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
    if needle == "card":
        matched = True
    elif re.fullmatch(r'(white|blue|black|red|green)_(artifact|creature|enchantment|land|planeswalker|battle|permanent)', needle):
        from rules_engine.colors import card_color_names
        color, kind = needle.split('_', 1)
        matched = color in card_color_names(card) and (
            bool(card_types.intersection({'artifact', 'enchantment', 'creature', 'land', 'planeswalker', 'battle'}))
            if kind == 'permanent' else kind in card_types)
    elif needle == "snow_or_legendary_or_saga":
        permanent = bool(card_types.intersection({"artifact", "enchantment", "creature", "land", "planeswalker", "battle"}))
        supertypes = set(type_line_parts[0].split()) | card_types
        matched = (permanent and "snow" in supertypes) or "legendary" in supertypes or "saga" in subtypes
    elif needle == "basic_land":
        matched = "basic" in type_line_parts[0].split() and "land" in card_types
    elif needle == "land_with_basic_type":
        matched = 'land' in card_types and bool(subtypes.intersection({'plains', 'island', 'swamp', 'mountain', 'forest'}))
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
    land_match = PUT_LANDS_FROM_TOP_RE.search(oracle)
    if not look_match or not (put_match or land_match):
        return None
    payload = {
        "top_n": max(1, int(action_targets.get("top_n", _parse_count_token(look_match.group(1))) or 1)),
        "max_permanents": max(1, int(action_targets.get("max_permanents", _parse_count_token((put_match or land_match).group(1))) or 1)),
        "bottom_random": "bottom of your library in a random order" in oracle,
        "bottom_any_order": "bottom of your library in any order" in oracle,
    }
    if land_match:
        payload.update({"allowed_type": "Land", "tapped": True})
    else:
        payload["mv_max"] = max(0, int(action_targets.get("mv_max", _parse_count_token(put_match.group(2))) or 0))
    return "topdeck_put_permanents_battlefield", payload


def inspect_target_hints(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from rules_engine.kicker import spell_kicker_view
    card = spell_kicker_view(card)
    raw_oracle = spell_resolution_text(card, card.oracle_text or "")
    action_targets = action_targets or {}
    selected_modes = _printed_mode_order(raw_oracle, action_targets.get("mode_texts") or [])
    selected_mode = action_targets.get("mode_text") or (selected_modes[0] if len(selected_modes) == 1 else None)
    oracle = without_reminder_text(str(" ".join(selected_modes) if selected_modes else selected_mode or raw_oracle).lower())
    hints: dict[str, Any] = {}
    from rules_engine.linked_targets import linked_damage_instruction, linked_target_hints
    if linked_damage_instruction(oracle, card.name):
        return linked_target_hints(state, card, controller)
    from rules_engine.ordered_targets import ordered_counter_allocations, ordered_creature_modifiers
    modifiers = ordered_creature_modifiers(oracle)
    if modifiers:
        hints['required_target_instance_count'] = len(modifiers)
        hints['ordered_creature_modifiers'] = modifiers
    allocation = ordered_counter_allocations(oracle)
    if allocation:
        hints['required_distinct_target_count'] = len(allocation['amounts'])
        hints['ordered_counter_amounts'] = allocation['amounts']
        hints['ordered_counter_type'] = allocation['counter']
    opponent = 1 if controller == 2 else 2
    graveyard_only_target = bool(re.search(r"\btarget\b[^.\n]{0,100}\bfrom\b[^.\n]{0,50}\bgraveyard\b", oracle))
    graveyard_creatures = [
        {"id": cid, "name": state.cards[cid].name, "owner": state.cards[cid].owner, "controller": state.cards[cid].controller}
        for pid in state.players
        for cid in getattr(state.players[pid], "graveyard", [])
        if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        and ("your graveyard" not in oracle or pid == controller)
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
    # X is announced for a mana cost or an explicitly supported additional cost.
    # Do not require x_value for cards whose oracle text references X contextually
    # (e.g. "where X is..." or cycling text) without an announced-cost X.
    from rules_engine.costs import PAY_X_LIFE_RE
    from rules_engine.spell_cost_clauses import spell_additional_costs
    resource_x = [branch for branch in spell_additional_costs(raw_oracle, card.name) or [] if branch.get('discard_x')]
    if resource_x:
        hints['requires_x_value'] = True
        from rules_engine.zone_actions import is_departed_token
        available = sum(cid != card.id and not is_departed_token(state.cards[cid]) for cid in state.players[controller].hand)
        hints['x_value_max'] = max(0, available - min(branch.get('discard_cards', 0) for branch in resource_x))
    if "{x}" in (card.mana_cost or "").lower() or PAY_X_LIFE_RE.search(raw_oracle):
        hints["requires_x_value"] = True
    if PAY_X_LIFE_RE.search(raw_oracle):
        from rules_engine.replacement import can_pay_life
        hints["x_value_max"] = max(0, state.players[controller].life) if can_pay_life(state, controller, 1) else 0
    up_to_match = UP_TO_RE.search(oracle)
    if up_to_match:
        hints["up_to_target_count"] = int(up_to_match.group(1))

    top_choice = LOOK_TOP_CHOICE_RE.search(oracle)
    if top_choice:
        hints["top_choice"] = {"top_n": _parse_count_token(top_choice.group(1))}

    # The cards are unknown until resolution; never peek during legal-move generation.
    topdeck_effect = _infer_topdeck_creature_put_effect(oracle, {}) or _infer_topdeck_permanent_put_effect(oracle, {})
    if topdeck_effect is not None:
        _, topdeck_payload = topdeck_effect
        hints["topdeck_choice"] = {
            "top_n": topdeck_payload["top_n"],
            "max_count": topdeck_payload.get("max_creatures", topdeck_payload.get("max_permanents")),
            "allow_zero": True,
        }

    if (COUNTER_TARGET_SPELL_RE.search(oracle)
            or "counter target activated ability" in oracle or "counter target triggered ability" in oracle
            or "counter target activated or triggered ability" in oracle or COUNTER_UNLESS_PAY_RE.search(oracle)
            or COPY_STACK_RE.search(oracle)):
        stack_restrictions = infer_target_restrictions(state, oracle, controller)
        allowed_kinds = set()
        if unless_match := COUNTER_UNLESS_PAY_RE.search(oracle):
            allowed_kinds.update(_counter_unless_kinds(unless_match))
        if COUNTER_TARGET_SPELL_RE.search(oracle):
            allowed_kinds.add("spell")
        if "counter target activated ability" in oracle:
            allowed_kinds.add("activated")
        if "counter target triggered ability" in oracle:
            allowed_kinds.add("triggered")
        if "counter target activated or triggered ability" in oracle:
            allowed_kinds.update(("activated", "triggered"))
        if "counter target spell or ability" in oracle or "counter target ability" in oracle:
            allowed_kinds.update(("activated", "triggered"))
        for match in COPY_STACK_RE.finditer(oracle):
            kind = match.group(1)
            if kind.endswith("spell"):
                allowed_kinds.add("spell")
            elif kind == "activated or triggered ability":
                allowed_kinds.update(("activated", "triggered"))
            else:
                allowed_kinds.add(kind.split()[0])
        stack_targets = []
        for item in state.stack:
            source = stack_source_card(state, item)
            if source is None or stack_object_kind(state, item) not in allowed_kinds:
                continue
            if ("ability you control" in oracle or "spell you control" in oracle) and item.controller != controller:
                continue
            if stack_restrictions and not _target_card_matches_restrictions(
                state, source, stack_restrictions, controller,
                x_value=int((item.payload or {}).get("x_value", 0) or 0),
            ):
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
    target_players = [1, 2]
    if re.search(r"target [^.\n]{0,65}\byou control\b", oracle):
        target_players = [controller]
    elif re.search(r"target [^.\n]{0,65}\b(?:an opponent|your opponent) controls\b", oracle):
        target_players = [opponent]
    if not graveyard_only_target and (re.search(r"\btarget (?:nonlegendary )?creature\b", oracle) or "destroy target" in oracle or "exile target" in oracle or "tap target" in oracle or "return target" in oracle):
        hints["creature_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in target_players for cid in state.players[pid].battlefield
            if "Creature" in effective_types(state, state.cards[cid])
            and ("nonlegendary creature" not in oracle or not _is_legendary_target(state.cards[cid]))
            and ("another target" not in oracle or cid != getattr(card, "id", None))
        ]
    if re.search(r"target (?:(?:basic|nonbasic|noncreature) )?land", oracle):
        land_players = [controller] if re.search(r"target (?:(?:basic|nonbasic|noncreature) )?land you control", oracle) else [opponent] if re.search(r"target (?:(?:basic|nonbasic|noncreature) )?land (?:an opponent|your opponent) controls", oracle) else [1, 2]
        hints["land_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in land_players
            for cid in state.players[pid].battlefield
            if "Land" in effective_types(state, state.cards[cid])
        ]
    if re.search(r"^enchant ", oracle, re.M):
        from rules_engine.attachments import attachment_target_is_legal
        aura_targets = [{"id": cid, "name": state.cards[cid].name}
                        for pid in state.players for cid in state.players[pid].battlefield
                        if attachment_target_is_legal(state, card, cid)]
        hints["aura_targets"] = aura_targets
        hints["creature_targets"] = aura_targets
    if not graveyard_only_target and ("target permanent" in oracle or "nonland permanent" in oracle or "target noncreature permanent" in oracle or "return target" in oracle):
        hints["permanent_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in target_players for cid in state.players[pid].battlefield
            if "nonland permanent" not in oracle or "Land" not in effective_types(state, state.cards[cid])
        ]
    if "artifact" in oracle:
        hints["artifact_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in target_players for cid in state.players[pid].battlefield
            if "Artifact" in effective_types(state, state.cards[cid])
        ]
    if "enchantment" in oracle:
        hints["enchantment_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in target_players for cid in state.players[pid].battlefield
            if "Enchantment" in effective_types(state, state.cards[cid])
        ]
    if "artifact" in oracle and "enchantment" in oracle:
        hints["noncreature_permanent_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in target_players for cid in state.players[pid].battlefield
            if ("Artifact" in effective_types(state, state.cards[cid]) or "Enchantment" in effective_types(state, state.cards[cid]))
        ]
    if "target" in oracle and "graveyard" in oracle and ("return" in oracle or "put" in oracle or "reanimate" in oracle or "exile target" in oracle):
        if re.search(r"(?:return|exile) target card from (?:your|a) graveyard", oracle):
            hints["graveyard_card_targets"] = [
                {"id": cid, "name": state.cards[cid].name}
                for pid in state.players for cid in state.players[pid].graveyard
                if "your graveyard" not in oracle or pid == controller
            ]
        else:
            hints["graveyard_creature_targets"] = graveyard_creatures
        graveyard_permanents = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in state.players
            for cid in state.players[pid].graveyard
            if any(t in {"Creature", "Artifact", "Enchantment", "Land", "Planeswalker"} for t in effective_types(state, state.cards[cid]))
            and ("your graveyard" not in oracle or pid == controller)
        ]
        graveyard_artifacts = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in state.players
            for cid in state.players[pid].graveyard
            if "Artifact" in effective_types(state, state.cards[cid])
            and ("your graveyard" not in oracle or pid == controller)
        ]
        graveyard_enchantments = [
            {"id": cid, "name": state.cards[cid].name}
            for pid in state.players
            for cid in state.players[pid].graveyard
            if "Enchantment" in effective_types(state, state.cards[cid])
            and ("your graveyard" not in oracle or pid == controller)
        ]
        if "artifact" in oracle:
            hints["graveyard_artifact_targets"] = graveyard_artifacts
        if "enchantment" in oracle:
            hints["graveyard_enchantment_targets"] = graveyard_enchantments
        if "permanent" in oracle or ("artifact" in oracle and "enchantment" in oracle):
            hints["graveyard_permanent_targets"] = graveyard_permanents if "permanent" in oracle else graveyard_artifacts + graveyard_enchantments
    if ("cast target" in oracle and "from your graveyard" in oracle
            or "target instant or sorcery card in your graveyard gains flashback" in oracle):
        hints["graveyard_spell_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[controller].graveyard
            if cid in state.cards and {"Instant", "Sorcery"}.intersection(effective_types(state, state.cards[cid]))
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
            "allow_zero": True,
        }
    divided_one_or_two = bool(DIVIDED_ONE_OR_TWO_RE.search(oracle))
    if "any target" in oracle or "any number of targets" in oracle or "target player" in oracle or divided_one_or_two:
        hints["player_targets"] = [
            {"id": 1, "name": state.players[1].name},
            {"id": 2, "name": state.players[2].name},
        ]
    elif "target opponent" in oracle:
        hints["player_targets"] = [{"id": opponent, "name": state.players[opponent].name}]
        hints["requires_opponent_target"] = True
    if REVEAL_CHOOSE_HAND_RE.fullmatch(raw_oracle.strip()):
        hints["requires_reveal_target"] = True
    alternative = single_player_permanent_alternative(oracle)
    if alternative:
        hints["single_target_alternative"] = True
        allowed_players = [opponent] if "opponent" in alternative else [1, 2]
        hints["player_targets"] = [{"id": pid, "name": state.players[pid].name} for pid in allowed_players]
        kind = next(kind for kind in ("creature", "planeswalker", "permanent", "artifact", "enchantment", "land") if kind in alternative)
        hints[f"{kind}_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for player in state.players.values() for cid in player.battlefield
            if kind == "permanent" or kind.capitalize() in effective_types(state, state.cards[cid])
        ]
    if DIVIDE_RE.search(oracle):
        hints["supports_divide"] = True
        if divided_one_or_two:
            hints["divide_max_targets"] = 2
    if "any target" in oracle or "any number of targets" in oracle or divided_one_or_two:
        hints["creature_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for player in state.players.values()
            for cid in player.battlefield
            if "Creature" in effective_types(state, state.cards[cid])
        ]
        hints["planeswalker_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for player in state.players.values()
            for cid in player.battlefield
            if "Planeswalker" in effective_types(state, state.cards[cid])
        ]
    elif "target creature or planeswalker" in oracle:
        hints["planeswalker_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if "Planeswalker" in effective_types(state, state.cards[cid])
        ]
    restrictions = infer_target_restrictions(state, oracle, controller)
    if TARGET_TYPE_UNION_RE.search(oracle) or 'combat_status' in restrictions:
        hints['permanent_targets'] = [
            {'id': cid, 'name': state.cards[cid].name}
            for pid in target_players for cid in state.players[pid].battlefield
        ]
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
    if "player_targets" in hints:
        hints["player_targets"] = [
            target for target in hints["player_targets"]
            if validate_hexproof_shroud_targets(state, controller, {"target_player": target["id"]})[0]
        ]
    source = card if isinstance(card, CardInstance) else state.cards.get(getattr(card, "id", None), card)
    for key in (
        "creature_targets", "planeswalker_targets", "permanent_targets", "land_targets",
        "artifact_targets", "enchantment_targets", "noncreature_permanent_targets", "aura_targets",
    ):
        if key in hints:
            hints[key] = [
                target for target in hints[key]
                if (validate_hexproof_shroud_targets(state, controller, {"target_card_id": target["id"]}, source)[0]
                    and validate_protection_targets(state, source, {"target_card_id": target["id"]})[0])
            ]
    return hints


def clause_target_assignments(
    state: MatchState, card: CardInstance, controller: int,
    announced: dict[str, Any], effects: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Map separate Oracle clauses to at most one announced target each."""
    from copy import copy

    selections = []
    for effect in effects:
        clause = effect.get("clause_text")
        if not clause:
            return None
        clause_card = copy(card)
        clause_card.oracle_text = clause
        hints = inspect_target_hints(state, clause_card, controller, announced)
        card_target = "target" in clause and any(key in hints for key in (
            "creature_targets", "planeswalker_targets", "permanent_targets", "land_targets",
            "artifact_targets", "enchantment_targets", "graveyard_card_targets", "graveyard_creature_targets", "graveyard_permanent_targets",
        ))
        allowed = {"target_card_id": card_target, "target_player": "player_targets" in hints,
                   "target_stack_id": "stack_targets" in hints}
        selected = {
            key: effect.get("payload", {}).get(key)
            for key in allowed
            if allowed[key] and announced.get(key) is not None and effect.get("payload", {}).get(key) == announced[key]
        }
        if len(selected) > 1:
            return None
        selections.append(selected)
    return selections


def infer_target_restrictions(state: MatchState, oracle_text: str, controller: int) -> dict[str, Any]:
    """Extract reusable restrictions for targeted permanent choices.

    This intentionally describes legality rather than naming cards. The same
    metadata supports target hints, human validation, AI materialization, and
    future stack-resolution rechecks.
    """
    oracle = without_reminder_text((oracle_text or "").lower())
    restrictions: dict[str, Any] = {}
    if "nonartifact" in oracle:
        restrictions.setdefault("exclude_types", []).append("Artifact")
    if "nonland" in oracle:
        restrictions.setdefault("exclude_types", []).append("Land")
    if "noncreature" in oracle:
        restrictions.setdefault("exclude_types", []).append("Creature")
    if "nonenchantment" in oracle:
        restrictions.setdefault("exclude_types", []).append("Enchantment")

    type_union = TARGET_TYPE_UNION_RE.search(oracle)
    if type_union:
        restrictions['allowed_types'] = [value.title() for value in re.findall(
            r'\b(artifact|creature|enchantment|planeswalker|land)\b', type_union[1])]
        if 'nonbasic land' in type_union[1]:
            restrictions['nonbasic_land_only'] = True
    elif "target instant or sorcery spell" in oracle:
        restrictions["allowed_types"] = ["Instant", "Sorcery"]
    elif "target permanent spell" in oracle:
        restrictions["allowed_types"] = ["Artifact", "Battle", "Creature", "Enchantment", "Planeswalker"]
    elif "target creature or planeswalker" in oracle:
        restrictions["allowed_types"] = ["Creature", "Planeswalker"]
    elif "target artifact or enchantment" in oracle:
        restrictions["allowed_types"] = ["Artifact", "Enchantment"]
    elif re.search(r"\btarget (?:nonlegendary )?creature\b", oracle):
        restrictions["allowed_types"] = ["Creature"]
    elif "target planeswalker" in oracle:
        restrictions["allowed_types"] = ["Planeswalker"]
    elif "target artifact" in oracle:
        restrictions["allowed_types"] = ["Artifact"]
    elif "target enchantment" in oracle:
        restrictions["allowed_types"] = ["Enchantment"]
    elif "target instant" in oracle:
        restrictions["allowed_types"] = ["Instant"]
    elif "target sorcery" in oracle:
        restrictions["allowed_types"] = ["Sorcery"]
    elif "target land" in oracle or "target noncreature land" in oracle:
        restrictions["allowed_types"] = ["Land"]
    combat = re.search(r'\btarget (attacking or blocking|attacking|blocking) creature\b', oracle)
    if combat:
        restrictions['allowed_types'] = ['Creature']
        restrictions['combat_status'] = combat[1]

    max_match = TARGET_MV_MAX_RE.search(oracle)
    min_match = TARGET_MV_MIN_RE.search(oracle)
    exact_match = TARGET_MV_EXACT_RE.search(oracle)
    if min_match:
        restrictions["mana_value_min"] = int(min_match.group(1))
    if exact_match:
        restrictions["mana_value_exact"] = int(exact_match.group(1))
    if max_match:
        restrictions["mana_value_max"] = int(max_match.group(1))
    elif TARGET_MV_GRAVEYARD_RE.search(oracle):
        restrictions["mana_value_max_source"] = "controller_graveyard"
    else:
        controlled_match = TARGET_MV_CONTROLLED_TYPE_RE.search(oracle)
        if controlled_match:
            restrictions["mana_value_max_source"] = f"controlled_{controlled_match.group(1).lower()}"
    return restrictions


def _is_legendary_target(card: CardInstance) -> bool:
    return ("Legendary" in (card.types or [])
            or "legendary" in (card.type_line or "").lower())


def _target_id_matches_restrictions(
    state: MatchState,
    card_id: str,
    restrictions: dict[str, Any],
    controller: int,
    x_value: int = 0,
) -> bool:
    return _target_card_matches_restrictions(state, state.cards.get(card_id), restrictions, controller, x_value)


def _target_card_matches_restrictions(state, card, restrictions, controller, x_value=0) -> bool:
    if card is None:
        return False
    types = set(effective_types(state, card) or [])
    excluded = set(restrictions.get("exclude_types") or [])
    if types.intersection(excluded):
        return False
    allowed = set(restrictions.get("allowed_types") or [])
    if allowed and not types.intersection(allowed):
        return False
    if (restrictions.get('nonbasic_land_only') and 'Land' in types
            and not types.intersection(allowed - {'Land'}) and 'Basic' in (card.type_line or '').split()):
        return False
    if restrictions.get('combat_status'):
        attacking = card.id in state.attackers
        blocking = any(card.id in ids for ids in state.blocks.values())
        status = restrictions['combat_status']
        if not (attacking if status == 'attacking' else blocking if status == 'blocking' else attacking or blocking):
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
            if subtype in {str(t).lower() for t in effective_types(state, state.cards[cid])}
            or subtype in str(state.cards[cid].type_line or "").lower().split()
        )
    min_value = restrictions.get("mana_value_min")
    exact_value = restrictions.get("mana_value_exact")
    if max_value is not None or min_value is not None or exact_value is not None:
        cost = parse_mana_cost(card.mana_cost or "", x_value=x_value)
        mana_value = int(cost.get("generic", 0) or 0) + int(cost.get("C", 0) or 0)
        mana_value += sum(int(cost.get(color, 0) or 0) for color in "WUBRG")
        if ((max_value is not None and mana_value > int(max_value))
                or (min_value is not None and mana_value < int(min_value))
                or (exact_value is not None and mana_value != int(exact_value))):
            return False
    return True


def _first_creature(state: MatchState, player_id: int) -> str | None:
    for cid in state.players[player_id].battlefield:
        if "Creature" in effective_types(state, state.cards[cid]):
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


def _printed_mode_order(oracle: str, selected: list[str]) -> list[str]:
    positions = {mode.casefold(): index for index, mode in enumerate(_extract_modes(oracle))}
    return sorted(selected, key=lambda mode: positions.get(str(mode).casefold(), len(positions)))


def _split_clauses(oracle: str) -> list[str]:
    cleaned = oracle.replace("\n", " ")
    parts = re.split(r"\.\s+|\s*;\s+|\s+then\s+", cleaned)
    out = []
    for part in parts:
        part = part.strip(' .;')
        if len(re.findall(r'\btarget creature\b', oracle, re.I)) == 1:
            part = re.sub(r'^(?:it|that creature) gets\b', 'target creature gets', part, flags=re.I)
        # Two unconditional instructions for the same announced recipient;
        # never promote a later part of an "if"/optional/quoted instruction.
        joined = re.fullmatch(r'(tap target (?:creature|artifact|land|permanent|enchantment|planeswalker)'
                              r'(?: (?:you control|an opponent controls))?) and (put .+ on it)', part)
        if joined and NAMED_COUNTER_RE.fullmatch(joined[2]):
            out.extend(joined.groups())
        elif part:
            out.append(part)
    return out


def extract_loyalty_abilities(card: CardInstance) -> list[dict[str, Any]]:
    oracle = (card.oracle_text or "").replace("\u2212", "-")
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
        symbols = [value.strip().upper() for value in match.group(1).split(',')]
        if any(symbol not in values for symbol in symbols):
            continue
        for roman in symbols:
            chapters.append({"number": values[roman], "text": match.group(2).strip(), "label": f"{roman} — {match.group(2).strip()}"})
    return sorted(chapters, key=lambda item: int(item["number"]))


def extract_activated_abilities(card: CardInstance) -> list[dict[str, Any]]:
    """Extract simple mana-cost activated abilities from a card surface."""
    out: list[dict[str, Any]] = []
    for index, match in enumerate(ACTIVATED_ABILITY_RE.finditer(without_reminder_text(card.oracle_text or ""))):
        cost = match.group(1).strip().upper()
        text = match.group(2).strip()
        # Mana abilities are handled by the mana source model and should not
        # be duplicated as stack actions here.
        if "add " in text.lower() and "target" not in text.lower() and not re.search(
                r'\b(?:draw|mill|library|libraries)\b', cost + ' ' + text, re.I):
            continue
        from rules_engine.activation_modifiers import ability_cost_modifier
        modifier = ability_cost_modifier(text)
        from rules_engine.costs import parse_activated_cost
        out.append({"index": index, "mana_cost": cost,
                    "text": modifier['effect_text'] if modifier else text,
                    "activation_zone": 'hand' if parse_activated_cost(cost).discard_source else 'battlefield',
                    "cost_modifier": modifier, "label": f"{cost}: {text}"})
    return out


def activation_source_eligible(state, player_id, card_id, ability):
    card = state.cards.get(card_id)
    zone = ability.get('activation_zone', 'battlefield')
    return (card is not None and card.zone.value == zone
            and card_id in getattr(state.players[player_id], zone)
            and (zone == 'hand' or card.controller == player_id))


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
    mill = re.fullmatch(r'mill (one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?,?', oracle.strip())
    if mill:
        return 'mill_cards', {'amount': _parse_count_token(mill[1])}
    recipient_mill = re.fullmatch(r'(target player|each opponent|you) mills? (one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?', oracle.strip())
    if recipient_mill:
        recipient = 3-controller if recipient_mill[1] == 'each opponent' else action_targets.get('target_player', 3-controller) if recipient_mill[1] == 'target player' else controller
        return 'mill_cards', {'target_player': recipient, 'amount': _parse_count_token(recipient_mill[2])}
    graveyard_return = UNTARGETED_GRAVEYARD_RETURN_RE.fullmatch(oracle.strip(' .'))
    if graveyard_return:
        return 'choose_graveyard_return', {'allowed_types': [value.title() for value in graveyard_return.groups() if value]}
    opponent = 1 if controller == 2 else 2
    target_player = action_targets.get("target_player")
    target_card_id = action_targets.get("target_card_id")

    self_damage = re.fullmatch(rf'(?:this spell|{re.escape(card.name.lower())}) deals (\d+) damage to you', oracle.strip(' .'))
    if self_damage:
        return 'deal_damage', {'target_player': controller, 'amount': int(self_damage[1])}
    if oracle.strip(' .') == 'proliferate':
        return 'proliferate', {}
    if oracle.strip(' .') == 'proliferate twice':
        return 'effect_sequence', {'effects': [{'effect_key': 'proliferate', 'payload': {}} for _ in range(2)]}
    if oracle.strip(" .") == "transform this artifact":
        return "transform_card", {"target_card_id": card.id, "face_index": 1}
    incubate_match = re.search(r"\bincubate\s+(\d+|x)\b", oracle)
    if incubate_match:
        raw = incubate_match.group(1)
        if raw == "x" and "where x is the number of lands you control" in oracle:
            amount = sum("Land" in effective_types(state, state.cards[cid]) for cid in state.players[controller].battlefield)
        elif raw == "x" and ("where x is" in oracle or "x_value" not in action_targets):
            return None
        else:
            amount = x_value if raw == "x" else int(raw)
        return "incubate", {"counters": amount, "times": 2 if re.search(r"\bincubate\s+(?:\d+|x)\s+twice\b", oracle) else 1}

    loss_text = oracle.strip(' .')
    temporary_loss = loss_text.startswith('until end of turn, ') or loss_text.endswith(' until end of turn')
    loss_text = loss_text.removeprefix('until end of turn, ').removesuffix(' until end of turn')
    loss = re.fullmatch(
        r'(target (?:creature|permanent|artifact)(?: you control| an opponent controls)?|it|this creature|creatures target player controls) '
        r'loses? all abilities(?: and (?:has|have) base power and toughness (\d+)/(\d+))?', loss_text,
    )
    if temporary_loss and loss:
        if loss[1] == 'creatures target player controls':
            payload = {'target_player': action_targets.get('target_player')}
        else:
            payload = {'target_card_id': card.id if loss[1] == 'this creature' else target_card_id}
        if any(value is not None for value in payload.values()):
            if loss[2] is not None:
                payload.update(base_power=int(loss[2]), base_toughness=int(loss[3]))
            return 'temporary_ability_loss', payload

    keyword_change = re.fullmatch(
        rf'(target (?:creature|permanent)(?: you control| an opponent controls)?|it|this (?:creature|permanent|artifact)|{re.escape(card.name.lower())}) '
        r'(gains|loses) (.+) until end of turn', oracle.strip(' .'),
    )
    if keyword_change:
        from rules_engine.continuous import _attached_keywords
        keywords = _attached_keywords(keyword_change[3])
        if keywords and all(keyword != 'ward' and not keyword.startswith('ward ') for keyword in keywords):
            subject = keyword_change[1]
            recipient = target_card_id if subject.startswith('target ') or subject == 'it' else card.id
            if recipient is not None:
                payload = {'target_card_id': recipient, 'until_end_of_turn': True}
                payload['keyword' if len(keywords) == 1 else 'keywords'] = keywords[0] if len(keywords) == 1 else keywords
                if keyword_change[2] == 'loses':
                    payload['operation'] = 'remove'
                return 'grant_keyword', payload

    targeted_pt = parse_temporary_target_buff(oracle)
    if targeted_pt:
        payload = {'target_card_id': target_card_id,
                   'power': targeted_pt['power'], 'toughness': targeted_pt['toughness']}
        if not targeted_pt['keywords']:
            return 'temporary_pt_buff', payload
        return 'effect_sequence', {'effects': [
            {'effect_key': 'temporary_pt_buff', 'payload': payload},
            {'effect_key': 'grant_keyword', 'payload': {
                'target_card_id': target_card_id, 'keywords': targeted_pt['keywords'], 'until_end_of_turn': True}},
        ]}

    if ALL_CREATURES_X_DEBUFF_RE.search(oracle):
        return "temporary_pt_buff_all", {"power": -x_value, "toughness": -x_value}

    tribal_buff = re.search(
        r"\b([a-z-]+) you control get ([+-]\d+)/([+-]\d+)"
        r"(?: and gain (haste|vigilance|trample|lifelink|deathtouch|flying|reach|menace|hexproof|indestructible))?"
        r" until end of turn\b",
        oracle,
    )
    if tribal_buff and tribal_buff.group(1) not in {
        "creatures", "tokens", "artifacts", "enchantments", "lands", "permanents", "planeswalkers",
    }:
        from rules_engine.card_types import creature_subtype_candidates

        return "temporary_pt_buff_all", {
            "power": int(tribal_buff.group(2)),
            "toughness": int(tribal_buff.group(3)),
            "controller_only": True,
            "keyword": tribal_buff.group(4),
            "creature_subtypes": sorted(creature_subtype_candidates(tribal_buff.group(1))),
            "creature_subtype_label": tribal_buff.group(1).title(),
        }

    team_buff = re.search(
        r"\bcreatures you control get ([+-]\d+)/([+-]\d+)"
        r"(?: and gain (haste|vigilance|trample|lifelink|deathtouch|flying|reach|menace|hexproof|indestructible))?"
        r" until end of turn\b",
        oracle,
    )
    if team_buff:
        return "temporary_pt_buff_all", {
            "power": int(team_buff.group(1)),
            "toughness": int(team_buff.group(2)),
            "controller_only": True,
            "keyword": team_buff.group(3),
        }

    if COPY_CREATURE_TOKEN_RE.search(oracle):
        return "create_token_copy", {
            "target_card_id": target_card_id,
            "grant_haste": "it has haste" in oracle,
            "sacrifice_next_end_step": "sacrifice it at the beginning of the next end step" in (card.oracle_text or "").lower(),
        }

    if "when you next cast a creature spell" in oracle and "additional +1/+1 counter" in oracle:
        return "set_next_creature_entry_counter", {"counter": "+1/+1", "amount": 1}

    if "exile this saga" in oracle and "return it to the battlefield transformed" in oracle:
        target = target_card_id or action_targets.get("source_card_id")
        if target:
            return "exile_return_transformed", {"target_card_id": target}

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
        if re.search(r"damage to (?:that|target) (?:creature|permanent)'s controller", oracle):
            return 'deal_damage_to_controller', {'target_card_id': target_card_id, 'amount': amount}
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

    each_draw = EACH_PLAYER_DRAW_RE.fullmatch(oracle.strip())
    if each_draw:
        raw = each_draw.group(1)
        amount = max(0, x_value) if raw.lower() == "x" else _parse_count_token(raw)
        return "effect_sequence", {"effects": [
            {"effect_key": "draw_cards", "payload": {"target_player": pid, "amount": amount}}
            for pid in (state.active_player, 1 if state.active_player == 2 else 2)
        ]}
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
                {"effect_key": "discard_cards", "payload": {"self_discard": True, "amount": disc_n}},
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
                if candidate and cast_from_graveyard.group(1).title() in effective_types(state, candidate):
                    target = cid
                    break
        # Keep the effect structured even when no qualifying graveyard card
        # exists yet. Move generation and target validation decide whether the
        # action is currently legal; parsing should not depend on board state.
        permission_text = action_targets.get('mode_text') or getattr(card, 'source_oracle_text', card.oracle_text or '')
        return "cast_from_graveyard", {"target_card_id": target,
            'exile_after_cast': bool(re.search(r'without paying its mana cost\.\s*if that spell would be put into your graveyard, exile it instead', permission_text.lower()))}

    if "destroy all artifacts and enchantments" in oracle or "destroy all artifact and enchantment" in oracle:
        return "destroy_all_artifacts_and_enchantments", {}
    if "destroy all artifacts" in oracle:
        return "destroy_all_artifacts", {}
    if "destroy all enchantments" in oracle:
        return "destroy_all_enchantments", {}
    if "exile all creatures" in oracle:
        return "exile_all_creatures", {}
    if "exile all graveyards" in oracle:
        return "exile_all_graveyards", {}
    if re.fullmatch(
        r"exile each permanent with mana value x or less that(?:'s| is) one or more colors\.?",
        oracle.strip(),
    ):
        return "exile_colored_permanents_mana_value_at_most", {"mv_max": x_value}

    if "exile target" in oracle and "artifact" in oracle and "enchantment" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Artifact", "Enchantment"})
        if target:
            return "exile", {"target_card_id": target}
    if "destroy target" in oracle and "artifact" in oracle and "enchantment" in oracle:
        target = _choose_noncreature_permanent_target(state, controller, action_targets, allowed_types={"Artifact", "Enchantment"})
        if target:
            return "destroy_permanent", {"target_card_id": target}
    if "destroy target" in oracle and ("nonland permanent" in oracle or "target noncreature permanent" in oracle):
        target = _choose_any_permanent_target(state, controller, action_targets,
                                            exclude_types={"Land"} if "nonland permanent" in oracle else {"Creature"})
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

    if "return target" in oracle and "to its owner's hand" in oracle and "permanent" in oracle:
        target = _choose_any_permanent_target(
            state, controller, action_targets,
            exclude_types={"Land"} if "nonland permanent" in oracle else set(),
        )
        if target:
            return "return_permanent_to_hand", {"target_card_id": target}
    if "return target" in oracle and "to its owner's hand" in oracle and TARGET_TYPE_UNION_RE.search(oracle):
        restrictions = infer_target_restrictions(state, oracle, controller)
        target = target_card_id or next((cid for pid in [opponent, controller]
            for cid in state.players[pid].battlefield
            if _target_id_matches_restrictions(state, cid, restrictions, controller)), None)
        if target:
            return 'return_permanent_to_hand', {'target_card_id': target}
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

    if re.search(r'\btap all creatures your opponents control\b',oracle):
        return "tap_all_opponent_creatures", {}

    if re.search(r'\btap (?:another )?target\b',oracle):
        if "nonland permanent" in oracle:
            target = _choose_any_permanent_target(state, controller, action_targets, exclude_types={"Land"})
        else:
            target = target_card_id or _first_creature(state, opponent)
        if target:
            return "tap", {"target_card_id": target}

    if re.fullmatch(r'untap (?:target (?:(?:nonland|noncreature|tapped) )?(?:artifact|creature|land|permanent)(?: you control| an opponent controls)?|it|that (?:creature|artifact|land|permanent))',oracle.strip(' .')):
        target = target_card_id
        if target:
            return "untap", {"target_card_id": target}

    if "return target" in oracle and "graveyard" in oracle and "hand" in oracle:
        return "return_from_graveyard", {"target_card_id": target_card_id}
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
            count_match = SEARCH_COUNT_RE.search(oracle)
            if count_match:
                count = _parse_count_token(count_match.group(1))
            else:
                count = 1
        if mv_max is None:
            mv_match = SEARCH_MV_MAX_RE.search(oracle)
            if mv_match:
                mv_max = _parse_count_token(mv_match.group(1))
        split_destination = ("put one onto the battlefield tapped" in oracle
                             and ("the other into your hand" in oracle or "the rest into your hand" in oracle))
        destination = "split_battlefield_hand" if split_destination else "battlefield" if "onto the battlefield" in oracle else "hand"
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
        token_count = (max(0, x_value) if count_match.group(1).lower() == 'x'
                       else _parse_count_token(count_match.group(1))) if count_match else 1
        token_name_match = TOKEN_NAME_RE.search(oracle)
        token_name = "Token"
        token_colors: list[str] = []
        if token_name_match:
            token_name = token_name_match.group(1).strip().title()
            color_match = TOKEN_COLOR_RE.match(token_name)
            if color_match:
                token_name = color_match.group(3)
                token_colors = [TOKEN_COLOR_SYMBOLS[color.lower()] for color in color_match.groups()[:2] if color and color.lower() in TOKEN_COLOR_SYMBOLS]
        token_keywords = _extract_keywords_from_text(oracle)
        out = {
            "name": token_name,
            "power": int(token_match.group(1)),
            "toughness": int(token_match.group(2)),
            "amount": token_count,
            "keywords": token_keywords,
            "colors": token_colors,
        }
        if token_name_match:
            out["type_line"] = f"Token Creature — {token_name}"
        if "tapped and attacking" in oracle:
            out["tapped_and_attacking"] = True
        if re.search(r"\bfor each basic land type among lands you control\b", oracle):
            out["per_basic_land_type"] = True
        followup = re.search(r'(?:^|\.\s+)' + re.escape(oracle.rstrip(' .'))
                             + r'\.\s+they gain ([a-z ]+) until end of turn(?:\.|$)',
                             (card.oracle_text or '').lower().strip())
        if followup:
            out['temporary_keywords'] = _extract_keywords_from_text(followup[1])
        quoted_ability = TOKEN_CREATURE_ABILITY_RE.search(getattr(card, "source_oracle_text", card.oracle_text or ""))
        if quoted_ability:
            out["oracle_text"] = quoted_ability.group(1).strip()
        if SAC_AT_EOT_RE.search(oracle):
            out["sacrifice_next_end_step"] = True
        return "create_token", out

    named_token = NAMED_ARTIFACT_TOKEN_RE.search(oracle)
    source_oracle = getattr(card, "source_oracle_text", card.oracle_text or "")
    reminder_ability = TOKEN_REMINDER_ABILITY_RE.search(source_oracle)
    token_definition = named_artifact_token(named_token.group(2)) if named_token else None
    if named_token and (reminder_ability or token_definition) and " instead" not in oracle:
        token_name = named_token.group(2).title()
        amount = _parse_count_token(named_token.group(1))
        conditional = SAC_TOUGHNESS_TOKEN_RE.search(without_reminder_text(source_oracle))
        sacrificed_toughness = getattr(card, "sacrificed_toughness", None)
        if (conditional and conditional.group(3).lower() == token_name.lower()
                and sacrificed_toughness is not None and int(sacrificed_toughness) >= int(conditional.group(1))):
            amount = _parse_count_token(conditional.group(2))
        return "create_token", {
            "name": token_name, "amount": amount, "types": ["Artifact", "Token"],
            "type_line": token_definition["type_line"] if token_definition else f"Token Artifact - {token_name}",
            "oracle_text": reminder_ability.group(1).strip() if reminder_ability else token_definition["oracle_text"],
        }

    self_counter = SELF_COUNTER_RE.search(oracle)
    if self_counter and getattr(card, "id", None) and (
        self_counter.group(2).lower().startswith("this ")
        or self_counter.group(2).strip().lower() == card.name.lower()
    ):
        return "add_counters", {
            "target_card_id": card.id, "counter": "+1/+1",
            "amount": _parse_count_token(self_counter.group(1)),
        }

    counters_match = COUNTER_RE.search(oracle)
    if counters_match:
        amount = _parse_count_token(counters_match.group(1))
        target = target_card_id
        if target is None and "up to one target" in oracle:
            return None
        if target is None and counters_match.group(2).lower() == "land":
            target = next(
                (cid for cid in state.players[controller].battlefield if "Land" in effective_types(state, state.cards[cid])),
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
                "animate_keywords": [keyword for keyword in ("vigilance", "haste") if keyword in oracle],
                "animate_untap": "untap it" in oracle,
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
        own_creatures = [cid for cid in state.players[controller].battlefield if "Creature" in effective_types(state, state.cards[cid])]
        if own_creatures and amount == 1:
            return "sacrifice", {"target_card_id": own_creatures[0]}

    if "discard" in oracle and "card" in oracle:
        each_discard = re.fullmatch(r"each player discards? (a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?( at random)?\.?", oracle.strip(), re.IGNORECASE)
        if each_discard:
            return "each_player_discard", {"amount": _parse_count_token(each_discard.group(1)), "random": bool(each_discard.group(2))}
        amount = 1
        if "two cards" in oracle:
            amount = 2
        if "three cards" in oracle:
            amount = 3
        if "you discard" in oracle or oracle.startswith("discard "):
            return "discard_cards", {"self_discard": True, "amount": amount, "random": "at random" in oracle}
        return "discard_cards", {"target_player": target_player or opponent, "amount": amount, "random": "at random" in oracle}

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
        if allowed_types.intersection(set(effective_types(state, target_card) or [])):
            return target_card_id
    opponent = 1 if controller == 2 else 2
    candidates: list[str] = []
    for cid in state.players[opponent].battlefield:
        card = state.cards.get(cid)
        if not card:
            continue
        if allowed_types.intersection(set(effective_types(state, card) or [])):
            candidates.append(cid)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda cid: (
            0 if "Artifact" in effective_types(state, state.cards[cid]) else 1,
            0 if "Enchantment" in effective_types(state, state.cards[cid]) else 1,
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
        if not exclude_types.intersection(set(effective_types(state, target_card) or [])):
            return target_card_id
    opponent = 1 if controller == 2 else 2
    candidates: list[str] = []
    for cid in state.players[opponent].battlefield:
        card = state.cards.get(cid)
        if not card:
            continue
        if exclude_types.intersection(set(effective_types(state, card) or [])):
            continue
        candidates.append(cid)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda cid: (
            0 if "Creature" in effective_types(state, state.cards[cid]) else 1,
            0 if "Artifact" in effective_types(state, state.cards[cid]) else 1,
            0 if "Enchantment" in effective_types(state, state.cards[cid]) else 1,
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
