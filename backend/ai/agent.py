from __future__ import annotations
from rules_engine.type_effects import effective_types

import copy
import re
from itertools import combinations
from dataclasses import dataclass

from ai.endgame_policy import should_force_closure, should_force_inevitability_line
from ai.heuristics import evaluate_board, recurring_engine_value, repeatable_mana_value
from ai.log_priors import load_log_priors
from ai.matchup_profiles import profile_for
from card_data.tactical import tactical_tags
from game_state.state import CardInstance, MatchState, Step, Zone, object_incarnation
from rules_engine.engine import RulesEngine
from ai.pending_effects import planning_copy, prospective_creature_stats
from rules_engine import combat
from rules_engine.continuous import effective_combat_stats, effective_keywords, effective_power, effective_toughness, has_keyword
from rules_engine.card_types import is_land_card as _card_looks_like_land, is_token_card
from rules_engine.colors import card_color_names
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.restrictions import card_cant_block
from rules_engine.mana import can_pay_with_pool_and_lands, mana_value, parse_mana_cost
from rules_engine.replacement import graveyard_destination
from rules_engine.costs import PAY_X_LIFE_RE
from rules_engine.oracle_effects import ALL_CREATURES_X_DEBUFF_RE, EACH_PLAYER_DRAW_RE, _parse_count_token
from rules_engine.oracle_text import without_reminder_text
from rules_engine.targeting import spell_cant_be_countered, stack_object_kind


_PURE_COUNTER_SPELL_RE = re.compile(
    r"counter target (?:(?:noncreature|creature|artifact|enchantment|planeswalker|instant|sorcery) )?spell"
    r"(?: you (?:don't )?control)?(?: with mana value (?:\d+|x)(?: or (?:less|greater))?)?"
    r"(?: unless its controller pays (?:\{[^}]+\})+)?\.?", re.IGNORECASE,
)


def _only_counter_spell_text(text: str) -> bool:
    return bool(_PURE_COUNTER_SPELL_RE.fullmatch(without_reminder_text(text).strip()))


def _has_counter_spell_text(text: str) -> bool:
    return bool(re.search(r"\bcounter target(?: [a-z -]{0,45})?\b(?:spell|ability)\b",
                          without_reminder_text(str(text or "")).lower()))


def _oracle_text(card) -> str:
    return without_reminder_text(str(getattr(card, "oracle_text", "") or "")).lower()


def _card_for_move(state, move):
    card = state.cards.get(move.get("card_id"))
    if card and move.get("type") == "cast_spell" and getattr(card, "card_faces", None):
        from rules_engine.card_faces import select_cast_face
        card = select_cast_face(card, move.get("selected_face_index", 0))
    if card and move.get('cast_variant') == 'bestow':
        from rules_engine.bestow import bestow_cast_view
        card = bestow_cast_view(card)
    return card


def _fixed_color_pips(mana_cost: str) -> dict[str, int]:
    symbols = re.findall(r"\{([^{}]+)\}", (mana_cost or "").upper())
    return parse_mana_cost("".join(
        "{" + symbol + "}" for symbol in symbols if not _supported_hybrid_symbol(symbol)
    ))


def _supported_hybrid_symbol(symbol: str) -> bool:
    parts = symbol.split("/")
    return (len(parts) == 2 and all(part in {"W", "U", "B", "R", "G", "C", "2"} for part in parts)) or (
        len(parts) in {2, 3} and parts[-1] == "P" and all(part in {"W", "U", "B", "R", "G"} for part in parts[:-1])
    )


def _effective_combat_stats(state: MatchState, card_id: str) -> tuple[int, int]:
    """Read resolved combat stats, falling back safely for lightweight fixtures."""
    card = state.cards.get(card_id)
    if card is None:
        return (0, 0)
    try:
        return (int(effective_power(state, card_id)), int(effective_toughness(state, card_id)))
    except Exception:
        return (int(getattr(card, "power", 0) or 0), int(getattr(card, "toughness", 0) or 0))


@dataclass
class AIDecision:
    action: dict
    reasoning: str


def _shortlist_with_priority_pass(ranked: list[dict], legal: list[dict], limit: int) -> list[dict]:
    shortlist = ranked[:limit]
    if not any(move.get('type') == 'pass_priority' for move in shortlist):
        wait = next((move for move in legal if move.get('type') == 'pass_priority'), None)
        if wait is not None:
            shortlist.append(wait)
    return shortlist


class AIAgent:
    _log_priors_cache: dict | None = None

    def __init__(self, difficulty: str = "strong", archetype: str = "Midrange", opponent_archetype: str | None = None):
        self.difficulty = difficulty.lower()
        self.archetype = archetype
        self.opponent_archetype = opponent_archetype
        self.matchup_profile = profile_for(archetype, opponent_archetype)
        self.engine = RulesEngine()
        self._main_pass_signature_counts: dict[tuple, int] = {}
        if AIAgent._log_priors_cache is None:
            AIAgent._log_priors_cache = load_log_priors()

    def choose_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> AIDecision:
        from ai.pending_effects import decision_projection_scope
        from ai.information import decision_view
        state, legal_moves = decision_view(state, player_id, legal_moves)
        with decision_projection_scope(state, player_id):
            decision = self._choose_action(state, [move for move in legal_moves if move['type'] != 'foretell'], player_id)
            if decision.action.get('type') == 'pass_priority':
                from ai.foretell_policy import idle_foretell_action
                action = idle_foretell_action(self, state, legal_moves, player_id)
                if action:
                    decision = AIDecision(action=action, reasoning='Bank idle mana without displacing a play or known answer')
            from ai.declaration_policy import finalize_declaration
            return AIDecision(action=finalize_declaration(state, decision.action), reasoning=decision.reasoning)

    def _choose_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> AIDecision:
        trigger_choice = getattr(state, 'pending_trigger_order', None) or {}
        if trigger_choice.get('current_controller') == player_id and trigger_choice.get('phase') in {'targets', 'optional'}:
            choices = [move for move in legal_moves if move.get('type') in {'choose_trigger_target', 'choose_optional_effect'}]
            if choices:
                from ai.trigger_targets import choose_target
                action, known = choose_target(state, choices, player_id)
                return AIDecision(action=action, reasoning='Choose the best projected public trigger option' if known
                                  else 'Trigger continuation unknown; retain a legal option without claiming a forecast')
        if trigger_choice.get('current_controller') == player_id and trigger_choice.get('phase') != 'targets':
            from ai.trigger_policy import preferred_trigger_order
            group = trigger_choice.get('groups', {}).get(str(player_id), [])
            requested = [item['_choice_id'] for item in preferred_trigger_order(group, player_id)]
            move = next((move for move in legal_moves if move.get('type') == 'choose_trigger_order'
                         and move.get('trigger_order') == requested), None)
            if move:
                return AIDecision(action=move, reasoning='Order supported simultaneous effects by public creation/buff dependencies')
        pending = getattr(state, 'pending_replacement_choice', None)
        if pending and pending.get('event') == 'damage_to_permanent' and pending.get('player_id') == player_id:
            choices = [move for move in legal_moves if move.get('type') == 'choose_replacement']
            if choices:
                selected = next((move for move in choices
                                 if not str(move.get('replacement_source_id', '')).startswith('shield-counter:')), choices[0])
                return AIDecision(action=selected, reasoning='Apply free damage reduction before spending a shield counter')
        if pending and pending.get('resume_kind') == 'counter_event' and pending.get('player_id') == player_id:
            from ai.counter_policy import preferred_counter_option
            selected = preferred_counter_option(pending)
            move = next(move for move in legal_moves if move.get('replacement_source_id') == selected)
            return AIDecision(action=move, reasoning='Order counter replacements by resulting public counter amount')
        # Payment planning activates mana sources when a chosen action needs them.
        legal_moves = [move for move in legal_moves if not str(move.get("type", "")).endswith("_restricted")
                       and move.get('type') != 'activate_mana_ability']
        def useful_variable_sweep(move: dict) -> bool:
            if move.get("type") != "cast_spell":
                return True
            card = state.cards.get(move.get("card_id"))
            mana_cost = getattr(card, "mana_cost", "") or ""
            if "{X}" not in mana_cost.upper() or not ALL_CREATURES_X_DEBUFF_RE.search(getattr(card, "oracle_text", "") or ""):
                return True
            x_value = self._choose_x_value(state, player_id, mana_cost, card=card)
            return any(
                cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
                and effective_toughness(state, cid) <= x_value
                for cid in state.players[3 - player_id].battlefield
            )

        legal_moves = [move for move in legal_moves if useful_variable_sweep(move)]
        stack_items = getattr(state, "stack", []) or []
        if len(stack_items) == 1:
            item = stack_items[0]
            from rules_engine.targeting import stack_source_card
            source = stack_source_card(state, item)
            if (
                getattr(item, "controller", player_id) != player_id
                and source is not None
                and "Creature" in effective_types(state, source)
                and self._stack_item_threat_score(state, item.id, player_id) < 2.0
            ):
                legal_moves = [
                    move for move in legal_moves
                    if move.get("type") != "cast_spell"
                    or not self._is_counter_card(state.cards.get(move.get("card_id")))
                    or (move.get("target_hints") or {}).get("creature_targets")
                ]
        if stack_items and getattr(stack_items[-1], "controller", None) == player_id and getattr(stack_items[-1], "effect_key", None) in {"counter_spell", "counter_ability"}:
            covered_id = (getattr(stack_items[-1], "payload", {}) or {}).get("target_stack_id")
            uncovered_moves = []
            for move in legal_moves:
                hints = move.get("target_hints") or {}
                if move.get("type") != "cast_spell" or not self._is_counter_card(state.cards.get(move.get("card_id"))) or hints.get("creature_targets"):
                    uncovered_moves.append(move)
                    continue
                remaining = [target for target in hints.get("stack_targets", []) if target.get("id") != covered_id and target.get("id") != stack_items[-1].id]
                if remaining:
                    uncovered_moves.append({**move, "target_hints": {**hints, "stack_targets": remaining}})
            legal_moves = uncovered_moves
        pending_crews = {
            item.source_card_id for item in (getattr(state, "stack", []) or [])
            if getattr(item, "effect_key", None) == "crew_vehicle"
        }
        legal_moves = [
            move for move in legal_moves
            if move.get("type") != "crew"
            or (move.get("card_id") not in pending_crews
                and "Creature" not in (effective_types(state, state.cards.get(move.get("card_id"))) or []))
        ]
        legal_moves = [move for move in legal_moves if not self._burn_has_only_friendly_targets(state, move, player_id)]
        legal_moves = self._without_losing_life_actions(state, legal_moves, player_id)
        if getattr(state, "pregame_pending", False) and not any(move.get("type") == "choose_mechanic" for move in legal_moves):
            return self.choose_mulligan_action(state, player_id)
        if (
            getattr(state, "active_player", None) == player_id
            and getattr(state, "step", None) in {Step.UPKEEP, Step.DRAW}
            and not getattr(state, "stack", [])
        ):
            legal_moves = [move for move in legal_moves if move.get("type") != "cycle_card"]
        if not legal_moves:
            return AIDecision(action={"type": "pass_priority"}, reasoning="No legal actions")
        choice = next((move for move in legal_moves if move.get("type") == "choose_mechanic"), None)
        if choice:
            options = list(choice.get("options", []))
            if choice['kind'] == 'effect_cast':
                from ai.effect_cast_policy import usable_cast
                target = state.pending_mechanic_choice['effect_payload']['target_card_id']
                action = usable_cast(state, player_id, target)
                return AIDecision(action=action or {'type': 'choose_mechanic', 'card_ids': ['decline']},
                                  reasoning='Cast a supported usable graveyard spell or decline the permission')
            if choice['kind'] in {'surveil', 'surveil_top_order'}:
                selected = (self._surveil_graveyard_choices(state, options, player_id)
                            if choice['kind'] == 'surveil'
                            else self._choose_library_search(state, options, len(options), player_id))
                return AIDecision(action={'type': 'choose_mechanic', 'card_ids': selected},
                                  reasoning='Surveil from inspected cards, curve/fixing needs and known graveyard access')
            if choice['kind'] in {'scry', 'scry_top_order'}:
                selected = self._choose_library_search(state, options, len(options), player_id)
                if choice['kind'] == 'scry':
                    # Preserve curve/fixing resources; do not apply one land
                    # threshold to ramp, aggro and control alike.
                    lands = sum('Land' in effective_types(state, state.cards[cid]) for cid in state.players[player_id].hand)
                    lands += sum('Land' in effective_types(state, state.cards[cid]) for cid in state.players[player_id].battlefield)
                    known = state.players[player_id].hand + options
                    goal = max([3, *(mana_value(state.cards[cid].mana_cost) for cid in known
                                     if 'Land' not in effective_types(state, state.cards[cid]))])
                    demand = self._color_demand(state, player_id)
                    sources = self._current_color_sources(state, player_id)
                    selected = [cid for cid in reversed(selected) if 'Land' in effective_types(state, state.cards[cid])
                                and lands > goal + 1 and not any(demand.get(color, 0) and not sources.get(color, 0)
                                                               for color in self._land_colors(state.cards[cid], state))]
                return AIDecision(action={'type': 'choose_mechanic', 'card_ids': selected},
                                  reasoning='Scry using known inspected cards, current resources and library-search ordering')
            if choice['kind'] == 'proliferate':
                from ai.proliferation_policy import preferred_recipients
                from rules_engine.proliferation import recipients
                available = {key: value for key, value in recipients(state).items() if key in options}
                selected = preferred_recipients(state, player_id, available)
                return AIDecision(action={'type': 'choose_mechanic', 'card_ids': selected},
                                  reasoning='Evaluate all counter kinds together; avoid self-poison and strengthen favorable public recipients')
            if choice["kind"] in {"ward_payment", "ward_cost_cards", "counter_payment"}:
                selected = self._ward_selection(state, player_id, choice)
                return AIDecision(action={"type": "choose_mechanic", "card_ids": selected},
                                  reasoning="Compare stack payment with losing the targeted stack object")
            if choice['kind'] == 'optional_search':
                return AIDecision(action={'type': 'choose_mechanic', 'card_ids': ['search']},
                                  reasoning='Accept a supported optional land search')
            if choice['kind'] == 'graveyard_return':
                selected = max(options, key=lambda cid: (self._hand_retention_value(state, cid, player_id), cid))
                return AIDecision(action={'type': 'choose_mechanic', 'card_ids': [selected]},
                                  reasoning='Return the most useful eligible graveyard card after milling')
            if choice["kind"] == "opening_hand":
                # ponytail: free-entry heuristic; symmetric-effect matchup planning remains open.
                candidates = [cid for cid in options if cid in state.cards]
                candidates.sort(key=lambda cid: (-self._hand_retention_value(state, cid, player_id), cid))
                selected = candidates[0] if candidates else "__finish_opening__"
                return AIDecision(action={"type": "choose_mechanic", "card_ids": [selected]}, reasoning="Use supported free opening-hand permanent")
            if choice["kind"] in {"mulligan_bottom", "opening_hand_exile"}:
                options.sort(key=lambda cid: (self._hand_retention_value(state, cid, player_id), cid))
                return AIDecision(action={"type": "choose_mechanic", "card_ids": options[:choice["count"]]}, reasoning="Select least useful cards for required pregame instruction")
            if choice["kind"] == "copy_target":
                copied = next((item for item in state.stack if item.id == choice.get("stack_id")), None)
                if copied and choice.get('linked_target_index') is not None:
                    from ai.linked_targets import choose_linked_copy_option
                    selected = choose_linked_copy_option(self, state, player_id, choice)
                    return AIDecision(action={'type': 'choose_mechanic', 'card_ids': [selected]},
                                      reasoning='Choose a legal linked copy continuation from bounded public outcomes')
                opponent = 3 - player_id
                selected = "keep" if "keep" in options else options[0]
                if copied and (choice.get("mode_target_text") or choice.get("clause_effect_index") is not None
                               or choice.get('ordered_target_index') is not None
                               or copied.effect_key == 'landfall_alternative'):
                    if choice.get("mode_target_text"):
                        mode = choice["mode_target_text"]
                        effects = [effect for effect in copied.payload.get("effects", []) if effect.get("mode_text") == mode]
                        original = (copied.payload.get("__announced_targets", {}).get("mode_targets", {}).get(mode) or {})
                    elif choice.get('ordered_target_index') is not None:
                        index = int(choice['ordered_target_index'])
                        effects = (copied.payload.get('effects') or [])[index:index + 1]
                        original = {'target_card_id': copied.payload['__announced_targets']['target_card_ids'][index]}
                    elif copied.effect_key == 'landfall_alternative':
                        from rules_engine.land_history import landfall_status
                        status = landfall_status(state, copied.controller)
                        effects = [] if status is None else [copied.payload['branches'][int(status)]]
                        original = {key: value for key, value in copied.payload.get('__announced_targets', {}).items()
                                    if key in ('target_player', 'target_card_id', 'target_stack_id')}
                    else:
                        index = int(choice["clause_effect_index"])
                        effects = (copied.payload.get("effects") or [])[index:index + 1]
                        key = choice["clause_target_key"]
                        original = {key: copied.payload.get("__announced_targets", {}).get(key)}
                    if len(effects) == 1 and len(original) == 1:
                        effect = effects[0]
                        old_key, old_value = next(iter(original.items()))

                        def score_target(option: str) -> float:
                            key, value = (old_key, str(old_value)) if option == "keep" else option.split(":", 1)
                            if key == "target_player":
                                if effect["effect_key"] == "deal_damage":
                                    amount = int(effect.get("payload", {}).get("amount", 0) or 0)
                                    return 100.0 if int(value) == opponent and state.players[opponent].life <= amount else 3.0 if int(value) == opponent else -100.0
                                if effect["effect_key"] == "gain_life":
                                    from ai.life_targets import life_target_score
                                    score = life_target_score(state, player_id, int(value),
                                                             int(effect.get('payload', {}).get('amount', 0) or 0))
                                    if score is not None:
                                        return score
                                    return 5.0 if int(value) == player_id else -5.0
                                return 5.0 if int(value) == opponent else -5.0
                            if key == "target_stack_id" and effect["effect_key"] in {"counter_spell", "counter_ability"}:
                                target = next((item for item in state.stack if item.id == value), None)
                                return 10.0 if target and target.controller == opponent else -10.0
                            card = state.cards.get(value)
                            if card is None:
                                return -100.0
                            if effect["effect_key"] == "destroy_permanent":
                                return self._noncreature_permanent_threat_score(state, value, player_id)
                            if effect["effect_key"] == "return_permanent_to_hand":
                                return 4.0 + self._noncreature_permanent_threat_score(state, value, player_id) if card.controller == opponent else -5.0
                            if effect["effect_key"] == "deal_damage":
                                if card.controller == player_id:
                                    return -100.0
                                amount = int(effect.get("payload", {}).get("amount", 0) or 0)
                                toughness = effective_combat_stats(state, value)[1]
                                lethal = ("Creature" in effective_types(state, card) and toughness is not None
                                          and amount > 0 and toughness <= amount + int(card.counters.get("__damage_marked", 0))
                                          and not has_keyword(state, value, "indestructible"))
                                return 5.0 + self._creature_threat_score(state, value, player_id) if lethal else 0.0
                            if effect["effect_key"] == "add_counters":
                                counter = effect.get("payload", {}).get("counter")
                                if counter in {"+1/+1", "-1/-1"}:
                                    helps_creature = counter == "+1/+1"
                                    return 5.0 if (card.controller == player_id) == helps_creature else -5.0
                            if effect['effect_key'] == 'temporary_pt_buff':
                                packet = effect.get('payload') or {}
                                power, toughness = packet.get('power', 0), packet.get('toughness', 0)
                                threat = self._creature_threat_score(state, value, player_id)
                                if power <= 0 and toughness <= 0:
                                    if card.controller == player_id:
                                        return -100.0
                                    from ai.pending_effects import negative_pt_would_be_lethal
                                    return threat + (20.0 if negative_pt_would_be_lethal(state, value, power, toughness) else 0.0)
                                if power >= 0 and toughness >= 0:
                                    return threat if card.controller == player_id else -100.0
                            return 0.0

                        selected = max(options, key=score_target)
                elif copied and copied.effect_key in {"deal_damage", "deal_damage_multi"} and f"target_player:{opponent}" in options:
                    selected = f"target_player:{opponent}"
                elif copied and copied.effect_key == "gain_life" and f"target_player:{player_id}" in options:
                    selected = f"target_player:{player_id}"
                    from ai.life_targets import life_target_score
                    scores = {}
                    for option in options:
                        if option == 'keep':
                            target = copied.payload.get('__announced_targets', {}).get('target_player')
                        elif option.startswith('target_player:'):
                            target = int(option.split(':', 1)[1])
                        else:
                            continue
                        if target is not None:
                            score = life_target_score(state, player_id, target, int(copied.payload.get('amount', 0)))
                            if score is not None:
                                scores[option] = score
                    if scores and len(scores) == len(options):
                        selected = max(options, key=lambda option: (scores[option], option == selected))
                return AIDecision(action={"type": "choose_mechanic", "card_ids": [selected]},
                                  reasoning="Choose a legal copy target")
            if choice["kind"] in {"choose_revealed_discard", "choose_revealed_exile"}:
                target = int(choice["target_player"])
                target_archetype = self.opponent_archetype if target != player_id else self.archetype
                options.sort(key=lambda cid: (-self._hand_retention_value(state, cid, target, target_archetype or "Midrange"), cid))
                return AIDecision(action={"type": "choose_mechanic", "card_ids": options[:1]}, reasoning="Remove the opponent's most useful revealed card")
            if choice['kind'] == 'foretell_from_hand':
                from ai.foretell_policy import choose_effect_foretell_card
                selected = choose_effect_foretell_card(self, state, player_id, options, choice['reduction'])
                return AIDecision(action={'type': 'choose_mechanic', 'card_ids': [selected]},
                                  reasoning='Foretell a future spell while retaining affordable interaction')
            if choice["kind"] == "linked_exile_copy":
                selected = self._choose_library_search(state, options, 1, player_id)
                return AIDecision(action={"type": "choose_mechanic", "card_ids": selected}, reasoning="Copy the most useful eligible exiled creature")
            if choice["kind"] == "attacking_token_target":
                opponent = 3 - player_id
                power = int((choice.get("effect_payload") or {}).get("power", 1) or 1)
                selected = f"player:{opponent}"
                if state.players[opponent].life > power:
                    vulnerable = [key for key in options if key.startswith("planeswalker:")
                                  and key.split(":", 1)[1] in state.cards
                                  and (state.cards[key.split(":", 1)[1]].loyalty or 0) <= power]
                    if vulnerable:
                        selected = max(vulnerable, key=lambda key: self._noncreature_permanent_threat_score(
                            state, key.split(":", 1)[1], player_id))
                return AIDecision(action={"type": "choose_mechanic", "card_ids": [selected]},
                                  reasoning="Choose a legal defender for the attacking token")
            if choice["kind"] == "combat_damage":
                return AIDecision(
                    action={"type": "choose_mechanic", "damage_assignment": self._choose_combat_damage_allocation(state, choice)},
                    reasoning="Assign combat damage to maximize trades and trample pressure",
                )
            if choice["kind"] == "draw":
                prefer_dredge = self.archetype in {"Reanimator", "Drain", "Aristocrats", "Combo-lite"}
                selected = next((option for option in options if option != "draw"), "draw") if prefer_dredge else "draw"
                return AIDecision(action={"type": "choose_mechanic", "choice_id": selected}, reasoning="Choose draw or graveyard dredge replacement")
            if choice['kind'] == 'saga_entry':
                return AIDecision(action={'type': 'choose_mechanic', 'choice_id': options[0]},
                                  reasoning='Retain all future Saga chapters; tactical read-ahead planning remains limited')
            if choice["kind"] == "land_entry":
                pay = ("pay_two_life" in options and not (choice.get("effect_payload") or {}).get("tapped")
                       and self._should_pay_two_life_for_land(state, player_id, choice.get("entry_card_id")))
                return AIDecision(action={"type": "choose_mechanic", "choice_id": "pay_two_life" if pay else "tapped"}, reasoning="Pay life only when untapped mana enables a current play")
            if choice["kind"] in {"search_library", "topdeck_put", "topdeck_reveal_creature", "look_top_choose", "look_top_select_hand"}:
                kind = choice["kind"]
                candidates = [cid for cid in options if cid in state.cards]
                if kind == "look_top_choose":
                    hand = self._choose_library_search(state, candidates, 1, player_id)
                    remaining = [cid for cid in candidates if cid not in hand]
                    exile = self._choose_library_search(state, remaining, 1, player_id)
                    selected = hand + exile + [cid for cid in options if cid not in hand + exile]
                else:
                    payload = choice.get("effect_payload") or {}
                    destination = str(payload.get("destination", "hand"))
                    if kind == "search_library" and destination == "graveyard" and payload.get("up_to"):
                        candidates = [cid for cid in candidates if graveyard_destination(state, state.cards[cid]) == "graveyard"]
                    distinct_types_choice = kind == "topdeck_put" and choice.get("effect_key") == "look_top_distinct_types_to_hand"
                    selected = self._choose_library_search(
                        state, candidates, len(candidates) if distinct_types_choice else int(choice["count"]), player_id,
                        free_battlefield=kind == "topdeck_put" and not distinct_types_choice,
                        destination=destination,
                    )
                    if distinct_types_choice:
                        from rules_engine.card_types import cards_have_distinct_card_types
                        distinct = []
                        for cid in selected:
                            if cards_have_distinct_card_types(state, [*distinct, cid]):
                                distinct.append(cid)
                            if len(distinct) == choice["count"]:
                                break
                        selected = distinct
                    if kind == "topdeck_reveal_creature" and not selected:
                        selected = ["__none__"]
                return AIDecision(action={"type": "choose_mechanic", "card_ids": selected}, reasoning=f"Choose {kind} cards at resolution")
            if choice["kind"] == "sacrifice":
                options.sort(key=lambda cid: (self._sacrifice_loss(state, cid, player_id), cid))
                return AIDecision(action={"type": "choose_mechanic", "card_ids": options[:choice["count"]]}, reasoning="Sacrifice least valuable permanents")
            if choice["kind"] in {"cleanup_discard", "discard", "each_player_discard"}:
                options.sort(key=lambda cid: (self._hand_retention_value(state, cid, player_id), cid))
                if choice['kind'] == 'discard' and choice.get('min_count') == 0:
                    from ai.information import known_search_land_count
                    followup = choice.get('followup_effect') or {}
                    count = 0
                    if followup.get('effect_key') == 'search_library':
                        payload = followup.get('payload') or {}
                        basics = known_search_land_count(state, player_id, payload.get('contains'))
                        target = 6 if self.archetype == 'Ramp' else 4
                        lands = sum('Land' in effective_types(state, state.cards[cid]) for cid in state.players[player_id].battlefield + state.players[player_id].hand)
                        scored = [(0.0, 0)]
                        for size in range(1, min(basics, len(options), choice['count']) + 1):
                            removed_lands = sum('Land' in effective_types(state, state.cards[cid]) for cid in options[:size])
                            if size <= max(0, target - lands + removed_lands):
                                gain = size * self._land_retention_value(state, player_id)
                                loss = sum(self._hand_retention_value(state, cid, player_id) for cid in options[:size])
                                # Equal-value trades retain more cards despite float noise.
                                scored.append((round(gain - loss, 6), -size))
                        count = -max(scored)[1]
                    elif followup.get('effect_key') == 'draw_cards':
                        count, _ = self._linked_draw_trade(state, player_id, options, choice['count'])
                    return AIDecision(action={'type': 'choose_mechanic', 'card_ids': options[:count]}, reasoning='Preserve hand unless linked follow-up improves known resources')
                return AIDecision(action={"type": "choose_mechanic", "card_ids": options[:choice["count"]]}, reasoning="Discard least useful hand cards")
            options.sort(key=lambda cid: (("Creature" in effective_types(state, state.cards[cid])), mana_value(state.cards[cid].mana_cost), cid))
            return AIDecision(action={"type": "choose_mechanic", "card_ids": options[:choice["count"]]}, reasoning="Resolve mandatory mechanic choice")
        from ai.mana_resource_policy import resource_change_plan
        legal_moves = [move for move in legal_moves if not self._bad_shared_draw_cast(state, move, player_id)
                       and not ((plan := resource_change_plan(self, state, move, player_id))
                                and move.get('type') == 'cast_spell' and plan['defer'])]
        self_removal_win = self._winning_self_removal_action(state, legal_moves, player_id)
        if self_removal_win is not None:
            return AIDecision(action=self_removal_win, reasoning="Announced self-removal line wins if unanswered")
        legal_moves = self._without_losing_mass_destruction(state, legal_moves, player_id)
        from ai.combat_response import choose_response
        combat_response = choose_response(self, state, legal_moves, player_id)
        if combat_response is not None:
            return AIDecision(action=combat_response, reasoning='Compare declared combat responses by checked outcomes and retained resources')

        if _step_key(getattr(state, "step", "")) == "declare_attackers" and getattr(state, "active_player", player_id) == player_id:
            forced_attack = self._forced_progress_attack(state, legal_moves, player_id)
            if forced_attack is not None:
                return AIDecision(action=forced_attack, reasoning="Late-game progress attack to avoid stall timeout")

        forced_land = self._choose_forced_land_play(state, legal_moves, player_id)
        if forced_land is not None:
            hand_abilities = [move for move in legal_moves if move.get('type') == 'activate_ability'
                              and move.get('card_id') == forced_land.get('card_id')]
            if hand_abilities:
                winning_ability = self._tactical_combat_setup_action(state, hand_abilities, player_id)
                if winning_ability and winning_ability.get('type') == 'activate_ability':
                    return AIDecision(action=winning_ability,
                                      reasoning='Keep the land card in hand to execute its proved winning ability')
            return AIDecision(action=forced_land, reasoning="Prioritize reliable land development on own main phase")

        forced_stabilize = self._forced_sweeper_stabilization_line(state, legal_moves, player_id)
        if forced_stabilize is not None:
            return AIDecision(action=forced_stabilize, reasoning="Burn matchup stabilization: remove pressure before value lines")

        tactical_loyalty = self._tactical_loyalty_action(state, legal_moves, player_id)
        if tactical_loyalty is not None:
            return AIDecision(action=tactical_loyalty, reasoning="Choose immediate lethal or a profitable X-loyalty sweep")

        combat_setup = self._tactical_combat_setup_action(state, legal_moves, player_id)
        if combat_setup is not None:
            return AIDecision(action=combat_setup, reasoning="Public-board combat setup forecasts a winning attack")

        stack_interaction = self._forced_stack_interaction(state, legal_moves, player_id)
        if stack_interaction is not None:
            return AIDecision(action=stack_interaction, reasoning="Answer threatening stack item with available interaction")

        endstep_draw = self._forced_endstep_card_advantage(state, legal_moves, player_id)
        if endstep_draw is not None:
            return AIDecision(action=endstep_draw, reasoning="Use opponent end step for instant-speed card advantage")
        tempo_closure = self._choose_forced_tempo_noncontrol_closure_action(state, legal_moves, player_id)
        if tempo_closure is not None:
            return AIDecision(action=tempo_closure, reasoning="Tempo non-control closure: force proactive conversion to avoid stalls")

        inevitability = self._choose_forced_inevitability_action(state, legal_moves, player_id)
        if inevitability is not None:
            return AIDecision(action=inevitability, reasoning="Control endgame planner selected long-game conversion line")
        closure = self._choose_forced_closure_action(state, legal_moves, player_id)
        if closure is not None:
            return AIDecision(action=closure, reasoning="Force late-game proactive line to avoid control stall/timeouts")

        strategic = self._strategic_plan_action(state, legal_moves, player_id)
        if strategic is not None:
            return AIDecision(action=strategic, reasoning="Complex-board strategic planner selected best line")

        sorted_moves = self._rank_moves(state, legal_moves, player_id)
        if self._should_break_stall(state, legal_moves, player_id):
            proactive = self._best_proactive_non_pass(sorted_moves, state, player_id)
            if proactive is not None:
                proactive = self._materialize_action(state, proactive, player_id)
                if not proactive.get("_invalid_ai_choice") and not self._is_unplayable_x_action(proactive):
                    return AIDecision(action=proactive, reasoning="Break pass-loop by selecting proactive legal action")
        if self.difficulty == "casual":
            ranked_candidates = sorted_moves[min(1, len(sorted_moves) - 1) :]
        else:
            ranked_candidates = sorted_moves
        move = None
        for cand in ranked_candidates:
            materialized = self._materialize_action(state, cand, player_id)
            if materialized.get("_invalid_ai_choice"):
                continue
            if self._is_action_obviously_illegal(state, materialized, player_id):
                continue
            if self._is_unplayable_x_action(materialized):
                continue
            move = materialized
            break
        if move is None:
            move = {"type": "pass_priority"}
        move = self._avoid_pass_with_main_phase_options(state, legal_moves, player_id, move)
        if move.get("type") == "block" and not move.get("blocks"):
            return AIDecision(action={"type": "pass_priority"}, reasoning="No profitable/legal block assignment; pass")
        if move.get("type") == "attack" and not (move.get("attackers") or []):
            return AIDecision(action={"type": "pass_priority"}, reasoning="No favorable attacks; pass priority")

        return AIDecision(action=move, reasoning=f"{self.archetype} plan selected best-scoring move")

    def _ward_selection(self, state, player_id, choice):
        from rules_engine.ward import finish_ward_choice
        from rules_engine.stack_engine import resolve_top_of_stack
        from rules_engine.state_based_actions import apply_state_based_actions

        def cost_selection(game, pending):
            options = list(pending["options"])
            if pending["ward_cost"]["kind"] == "discard":
                options.sort(key=lambda cid: (self._hand_retention_value(game, cid, player_id), cid))
            else:
                # Price a sacrifice by its actual loss from the public board.
                base = evaluate_board(game, player_id)
                def loss(cid):
                    projected = planning_copy(game)
                    projected.players[player_id].battlefield.remove(cid)
                    return base - evaluate_board(projected, player_id), cid
                options.sort(key=loss)
            return options[:pending["count"]]

        pending = state.pending_mechanic_choice
        if choice["kind"] == "ward_cost_cards":
            return cost_selection(state, pending)
        target_id = pending["effect_payload"]["target_stack_id"]
        target = next((item for item in state.stack if item.id == target_id), None)
        if ("pay" not in choice["options"] or target is None
                or (stack_object_kind(state, target) == "spell" and spell_cant_be_countered(state, target))):
            return ["decline"]
        scores = {}
        for option in ("pay", "decline"):
            game = planning_copy(state)
            if not finish_ward_choice(game, player_id, {"card_ids": [option]}):
                continue
            if game.pending_mechanic_choice:
                if not finish_ward_choice(game, player_id, {"card_ids": cost_selection(game, game.pending_mechanic_choice)}):
                    continue
            remaining = next((item for item in game.stack if item.id == target_id), None)
            if remaining:
                # Bounded local projection, not an assertion that later responses
                # or additional ward costs will be paid.
                game.stack = [remaining]
                resolve_top_of_stack(game)
            apply_state_based_actions(game)
            scores[option] = -100000 if game.winner == 3 - player_id else evaluate_board(game, player_id)
        return ["pay" if scores.get("pay", -100000) > scores.get("decline", -100000) + 0.25 else "decline"]

    def _linked_draw_trade(self, state, player_id, options, limit):
        from rules_engine.draw_restrictions import forecast_draw_count
        ranked = sorted(options, key=lambda cid: (self._hand_retention_value(state, cid, player_id), cid))
        scored = [(0.0, 0)]
        for count in range(1, min(len(ranked), limit) + 1):
            draws = forecast_draw_count(state, player_id, count)
            if draws <= len(state.players[player_id].library):
                loss = sum(self._hand_retention_value(state, cid, player_id) for cid in ranked[:count])
                gain = self._draw_trade_value(state, player_id, draws, ranked[:count])
                scored.append((round(gain - loss, 6), -count))
        value, negative_count = max(scored)
        return -negative_count, value

    def _bad_shared_draw_cast(self, state: MatchState, move: dict, player_id: int) -> bool:
        if move.get("type") != "cast_spell":
            return False
        card = state.cards.get(move.get("card_id"))
        if card is None:
            return False
        from rules_engine.linked_discard import linked_discard_effect, simultaneous_discard_draw_effect
        wheel = simultaneous_discard_draw_effect(_oracle_text(card))
        if wheel:
            return self._wheel_exchange_value(state, player_id, wheel['draw_followup'], card.id) <= 0
        linked = linked_discard_effect(_oracle_text(card))
        hints = move.get('target_hints') or {}
        modes = hints.get('available_modes', hints.get('modes', []))
        if linked is None and modes:
            draws = [linked_discard_effect(mode) for mode in modes]
            if all(item and item.get('up_to') and item['followup_effect']['effect_key'] == 'draw_cards' for item in draws):
                hand = [cid for cid in state.players[player_id].hand if cid != card.id]
                return all(self._linked_draw_trade(state, player_id, hand, item.get('amount', len(hand)))[1] <= 0 for item in draws)
        if linked and linked['followup_effect']['effect_key'] == 'draw_cards':
            hand = [cid for cid in state.players[player_id].hand if cid != card.id]
            followup = linked['followup_effect']
            if linked.get('up_to'):
                return self._linked_draw_trade(state, player_id, hand, linked.get('amount', len(hand)))[1] <= 0
            amount = len(hand) if followup.get('count_field') else followup['payload'].get('amount', 0)
            if followup.get('count_history') == 'discards_this_turn':
                amount += state.discards_this_turn.get(player_id, 0) + len(hand)
            from rules_engine.draw_restrictions import forecast_draw_count
            draws = forecast_draw_count(state, player_id, amount)
            return (not draws or draws > len(state.players[player_id].library)
                    or self._draw_trade_value(state, player_id, draws, hand)
                    <= sum(self._hand_retention_value(state, cid, player_id) for cid in hand))
        match = EACH_PLAYER_DRAW_RE.fullmatch(str(getattr(card, "oracle_text", "") or "").strip())
        if match is None:
            return False
        raw = match.group(1).lower()
        amount = (self._choose_x_value(state, player_id, card.mana_cost, card=card)
                  if raw == "x" else _parse_count_token(raw))
        if amount <= 0:
            return True
        opponent_id = 1 if player_id == 2 else 2
        me, opponent = state.players[player_id], state.players[opponent_id]
        if len(opponent.library) < amount:
            return False
        if len(me.library) < amount:
            return True
        return len(me.hand) >= 5 and len(opponent.hand) <= 2

    def _wheel_exchange_value(self, state, player_id, rule, source_id=None):
        from rules_engine.linked_discard import wheel_draw_counts
        from rules_engine.draw_restrictions import forecast_draw_count
        opponent = 3-player_id
        own = [cid for cid in state.players[player_id].hand if cid != source_id]
        # Opposing hand size is public; opposing card identities are not.
        discarded = {player_id: len(own), opponent: len(state.players[opponent].hand)}
        amounts = wheel_draw_counts(rule, discarded)
        draws = {pid: forecast_draw_count(state, pid, amount) for pid, amount in amounts.items()}
        if draws[player_id] > len(state.players[player_id].library):
            return -100000.0
        if draws[opponent] > len(state.players[opponent].library):
            return 100000.0
        lost = sum(self._hand_retention_value(state, cid, player_id) for cid in own)
        if source_id in state.players[player_id].hand:
            lost += self._hand_retention_value(state, source_id, player_id)
        return draws[player_id] * 5 - lost - (draws[opponent] - discarded[opponent]) * 5

    def _choose_combat_damage_allocation(self, state: MatchState, choice: dict) -> dict[str, int]:
        source = state.cards[choice["source_id"]]
        options = list(choice["options"])
        allocation = {target: 0 for target in options}
        remaining = int(choice["count"])
        defender = next((target for target in options if target.startswith(("player:", "planeswalker:", "battle:"))), None)
        creatures = [target for target in options if target != defender and target in state.cards]

        def threat(target: str) -> float:
            card = state.cards[target]
            power, toughness = _effective_combat_stats(state, target)
            return max(0, power) * 1.5 + max(0, toughness) + mana_value(card.mana_cost) * 0.5

        creatures.sort(key=lambda target: (-threat(target), target))
        if choice.get("player_id") != source.controller:
            for target in creatures:
                toughness = _effective_combat_stats(state, target)[1]
                marked = int(state.cards[target].counters.get("__damage_marked", 0))
                safe = max(0, toughness - marked - 1)
                allocated = min(remaining, safe)
                allocation[target] = allocated
                remaining -= allocated
            if remaining and creatures:
                allocation[min(creatures, key=lambda target: (threat(target), target))] += remaining
            return allocation
        lethal_needs: dict[str, int] = {}
        for target in creatures:
            prior = sum(amounts.get(target, 0) for cid, amounts in state.combat_damage_assignments.items() if cid in state.attackers)
            prior_deathtouch = any(
                amounts.get(target, 0) > 0 and has_keyword(state, cid, "deathtouch")
                for cid, amounts in state.combat_damage_assignments.items() if cid in state.attackers
            )
            remaining_toughness = max(0, _effective_combat_stats(state, target)[1] - int(state.cards[target].counters.get("__damage_marked", 0)) - prior)
            lethal = 0 if prior_deathtouch or remaining_toughness == 0 else (1 if has_keyword(state, source.id, "deathtouch") else remaining_toughness)
            lethal_needs[target] = lethal
            if remaining >= lethal:
                allocation[target] = lethal
                remaining -= lethal
        if remaining > 0:
            if defender is not None and all(allocation[target] >= lethal_needs[target] for target in creatures):
                allocation[defender] += remaining
            elif creatures:
                allocation[creatures[0]] += remaining
            elif defender is not None:
                allocation[defender] += remaining
        return allocation

    def _tactical_loyalty_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        from types import SimpleNamespace
        from rules_engine.oracle_effects import extract_loyalty_abilities, infer_effect_from_oracle
        from rules_engine.stack_engine import resolve_top_of_stack
        from rules_engine.state_based_actions import apply_state_based_actions

        x_moves = [
            move for move in legal_moves
            if move.get("type") == "activate_loyalty" and move.get("ability_x_cost") and move.get("ability_x_sign") == -1
        ]
        if not x_moves:
            return None
        opponent = 1 if player_id == 2 else 2
        base = evaluate_board(state, player_id)
        best: tuple[float, int, dict] | None = None
        for move in legal_moves:
            if move.get("type") != "activate_loyalty" or move.get("ability_x_cost"):
                continue
            if opponent not in {target.get("id") for target in (move.get("target_hints") or {}).get("player_targets", [])}:
                continue
            damage = re.search(r"\bdeals?\s+(\d+)\s+damage\b", str(move.get("ability_label") or "").lower())
            if damage is None or state.players[opponent].life > int(damage.group(1)):
                continue
            action = {"type": "activate_loyalty", "card_id": move["card_id"], "ability_index": move["ability_index"], "targets": {"target_player": opponent}}
            try:
                sim = planning_copy(state)
                self.engine.take_action(sim, player_id, action, reject_invalid=True)
                if sim.stack and resolve_top_of_stack(sim):
                    apply_state_based_actions(sim)
                    if sim.winner == player_id:
                        return action
            except Exception:
                continue
        for move in x_moves:
            source = state.cards.get(move.get("card_id"))
            if source is None or int(source.loyalty or 0) < 1:
                continue
            abilities = extract_loyalty_abilities(source)
            index = int(move.get("ability_index", -1))
            if not 0 <= index < len(abilities):
                continue
            proxy = SimpleNamespace(name=source.name, oracle_text=abilities[index]["text"], mana_cost="", types=[])
            parse_state = planning_copy(state)
            effect_key, _ = infer_effect_from_oracle(parse_state, proxy, player_id, {"x_value": 1})
            if effect_key != "exile_colored_permanents_mana_value_at_most":
                continue
            x_values = sorted({
                max(1, mana_value(state.cards[cid].mana_cost or ""))
                for cid in state.players[opponent].battlefield
                if card_color_names(state.cards[cid]) and mana_value(state.cards[cid].mana_cost or "") <= source.loyalty
            })
            for x_value in x_values:
                action = {"type": "activate_loyalty", "card_id": source.id, "ability_index": index, "targets": {"x_value": x_value}}
                try:
                    sim = planning_copy(state)
                    self.engine.take_action(sim, player_id, action, reject_invalid=True)
                    if not sim.stack or not resolve_top_of_stack(sim):
                        continue
                    apply_state_based_actions(sim)
                    score = evaluate_board(sim, player_id) - base
                except Exception:
                    continue
                candidate = (score, -x_value, action)
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
        return best[2] if best is not None and best[0] >= 4.0 else None

    def _strategic_plan_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.difficulty not in {"master", "master_plus"}:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if not self._is_complex_board_state(state, player_id):
            return None
        if turn < 8 and self.archetype not in {"Control", "Counter-heavy", "Midrange", "Ramp", "Tempo"}:
            return None
        if turn < 6 and len(state.players[player_id].battlefield) + len(state.players[1 if player_id == 2 else 2].battlefield) < 12:
            return None
        proactive_legal = [
            mv
            for mv in legal_moves
            if mv.get("type") in {"cast_spell", "activate_ability", "activate_loyalty", "cycle_card", "equip", "attack"}
        ]
        if not proactive_legal:
            return None
        candidates = []
        search_depth = self._strategic_search_depth(state, player_id)
        beam_limit = 4 if search_depth > 2 else (6 if search_depth > 1 else 8)
        shortlist = _shortlist_with_priority_pass(self._rank_moves(state, legal_moves, player_id),
                                                 legal_moves, beam_limit)
        for mv in shortlist:
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            candidates.append(mat)
        if not candidates:
            return None
        scored: list[tuple[float, dict]] = []
        for mv in candidates:
            score = self._strategic_line_score(state, mv, player_id, depth=search_depth)
            scored.append((score, mv))
        scored.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        return scored[0][1]

    def _strategic_search_depth(self, state: MatchState, player_id: int) -> int:
        """Choose a bounded tactical horizon without making every turn expensive."""
        if self.difficulty == "master_plus":
            turn = int(getattr(state, "turn", 1) or 1)
            board_size = sum(
                len(getattr(state.players[pid], "battlefield", []) or [])
                for pid in state.players
            )
            if turn >= 8 and board_size >= 10:
                return 3
            return 2
        if self.difficulty != "master":
            return 1
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        board_size = len(getattr(state.players[player_id], "battlefield", []) or []) + len(
            getattr(state.players[opp_id], "battlefield", []) or []
        )
        if turn >= 10 and board_size >= 14:
            return 2
        return 1

    def _is_complex_board_state(self, state: MatchState, player_id: int) -> bool:
        if getattr(state, "pregame_pending", False):
            return False
        opp_id = 1 if player_id == 2 else 2
        my_bf = len(state.players[player_id].battlefield)
        opp_bf = len(state.players[opp_id].battlefield)
        both_hands = len(state.players[player_id].hand) + len(state.players[opp_id].hand)
        stack_size = len(getattr(state, "stack", []) or [])
        turn = int(getattr(state, "turn", 1) or 1)
        return my_bf + opp_bf >= 10 or both_hands >= 10 or stack_size >= 2 or turn >= 10

    def _strategic_line_score(self, state: MatchState, move: dict, player_id: int, depth: int) -> float:
        try:
            sim = planning_copy(state)
            self.engine.take_action(sim, player_id, move, reject_invalid=True)
        except Exception:
            return -9999.0
        score = evaluate_board(sim, player_id)
        score += self._strategic_features(sim, player_id)
        score += self._stack_two_ply_value(sim, player_id)
        return self._strategic_state_score(sim, player_id, depth, score)

    def _strategic_state_score(self, sim: MatchState, player_id: int, depth: int, score: float) -> float:
        """Continue the chosen, already executed prefix from its original perspective."""
        if depth <= 0 or sim.winner is not None:
            return score
        pid = sim.priority_player
        available = self.engine.legal_moves(sim, pid)
        legal = self._rank_moves(sim, available, pid, shallow=True)
        if not legal:
            return score
        beam: list[tuple[float, MatchState]] = []
        for cand in _shortlist_with_priority_pass(legal, available, 6):
            try:
                materialized = self._materialize_action(sim, cand, pid)
                if materialized.get("_invalid_ai_choice") or self._is_unplayable_x_action(materialized):
                    continue
                nxt = planning_copy(sim)
                self.engine.take_action(nxt, pid, materialized, reject_invalid=True)
                val = evaluate_board(nxt, player_id) + self._strategic_features(nxt, player_id) + self._stack_two_ply_value(
                    nxt, player_id
                )
                beam.append((val, nxt))
            except Exception:
                continue
        if not beam:
            return score
        beam.sort(key=lambda x: x[0], reverse=(pid == player_id))
        # Opponent turn: assume best line against us; own turn: assume best for us.
        chosen_score, chosen_state = beam[0]
        beam.clear()
        return 0.6 * score + 0.4 * self._strategic_state_score(chosen_state, player_id, depth - 1, chosen_score)

    def _stack_two_ply_value(self, state: MatchState, player_id: int) -> float:
        """Depth-limited stack planner for counter wars; only runs while stack is active."""
        stack_items = list(getattr(state, "stack", []) or [])
        if not stack_items or getattr(state, "winner", None) is not None:
            return 0.0
        pid = getattr(state, "priority_player", player_id)
        legal = self.engine.legal_moves(state, pid)
        if not legal:
            return 0.0
        top_actions = self._strategic_top_actions(state, legal, pid, limit=3)
        if not top_actions:
            return 0.0
        maximizing = pid == player_id
        best = -9999.0 if maximizing else 9999.0
        for act in top_actions:
            try:
                sim = planning_copy(state)
                self.engine.take_action(sim, pid, act, reject_invalid=True)
            except Exception:
                continue
            immediate = evaluate_board(sim, player_id) + self._strategic_features(sim, player_id)
            if getattr(sim, "winner", None) is not None or not (getattr(sim, "stack", []) or []):
                val = immediate
            else:
                reply_pid = getattr(sim, "priority_player", pid)
                reply_legal = self.engine.legal_moves(sim, reply_pid)
                replies = self._strategic_top_actions(sim, reply_legal, reply_pid, limit=2)
                if not replies:
                    val = immediate
                else:
                    reply_vals: list[float] = []
                    for rep in replies:
                        try:
                            nxt = planning_copy(sim)
                            self.engine.take_action(nxt, reply_pid, rep, reject_invalid=True)
                            reply_vals.append(evaluate_board(nxt, player_id) + self._strategic_features(nxt, player_id))
                        except Exception:
                            continue
                    if not reply_vals:
                        val = immediate
                    elif reply_pid == player_id:
                        val = max(reply_vals)
                    else:
                        val = min(reply_vals)
            best = max(best, val) if maximizing else min(best, val)
        if best in {-9999.0, 9999.0}:
            return 0.0
        return 0.2 * best

    def _strategic_top_actions(self, state: MatchState, legal_moves: list[dict], player_id: int, limit: int) -> list[dict]:
        ranked = self._rank_moves(state, legal_moves, player_id)
        picked: list[dict] = []
        for mv in ranked[: max(1, limit * 2)]:
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            picked.append(mat)
            if len(picked) >= limit:
                break
        return _shortlist_with_priority_pass(picked, legal_moves, limit)

    def _move_sort_key(self, move: dict) -> tuple:
        def _ids(values: object) -> str:
            if not isinstance(values, list):
                return ""
            out: list[str] = []
            for item in values:
                if isinstance(item, dict):
                    out.append(str(item.get("id") or item.get("name") or ""))
                else:
                    out.append(str(item))
            return ",".join(sorted(out))

        cost_choice = move.get("cost_choice")
        targets = move.get("targets")
        cost_choice_id = str(cost_choice.get("id")) if isinstance(cost_choice, dict) and cost_choice.get("id") is not None else ""
        return (
            str(move.get("type") or ""),
            str(move.get("card_name") or ""),
            str(move.get("card_name") or ""),
            str(move.get("ability_index") if move.get("ability_index") is not None else ""),
            str(move.get("ability_label") or ""),
            str(move.get("target_card_name") or ""),
            str(move.get("target_player_name") or ""),
            str(move.get("target_stack_label") or ""),
            cost_choice_id,
            str(targets.get("x_value", "")) if isinstance(targets, dict) else _ids(targets),
            _ids(move.get("attackers")),
            _ids(move.get("blockers")),
            _ids(move.get("options")),
        )

    def _strategic_features(self, state: MatchState, player_id: int) -> float:
        opp = 1 if player_id == 2 else 2
        my_life = int(getattr(state.players[player_id], "life", 20) or 20)
        opp_life = int(getattr(state.players[opp], "life", 20) or 20)
        my_hand = len(state.players[player_id].hand)
        opp_hand = len(state.players[opp].hand)
        my_untapped = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Land" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        )
        opp_untapped = sum(
            1
            for cid in state.players[opp].battlefield
            if cid in state.cards and "Land" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        )
        f = 0.0
        f += (my_life - opp_life) * 0.25
        f += (my_hand - opp_hand) * 0.35
        if self.archetype in {"Control", "Counter-heavy"}:
            f += min(3.0, my_untapped * 0.25)
            f -= max(0.0, opp_untapped - 2) * 0.2
        if self.archetype in {"Aggro", "Burn", "Tempo"}:
            f += max(0.0, 14 - opp_life) * 0.2
        if state.winner == player_id:
            f += 200.0
        elif state.winner is not None and state.winner != player_id:
            f -= 200.0
        return f

    def _forced_progress_attack(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        turn = int(getattr(state, "turn", 1) or 1)
        if turn < 20:
            return None
        attack_moves = [m for m in legal_moves if m.get("type") == "attack"]
        if not attack_moves:
            return None
        move = dict(attack_moves[0])
        options = list(move.get("options") or move.get("attackers") or [])
        if not options:
            return None
        chosen = self._choose_attackers(state, options, player_id)
        if not chosen:
            chosen = self._fallback_progress_attackers(state, options, player_id)
            if not any("Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
                       for cid in state.players[3 - player_id].battlefield):
                chosen = self._reserve_postcombat_mana(state, chosen, player_id)
        if not chosen:
            return None
        move["attackers"] = chosen
        return move

    def _fallback_progress_attackers(self, state: MatchState, candidates: list[str], player_id: int) -> list[str]:
        opp_id = 1 if player_id == 2 else 2
        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        opp_blockers = [
            cid
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        ]
        out: list[str] = []
        for cid in candidates:
            card = state.cards.get(cid)
            if not card:
                continue
            p = _eff_pow(state, cid)
            t = _eff_tgh(state, cid)
            if p <= 0:
                continue
            kws = set(effective_keywords(state, cid))
            evasive = bool(kws.intersection({"flying", "trample", "deathtouch", "menace"}))
            dies_to_any = any(_eff_pow(state, b) >= t for b in opp_blockers)
            trades_up = any(_eff_tgh(state, b) <= p for b in opp_blockers)
            if evasive or not dies_to_any or trades_up or p >= 3:
                out.append(cid)
        return out

    def _choose_forced_closure_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if getattr(state, "active_player", player_id) != player_id:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if not should_force_closure(turn, self.archetype, self.opponent_archetype):
            return None

        # Look for non-pass cast lines that actually advance board/card quality.
        cast_moves = [m for m in legal_moves if m.get("type") == "cast_spell"]
        if not cast_moves:
            return None

        candidates: list[tuple[float, dict]] = []
        for m in cast_moves:
            cid = m.get("card_id")
            card = _card_for_move(state, m)
            if not card:
                continue
            text = _oracle_text(card)
            # Do not force pure stack-dependent counters when stack is empty.
            if _has_counter_spell_text(text) and not (getattr(state, "stack", []) or []):
                continue
            materialized = self._materialize_action(state, m, player_id)
            if materialized.get("_invalid_ai_choice") or self._is_unplayable_x_action(materialized):
                continue
            score = self._closure_spell_score(card, text, state=state, player_id=player_id)
            candidates.append((score, materialized))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        # Require meaningful proactive value.
        if candidates[0][0] < 1.0:
            return None
        return candidates[0][1]

    def _closure_spell_score(self, card, text: str, *, state=None, player_id=None) -> float:
        score = 0.0
        types = set(effective_types(state, card) or [])
        if "Planeswalker" in types:
            score += 5.0
        if "Creature" in types:
            stats = (prospective_creature_stats(state, card, player_id)
                     if state is not None and player_id is not None else (card.power, card.toughness))
            p, t = (int(value or 0) for value in stats)
            score += min(6.0, p * 0.9 + t * 0.25)
        if "draw" in self._spell_tags(card) or "scry" in text or "surveil" in text:
            score += 1.8
        if "token" in text or "create " in text:
            score += 1.5
        if _has_counter_spell_text(text):
            score -= 2.5
        return score

    def _forced_stack_interaction(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo", "Midrange"}:
            return None
        if getattr(state, "priority_player", player_id) != player_id:
            return None
        if not (getattr(state, "stack", []) or []):
            return None
        cast_moves = [m for m in legal_moves if m.get("type") == "cast_spell"]
        if not cast_moves:
            return None
        if self._best_stack_threat_score(state, player_id) < 2.0:
            return None
        best: tuple[float, dict] | None = None
        for move in cast_moves:
            cid = move.get("card_id")
            card = _card_for_move(state, move)
            if not card:
                continue
            text = _oracle_text(card)
            score = 0.0
            if _has_counter_spell_text(text):
                score += 7.0
            elif any(k in text for k in ["destroy target", "exile target", "deals"]):
                score += 2.5
            if score <= 0.0:
                continue
            mat = self._materialize_action(state, move, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if best is None or score > best[0]:
                best = (score, mat)
        return best[1] if best else None

    def _forced_endstep_card_advantage(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo"}:
            return None
        if getattr(state, "priority_player", player_id) != player_id:
            return None
        if getattr(state, "active_player", player_id) == player_id:
            return None
        if _step_key(getattr(state, "step", "")) != "end_step":
            return None
        if getattr(state, "stack", []) or []:
            return None
        candidates: list[dict] = []
        for move in legal_moves:
            if move.get("type") != "cast_spell":
                continue
            cid = move.get("card_id")
            card = _card_for_move(state, move)
            if not card:
                continue
            if "Instant" not in (effective_types(state, card) or []):
                continue
            text = _oracle_text(card)
            if "draw" not in self._spell_tags(card) and not any(k in text for k in ["scry", "surveil"]):
                continue
            mat = self._materialize_action(state, move, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            candidates.append(mat)
        return candidates[0] if candidates else None

    def _forced_sweeper_stabilization_line(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if getattr(state, "active_player", player_id) != player_id:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        opp_id = 1 if player_id == 2 else 2
        own_creatures = [
            cid
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        ]
        opp_creatures = [
            cid
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        ]
        if not opp_creatures:
            return None
        opp_power = sum(max(0, effective_power(state, cid)) for cid in opp_creatures)
        own_life = int(getattr(state.players[player_id], "life", 20) or 20)
        should_force = (
            len(opp_creatures) >= 3
            or opp_power >= max(3, own_life // 2)
            or len(own_creatures) <= 1
            or self.archetype in {"Control", "Counter-heavy", "Midrange"}
        )
        if not should_force:
            return None
        cast_moves = [m for m in legal_moves if m.get("type") == "cast_spell"]
        best: tuple[float, dict] | None = None
        for move in cast_moves:
            cid = move.get("card_id")
            card = _card_for_move(state, move)
            if not card:
                continue
            tags = self._spell_tags(card)
            if "removal" not in tags and "sweeper" not in tags:
                continue
            mat = self._materialize_action(state, move, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            text = _oracle_text(card)
            score = 0.0
            if "sweeper" in tags:
                score += 6.0 if len(opp_creatures) >= 3 else 3.0
                score += min(opp_power, 8) * 0.4
                if own_creatures:
                    score += 1.5
            if "removal" in tags:
                score += 2.0
            if any(k in text for k in ["exile", "destroy"]):
                score += 0.8
            if "destroy all creatures" in text or "exile all creatures" in text:
                score += 3.0
            if best is None or score > best[0]:
                best = (score, mat)
        return best[1] if best else None

    def _choose_forced_land_play(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        step = _step_key(getattr(state, "step", ""))
        own_main = step in {"precombat_main", "postcombat_main"}
        if not own_main:
            return None
        if getattr(state, "stack", []) or []:
            return None
        # Must be active player to play lands — skip the defensive fallback otherwise
        if getattr(state, "active_player", player_id) != player_id:
            return None
        land_moves = [m for m in legal_moves if m.get("type") == "play_land"]
        if land_moves:
            return self._best_land_move(state, land_moves, player_id)
        return None

    def choose_mulligan_action(self, state: MatchState, player_id: int) -> AIDecision:
        player = state.players[player_id]
        hand = [state.cards[cid] for cid in player.hand]
        profile = self._opening_hand_profile(hand)
        lands = int(profile["lands"])
        cheap_interaction = int(profile["cheap_interaction"])
        likely_sources = profile["sources"]
        missing_primary_color = bool(profile["missing_primary_color"])
        mulligans = state.mulligan_count.get(player_id, 0)
        min_lands, max_lands = self._preferred_land_window()
        too_land_light = lands < min_lands
        too_land_heavy = lands > max_lands
        quality = float(profile["quality"])
        critical_miss = bool(profile["critical_miss"])
        if critical_miss and mulligans < 2:
            return AIDecision(action={"type": "mulligan"}, reasoning=profile["critical_reason"])
        if mulligans < 2 and too_land_light:
            # Keep a few borderline 2-land action hands when the deck can actually
            # convert them into development, draw, or acceleration.
            if not (
                lands >= 2
                and (
                    (self.archetype == "Ramp" and int(profile.get("ramp_spells", 0)) + int(profile.get("draw_spells", 0)) >= 1)
                    or (
                        self.archetype in {"Control", "Counter-heavy"}
                        and int(profile.get("draw_spells", 0)) + int(profile.get("counter_spells", 0)) + int(profile.get("removal_spells", 0)) >= 2
                    )
                )
            ):
                return AIDecision(
                    action={"type": "mulligan"},
                    reasoning=f"Opening hand outside {min_lands}-{max_lands} land window for {self.archetype}",
                )
        if mulligans < 2 and too_land_heavy:
            return AIDecision(
                action={"type": "mulligan"},
                reasoning=f"Opening hand outside {min_lands}-{max_lands} land window for {self.archetype}",
            )
        if mulligans < 2 and missing_primary_color and lands <= 3:
            return AIDecision(action={"type": "mulligan"}, reasoning="Missing key color access in opening hand")
        arche_quality_floor = 0.42
        if self.archetype in {"Control", "Counter-heavy", "Ramp"}:
            arche_quality_floor = 0.46
        elif self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"}:
            arche_quality_floor = 0.44
        if mulligans < 2 and quality < arche_quality_floor:
            return AIDecision(action={"type": "mulligan"}, reasoning="Opening hand quality too low")
        if mulligans < 2 and self._is_burn_matchup() and (lands < 2 or cheap_interaction == 0):
            return AIDecision(action={"type": "mulligan"}, reasoning="Burn matchup requires stable mana and early interaction")
        return AIDecision(action={"type": "keep_hand", "bottom_card_ids": []}, reasoning="Keep acceptable hand")

    def _opening_hand_profile(self, hand: list) -> dict[str, object]:
        lands = 0
        early_spells = 0
        early_pressure = 0
        cheap_interaction = 0
        draw_spells = 0
        counter_spells = 0
        removal_spells = 0
        ramp_spells = 0
        token_spells = 0
        engine_spells = 0
        threats = 0
        creatures = 0
        colored_pips = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for c in hand:
            if _card_looks_like_land(c):
                lands += 1
                for sym in self._land_colors(c):
                    if sym in colored_pips:
                        colored_pips[sym] += 1
                continue
            mana_cost = getattr(c, "mana_cost", "") or ""
            cost = _fixed_color_pips(mana_cost)
            cmc = mana_value(mana_cost, is_land=False)
            text = _oracle_text(c)
            types = set(getattr(c, "types", []) or [])
            if cmc <= 2:
                early_spells += 1
            if cmc <= 3 and (
                "Creature" in types
                or _has_counter_spell_text(text)
                or "destroy target" in text
                or "exile target" in text
                or "deal" in text
                or ("create" in text and "token" in text)
            ):
                early_pressure += 1
            if cmc <= 2 and any(k in text for k in ["counter target spell", "destroy target", "exile target", "deals", "deal", "remove target"]):
                cheap_interaction += 1
            if "draw" in self._spell_tags(c) or "scry" in text or "surveil" in text:
                draw_spells += 1
            if _has_counter_spell_text(text):
                counter_spells += 1
            if "destroy target" in text or "exile target" in text or "deals" in text:
                removal_spells += 1
            if "ramp" in self._spell_tags(c):
                ramp_spells += 1
            if "create" in text and "token" in text:
                token_spells += 1
            if any(k in text for k in ["whenever", "at the beginning", "landfall", "magecraft", "prowess", "artifact or enchantment", "another permanent enters the battlefield", "another permanent dies"]):
                engine_spells += 1
            if "Creature" in types:
                creatures += 1
                if cmc <= 3 or int(getattr(c, "power", 0) or 0) >= 3:
                    threats += 1
            for sym in ["W", "U", "B", "R", "G"]:
                colored_pips[sym] += int(cost[sym] or 0)

        likely_sources = self._opening_color_sources_from_hand(hand)
        missing_primary_color = any(v >= 2 and likely_sources.get(k, 0) == 0 for k, v in colored_pips.items())
        arche = self.archetype
        opp = (self.opponent_archetype or "").strip().lower()
        curve_fit = 1.0 - min(abs(lands - (3 if arche in {"Control", "Counter-heavy", "Ramp"} else 2 if arche in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} else 3)), 3) / 3
        action_density = min((early_spells + draw_spells + counter_spells + removal_spells + ramp_spells + token_spells + engine_spells) / 5.0, 1.6)
        quality = curve_fit * 0.55 + action_density * 0.3 + (0.15 if not missing_primary_color else 0.0)
        quality += min(0.2, threats * 0.05)

        critical_miss = False
        critical_reason = "Opening hand quality too low"
        if arche in {"Control", "Counter-heavy"}:
            quality += min(0.2, (draw_spells + counter_spells + removal_spells) * 0.04)
            if opp in {"aggro", "burn", "tempo"} and lands <= 3 and cheap_interaction == 0:
                critical_miss = True
                critical_reason = "Control hand lacks early interaction against pressure"
            elif lands <= 2 and draw_spells + counter_spells == 0:
                critical_miss = True
                critical_reason = "Control hand is too land-light without card selection"
            elif lands >= 6 and draw_spells + counter_spells == 0:
                critical_miss = True
                critical_reason = "Control hand is too land-heavy without action"
        elif arche == "Ramp":
            quality += min(0.2, (ramp_spells + draw_spells) * 0.05)
            if lands <= 2 and ramp_spells == 0:
                critical_miss = True
                critical_reason = "Ramp hand needs either stable lands or an accelerator"
            elif lands >= 6 and ramp_spells + draw_spells == 0:
                critical_miss = True
                critical_reason = "Ramp hand is too land-heavy without ramp or draw"
        elif arche in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"}:
            quality += min(0.2, (creatures + early_spells + cheap_interaction) * 0.04)
            if lands <= 1:
                critical_miss = True
                critical_reason = "Aggro hand is too land-light"
            elif early_pressure == 0:
                critical_miss = True
                critical_reason = "Aggro hand lacks early pressure"
        else:
            quality += min(0.15, (threats + draw_spells + removal_spells + ramp_spells) * 0.03)
            if lands <= 2 and threats + draw_spells + removal_spells == 0:
                critical_miss = True
                critical_reason = "Midrange hand lacks playable early action"

        return {
            "lands": lands,
            "cheap_interaction": cheap_interaction,
            "sources": likely_sources,
            "missing_primary_color": missing_primary_color,
            "quality": round(quality, 3),
            "draw_spells": draw_spells,
            "counter_spells": counter_spells,
            "removal_spells": removal_spells,
            "ramp_spells": ramp_spells,
            "token_spells": token_spells,
            "engine_spells": engine_spells,
            "creatures": creatures,
            "threats": threats,
            "early_spells": early_spells,
            "early_pressure": early_pressure,
            "critical_miss": critical_miss,
            "critical_reason": critical_reason,
        }

    def _current_hand_profile(self, state: MatchState, player_id: int) -> dict[str, object]:
        hand = [state.cards[cid] for cid in getattr(state.players[player_id], "hand", []) if cid in state.cards]
        profile = self._opening_hand_profile(hand)
        action_density = int(
            int(profile["cheap_interaction"])
            + min(3, int(profile["lands"]))
            + min(2, int(float(profile["quality"]) * 2))
        )
        profile["action_density"] = action_density
        return profile

    def _preferred_land_window(self) -> tuple[int, int]:
        arche = self.archetype
        if arche in {"Control", "Counter-heavy"}:
            return (3, 5)
        if arche in {"Ramp"}:
            return (3, 5)
        if arche in {"Aggro", "Burn", "Tempo", "Tribal", "Tokens"}:
            return (2, 4)
        return (2, 5)

    def _rank_moves(self, state: MatchState, moves: list[dict], player_id: int, *, shallow: bool = False) -> list[dict]:
        from rules_engine.query_context import rule_query_scope
        with rule_query_scope(state):
            return self._rank_moves_query(state, moves, player_id, shallow=shallow)

    def _rank_moves_query(self, state: MatchState, moves: list[dict], player_id: int, *, shallow: bool = False) -> list[dict]:
        in_main = _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}
        own_main_sorcery_window = (
            in_main
            and getattr(state, "active_player", player_id) == player_id
            and not (getattr(state, "stack", []) or [])
        )
        castable_creature_moves = []
        for m in moves:
            if m.get("type") != "cast_spell":
                continue
            cid = m.get("card_id")
            card = state.cards.get(cid) if cid else None
            if card and "Creature" in effective_types(state, card):
                castable_creature_moves.append(m)
        # Deep-copy two-ply search is valuable on ordinary boards but scales
        # poorly with token armies and large action surfaces. Preserve the
        # deterministic heuristic/combat paths on dense boards instead of
        # allowing Master simulations to monopolize a match run.
        battlefield_size = sum(len(getattr(player, "battlefield", []) or []) for player in state.players.values())
        use_deep_search = (
            not shallow and self.difficulty in {"master", "master_plus"}
            and battlefield_size <= 10
            and len(moves) <= 24
        )

        def score(move: dict) -> float:
            mtype = move.get("type")
            base = evaluate_board(state, player_id)
            stack_items = getattr(state, "stack", []) or []
            cast_moves = [m for m in moves if m.get("type") == "cast_spell"]
            if mtype == "cast_spell":
                card = _card_for_move(state, move)
                from ai.mana_resource_policy import resource_change_plan
                resource_plan = resource_change_plan(self, state, move, player_id)
                if resource_plan is not None:
                    base += resource_plan['score']
                tags = self._spell_tags(card)
                from rules_engine.attachments import is_aura
                if is_aura(card):
                    _, gain = self._attachment_projection(state, move, player_id)
                    base += gain if gain > 0 else -10.0
                base += self._cast_bias(state, move, player_id)
                if "burn" in tags:
                    base += 6 if self.archetype in {"Burn", "Aggro", "Tempo"} else 3
                if "counter" in tags:
                    if stack_items:
                        base += (9 if self.archetype in {"Control", "Counter-heavy", "Tempo"} else 4) + self._best_stack_threat_score(
                            state, player_id
                        )
                    else:
                        base -= 2
            elif mtype == "play_land":
                base += 8
            elif mtype == "cycle_card":
                # Cycling is a card-selection action, not a spell cast. Keep
                # it below a playable land/threat, but prefer it to passing
                # when the card is low-impact or the hand needs filtering.
                base += 2.0
                card = state.cards.get(move.get("card_id"))
                if card and "Land" in effective_types(state, card):
                    base -= 2.0
                if len(state.players[player_id].hand) <= 3:
                    base += 1.5
            elif mtype == "tap_land_for_mana":
                # Avoid floating mana loops: only tap proactively if it helps convert to a cast now.
                if cast_moves:
                    base += 0.4
                else:
                    base -= 3.0
            elif mtype == "attack":
                base += self._attack_bias(state, move, player_id)
            elif mtype == "block":
                base += self._block_bias(state, move, player_id)
            elif mtype == "activate_ability":
                base += 2.5
                label = str(move.get("ability_label", "")).lower()
                from ai.combat_tax_policy import combat_tax_plan
                tax_plan = combat_tax_plan(state, move, player_id)
                if tax_plan is not None:
                    base += tax_plan['score'] - 2.5
                if "look at the top" in label or "draw" in label or "search" in label:
                    base += 4.0
                if "x damage to each creature and each player" in label:
                    from rules_engine.costs import restricted_x_color
                    source = state.cards.get(move.get("card_id"))
                    x = self._choose_x_value(
                        state, player_id, str(move.get("mana_cost") or ""), card=source,
                        restricted_x_color=restricted_x_color(label),
                    )
                    base += (self._score_x_value(state, player_id, source, str(move.get("mana_cost") or ""), x, x, 1)
                             if x else -20.0) - 2.5
            elif mtype == "equip":
                _, gain = self._attachment_projection(state, move, player_id)
                base += gain if gain > 0 else -10.0
            elif mtype == "ninjutsu":
                ninja = state.cards[move["card_id"]]
                returned_power = effective_power(state, move["return_card_id"])
                base += max(0, int(ninja.power or 0) - returned_power) + (3 if "draw" in ninja.oracle_text.lower() else 1)
            elif mtype == "pass_priority":
                base += self._pass_bias(state, player_id)
                if own_main_sorcery_window and castable_creature_moves:
                    # Avoid stalling with threats stranded in hand when we can safely deploy.
                    base -= 2.6
            base += self._matchup_move_adjustment(state, move, player_id)
            if use_deep_search:
                base += self._simulate_delta(state, move, player_id)
            if self.difficulty == "master_plus" and use_deep_search:
                base += self._rollout_delta(state, move, player_id)
            return base

        ranked = sorted(moves, key=lambda mv: (score(mv), self._move_sort_key(mv)), reverse=True)
        normalized = []
        for move in ranked:
            if move.get("type") == "attack" and "attackers" not in move:
                move = move.copy()
                move["attackers"] = move.get("options", [])
            normalized.append(move)
        return normalized

    def _simulate_delta(self, state: MatchState, move: dict, player_id: int) -> float:
        # Two-ply lookahead: own action value minus opponent best reply value.
        try:
            before = evaluate_board(state, player_id)
            materialized = self._materialize_action(state, move, player_id)
            if materialized.get("_invalid_ai_choice") or self._is_unplayable_x_action(materialized):
                return 0.0
            sim_state = planning_copy(state)
            self.engine.take_action(sim_state, player_id, materialized, reject_invalid=True)
            self._approximate_resolution_for_creature_cast(sim_state, materialized, player_id)
            self._approximate_resolution_for_ramp_spell(sim_state, materialized, player_id)
            self._approximate_resolution_for_activated_action(sim_state, materialized, player_id)
            after = evaluate_board(sim_state, player_id)
            opp_id = 1 if player_id == 2 else 2
            opp_moves = self.engine.legal_moves(sim_state, sim_state.priority_player)
            if sim_state.priority_player == opp_id and opp_moves:
                best_reply = self._best_reply_delta(sim_state, opp_moves, player_id, opp_id)
            else:
                best_reply = 0.0
            return (after - before) * 0.7 - best_reply * 0.5
        except Exception:
            return 0.0

    def _best_reply_delta(self, sim_state: MatchState, opp_moves: list[dict], eval_for_player: int, opp_id: int) -> float:
        worst = 0.0
        before = evaluate_board(sim_state, eval_for_player)
        for reply in self._rank_moves(sim_state, opp_moves, opp_id, shallow=True)[:8]:
            try:
                materialized = self._materialize_action(sim_state, reply, opp_id)
                if materialized.get("_invalid_ai_choice") or self._is_unplayable_x_action(materialized):
                    continue
                branch = planning_copy(sim_state)
                self.engine.take_action(branch, opp_id, materialized, reject_invalid=True)
                delta = before - evaluate_board(branch, eval_for_player)
                if delta > worst:
                    worst = delta
            except Exception:
                continue
        return worst

    def _attack_bias(self, state: MatchState, move: dict, player_id: int) -> float:
        attackers = move.get("options") or move.get("attackers") or []
        if not attackers:
            return -1.0
        opp_id = 1 if player_id == 2 else 2
        attack_power = sum(_effective_combat_stats(state, c)[0] for c in attackers if c in state.cards)
        opp_block_power = sum(
            _effective_combat_stats(state, c)[0]
            for c in state.players[opp_id].battlefield
            if c in state.cards and "Creature" in effective_types(state, state.cards[c]) and not state.cards[c].tapped
        )
        opp_blockers = sum(
            1
            for c in state.players[opp_id].battlefield
            if c in state.cards and "Creature" in effective_types(state, state.cards[c]) and not state.cards[c].tapped
        )
        race_pressure = max(0, 20 - state.players[opp_id].life) * 0.2
        role = self._board_role(state, player_id)
        archetype_bias = 5 if self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} else 2
        archetype_bias += float(self.matchup_profile.get("proactive_bias", 0.0)) * 1.2
        risk_penalty = 0.0
        if role in {"defend", "stabilize"}:
            archetype_bias -= 2.2
            risk_penalty += 1.2
        elif role == "race":
            archetype_bias += 1.4
        elif role == "convert":
            archetype_bias += 1.2
        # Safer aggression: avoid low-output swings into clearly superior blockers.
        if opp_blockers > 0 and attack_power > 0:
            if attack_power < (opp_block_power * 0.6):
                risk_penalty += 2.2
            if role in {"defend", "stabilize"}:
                risk_penalty += 1.8
            if self.archetype in {"Aggro", "Tempo"} and attack_power <= 2 and opp_block_power >= 4:
                risk_penalty += 1.6
        unblocked_bonus = 3.5 if opp_blockers == 0 else 0.0
        if role == "convert" and opp_blockers > 0:
            unblocked_bonus += 0.8
        lethal_bonus = 20.0 if attack_power >= state.players[opp_id].life else 0.0
        risk_penalty += max(0.0, -float(self.matchup_profile.get("risk_tolerance", 0.0))) * 0.9
        return archetype_bias + attack_power * 0.8 - opp_block_power * 0.35 + race_pressure + unblocked_bonus + lethal_bonus - risk_penalty

    def _pass_bias(self, state: MatchState, player_id: int) -> float:
        has_instant_like = False
        for cid in state.players[player_id].hand:
            c = state.cards.get(cid)
            if not c:
                continue
            keywords = [k.lower() for k in (getattr(c, "keywords", []) or [])]
            if "Instant" in effective_types(state, c) or "flash" in keywords:
                has_instant_like = True
                break
        if getattr(state, "stack", []) or []:
            return -2.0
        if self._can_deploy_major_threat(state, player_id):
            return -1.2
        if self._should_force_inevitability_plan(state, player_id):
            return -1.3
        if self._should_force_proactive_control_line(state, player_id):
            return -2.1
        if self._is_burn_matchup() and getattr(state, "active_player", player_id) == player_id and _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}:
            return -1.0
        hand_profile = self._current_hand_profile(state, player_id)
        role = self._board_role(state, player_id)
        if int(hand_profile["action_density"]) >= 3 and role in {"normal", "convert", "race"}:
            return -0.2 - float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.2
        if role in {"stabilize", "defend"} and self.archetype in {"Control", "Counter-heavy", "Tempo", "Midrange"}:
            return 1.7 + float(self.matchup_profile.get("holdup_bias", 0.0))
        if role == "convert" and self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"}:
            return -0.8 + float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.2
        if self.archetype == "Tempo":
            opp = (self.opponent_archetype or "").strip()
            if opp in {"Burn", "Aggro", "Midrange", "Ramp", "Drain", "Aristocrats", "Tokens", "Tribal"}:
                if getattr(state, "active_player", player_id) == player_id and _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}:
                    turn = int(getattr(state, "turn", 1) or 1)
                    if turn <= 6:
                        return -1.6
        has_urgent_interaction = self._has_urgent_interaction(state, player_id)
        has_castable_value = self._has_castable_value_spell(state, player_id)
        if has_instant_like and self.archetype in {"Control", "Counter-heavy", "Tempo"}:
            if has_castable_value and not has_urgent_interaction:
                return -0.4 + float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.2
            return 1.8 + float(self.matchup_profile.get("holdup_bias", 0.0))
        if self._should_hold_up_interaction(state, player_id):
            return 1.4 + float(self.matchup_profile.get("holdup_bias", 0.0))
        return 0.3 - float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.25

    def _should_hold_up_interaction(self, state: MatchState, player_id: int) -> bool:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo"}:
            return False
        if self._can_deploy_major_threat(state, player_id):
            return False
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if self._has_castable_value_spell(state, player_id) and not self._has_urgent_interaction(state, player_id):
            return False
        opp_id = 1 if player_id == 2 else 2
        opp_untapped = sum(
            1
            for cid in state.players[opp_id].battlefield
            if "Land" in (effective_types(state, state.cards.get(cid)) if cid in state.cards else []) and not state.cards[cid].tapped
        )
        # If opponent cannot realistically represent interaction, be more proactive.
        if opp_untapped <= 1:
            return False
        if self._should_force_proactive_control_line(state, player_id):
            return False
        has_counter = any(
            _has_counter_spell_text(_oracle_text(state.cards[cid]))
            for cid in state.players[player_id].hand
            if cid in state.cards
        )
        return has_counter and opp_untapped >= 2 and float(self.matchup_profile.get("holdup_bias", 0.0)) >= -0.2

    def _matchup_move_adjustment(self, state: MatchState, move: dict, player_id: int) -> float:
        delta = 0.0
        mtype = move.get("type")
        role = self._board_role(state, player_id)
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        opp_board_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        opp_board_power = sum(
            max(0, _effective_combat_stats(state, cid)[0])
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        my_board_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        if mtype == "cast_spell":
            cid = move.get("card_id")
            card = state.cards.get(cid) if cid else None
            if card:
                tags = self._spell_tags(card)
                if "draw" in tags or "removal" in tags or "counter" in tags:
                    delta += float(self.matchup_profile.get("holdup_bias", 0.0)) * 0.35
                if "token" in tags or "ramp" in tags:
                    delta += float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.45
                if self.archetype in {"Control", "Counter-heavy"} and self.opponent_archetype in {"Aggro", "Burn"} and "counter" in tags:
                    delta += 0.5
                if self.archetype in {"Tempo"} and self.opponent_archetype in {"Control", "Counter-heavy"} and ("counter" in tags or "removal" in tags):
                    delta += 0.4
                if role in {"stabilize", "defend"} and any(tag in tags for tag in {"removal", "counter", "draw", "sweeper"}):
                    delta += 1.2
                    if opp_board_creatures > 0:
                        delta += min(opp_board_power, 6) * 0.15
                if role in {"race", "convert"} and any(tag in tags for tag in {"token", "burn", "attack", "anthem"}):
                    delta += 1.0
                    if my_board_creatures >= opp_board_creatures:
                        delta += 0.3
                if self.archetype == "Ramp" and "ramp" in tags:
                    delta += 3.0
                    if turn <= 5:
                        delta += 1.2
                    if role in {"normal", "stabilize"}:
                        delta += 0.3
                if self.archetype == "Ramp" and "draw" in tags and turn >= 5:
                    delta += 0.3
                if self.archetype in {"Control", "Counter-heavy"} and "sweeper" in tags and opp_board_creatures >= 2:
                    delta += 1.5
                if self.archetype in {"Aggro", "Burn", "Tempo"} and "burn" in tags and opp_board_power > 0:
                    delta += min(opp_board_power, 6) * 0.12
        elif mtype == "attack":
            delta += float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.35
        elif mtype == "pass_priority":
            delta -= float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.25
        return delta

    def _has_urgent_interaction(self, state: MatchState, player_id: int) -> bool:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo"}:
            return False
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        stack_live = bool(getattr(state, "stack", []) or [])
        for cid in state.players[player_id].hand:
            card = state.cards.get(cid)
            if not card:
                continue
            if not self._can_pay_card_cost(state, player_id, card):
                continue
            tags = self._spell_tags(card)
            if stack_live and "counter" in tags:
                return True
            if opp_creatures > 0 and "removal" in tags:
                return True
        return False

    def _has_castable_value_spell(self, state: MatchState, player_id: int) -> bool:
        for cid in state.players[player_id].hand:
            card = state.cards.get(cid)
            if not card or "Land" in (effective_types(state, card) or []):
                continue
            if not self._can_pay_card_cost(state, player_id, card):
                continue
            if self._is_major_threat_card(card):
                return True
            tags = self._spell_tags(card)
            if any(tag in tags for tag in {"draw", "removal", "counter", "ramp", "token"}):
                return True
        return False

    def _can_pay_card_cost(self, state: MatchState, player_id: int, card) -> bool:
        try:
            from rules_engine.attachments import is_aura
            if is_aura(card):
                from rules_engine.cast_choice import available_cast_options_and_hints
                return bool(available_cast_options_and_hints(state, card, player_id)[0])
            return bool(can_pay_with_pool_and_lands(
                state, player_id, getattr(card, "mana_cost", ""),
                card_name=getattr(card, "name", ""), spell_types=set(effective_types(state, card) or []),
                oracle_text=getattr(card, "oracle_text", "") or "",
            ))
        except Exception:
            return False

    def _block_bias(self, state: MatchState, move: dict, player_id: int) -> float:
        blocker_ids = [x["id"] for x in (move.get("blockers") or [])]
        attacker_ids = [x["id"] for x in (move.get("attackers") or [])]
        if not blocker_ids or not attacker_ids:
            return -0.8
        threatened = sum(_effective_combat_stats(state, cid)[0] for cid in attacker_ids if cid in state.cards)
        life = state.players[player_id].life
        lethal_pressure = 4.0 if threatened >= life else 0.0
        profitable = 0.0
        for aid in attacker_ids:
            atk = state.cards.get(aid)
            if not atk:
                continue
            atk_pow, atk_tgh = _effective_combat_stats(state, aid)
            best = 0.0
            for bid in blocker_ids:
                blk = state.cards.get(bid)
                if not blk:
                    continue
                blk_pow, blk_tgh = _effective_combat_stats(state, bid)
                score = 0.0
                if blk_pow >= atk_tgh:
                    score += 1.6
                if blk_tgh > atk_pow:
                    score += 0.8
                if atk_pow > 0:
                    score += min(atk_pow, 4) * 0.2
                if score > best:
                    best = score
            profitable += best
        arche_bonus = 0.8 if self.archetype in {"Control", "Midrange", "Ramp"} else 0.3
        if self.archetype in {"Aggro", "Burn", "Tempo"} and life > 8:
            arche_bonus -= 0.4
        # Penalize blocking with mana-producing creatures
        mana_penalty = 0.0
        for bid in blocker_ids:
            blk = state.cards.get(bid)
            if blk:
                blk_text = (getattr(blk, "oracle_text", "") or "").lower()
                if ("{t}" in blk_text or "(t)" in blk_text) and ("add " in blk_text or "adds " in blk_text):
                    mana_penalty += 3.5
        return profitable + lethal_pressure + arche_bonus - mana_penalty

    def _cast_bias(self, state: MatchState, move: dict, player_id: int) -> float:
        cid = move.get("card_id")
        card = state.cards.get(cid) if cid else None
        if not card:
            return 0.0
        role = self._board_role(state, player_id)
        if getattr(card, "layout", "") in {"modal_dfc", "adventure", "split"}:
            from rules_engine.card_faces import select_cast_face
            index = int(move.get("selected_face_index", 0))
            face_score = self._score_modal_face(state, card, card.card_faces[index], player_id)
            card = select_cast_face(card, index)
        elif self._modal_face_options(card):
            _, face_score = self._select_modal_face_index(state, card, player_id)
        else:
            face_score = 0.0
        if move.get('cast_variant') == 'bestow':
            from rules_engine.bestow import bestow_cast_view
            card = bestow_cast_view(card)
        if self._should_hold_up_interaction(state, player_id) and "Instant" not in effective_types(state, card) and not self._is_major_threat_card(card):
            return -1.4
        is_creature = "Creature" in effective_types(state, card)
        arche = self.archetype
        tags = self._spell_tags(card)
        my_creatures = sum(
            1
            for perm_id in state.players[player_id].battlefield
            if "Creature" in effective_types(state, state.cards.get(perm_id, type("X", (), {"types": []})()))
        )
        early_turn = state.turn <= 4
        in_main = _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}
        own_main_sorcery_window = (
            in_main
            and getattr(state, "active_player", player_id) == player_id
            and not (getattr(state, "stack", []) or [])
        )
        mana_req = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=("Land" in effective_types(state, card)))
        cmc = mana_req["generic"] + sum(mana_req[c] for c in ["W", "U", "B", "R", "G"])
        mana_cost_text = (getattr(card, "mana_cost", "") or "").upper()
        x_value = 0
        life_x = bool(PAY_X_LIFE_RE.search(getattr(card, "oracle_text", "") or ""))
        if "{X}" in mana_cost_text:
            x_value = self._choose_x_value(state, player_id, mana_cost_text, card=card)
            if x_value <= 0:
                # Avoid invalid X=0 loops for spells that need explicit positive X targeting.
                return -8.0
            x_penalty = self._x_spell_timing_penalty(state, card, player_id, x_value)
            if x_penalty <= -3.5:
                return x_penalty
        elif life_x:
            x_value = self._choose_variable_life_x(state, player_id, card)
            if x_value <= 0:
                return -8.0
        power = (prospective_creature_stats(state, card, player_id)[0] or 0
                 if is_creature else getattr(card, "power", 0) or 0)
        is_big_threat = power >= 4 or cmc >= 4
        if face_score:
            bonus_face = face_score * 0.45
            if own_main_sorcery_window and face_score <= 0.0 and state.turn <= 4:
                bonus_face -= 0.8
        else:
            bonus_face = 0.0

        if is_creature:
            engine_bonus = (recurring_engine_value(state, cid, surface_card=card)
                            + repeatable_mana_value(state, cid, surface_card=card))
            if arche in {"Aggro", "Tribal", "Tokens", "Tempo"}:
                bonus = 4.0
                if in_main:
                    bonus += 1.2
                if my_creatures < 2:
                    bonus += 2.0
                if early_turn:
                    bonus += 1.0
                return bonus + bonus_face + engine_bonus
            if arche in {"Midrange", "Ramp", "Aristocrats"}:
                bonus = 2.0 + (0.8 if my_creatures < 2 else 0.0)
                if is_big_threat and (my_creatures < 2 or state.turn >= 5):
                    bonus += 2.2
                if arche == "Ramp" and state.turn >= 4 and is_big_threat:
                    bonus += 1.2
                return bonus + bonus_face + engine_bonus
            if arche in {"Control", "Counter-heavy"}:
                bonus = 0.8
                if is_big_threat and (my_creatures == 0 or state.turn >= 6):
                    bonus += 3.0
                if own_main_sorcery_window and is_big_threat:
                    bonus += 0.7
                if "recursion" in tags:
                    bonus += self._graveyard_recursion_bonus(state, player_id)
                return bonus + bonus_face + engine_bonus
            return 1.2 + bonus_face + engine_bonus

        if "creature_deploy_topdeck" in tags:
            bonus = 3.6
            if arche in {"Tribal", "Aggro", "Midrange", "Tempo", "Ramp"}:
                bonus += 2.2
            if len(state.players[player_id].hand) <= 2:
                bonus += 1.4
            if state.turn >= 4:
                bonus += 0.8
            return bonus

        if arche in {"Control", "Counter-heavy"}:
            bonus = 0.0
            opp_id = 1 if player_id == 2 else 2
            opp_creatures = sum(
                1
                for cid in state.players[opp_id].battlefield
                if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
            )
            opp_untapped_lands = sum(
                1
                for cid in state.players[opp_id].battlefield
                if cid in state.cards and "Land" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
            )
            if "counter" in tags:
                bonus += 5.5 if getattr(state, "stack", []) else -2.5
            if "draw" in tags:
                bonus += 2.2
                if self._should_force_inevitability_plan(state, player_id):
                    bonus += 1.4
                if "Instant" in effective_types(state, card):
                    on_opp_turn = getattr(state, "active_player", player_id) != player_id
                    in_end = _step_key(getattr(state, "step", "")) == "end_step"
                    if on_opp_turn or in_end:
                        bonus += 2.4
                # Be proactive when opponent is tapped down and interaction risk is low.
                if opp_untapped_lands <= 1 and own_main_sorcery_window:
                    bonus += 1.1
                if own_main_sorcery_window and self._should_force_proactive_control_line(state, player_id):
                    bonus += 1.0
                if self._is_burn_matchup() and state.turn <= 4 and opp_creatures > 0:
                    bonus -= 2.0
            if "recursion" in tags:
                bonus += self._graveyard_recursion_bonus(state, player_id)
            if "removal" in tags:
                bonus += 2.0
                # Don't fire premium removal into empty/low-pressure board states.
                if opp_creatures == 0:
                    bonus -= 2.5
                elif own_main_sorcery_window and self._should_force_proactive_control_line(state, player_id):
                    bonus += 0.8
                if self._is_burn_matchup() and opp_creatures > 0:
                    bonus += 2.4
                creature_targets = (move.get("target_hints") or {}).get("creature_targets") or []
                if creature_targets:
                    target_threat = max(
                        (
                            self._creature_threat_score(state, t.get("id"), player_id)
                            for t in creature_targets
                            if t.get("id")
                        ),
                        default=0.0,
                    )
                    bonus += min(3.5, max(0.0, target_threat) * 0.35)
                if self._is_burn_matchup() and "counter" in tags and state.turn <= 3 and not (getattr(state, "stack", []) or []):
                    bonus -= 0.8
                if self._is_burn_matchup() and "sweeper" in tags:
                    if opp_creatures >= 2:
                        bonus += 2.8
                    else:
                        bonus -= 1.2
            if "engine" in tags:
                if self.archetype in {"Control", "Counter-heavy", "Midrange", "Tokens", "Aristocrats", "Drain"}:
                    bonus += 1.7
                if self.archetype in {"Tempo", "Aggro", "Burn"} and own_main_sorcery_window:
                    bonus += 0.4
                if role in {"stabilize", "convert"}:
                    bonus += 0.8
            if ("Planeswalker" in set(effective_types(state, card) or []) or is_big_threat) and own_main_sorcery_window:
                if self._should_force_proactive_control_line(state, player_id):
                    bonus += 2.3
                if self._should_force_inevitability_plan(state, player_id):
                    bonus += 1.6
            if self._should_force_inevitability_plan(state, player_id):
                if "discard" in tags or "mill" in tags:
                    bonus += 1.7
                if "counter" in tags and not (getattr(state, "stack", []) or []):
                    bonus -= 1.0
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus + bonus_face

        if arche in {"Midrange"}:
            bonus = 0.0
            # Midrange: prefer board development on-curve, hold premium removal for real pressure.
            if "Creature" in set(effective_types(state, card) or []):
                bonus += 1.6
                if 2 <= cmc <= 4 and state.turn <= 6:
                    bonus += 1.2
            if "removal" in tags:
                bonus += 2.0
                opp_id = 1 if player_id == 2 else 2
                opp_creatures = sum(
                    1
                    for ocid in state.players[opp_id].battlefield
                    if ocid in state.cards and "Creature" in effective_types(state, state.cards[ocid])
                )
                if opp_creatures == 0:
                    bonus -= 2.2
            if "draw" in tags:
                bonus += 1.2
            if "burn" in tags and state.players[1 if player_id == 2 else 2].life <= 6:
                bonus += 1.5
            if "engine" in tags:
                bonus += 1.0
            return bonus + bonus_face

        if arche in {"Ramp"}:
            bonus = 0.0
            if "ramp" in tags:
                bonus += 4.0 if early_turn else 1.0
            opp_id = 1 if player_id == 2 else 2
            opp_creatures = sum(
                1
                for ocid in state.players[opp_id].battlefield
                if ocid in state.cards and "Creature" in effective_types(state, state.cards[ocid])
            )
            # Under pressure, stabilize before greed.
            if state.players[player_id].life <= 10 and opp_creatures >= 2 and "ramp" in tags:
                bonus -= 2.0
            if "removal" in tags and opp_creatures > 0:
                bonus += 2.0
            if "Creature" in set(effective_types(state, card) or []) and cmc >= 5 and state.turn >= 5:
                bonus += 1.8
            if "draw" in tags:
                bonus += 1.5
            if "engine" in tags:
                bonus += 0.8
            return bonus + bonus_face

        if arche in {"Tokens"}:
            bonus = 0.0
            if "token" in tags:
                bonus += 5.5
            if "anthem" in tags:
                bonus += 5.0 if my_creatures >= 2 else 2.2
            if "Enchantment" in effective_types(state, card):
                bonus += 3.2
                if state.turn <= 4:
                    bonus += 1.2
            if "engine" in tags:
                bonus += 1.6
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus + bonus_face

        if arche in {"Reanimator"}:
            bonus = 0.0
            if "reanimate" in tags:
                bonus += 4.0
            if "discard" in tags or "mill" in tags:
                bonus += 2.0
            return bonus + bonus_face

        if arche in {"Aristocrats", "Drain"}:
            bonus = 0.0
            if "drain" in tags:
                bonus += 3.2
            if "sacrifice" in tags:
                bonus += 2.4
            if "engine" in tags:
                bonus += 1.6
            # Deploy engine pieces before pure payoff where possible.
            if "sacrifice" in tags and ("token" in tags or "drain" in tags or "draw" in tags):
                bonus += 2.2
            return bonus + bonus_face

        if arche in {"Tempo"}:
            bonus = 0.0
            if "Creature" in set(effective_types(state, card) or []) and cmc <= 2:
                bonus += 2.4
            if "counter" in tags:
                bonus += 3.6 if getattr(state, "stack", []) else -1.4
            if "removal" in tags:
                bonus += 1.8
            if "engine" in tags:
                bonus += 0.9
            # Tempo: prefer threat+protection lines when threat already on board.
            my_creatures_now = sum(
                1
                for pid in state.players[player_id].battlefield
                if pid in state.cards and "Creature" in effective_types(state, state.cards[pid])
            )
            if my_creatures_now > 0 and "counter" in tags and (getattr(state, "stack", []) or []):
                bonus += 1.0
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus + bonus_face

        if arche in {"Aggro", "Tribal", "Tokens", "Tempo"} and my_creatures == 0 and early_turn and in_main:
            return -1.8 + bonus_face
        # Log-driven priors: leverage observed tournament/simulation cast timing.
        return self._historical_cast_timing_bias(state, card, player_id) + bonus_face

    def _graveyard_recursion_bonus(self, state: MatchState, player_id: int) -> float:
        targets = sum(
            1
            for grave_id in getattr(state.players[player_id], "graveyard", []) or []
            if grave_id in state.cards
            and bool(set(effective_types(state, state.cards[grave_id]) or []) & {"Instant", "Sorcery"})
        )
        # Graveyard-casting threats are premium only when a qualifying spell
        # is available to recast; otherwise preserve mana for another line.
        return 3.0 if targets else -1.5

    def _historical_cast_timing_bias(self, state: MatchState, card, player_id: int) -> float:
        priors = AIAgent._log_priors_cache or {}
        cards = priors.get("cards") if isinstance(priors, dict) else None
        if not isinstance(cards, dict):
            return 0.0
        key = str(getattr(card, "name", "") or "").strip().lower()
        row = cards.get(key)
        if not isinstance(row, dict):
            return 0.0
        casts = int(row.get("casts", 0) or 0)
        if casts < 6:
            return 0.0
        turn = int(getattr(state, "turn", 1) or 1)
        role = self._board_role(state, player_id)
        role_rows = row.get("board_roles")
        if isinstance(role_rows, dict):
            role_row = role_rows.get(role)
            if not isinstance(role_row, dict) and role in {"stabilize", "defend"}:
                role_row = role_rows.get("control")
            if isinstance(role_row, dict):
                role_casts = int(role_row.get("casts", 0) or 0)
                if role_casts >= 3:
                    row = role_row
        preferred_min = int(row.get("preferred_min_turn", 1) or 1)
        early_rate = float(row.get("early_turn_cast_rate", 0.0) or 0.0)
        late_rate = float(row.get("late_turn_cast_rate", 0.0) or 0.0)
        text = (getattr(card, "oracle_text", "") or "").lower()
        non_creature = "Creature" not in set(effective_types(state, card) or [])
        # Slow-play/control heuristics from logs: punish premature timing on low-early cards.
        if turn < preferred_min and early_rate <= 0.2 and non_creature:
            severity = min(3.5, max(0.6, (preferred_min - turn) * 0.8))
            if _has_counter_spell_text(text) and not (getattr(state, "stack", []) or []):
                severity += 0.8
            return -severity
        # Reward cards historically skewed late once the game is developed.
        if turn >= preferred_min and late_rate >= 0.45:
            return 0.8
        return 0.0

    def _x_spell_timing_penalty(self, state: MatchState, card, player_id: int, x_value: int) -> float:
        text = _oracle_text(card)
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        if x_value <= 0:
            return -8.0
        if ALL_CREATURES_X_DEBUFF_RE.search(getattr(card, "oracle_text", "") or ""):
            opponent = state.players[3 - player_id]
            if not any(
                cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
                and effective_toughness(state, cid) <= x_value
                for cid in opponent.battlefield
            ):
                return -8.0
        # Token X-spells (e.g. Secure the Wastes): avoid low-impact early casts.
        if "create x" in text and "token" in text:
            if x_value <= 1:
                return -7.0
            if x_value == 2 and turn < 7:
                return -4.0
            if x_value <= 3 and self.archetype in {"Control", "Counter-heavy"} and opp_life > 8:
                return -2.0
        # Draw-X spells should usually wait for meaningful value.
        if "draw x" in text and x_value <= 1:
            return -3.0
        # X-damage with tiny X is usually poor unless lethal.
        if "deals x damage" in text and x_value <= 1 and opp_life > x_value:
            return -2.5
        return 0.0

    def _approximate_resolution_for_creature_cast(self, sim_state: MatchState, move: dict, player_id: int) -> None:
        if move.get("type") == "equip":
            if sim_state.stack and sim_state.stack[-1].effect_key == "equip_attachment" and sim_state.priority_player == player_id:
                self.engine.take_action(sim_state, player_id, {"type": "pass_priority"})
                self.engine.take_action(sim_state, 3 - player_id, {"type": "pass_priority"})
            return
        if move.get("type") != "cast_spell":
            return
        cid = move.get("card_id")
        if not cid:
            return
        card = sim_state.cards.get(cid)
        from rules_engine.attachments import is_aura
        if not card or ("Creature" not in card.types and not is_aura(card)):
            return
        if not getattr(sim_state, "stack", []):
            return
        # Approximation: if both players pass, this permanent resolves.
        # This prevents lookahead from systematically undervaluing creature development.
        if sim_state.priority_player != player_id:
            return
        opp_id = 1 if player_id == 2 else 2
        self.engine.take_action(sim_state, player_id, {"type": "pass_priority"})
        self.engine.take_action(sim_state, opp_id, {"type": "pass_priority"})

    def _approximate_resolution_for_ramp_spell(self, sim_state: MatchState, move: dict, player_id: int) -> None:
        if move.get("type") != "cast_spell":
            return
        cid = move.get("card_id")
        if not cid:
            return
        card = sim_state.cards.get(cid)
        if not card:
            return
        text = _oracle_text(card)
        if "land" not in text or "ramp" not in self._spell_tags(card):
            return
        if "put a land card from your hand onto the battlefield" not in text and "search your library for" not in text:
            return
        land_ids = [
            lid
            for lid in list(sim_state.players[player_id].library)
            if lid in sim_state.cards and "Land" in sim_state.cards[lid].types
        ]
        if not land_ids:
            return

        first = land_ids[0]
        if first in sim_state.players[player_id].library:
            sim_state.players[player_id].library.remove(first)
            sim_state.players[player_id].battlefield.append(first)
            land = sim_state.cards[first]
            land.zone = Zone.BATTLEFIELD
            land.controller = player_id
            land.tapped = True
            land.summoning_sick = False

        if "put it into your hand" in text or "put that card into your hand" in text or "put it into your hand" in text:
            if len(land_ids) > 1:
                second = land_ids[1]
                if second in sim_state.players[player_id].library:
                    sim_state.players[player_id].library.remove(second)
                    sim_state.players[player_id].hand.append(second)
                    land2 = sim_state.cards[second]
                    land2.move_to_zone(Zone.HAND)
                    land2.controller = player_id

    def _spell_tags(self, card) -> set[str]:
        return tactical_tags(
            getattr(card, "oracle_text", ""), getattr(card, "type_line", ""),
            getattr(card, "types", None),
        )

    def _modal_face_options(self, card) -> list[dict]:
        faces = list(getattr(card, "card_faces", []) or [])
        return faces[:1] if getattr(card, "layout", "") in {"transform", "meld", "flip", "double_faced_token"} else faces

    def _modal_face_proxy(self, card, face: dict) -> object:
        proxy = type("ModalFaceProxy", (), {})()
        proxy.name = str(face.get("name") or getattr(card, "name", ""))
        proxy.oracle_text = str(face.get("oracle_text") or getattr(card, "oracle_text", "") or "")
        proxy.mana_cost = str(face.get("mana_cost") or getattr(card, "mana_cost", "") or "")
        proxy.types = self._types_from_type_line(str(face.get("type_line") or getattr(card, "type_line", "") or ""))
        return proxy

    def _types_from_type_line(self, type_line: str) -> list[str]:
        tl = (type_line or "").strip()
        if not tl:
            return []
        parts = tl.split("—", 1)
        primary = parts[0]
        if "-" in primary:
            primary = primary.split("-", 1)[0]
        return [part.strip() for part in primary.split() if part.strip()]

    def _score_modal_face(self, state: MatchState, card, face: dict, player_id: int) -> float:
        proxy = self._modal_face_proxy(card, face)
        tags = self._spell_tags(proxy)
        text = _oracle_text(proxy)
        mana_req = parse_mana_cost(getattr(proxy, "mana_cost", ""), is_land=False)
        cmc = mana_req["generic"] + sum(mana_req[c] for c in ["W", "U", "B", "R", "G"])
        score = 0.0
        types = set(effective_types(state, proxy) or [])
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        my_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        early_turn = int(getattr(state, "turn", 1) or 1) <= 4
        board_pressure = max(0, opp_creatures - my_creatures)
        if "burn" in tags or "damage" in text:
            score += 1.4
        if "draw" in tags:
            score += 1.2
            if self.archetype in {"Control", "Counter-heavy"} and opp_life > 10:
                score += 0.8
            if self.archetype == "Tempo" and my_creatures > 0:
                score += 0.3
        if "counter" in tags:
            score += 2.1 if getattr(state, "stack", []) else -1.0
            if self.archetype in {"Control", "Counter-heavy", "Tempo"} and getattr(state, "stack", []):
                score += 0.8
        if "removal" in tags:
            score += 1.8 if opp_creatures > 0 else -1.0
            if opp_creatures >= 2:
                score += 0.5
        if "token" in tags:
            score += 1.0
        if "attack" in tags:
            score += 0.6
            if self.archetype in {"Aggro", "Tempo", "Tokens", "Tribal"}:
                score += 0.7
        if "block" in tags:
            score += 0.5
            if self.archetype in {"Control", "Counter-heavy", "Midrange"}:
                score += 0.5
        if "Creature" in types:
            score += 0.5
            if self.archetype in {"Aggro", "Tempo", "Tribal", "Tokens"}:
                score += 1.3 if cmc <= 3 else 0.7
                if my_creatures == 0:
                    score += 0.9
                if early_turn:
                    score += 0.5
                if "flash" in text or "haste" in text:
                    score += 0.4
            elif self.archetype in {"Midrange", "Ramp"}:
                if cmc <= 4 or (getattr(proxy, "power", None) or 0) + (getattr(proxy, "toughness", None) or 0) >= 4:
                    score += 1.0
                if early_turn and cmc >= 4:
                    score -= 0.3
            else:
                # Control and counter-heavy decks should only value the creature face
                # when it meaningfully stabilizes the board or carries immediate utility.
                if my_creatures == 0 and opp_creatures == 0 and cmc <= 3:
                    score += 0.4
                else:
                    score -= 0.2
                if early_turn and cmc >= 4:
                    score -= 0.8
                if "flash" in text or "lifelink" in text or "flying" in text:
                    score += 0.3
        if cmc <= 2:
            score += 0.5
        if self.archetype in {"Control", "Counter-heavy"} and any(k in tags for k in {"draw", "counter", "removal"}):
            score += 1.3
            if board_pressure > 0:
                score += min(0.9, board_pressure * 0.35)
        if self.archetype in {"Burn", "Aggro"} and ("damage" in text or "burn" in tags):
            score += 1.2
        if self.archetype == "Tempo" and (cmc <= 2 or "counter" in tags):
            score += 0.9
        if self.archetype in {"Midrange", "Ramp"} and "Creature" in types and cmc <= 3:
            score += 0.7
        turn = int(getattr(state, "turn", 1) or 1)
        if turn <= 3 and score < 1.0:
            score -= 1.5
        if turn >= 6 and "Creature" in types and my_creatures <= opp_creatures:
            score += 0.6
        if turn >= 6 and ("draw" in tags or "counter" in tags or "removal" in tags):
            score += 0.4
        if cmc >= 5 and early_turn:
            score -= 0.5
        if self.archetype in {"Control", "Counter-heavy"} and "Creature" in types and not any(k in tags for k in {"draw", "counter", "removal"}):
            score -= 0.1
        return score

    def _select_modal_face_index(self, state: MatchState, card, player_id: int) -> tuple[int, float]:
        faces = self._modal_face_options(card)
        if len(faces) <= 1:
            return 0, 0.0
        scored: list[tuple[float, int]] = []
        for idx, face in enumerate(faces):
            scored.append((self._score_modal_face(state, card, face, player_id), idx))
        scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        best_score, best_idx = scored[0]
        if best_score <= 0.0:
            return 0, best_score
        return best_idx, best_score

    def _score_mode_text(self, state: MatchState, card, mode_text: str, player_id: int) -> float:
        text = (mode_text or "").lower()
        from rules_engine.linked_discard import linked_discard_effect, simultaneous_discard_draw_effect
        wheel = simultaneous_discard_draw_effect(text)
        if wheel:
            return self._wheel_exchange_value(state, player_id, wheel['draw_followup'], card.id) / 5
        linked = linked_discard_effect(text)
        if linked and linked.get('up_to') and linked['followup_effect']['effect_key'] == 'draw_cards':
            options = [cid for cid in state.players[player_id].hand if cid != card.id]
            _, value = self._linked_draw_trade(state, player_id, options, linked.get('amount', len(options)))
            return value / 5 if value > 0 else -8.0
        if isinstance(state, MatchState) and _only_counter_spell_text(text):
            from rules_engine.oracle_effects import inspect_target_hints
            options = inspect_target_hints(state, card, player_id, {"mode_text": mode_text}).get("stack_targets") or []
            if self._choose_best_stack_target_id(state, player_id, options, allow_protected=False) is None:
                return -8.0
        tags = self._spell_tags(card)
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        my_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        turn = int(getattr(state, "turn", 1) or 1)
        role = self._board_role(state, player_id)
        board_pressure = opp_creatures - my_creatures
        score = 0.0
        if "counter" in text:
            score += 3.2 if getattr(state, "stack", []) else 0.2
            if self.archetype in {"Control", "Counter-heavy", "Tempo"}:
                score += 1.4
            if role in {"stabilize", "defend"} and getattr(state, "stack", []):
                score += 0.8
        if "destroy" in text or "exile" in text or "bounce" in text:
            score += 2.2 if opp_creatures > 0 else -0.6
            if opp_creatures >= 2:
                score += 0.4
            if self.archetype in {"Control", "Counter-heavy", "Tempo", "Midrange"}:
                score += 0.6
            if role in {"stabilize", "defend"}:
                score += 0.6
            if board_pressure > 0:
                score += min(1.0, board_pressure * 0.25)
        if "draw" in text:
            score += 1.6
            if self.archetype in {"Control", "Counter-heavy"} and opp_life > 10:
                score += 0.8
            if self.archetype in {"Tempo", "Aggro"} and my_creatures > 0:
                score += 0.2
            if role in {"normal", "control"} and board_pressure <= 0:
                score += 0.2
        if "create" in text and "token" in text:
            score += 1.7
            if self.archetype in {"Aggro", "Tokens", "Tribal", "Tempo"}:
                score += 1.0
                if my_creatures == 0:
                    score += 0.7
            elif self.archetype in {"Control", "Counter-heavy"}:
                score += 0.25 if opp_creatures > my_creatures else -0.4
            if role in {"race", "convert"}:
                score += 0.7
        if "damage" in text or "burn" in tags:
            score += 1.3
            if self.archetype in {"Burn", "Aggro", "Tempo"}:
                score += 0.8
            elif opp_life <= 6:
                score += 0.6
            if role == "race":
                score += 0.5
        if "gain" in text or "life" in text:
            score += 0.7
            if self.archetype in {"Control", "Counter-heavy"} and state.players[player_id].life <= 10:
                score += 0.5
            if role in {"stabilize", "defend"} and state.players[player_id].life <= 12:
                score += 0.4
        if "attack" in text:
            score += 0.7
            if role == "convert":
                score += 0.5
        if "block" in text:
            score += 0.5
            if role in {"stabilize", "defend"}:
                score += 0.3
        if "dies" in text or "sacrifice" in text:
            score += 0.8
            if self.archetype in {"Aristocrats", "Drain"}:
                score += 0.9
            if role in {"stabilize", "convert"}:
                score += 0.2
        if "ramp" in tags or "add mana" in text:
            score += 1.0
            if self.archetype in {"Ramp", "Midrange"}:
                score += 1.4
            if role in {"normal", "convert"} and turn <= 5:
                score += 0.4
        if "discard" in text or "mill" in text:
            score += 1.1
            if self.archetype in {"Control", "Counter-heavy"}:
                score += 0.5
            if role in {"stabilize", "defend"}:
                score += 0.3
        if turn <= 3 and score < 1.0:
            score -= 1.0
        if turn >= 6 and ("draw" in text or "counter" in text or "destroy" in text or "exile" in text):
            score += 0.4
        return score

    def _select_mode_text(self, state: MatchState, card, modes: list[str], player_id: int) -> str:
        if not modes:
            return ""
        scored = [(self._score_mode_text(state, card, mode, player_id), idx, mode) for idx, mode in enumerate(modes)]
        scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        best_score, _, best_mode = scored[0]
        if best_score <= 0.0:
            return modes[0]
        return best_mode

    def _select_mode_texts(self, state: MatchState, card, modes: list[str], player_id: int) -> list[str]:
        if len(modes) <= 2:
            scored = sorted(
                [(self._score_mode_text(state, card, mode, player_id), idx, mode) for idx, mode in enumerate(modes)],
                key=lambda item: (item[0], -item[1]),
                reverse=True,
            )
            return [mode for _, _, mode in scored]
        scored = sorted(
            [(self._score_mode_text(state, card, mode, player_id), idx, mode) for idx, mode in enumerate(modes)],
            key=lambda item: (item[0], -item[1]),
            reverse=True,
        )
        return [scored[0][2], scored[1][2]]

    def _burn_has_only_friendly_targets(self, state: MatchState, move: dict, player_id: int) -> bool:
        if move.get("type") != "cast_spell":
            return False
        card = state.cards.get(move.get("card_id"))
        if card is None or not re.fullmatch(r"[^.\n]*\bdeals? \d+ damage to any target\.", (getattr(card, "oracle_text", "") or "").strip(), re.I):
            return False
        hints = move.get("target_hints") or {}
        opponent = 3 - player_id
        if any(int(target["id"]) == opponent for target in hints.get("player_targets") or []):
            return False
        return not any(
            state.cards[target["id"]].controller == opponent
            for key in ("creature_targets", "planeswalker_targets")
            for target in hints.get(key) or []
            if target.get("id") in state.cards
        )

    def _without_losing_mass_destruction(self, state, moves, player_id):
        """Do not wipe into a proven public death-trigger loss; unknowns stay."""
        if not isinstance(state, MatchState) or not any(
            re.search(r"\bdies\b[^.\n]*\bloses?\s+\d+\s+life", _oracle_text(state.cards[cid]))
            for cid in state.players[3 - player_id].battlefield
        ):
            return moves
        from ai.pending_effects import unanswered_action_loses
        kept = []
        for move in moves:
            card = _card_for_move(state, move)
            if (move.get("type") == "cast_spell" and card
                    and "{X}" not in card.mana_cost.upper()
                    and re.search(r"\bdestroy all (?:creatures|nonland permanents|permanents)\b", _oracle_text(card))):
                action = self._materialize_action(state, move, player_id)
                if not action.get("_invalid_ai_choice") and unanswered_action_loses(state, player_id, action) is True:
                    continue
            kept.append(move)
        return kept

    def _without_losing_life_actions(self, state, moves, player_id):
        """Do not force conversion into a checked public life-replacement loss."""
        from rules_engine.replacement import replacement_options
        if not isinstance(state, MatchState) or not replacement_options(state, 'life_gain', target_player=player_id):
            return moves
        from ai.pending_effects import unanswered_action_loses
        kept = []
        for move in moves:
            card = _card_for_move(state, move)
            if (move.get('type') in {'cast_spell', 'activate_ability', 'activate_loyalty'} and card
                    and ('gain' in self._spell_tags(card)
                         or re.search(r'\bgains?\b[^.\n]*\blife\b', str(move.get('ability_label') or ''), re.I))):
                action = self._materialize_action(state, move, player_id)
                if not action.get('_invalid_ai_choice') and unanswered_action_loses(state, player_id, action) is True:
                    continue
            kept.append(move)
        return kept

    def _winning_self_removal_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if not isinstance(state, MatchState):
            return None
        from ai.pending_effects import unanswered_action_wins
        choice_agent = AIAgent(difficulty=self.difficulty, archetype=self.archetype, opponent_archetype=self.opponent_archetype)
        friendly = set(state.players[player_id].battlefield)
        for move in legal_moves:
            if move.get("type") not in {"cast_spell", "activate_ability", "activate_loyalty"}:
                continue
            card = state.cards.get(move.get("card_id"))
            if card is None:
                continue
            text = move.get("ability_label") or card.oracle_text
            faces = getattr(card, "card_faces", []) or []
            if move.get("type") == "cast_spell" and faces and move.get("selected_face_index") is not None:
                text = faces[int(move["selected_face_index"])].get("oracle_text", text)
            if "destroy target" not in text.lower():
                continue
            candidates = {target["id"] for key, options in (move.get("target_hints") or {}).items()
                          if key.endswith("_targets") and isinstance(options, list)
                          for target in options if target.get("id") in friendly}
            for cid in sorted(candidates, key=lambda cid: (self._sacrifice_loss(state, cid, player_id), cid)):
                candidate = {**move, "targets": {**(move.get("targets") or {}), "target_card_id": cid}}
                action = self._materialize_action(state, candidate, player_id, allow_friendly_target=True)
                if action.get("_invalid_ai_choice") or self._is_unplayable_x_action(action):
                    continue
                if unanswered_action_wins(
                    state, player_id, action,
                    own_choice_action=lambda projected, legal, pid: choice_agent.choose_action(projected, legal, pid).action,
                ) is True:
                    return action
        return None

    def _attachment_projection(self, state: MatchState, move: dict, player_id: int) -> tuple[dict | None, float]:
        from rules_engine.stack_engine import resolve_top_of_stack
        from rules_engine.state_based_actions import apply_state_based_actions
        source = state.cards.get(move.get("card_id"))
        if source is None:
            return None, 0.0
        casting = move.get("type") == "cast_spell"
        targets = (move.get("target_hints") or {}).get("aura_targets", []) if casting else move.get("targets", [])
        before = evaluate_board(state, player_id)
        best = None
        for target in targets:
            if not casting and source.attached_to == target["id"]:
                continue
            action = {"type": "equip", "card_id": source.id, "target_card_id": target["id"]}
            if casting:
                compatible = move["target_hints"].get("aura_cost_options", {}).get(target["id"], [])
                action = {"type": "cast_spell", "card_id": source.id, "targets": {"target_card_id": target["id"]}}
                action.update({flag: True for flag in ("from_exile", "from_graveyard", "from_library") if move.get(flag)})
                if compatible:
                    action["cost_choice"] = {"id": compatible[0]}
                if move.get("selected_face_index") is not None:
                    action["selected_face_index"] = move["selected_face_index"]
            projected = planning_copy(state)
            try:
                self.engine.take_action(projected, player_id, action, reject_invalid=True)
                if not projected.stack or not resolve_top_of_stack(projected):
                    continue
                if casting:
                    # Immediate cast triggers (for example heroic) resolve above
                    # the Aura. Do not value an unfinished paid spell as a buff.
                    for _ in range(64):
                        if projected.cards[source.id].zone != Zone.STACK:
                            break
                        if not resolve_top_of_stack(projected):
                            break
                    if projected.cards[source.id].zone == Zone.STACK:
                        continue
                apply_state_based_actions(projected)
            except (ValueError, KeyError):
                continue
            from ai.mana_resource_policy import resource_delta
            from rules_engine.land_types import land_type_instructions
            gain = (evaluate_board(projected, player_id) - before
                    + (resource_delta(state, projected, player_id, excluded_card_ids={source.id})
                       if land_type_instructions(source.oracle_text) else 0.0))
            if gain <= 1e-9:
                continue
            score = (gain, self._creature_threat_score(projected, target["id"], player_id), target["id"])
            if best is None or score > best[0]:
                best = (score, action)
        return (best[1], best[0][0]) if best else (None, 0.0)

    def _spell_payment_loss(self, state, player_id, option, life_value=1):
        life = option.get('pay_life', 0)
        remaining = state.players[player_id].life - life
        loss = float('inf') if life and remaining <= 0 else life * (2 if remaining <= 5 else life_value)
        for key, count, rank in [
            ('discard_card_ids', option.get('discard_cards', 0), self._hand_retention_value),
            ('sacrifice_card_ids', option.get('sacrifice_creatures', 0), self._sacrifice_loss),
        ]:
            if option.get('discard_all' if key == 'discard_card_ids' else 'sacrifice_all'):
                count = len(option.get(key, []))
            values = sorted(rank(state, cid, player_id) for cid in option.get(key, []))
            if len(values) < count:
                return float('inf')
            loss += sum(values[:count])
        return loss

    def _kicker_draw_gain(self, state, player_id, base_count, kicked_count):
        """Use public library counts and restrictions, never future card identities."""
        from rules_engine.draw_restrictions import forecast_draw_count
        capacity = forecast_draw_count(state, player_id, kicked_count)
        if capacity > len(state.players[player_id].library):
            return -1000
        base_capacity = forecast_draw_count(state, player_id, base_count)
        return 3 * max(0, capacity - base_capacity)

    def _kicked_cast_gain(self, state, player_id):
        from rules_engine.kicker import kicked_cast_clauses
        from rules_engine.counter_placement import counter_placement_forbidden
        from rules_engine.continuous import printed_abilities_suppressed
        value = 0
        for cid in state.players[player_id].battlefield:
            source = state.cards[cid]
            if printed_abilities_suppressed(state, cid):
                continue
            for clause in kicked_cast_clauses(source.oracle_text):
                text = clause['instruction'].lower()
                if text.startswith('create '):
                    value += 3
                elif text.startswith('put '):
                    counter = re.search(r'([+-]\d+/[+-]\d+)', text)[1]
                    if not counter_placement_forbidden(state, counter, target_card_id=cid):
                        value += 1
                elif (not source.tapped and not source.summoning_sick
                      and state.step in {Step.PRECOMBAT_MAIN, Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS}):
                    power = int(re.search(r'toughness (\d+)/(\d+)', text)[1])
                    value += max(0, power - effective_power(state, cid))
        return value

    def _kicker_gain(self, state, card, player_id, hints):
        """Known damage breakpoints/card gain, not hidden draws or full search."""
        from rules_engine.kicker import kicker_surfaces, permanent_kicker
        surfaces = kicker_surfaces(card.oracle_text)
        if not surfaces:
            permanent = permanent_kicker(card.oracle_text)
            if not permanent:
                return float('-inf')
            score = self._kicked_cast_gain(state, player_id) - 0.4 * mana_value(permanent['price'])
            counters = permanent.get('counters', {}).get('+1/+1', 0)
            if counters:
                from rules_engine.counter_placement import counter_placement_forbidden
                if counter_placement_forbidden(state, '+1/+1', target_card_id=card.id):
                    return score
                return score + 0.8 * counters
            text = permanent.get('instruction', '')
            draw = re.fullmatch(r'draw (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?\.', text, re.I)
            if draw:
                return score + self._kicker_draw_gain(state, player_id, 0, _parse_count_token(draw[1].lower()))
            if text.lower().startswith('create '):
                return score + 3
            from copy import copy
            from rules_engine.oracle_effects import inspect_target_hints
            proxy = copy(card)
            proxy.oracle_text, proxy.card_faces, proxy.types = text, [], []
            target_hints = inspect_target_hints(state, proxy, player_id)
            candidates = {target['id'] for key, targets in target_hints.items()
                          if key.endswith('_targets') and isinstance(targets, list)
                          for target in targets if isinstance(target, dict) and 'id' in target}
            damage = re.search(r'deals (\d+) damage', text)
            for cid in state.players[3-player_id].battlefield:
                if cid not in candidates or has_keyword(state, cid, 'indestructible'):
                    continue
                if damage and effective_toughness(state, cid) - int(state.cards[cid].counters.get('__damage_marked', 0)) > int(damage[1]):
                    continue
                return score + 5
            return score
        price, base, kicked = surfaces
        opponent = 3-player_id
        score = self._kicked_cast_gain(state, player_id) - 0.4 * mana_value(price)
        amounts = [re.search(r'\bdeals? (\d+) damage', text, re.I) for text in [base, kicked]]
        if all(amounts):
            low, high = [int(amount[1]) for amount in amounts]
            if low < state.players[opponent].life <= high and any(target['id'] == opponent for target in hints.get('player_targets', [])):
                score += 100
            legal_creatures = {target['id'] for target in hints.get('creature_targets', [])}
            for cid in state.players[opponent].battlefield:
                remaining = effective_toughness(state, cid) - int(state.cards[cid].counters.get('__damage_marked', 0))
                if cid in legal_creatures and not has_keyword(state, cid, 'indestructible') and low < remaining <= high:
                    score += 5 + self._creature_threat_score(state, cid, player_id)
                    break
        def draws(text):
            return sum(_parse_count_token(amount) for amount in re.findall(r'\bdraw (a|one|two|three|\d+) cards?\b', text, re.I))
        score += self._kicker_draw_gain(state, player_id, draws(base), draws(kicked))
        pumps = [re.search(r'gets ([+-]\d+)/([+-]\d+)', text, re.I) for text in [base, kicked]]
        if all(pumps) and int(pumps[1][2]) < int(pumps[0][2]) <= 0:
            from ai.pending_effects import negative_pt_would_be_lethal
            low, high = [tuple(map(int, pump.groups())) for pump in pumps]
            legal_creatures = {target['id'] for target in hints.get('creature_targets', [])}
            for cid in state.players[opponent].battlefield:
                if (cid in legal_creatures and not negative_pt_would_be_lethal(state,cid,*low)
                        and negative_pt_would_be_lethal(state,cid,*high)):
                    score += 5 + self._creature_threat_score(state, cid, player_id)
                    break
        def discards(text):
            match = re.search(r'target player discards (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?', text, re.I)
            return _parse_count_token(match[1].lower()) if match else 0
        hand_count = len(state.players[opponent].hand)
        score += 3 * max(0, min(hand_count, discards(kicked)) - min(hand_count, discards(base)))
        if re.search(r'gets \+\d+/\+\d+', kicked) and state.step in {Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS}:
            score += 3
        return score

    def _materialize_action(self, state: MatchState, move: dict, player_id: int, *, allow_friendly_target: bool = False, allow_zero_x: bool = False) -> dict:
        mtype = move.get("type")
        from rules_engine.attachments import is_aura
        source = state.cards.get(move.get("card_id"))
        from ai.information import is_unknown
        if is_unknown(source):
            return {**move, '_invalid_ai_choice': True}
        if source is not None and move.get("selected_face_index") is not None:
            from rules_engine.card_faces import select_cast_face
            source = select_cast_face(source, int(move["selected_face_index"]))
        if source is not None and move.get('cast_variant') == 'bestow':
            from rules_engine.bestow import bestow_cast_view
            source = bestow_cast_view(source)
        if mtype == "equip" or (mtype == "cast_spell" and source is not None and is_aura(source)):
            action, _ = self._attachment_projection(state, move, player_id)
            return action or {"type": mtype, "card_id": move.get("card_id"), "_invalid_ai_choice": True}
        if mtype == "attack":
            out = dict(move)
            candidates = list(move.get("options") or out.get("attackers") or [])
            if candidates:
                out["attackers"] = self._choose_attackers(state, candidates, player_id)
            return out
        if mtype == "block":
            out = dict(move)
            attackers = list(move.get("attackers") or [])
            blockers = list(move.get("blockers") or [])
            if attackers and blockers and not out.get("blocks"):
                out["blocks"] = self._choose_blocks(state, attackers, blockers)
            return out
        if mtype == "crew":
            out = dict(move)
            if "suggested_crew_card_ids" in move:
                out["crew_card_ids"] = list(move["suggested_crew_card_ids"])
                return out
            options = list(move.get("crew_candidates") or [])
            required = int(move.get("crew_value", 0) or 0)
            selected: list[str] = []
            power = 0
            for option in sorted(options, key=lambda item: (int(item.get("power", 0) or 0), str(item.get("name") or "")), reverse=True) if required > 0 else []:
                selected.append(option["id"])
                power += max(0, int(option.get("power", 0) or 0))
                if power >= required:
                    break
            if power >= required:
                out["crew_card_ids"] = selected
            return out
        if mtype not in {"cast_spell", "activate_loyalty", "activate_ability"}:
            return move
        out = dict(move)
        hints = move.get("target_hints") or {}
        targets = dict((move.get("targets") or {}))
        cost_options = move.get("cost_options") or []
        if cost_options and not (move.get("cost_choice") or {}).get("id"):
            selected_cost = cost_options[0]
            if selected_cost.get('additional_cost_group'):
                group = selected_cost['additional_cost_group']
                alternatives = [option for option in cost_options if option.get('additional_cost_group') == group]
                selected_cost = min(alternatives, key=lambda option: (self._spell_payment_loss(state, player_id, option), option['id']))
            if source is not None and not selected_cost.get('kicked'):
                from rules_engine.costs import casting_method
                from rules_engine.kicker import kicker_cost
                extra = kicker_cost(source) or {}
                alternatives = [option for option in cost_options if option.get('kicked')
                                and option.get('kicker_base_id') == casting_method(selected_cost['id'])
                                and all(option.get(key, 0) == selected_cost.get(key, 0) + extra.get(key, 0)
                                        for key in ['pay_life', 'discard_cards', 'sacrifice_creatures'])
                                and option.get('sacrifice_kind') == extra.get('sacrifice_kind', selected_cost.get('sacrifice_kind'))]
                if alternatives:
                    candidate = alternatives[0]
                    added_loss = (self._spell_payment_loss(state, player_id, candidate, life_value=0.25)
                                  - self._spell_payment_loss(state, player_id, selected_cost, life_value=0.25))
                    if self._kicker_gain(state, source, player_id, candidate.get('target_hints') or {}) > added_loss:
                        selected_cost = candidate
            out["cost_choice"] = {"id": selected_cost["id"]}
        selected_cost = next((option for option in cost_options
                              if option['id'] == (out.get('cost_choice') or {}).get('id')), None)
        if selected_cost and selected_cost.get('target_hints') is not None:
            hints = selected_cost['target_hints']
        tags: set[str] = set()
        cid = move.get("card_id")
        card = state.cards.get(cid) if cid else None
        if card:
            tags = self._spell_tags(card)
            if mtype == "cast_spell" and self._modal_face_options(card):
                if getattr(card, "layout", "") in {"modal_dfc", "adventure", "split"}:
                    selected_face_index = int(move.get("selected_face_index", 0))
                else:
                    selected_face_index, _ = self._select_modal_face_index(state, card, player_id)
                out["selected_face_index"] = selected_face_index
                if getattr(card, "layout", "") in {"modal_dfc", "adventure", "split"}:
                    from rules_engine.card_faces import select_cast_face
                    from rules_engine.cast_choice import build_cast_hints
                    card = select_cast_face(card, selected_face_index)
                    tags = self._spell_tags(card)
                    hints = build_cast_hints(state, card, player_id, targets)
        opponent = 1 if player_id == 2 else 2

        # Choose the mode before deriving target candidates. Modal spells can
        # expose different target classes per mode (for example, counter
        # versus destroy), so selecting targets from the unselected union can
        # create invalid or strategically incoherent actions.
        if hints.get("modes") and not targets.get("mode_text") and not targets.get("mode_texts"):
            available_modes = list(hints.get("available_modes", hints["modes"]))
            if hints.get("choose_two_modes"):
                targets["mode_texts"] = self._select_mode_texts(state, card, available_modes, player_id)
            else:
                targets["mode_text"] = self._select_mode_text(state, card, available_modes, player_id)
        if targets.get("mode_text") or targets.get("mode_texts"):
            from rules_engine.cast_choice import build_cast_hints

            hints = build_cast_hints(state, card, player_id, targets)

        if mtype == 'cast_spell' and card is not None:
            from rules_engine.kicker import spell_kicker_view
            card = spell_kicker_view(card, bool(selected_cost and selected_cost.get('kicked')))
            tags = self._spell_tags(card)
        if isinstance(state, MatchState) and card is not None:
            from ai.pending_effects import covered_removal_targets, unproductive_destroy_targets
            ability_text = str(move.get("ability_label") or "").partition(":")[2].strip() if mtype != "cast_spell" else None
            excluded = unproductive_destroy_targets(state, card, player_id, targets, ability_text=ability_text,
                action=out, own_choice_action=lambda projected, legal, pid: self.choose_action(projected, legal, pid).action,
                candidates={target.get('id') for key, group in hints.items() if key.endswith('_targets') and isinstance(group, list)
                            for target in group if isinstance(target, dict)} | {targets.get('target_card_id')})
            friendly_target = targets.get("target_card_id")
            if allow_friendly_target and friendly_target in state.players[player_id].battlefield:
                excluded.discard(friendly_target)
            if mtype == "cast_spell":
                excluded |= covered_removal_targets(state, card, player_id, targets) or set()
            if excluded:
                if targets.get("target_card_id") in excluded:
                    out["_invalid_ai_choice"] = True
                    return out
                hints = {key: [candidate for candidate in value if candidate.get("id") not in excluded]
                         if key.endswith("_targets") and isinstance(value, list) else value
                         for key, value in hints.items()}
                from rules_engine.cast_choice import has_available_targets_for_action
                if not has_available_targets_for_action({**hints, "modes": []}):
                    out["_invalid_ai_choice"] = True
                    return out

        stack_targets = hints.get("stack_targets") or []
        if stack_targets and not targets.get("target_stack_id"):
            # For counters/interaction, target the most threatening spell on stack.
            if "counter" in tags:
                allow_friendly = bool(re.search(r"counter target[^.\n]{0,60}(?:spell|ability) you control", card.oracle_text.lower()))
                selected_text = "\n".join(targets.get("mode_texts") or []) or targets.get("mode_text") or card.oracle_text
                best = self._choose_best_stack_target_id(
                    state, player_id, stack_targets, allow_friendly=allow_friendly,
                    allow_protected=not _only_counter_spell_text(selected_text),
                )
                if best is None:
                    out["_invalid_ai_choice"] = True
                    return out
                targets["target_stack_id"] = best
            else:
                # Default to top-of-stack for most non-counter interactions.
                targets["target_stack_id"] = stack_targets[-1]["id"]

        if 'linked_target_pairs' in hints:
            from ai.linked_targets import choose_linked_pair
            from rules_engine.linked_targets import validate_linked_choice
            selected = targets if validate_linked_choice(hints, targets)[0] else choose_linked_pair(
                self, state, player_id, out, hints)
            if selected is None:
                out['_invalid_ai_choice'] = True
            else:
                out['targets'] = selected
            return out
        target_text = str(targets.get("mode_text") or move.get("ability_label") or getattr(card, "oracle_text", "") or "").lower()
        player_targets = hints.get("player_targets") or []
        if player_targets and targets.get("target_player") is None and not targets.get("target_card_id"):
            allowed_players = {int(target["id"]) for target in player_targets}
            if re.search(r"\btarget player gains\b[^.\n]*\blife\b", target_text) and "drain" not in tags:
                preferred = player_id
                from rules_engine.landfall import alternative_effect
                from rules_engine.land_history import landfall_status
                alternative = alternative_effect(target_text, {})
                status = landfall_status(state, player_id)
                amount_match = re.search(r'\btarget player gains (\d+) life\.', target_text)
                amount = int(amount_match[1]) if amount_match and alternative is None else 0
                if alternative is not None and status is not None:
                    amount = int(alternative[1]['branches'][int(status)]['payload'].get('amount', 0))
                if amount > 0:
                    from ai.life_targets import life_target_score
                    scores = {target: life_target_score(state, player_id, target, amount)
                              for target in allowed_players}
                    if all(score is not None for score in scores.values()):
                        preferred = max(sorted(allowed_players),
                                        key=lambda target: (scores[target], target == player_id))
            else:
                preferred = opponent
            targets["target_player"] = preferred if preferred in allowed_players else min(allowed_players)

        creature_targets = hints.get("creature_targets") or []
        if (re.search(r"return target[^.\n]+to its owner's hand", target_text)
                and not targets.get('target_card_id') and not targets.get('target_card_ids')):
            bounce_targets = {target['id']: target for key in ('creature_targets', 'planeswalker_targets',
                'permanent_targets', 'artifact_targets', 'enchantment_targets', 'land_targets')
                for target in hints.get(key, []) if target.get('id') in state.cards}
            if bounce_targets:
                selected = max(bounce_targets, key=lambda cid: (
                    state.cards[cid].controller != player_id,
                    self._creature_threat_score(state, cid, player_id) if 'Creature' in effective_types(state, state.cards[cid])
                    else self._noncreature_permanent_threat_score(state, cid, player_id), cid))
                targets['target_card_id'] = selected
        from rules_engine.oracle_effects import parse_temporary_target_buff
        pt_change = parse_temporary_target_buff(without_reminder_text(target_text).strip())
        if pt_change is None and mtype == 'cast_spell':
            from rules_engine.landfall import alternative_effect
            from rules_engine.land_history import landfall_status
            alternative = alternative_effect(target_text, targets)
            if alternative:
                branches = alternative[1]['branches']
                if all(branch['effect_key'] == 'temporary_pt_buff' for branch in branches):
                    status = landfall_status(state, player_id)
                    if status is not None:
                        pt_change = branches[int(status)]['payload']
                    elif all(branch['payload']['power'] >= 0 and branch['payload']['toughness'] >= 0
                             for branch in branches):
                        # Common beneficiary only; unknown history supplies no pump amount.
                        pt_change = {'power': 0, 'toughness': 0}
        from rules_engine.devotion import devotion_instruction, devotion_count
        devotion = devotion_instruction(target_text, getattr(card, 'name', '') or '')
        if pt_change or devotion and devotion['kind'] == 'pump':
            power, toughness = ((pt_change['power'], pt_change['toughness']) if pt_change else
                                (devotion_count(state, player_id, devotion['colors']),) * 2)
            preferred_controller = player_id if power >= 0 and toughness >= 0 else opponent if power <= 0 and toughness <= 0 else None
            if preferred_controller is not None:
                creature_targets = [target for target in creature_targets if state.cards[target["id"]].controller == preferred_controller]
                if not creature_targets:
                    out["_invalid_ai_choice"] = True
                    return out
        any_damage_target = "any target" in target_text or "any number of targets" in target_text
        if any_damage_target:
            creature_targets = [target for target in creature_targets if state.cards[target["id"]].controller != player_id]
            damage_match = re.search(r"\bdeals?\s+(\d+)\s+damage\b", target_text)
            if damage_match and player_targets and "any number of targets" not in target_text:
                amount = int(damage_match.group(1))
                if state.players[opponent].life <= amount:
                    creature_targets = []
                else:
                    creature_targets = [
                        target for target in creature_targets
                        if amount + int(state.cards[target["id"]].counters.get("__damage_marked", 0))
                        >= _effective_combat_stats(state, target["id"])[1]
                        and not has_keyword(state, target["id"], "indestructible")
                    ]
        required = hints.get('required_distinct_target_count')
        instances = hints.get('required_target_instance_count')
        if instances and not targets.get('target_card_ids'):
            from ai.ordered_targets import choose_modifier_targets
            assignments = choose_modifier_targets(self, state, player_id, out, targets, creature_targets, instances)
            if assignments is None:
                out['_invalid_ai_choice'] = True
                return out
            targets.pop('target_card_id', None)
            targets['target_card_ids'] = assignments
        if required and not targets.get('target_card_ids'):
            beneficiary = player_id if hints.get('ordered_counter_type', '').startswith('+') else opponent
            candidates = [target for target in creature_targets if state.cards[target['id']].controller == beneficiary]
            if len({target['id'] for target in candidates}) < required:
                out['_invalid_ai_choice'] = True
                return out
            candidates.sort(key=lambda target: (self._creature_threat_score(state, target['id'], player_id), target['id']), reverse=True)
            assignments = [None] * required
            for index, target in zip(sorted(range(required), key=lambda index: hints['ordered_counter_amounts'][index], reverse=True), candidates):
                assignments[index] = target['id']
            targets.pop('target_card_id', None)
            targets['target_card_ids'] = assignments
        if creature_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            if isinstance(state, MatchState) and pt_change and pt_change['toughness'] < 0:
                from ai.pending_effects import negative_pt_would_be_lethal
                power, toughness = pt_change['power'], pt_change['toughness']
                lethal = [target for target in creature_targets
                          if negative_pt_would_be_lethal(state,target['id'],power,toughness)]
                if lethal:
                    creature_targets = lethal
            keyword_scores = {}
            if mtype == 'cast_spell' and isinstance(state,MatchState) and card is not None:
                from ai.pending_effects import keyword_target_value
                keyword_scores = {target['id']: keyword_target_value(state,card,player_id,{**targets,'target_card_id':target['id']})
                                  for target in creature_targets}
            if keyword_scores and all(value is not None for value in keyword_scores.values()):
                best_score = max(keyword_scores.values())
                creature_targets = [target for target in creature_targets if keyword_scores[target['id']] == best_score]
            best = max(
                creature_targets,
                key=lambda t: (self._creature_threat_score(state, t.get("id"), player_id), str(t.get("name") or t.get("label") or "")),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]

        land_targets = hints.get("land_targets") or []
        if land_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            # Prefer a basic land that is currently untapped so an animation
            # loyalty line can attack or continue producing mana afterward.
            best_land = max(
                land_targets,
                key=lambda t: (
                    int(not bool(getattr(state.cards.get(t.get("id")), "tapped", False))),
                    str(t.get("name") or ""),
                ),
                default=None,
            )
            if best_land:
                targets["target_card_id"] = best_land["id"]
                targets["target_card_name"] = best_land.get("name") or ""

        graveyard_creature_targets = hints.get("graveyard_creature_targets") or hints.get("graveyard_card_targets") or []
        if graveyard_creature_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                graveyard_creature_targets,
                key=lambda t: (
                    self._graveyard_creature_reanimation_score(state, t.get("id"), player_id),
                    str(t.get("name") or t.get("label") or ""),
                ),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        graveyard_permanent_targets = hints.get("graveyard_permanent_targets") or []
        if graveyard_permanent_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                graveyard_permanent_targets,
                key=lambda t: (
                    self._noncreature_permanent_threat_score(state, t.get("id"), player_id),
                    str(t.get("name") or t.get("label") or ""),
                ),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        graveyard_spell_targets = hints.get("graveyard_spell_targets") or []
        if graveyard_spell_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                graveyard_spell_targets,
                key=lambda t: (
                    mana_value(getattr(state.cards.get(t.get("id")), "mana_cost", "") or ""),
                    str(t.get("name") or t.get("label") or ""),
                ),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        planeswalker_targets = hints.get("planeswalker_targets") or []
        if any_damage_target:
            planeswalker_targets = [target for target in planeswalker_targets if state.cards[target["id"]].controller != player_id]
        if (planeswalker_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or [])
                and not (hints.get('single_target_alternative') and targets.get('target_player') is not None)):
            targets["target_card_id"] = planeswalker_targets[0]["id"]

        noncreature_permanent_targets = (
            (hints.get("artifact_targets") or [])
            + (hints.get("enchantment_targets") or [])
            + (hints.get("noncreature_permanent_targets") or [])
        )
        if noncreature_permanent_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                noncreature_permanent_targets,
                key=lambda t: (
                    self._noncreature_permanent_threat_score(state, t.get("id"), player_id),
                    str(t.get("name") or t.get("label") or ""),
                ),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        if hints.get("permanent_targets") and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                hints["permanent_targets"],
                key=lambda t: (
                    int(state.cards[t["id"]].controller != player_id),
                    self._creature_threat_score(state, t["id"], player_id)
                    if "Creature" in effective_types(state, state.cards[t["id"]])
                    else self._noncreature_permanent_threat_score(state, t["id"], player_id),
                ),
            )
            targets["target_card_id"] = best["id"]

        if "any target" in target_text and target_text.count("target") == 1 and targets.get("target_card_id"):
            targets.pop("target_player", None)

        if hints.get("supports_divide") and not targets.get("target_distribution"):
            if creature_targets:
                # Start with one recipient, then use the rules-derived budget.
                best = max(
                    creature_targets,
                    key=lambda t: (self._creature_threat_score(state, t.get("id"), player_id), str(t.get("name") or t.get("label") or "")),
                    default=None,
                )
                if best:
                    targets["target_distribution"] = {best["id"]: 1}
            elif player_targets:
                preferred = opponent if any(int(target["id"]) == opponent for target in player_targets) else int(player_targets[0]["id"])
                targets["target_distribution"] = {str(preferred): 1}

        mana_cost = (selected_cost or {}).get('mana_cost')
        if mana_cost is None:
            mana_cost = move.get("mana_cost") or getattr(card, "mana_cost", "") or ""
        from rules_engine.costs import restricted_x_color
        x_color = restricted_x_color(str(move.get("ability_label", ""))) if mtype == "activate_ability" else None
        linked_copy = mtype == "activate_ability" and "becomes a copy of that card" in str(move.get("ability_label", "")).lower()
        if linked_copy and "x_value" not in targets and cid:
            from rules_engine.linked_exile import linked_exiled_creatures
            eligible = [card_id for card_id in linked_exiled_creatures(state, cid, object_incarnation(state.cards[cid]))
                        if can_pay_with_pool_and_lands(state, player_id, mana_cost,
                                                       card_name=state.cards[cid].name,
                                                       x_value=mana_value(state.cards[card_id].mana_cost or ""))]
            selected = self._choose_library_search(state, eligible, 1, player_id)
            targets["x_value"] = mana_value(state.cards[selected[0]].mana_cost or "") if selected else 0
        elif "{X}" in mana_cost.upper() and "x_value" not in targets:
            from ai.combat_tax_policy import combat_tax_plan
            tax_plan = combat_tax_plan(state, move, player_id) if mtype == 'activate_ability' else None
            targets["x_value"] = tax_plan['x_value'] if tax_plan is not None else self._choose_x_value(state, player_id, mana_cost, card=card, restricted_x_color=x_color)
        elif hints.get("requires_x_value") and "x_value" not in targets:
            if selected_cost and selected_cost.get('discard_x'):
                limit = int(hints.get('x_value_max', 0))
                values = sorted(self._hand_retention_value(state, item, player_id)
                                for item in selected_cost.get('discard_card_ids', []))
                scored = [(self._score_x_value(state, player_id, card, mana_cost, value, limit, 1)
                           - sum(values[:value + selected_cost.get('discard_cards', 0)]), value)
                          for value in range(1, limit + 1)]
                targets['x_value'] = max(scored, default=(0, 0))[1] if any(score > 0 for score, _ in scored) else 0
            elif mtype == "activate_loyalty" and cid:
                loyalty_now = int(getattr(state.cards.get(cid), "loyalty", 0) or 0)
                targets["x_value"] = max(0, min(3, loyalty_now))
            elif card is not None and PAY_X_LIFE_RE.search(getattr(card, "oracle_text", "") or ""):
                targets["x_value"] = self._choose_variable_life_x(state, player_id, card)
            else:
                targets["x_value"] = self._choose_x_value(state, player_id, mana_cost, card=card) or 0

        # The whole Oracle text may contain X in an unrelated activated ability.
        requires_x = bool(hints.get("requires_x_value")) or "{X}" in mana_cost.upper()

        if mtype == 'activate_ability' and requires_x:
            from rules_engine.costs import activated_cost_available
            proposed = max(0, int(targets.get('x_value', 0) or 0))
            targets['x_value'] = next((value for value in range(proposed, -1, -1)
                if activated_cost_available(state, player_id, cid, mana_cost, x_value=value,
                                            restricted_x_color=x_color, ability_index=move.get('ability_index'))), 0)

        if requires_x:
            try:
                xv = int(targets.get("x_value", 0) or 0)
            except Exception:
                xv = 0
            if xv < 0 or (xv == 0 and not allow_zero_x):
                out["_invalid_ai_choice"] = True
            if mtype == "activate_ability" and "x damage to each creature and each player" in str(move.get("ability_label", "")).lower():
                if (xv >= state.players[player_id].life
                        or (xv < state.players[opponent].life
                            and self._score_x_value(state, player_id, card, mana_cost, xv, xv, 1) <= 0)):
                    out["_invalid_ai_choice"] = True

        if hints.get("supports_divide") and card:
            from types import SimpleNamespace
            from rules_engine.cast_choice import enrich_divide_total
            from rules_engine.engine import _select_face_for_cast
            from rules_engine.oracle_effects import extract_activated_abilities, extract_loyalty_abilities
            allocation_card = _select_face_for_cast(card, out.get("selected_face_index"))
            if mtype != "cast_spell":
                abilities = extract_loyalty_abilities(card) if mtype == "activate_loyalty" else extract_activated_abilities(card)
                ability = next((item for index, item in enumerate(abilities) if item.get("index", index) == move.get("ability_index")), None)
                if ability:
                    allocation_card = SimpleNamespace(oracle_text=ability["text"])
            targets = enrich_divide_total(allocation_card, targets)
            budget = targets.get("divide_total")
            if budget is None:
                out["_invalid_ai_choice"] = True
            elif targets.get("target_distribution"):
                recipient = next(iter(targets["target_distribution"]))
                targets["target_distribution"] = {recipient: budget} if budget else {}

        if mtype == "cast_spell" and card is not None and targets.get("mode_texts"):
            from rules_engine.oracle_effects import inspect_target_hints

            mode_choices = dict(targets.get("mode_targets") or {})
            for mode in targets["mode_texts"]:
                choice = dict(mode_choices.get(mode) or {})
                if not choice:
                    mode_hints = inspect_target_hints(state, card, player_id, {"mode_text": mode})
                    text = mode.lower()
                    stack_options = mode_hints.get("stack_targets") or []
                    if stack_options:
                        if "counter" in text:
                            allow_friendly = bool(re.search(r"counter target[^.\n]{0,60}(?:spell|ability) you control", text))
                            best = self._choose_best_stack_target_id(state, player_id, stack_options, allow_friendly=allow_friendly)
                            if best is None:
                                out["_invalid_ai_choice"] = True
                                return out
                            choice["target_stack_id"] = best
                        else:
                            choice["target_stack_id"] = stack_options[-1]["id"]
                    elif "any target" in text:
                        damage_match = re.search(r"deals? (\d+) damage", text)
                        damage = int(damage_match.group(1)) if damage_match else 0
                        from rules_engine.continuous import effective_combat_stats
                        killable = [target for target in mode_hints.get("creature_targets") or []
                                    if state.cards[target["id"]].controller == opponent
                                    and damage >= effective_combat_stats(state, target["id"])[1]
                                    and not has_keyword(state, target["id"], "indestructible")]
                        if killable and state.players[opponent].life > damage:
                            choice["target_card_id"] = max(killable, key=lambda t: self._creature_threat_score(state, t["id"], player_id))["id"]
                        elif any(int(target["id"]) == opponent for target in mode_hints.get("player_targets") or []):
                            choice["target_player"] = opponent
                        elif mode_hints.get("creature_targets") or mode_hints.get("planeswalker_targets"):
                            options = (mode_hints.get("creature_targets") or []) + (mode_hints.get("planeswalker_targets") or [])
                            choice["target_card_id"] = max(options, key=lambda t: self._creature_threat_score(state, t["id"], player_id))["id"]
                        elif mode_hints.get("player_targets"):
                            choice["target_player"] = int(mode_hints["player_targets"][0]["id"])
                    elif "target player" in text or "target opponent" in text:
                        players = mode_hints.get("player_targets") or []
                        if players:
                            choice["target_player"] = opponent if any(int(target["id"]) == opponent for target in players) else int(players[0]["id"])
                    else:
                        if "graveyard" in text:
                            options = [target for target in mode_hints.get("graveyard_creature_targets") or []
                                       if state.cards[target["id"]].owner == player_id]
                        elif "target artifact" in text:
                            options = mode_hints.get("artifact_targets") or []
                        elif "target enchantment" in text:
                            options = mode_hints.get("enchantment_targets") or []
                        else:
                            options = (mode_hints.get("permanent_targets") or mode_hints.get("creature_targets") or [])
                        if options:
                            choice["target_card_id"] = max(
                                options,
                                key=lambda t: (
                                    int(state.cards[t["id"]].controller == opponent),
                                    self._creature_threat_score(state, t["id"], player_id)
                                    if "Creature" in effective_types(state, state.cards[t["id"]])
                                    else self._noncreature_permanent_threat_score(state, t["id"], player_id),
                                ),
                            )["id"]
                mode_choices[mode] = choice
            for key in ("target_card_id", "target_player", "target_stack_id", "target_card_ids", "target_distribution"):
                targets.pop(key, None)
            targets["mode_targets"] = mode_choices

        selected_text = "\n".join(targets.get("mode_texts") or []) or targets.get("mode_text") or getattr(card, "oracle_text", "")
        if isinstance(state, MatchState) and mtype == "cast_spell" and _only_counter_spell_text(selected_text):
            item = next((item for item in state.stack if item.id == targets.get("target_stack_id")), None)
            if item and stack_object_kind(state, item) == "spell" and spell_cant_be_countered(state, item):
                out["_invalid_ai_choice"] = True
        out["targets"] = targets
        if mtype == 'cast_spell' and cost_options:
            selected = next((option for option in cost_options
                             if option['id'] == (out.get('cost_choice') or {}).get('id')), None)
            if selected:
                choice = dict(out.get('cost_choice') or {})
                for key, count, rank in [
                    ('discard_card_ids', selected.get('discard_cards', 0), self._hand_retention_value),
                    ('sacrifice_card_ids', selected.get('sacrifice_creatures', 0), self._sacrifice_loss),
                ]:
                    if selected.get('discard_all' if key == 'discard_card_ids' else 'sacrifice_all'):
                        continue
                    if key == 'discard_card_ids' and selected.get('discard_x'):
                        count += int(targets.get('x_value', 0))
                    if count and key not in choice and key in selected:
                        choice[key] = sorted(selected[key], key=lambda cid: (rank(state, cid, player_id), cid))[:count]
                out['cost_choice'] = choice
                if (selected.get('sacrifice_all') and selected.get('sacrifice_card_ids')
                        and isinstance(state, MatchState) and not out.get('_invalid_ai_choice')):
                    from ai.pending_effects import unanswered_action_wins
                    if unanswered_action_wins(state, player_id, out,
                        own_choice_action=lambda projected, legal, pid: self.choose_action(projected, legal, pid).action) is False:
                        out['_invalid_ai_choice'] = True
        return out

    def _choose_blocks(self, state: MatchState, attackers: list[dict], blockers: list[dict]) -> dict[str, str | list[str]]:
        available = [b["id"] for b in blockers if b.get("id") in state.cards]
        if not available:
            return {}
        searched = self._search_block_assignments(state, attackers, blockers)
        if searched is not None:
            return searched
        assignments: dict[str, str | list[str]] = {}
        # During declare blockers priority may still belong to the active
        # attacker. The blocker controller, not priority_player, owns the
        # life-total and combat-role decisions here.
        player_id = next(
            (
                getattr(state.cards.get(bid), "controller", None)
                for bid in available
                if getattr(state.cards.get(bid), "controller", None) in getattr(state, "players", {})
            ),
            getattr(state, "priority_player", 1),
        )
        incoming_total = sum(
            _effective_combat_stats(state, a["id"])[0]
            for a in attackers
            if a.get("id") in state.cards
        )
        life = state.players[player_id].life if player_id in state.players else 20
        role = self._board_role(state, player_id)
        lethal_pressure = incoming_total >= life
        prevented = 0
        covered_attackers: set[str] = set()
        remaining_capacity = {bid: combat._max_attackers_blockable_by_creature(state, state.cards[bid])
                              if isinstance(state, MatchState) else 1 for bid in available}
        band_members = {
            cid: [member for member in band if member in state.attackers]
            for band in getattr(state, "attack_bands", [])
            for cid in band
        }
        def prevented_by_block(aid: str) -> set[str]:
            return set(band_members.get(aid, [aid])) - covered_attackers

        sorted_attackers = sorted(
            [a for a in attackers if a.get("id") in state.cards],
            key=lambda a: sum(_effective_combat_stats(state, cid)[0] for cid in band_members.get(a["id"], [a["id"]])),
            reverse=True,
        )
        for a in sorted_attackers:
            aid = a["id"]
            if aid in covered_attackers:
                continue
            atk = state.cards.get(aid)
            if not atk:
                continue
            atk_pow, atk_tgh = _effective_combat_stats(state, aid)
            atk_has_trample = "trample" in set(effective_keywords(state, aid))
            atk_has_deathtouch = "deathtouch" in set(effective_keywords(state, aid))
            protected_power = sum(max(0, _effective_combat_stats(state, cid)[0]) for cid in prevented_by_block(aid))
            required_blockers = self._minimum_blockers_for_ai(state, atk)
            best_bid = None
            best_score = -999.0
            scored: list[tuple[float, str]] = []
            for bid in available:
                blk = state.cards.get(bid)
                if not blk:
                    continue
                if isinstance(state, MatchState) and (
                    blk.zone != Zone.BATTLEFIELD or blk.tapped or card_cant_block(state, bid)
                    or not combat._can_block_attacker(state, atk, blk)
                ):
                    continue
                blk_pow, blk_tgh = _effective_combat_stats(state, bid)
                score = 0.0
                # Primary value: prevent face damage.
                score += protected_power * 1.15
                if blk_pow >= atk_tgh:
                    score += 2.2
                if blk_tgh > atk_pow:
                    score += 1.0
                if blk_pow < atk_tgh and blk_tgh <= atk_pow:
                    score -= 0.9
                if atk_has_trample and blk_tgh <= atk_pow:
                    score -= 0.7
                if atk_has_deathtouch:
                    score -= 0.6
                if blk_tgh <= atk_pow and blk_pow < atk_tgh:
                    # Pure chump trades are less desirable unless needed.
                    score -= 1.4
                score += min(atk_pow, 5) * 0.25
                # Penalize blocking with mana-producing creatures — they're
                # worth more untapped than the damage they prevent, especially early game.
                blk_text = (getattr(blk, "oracle_text", "") or "").lower()
                if ("{t}" in blk_text or "(t)" in blk_text) and ("add " in blk_text or "adds " in blk_text):
                    score -= 3.5
                    if lethal_pressure or role in {"stabilize", "defend"}:
                        score += 1.8
                if role in {"stabilize", "defend"}:
                    score += 0.35
                elif role == "convert" and not lethal_pressure:
                    score -= 0.2
                if atk_pow >= life:
                    score += 1.4
                elif atk_pow >= max(3, life // 2):
                    score += 0.6
                if atk_has_trample and blk_tgh > atk_pow:
                    score += 0.7
                scored.append((score, bid))
                if score > best_score:
                    best_score = score
                    best_bid = bid
            if role in {"stabilize", "defend"}:
                threshold = -0.5 if lethal_pressure else 0.15
            elif role == "convert":
                threshold = -0.4 if lethal_pressure else 0.65
            else:
                threshold = -0.6 if lethal_pressure else 0.4
            if required_blockers > 1:
                scored.sort(reverse=True)
                if len(scored) < required_blockers:
                    continue
                group = [item[1] for item in scored[:required_blockers]]
                group_score = sum(item[0] for item in scored[:required_blockers])
                if group_score <= threshold * required_blockers:
                    continue
                assignments[aid] = group
                prevented += protected_power
                covered_attackers.update(band_members.get(aid, [aid]))
                for bid in group:
                    remaining_capacity[bid] -= 1
                    if remaining_capacity[bid] <= 0 and bid in available:
                        available.remove(bid)
                if not available:
                    break
                # If we have prevented enough to avoid lethal and remaining trades are poor, stop.
                if lethal_pressure and incoming_total - prevented < life:
                    lethal_pressure = False
                continue

            if best_bid is not None and best_score > threshold:
                assignments[aid] = best_bid
                prevented += protected_power
                covered_attackers.update(band_members.get(aid, [aid]))
                remaining_capacity[best_bid] -= 1
                if remaining_capacity[best_bid] <= 0:
                    available.remove(best_bid)
                if not available:
                    break
                # If we have prevented enough to avoid lethal and remaining trades are poor, stop.
                if lethal_pressure and incoming_total - prevented < life:
                    lethal_pressure = False
        return assignments

    def _search_block_assignments(
        self,
        state: MatchState,
        attackers: list[dict],
        blockers: list[dict],
    ) -> dict[str, str | list[str]] | None:
        """Evaluate small-board blocker assignments by resolving cloned combat."""
        if self.difficulty not in {"master", "master_plus"}:
            return None
        attacker_ids = [item["id"] for item in attackers if item.get("id") in state.cards]
        blocker_ids = [item["id"] for item in blockers if item.get("id") in state.cards]
        if not attacker_ids or not blocker_ids or len(attacker_ids) > 4 or len(blocker_ids) > 5:
            return None
        defender = 3-state.active_player
        from ai.block_search import block_intents
        assignments = block_intents(state, attacker_ids, blocker_ids)
        if not assignments:
            return None
        best: tuple[float, tuple[tuple[str, tuple[str, ...]], ...], dict[str, str | list[str]]] | None = None
        initial_life = state.players[defender].life
        opponent = 1 if defender == 2 else 2
        incoming_power = sum(
            max(0, _effective_combat_stats(state, aid)[0])
            for aid in attacker_ids
        )
        keyword_combat = self._combat_keyword_board(state, defender) or self._combat_keyword_board(state, opponent)
        face_only = all(state.attack_targets.get(aid, f'player:{defender}') == f'player:{defender}' for aid in attacker_ids)
        for assignment in assignments:
            if face_only and initial_life > incoming_power and assignment and not keyword_combat:
                chump_only = True
                for aid, bids in assignment.items():
                    attacker = state.cards[aid]
                    assigned_blockers = [
                        state.cards[bid]
                        for bid in bids if bid in state.cards
                    ]
                    blocking_power = sum(
                        max(0, _effective_combat_stats(state, blocker.id)[0])
                        for blocker in assigned_blockers
                    )
                    if blocking_power >= max(0, _effective_combat_stats(state, attacker.id)[1]):
                        chump_only = False
                        break
                if chump_only:
                    continue
            try:
                sim = planning_copy(state)
                normalized = {aid: sorted(bids) for aid, bids in assignment.items()}
                self.engine.take_action(sim, defender, {"type": "block", "blocks": normalized}, reject_invalid=True)
                from ai.pending_effects import _settle_announced_stack
                if not _settle_announced_stack(sim):
                    continue
                if not self._finish_combat_projection(sim, state):
                    continue
            except Exception:
                continue
            score = evaluate_board(sim, defender)
            score += (sim.players[defender].life - initial_life) * 4.0
            before_blockers = set(state.players[defender].battlefield)
            after_blockers = set(sim.players[defender].battlefield)
            before_attackers = set(state.players[opponent].battlefield)
            after_attackers = set(sim.players[opponent].battlefield)
            blockers_lost = len(before_blockers - after_blockers)
            attackers_lost = len(before_attackers - after_attackers)
            # Preserve creatures when the incoming combat is not lethal and
            # the proposed assignment only chumps. This is a general combat
            # value rule, not an archetype/card exception; lethal prevention
            # and profitable trades remain preferred.
            if face_only and initial_life > incoming_power and sim.winner != defender and blockers_lost > attackers_lost:
                if attackers_lost == 0:
                    continue
                score -= (blockers_lost - attackers_lost) * (12.0 + incoming_power)
            if sim.winner == defender:
                score += 1000.0
            elif sim.winner is not None:
                score -= 1000.0
            normalized = {aid: bids if len(bids) > 1 else bids[0] for aid, bids in normalized.items()}
            key = tuple(sorted((aid, tuple(sorted(bids))) for aid, bids in assignment.items()))
            candidate = (score, key, normalized)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        return best[2] if best is not None else None

    def _requires_two_or_more_blockers(self, state, attacker) -> bool:
        attacker_id = getattr(attacker, "id", None)
        keywords = (
            set(effective_keywords(state, attacker_id))
            if attacker_id and attacker_id in getattr(state, "cards", {})
            else {str(k).lower() for k in (getattr(attacker, "keywords", []) or [])}
        )
        if "menace" in keywords:
            return True
        if isinstance(state, MatchState) and attacker_id in state.cards:
            from rules_engine.combat_constraints import combat_rule_text
            text = combat_rule_text(state, attacker_id)
        else:
            text = (getattr(attacker, "oracle_text", "") or "").lower()
        return "can't be blocked except by two or more creatures" in text or "cannot be blocked except by two or more creatures" in text

    def _minimum_blockers_for_ai(self, state, attacker) -> int:
        if isinstance(state, MatchState) and attacker.id in state.cards:
            return combat._minimum_blockers_required(state, attacker.id)
        return 2 if self._requires_two_or_more_blockers(state, attacker) else 1

    def _choose_attackers(self, state: MatchState, candidates: list[str], player_id: int) -> list[str]:
        opp_id = 1 if player_id == 2 else 2
        opp_blockers = [
            cid
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        ]
        if not opp_blockers:
            if self._combat_keyword_board(state, player_id):
                searched = self._search_attack_assignments(state, candidates, player_id)
                if searched is not None:
                    return self._reserve_postcombat_mana(state, searched, player_id)
            return self._reserve_postcombat_mana(state, candidates, player_id)

        searched = self._search_attack_assignments(state, candidates, player_id)
        if searched is not None:
            return searched

        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        opp_life = state.players[opp_id].life
        chosen: list[str] = []
        my_life = state.players[player_id].life
        hand_profile = self._current_hand_profile(state, player_id)
        role = self._board_role(state, player_id)
        race_mode = my_life <= 7 or opp_life <= 6
        board_pressure = sum(
            max(0, _eff_pow(state, cid))
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        ) - sum(
            max(0, _eff_pow(state, cid))
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        )
        commit_attack = (
            role in {"race", "convert"}
            or (role == "normal" and int(hand_profile["action_density"]) >= 3 and board_pressure <= 0)
            or (self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} and int(hand_profile["action_density"]) >= 2)
        )
        for cid in candidates:
            card = state.cards.get(cid)
            if not card:
                continue
            atk_pow = _eff_pow(state, cid)
            atk_tgh = _eff_tgh(state, cid)
            atk_kw = set(effective_keywords(state, cid))
            has_trample = "trample" in atk_kw
            has_deathtouch = "deathtouch" in atk_kw
            if atk_pow <= 0:
                continue

            dies_to_some = any(_eff_pow(state, b) >= atk_tgh for b in opp_blockers)
            kills_some = any(_eff_tgh(state, b) <= atk_pow for b in opp_blockers)
            favorable_trade = kills_some and (not dies_to_some or atk_pow >= 2)
            # Avoid obvious bad attacks with small bodies into larger blockers.
            if (
                atk_pow <= 1
                and opp_blockers
                and not has_trample
                and not has_deathtouch
                and opp_life > 1
                and not race_mode
                and not commit_attack
            ):
                continue
            # General anti-suicide rule for all archetypes.
            # Aggro can still pressure in race/lethal setups, but should not throw creatures away for no value.
            if (
                dies_to_some
                and not favorable_trade
                and not has_deathtouch
                and not has_trample
                and opp_life > atk_pow
                and not race_mode
                and not commit_attack
            ):
                continue

            chosen.append(cid)

        # Tactical crackback safety: avoid attacks that expose an immediate lethal swing.
        if chosen and not race_mode:
            safe = self._remove_high_risk_attackers(state, chosen, candidates, player_id)
            if safe:
                chosen = safe

        # If nothing qualifies but we have lethal on board, send all.
        if not chosen:
            total_power = sum(_effective_combat_stats(state, c)[0] for c in candidates if c in state.cards)
            if total_power >= opp_life:
                return list(candidates)
        return chosen

    def _reserve_postcombat_mana(self, state, candidates, player_id):
        """Compare known postcombat payment opportunities with unblocked damage."""
        from rules_engine.mana import mana_source_outputs, repeatable_nonland_mana_outputs
        from rules_engine.card_types import CARD_TYPES
        if (not isinstance(state, MatchState) or state.active_player != player_id
                or state.step != Step.DECLARE_ATTACKERS or state.stack
                or not state.players[player_id].hand):
            return list(candidates)
        sources = [cid for cid in candidates if cid in state.cards
                   and "vigilance" not in {kw.lower() for kw in effective_keywords(state, cid)}
                   and ("Land" in effective_types(state, state.cards[cid]) or repeatable_nonland_mana_outputs(
                       state.cards[cid], state=state, payment_context=("spell", CARD_TYPES)))
                   and mana_source_outputs(state, player_id, cid)]
        if not sources:
            return list(candidates)
        # Preserve the existing lethal-pressure line; this is not a combat proof.
        if sum(max(0, _effective_combat_stats(state, cid)[0]) for cid in candidates) >= state.players[3 - player_id].life:
            return list(candidates)
        sim = planning_copy(state)
        sim.step = Step.POSTCOMBAT_MAIN
        sim.priority_player = player_id
        sim.players[player_id].mana_pool.clear()
        sim.players[player_id].snow_mana_pool.clear()
        sim.players[player_id].restricted_mana_pool.clear()
        held = set(sim.players[player_id].hand)

        def opportunities():
            scores = {}
            for move in self.engine.legal_moves(sim, player_id):
                if move.get("type") != "cast_spell" or move.get("card_id") not in held:
                    continue
                card = _card_for_move(sim, move)
                if card is None or "{X}" in card.mana_cost.upper() or PAY_X_LIFE_RE.search(card.oracle_text or ""):
                    continue
                action = self._materialize_action(sim, move, player_id)
                if action.get("_invalid_ai_choice"):
                    continue
                value = (self._closure_spell_score(card, _oracle_text(card), state=sim, player_id=player_id)
                         + recurring_engine_value(sim, card.id, surface_card=card)
                         + repeatable_mana_value(sim, card.id, surface_card=card))
                targets = action.get("targets") or {}
                text = " ".join(targets.get("mode_texts") or []) or targets.get("mode_text") or _oracle_text(card)
                if targets.get("target_player") == 3 - player_id:
                    value += self._burn_damage_estimate(text) * 1.6
                if "ramp" in self._spell_tags(card) and not repeatable_nonland_mana_outputs(card, state=sim):
                    value += 2.0
                if value > 0:
                    key = (card.id, move.get("selected_face_index"))
                    scores[key] = value
            return scores

        before = opportunities()
        best = max(before.values(), default=0.0)
        if not best:
            return list(candidates)
        for cid in sources:
            sim.cards[cid].tapped = True
        after = max(opportunities().values(), default=0.0)
        if after >= best:
            return list(candidates)
        # Greedily release higher-power sources when some equally valuable cast
        # remains payable. Flexible colors remain shared, finite payment sources.
        reserved = set(sources)
        for cid in sources:
            sim.cards[cid].tapped = False
        for cid in sorted(sources, key=lambda cid: (-_effective_combat_stats(state, cid)[0], cid)):
            sim.cards[cid].tapped = True
            if max(opportunities().values(), default=0.0) >= best:
                reserved.remove(cid)
            else:
                sim.cards[cid].tapped = False
        damage_value = sum(max(0, _effective_combat_stats(state, cid)[0]) for cid in reserved) * 1.6
        return [cid for cid in candidates if cid not in reserved] if best - after > damage_value else list(candidates)

    def _combat_keyword_board(self, state, player_id):
        for cid in state.players[player_id].battlefield:
            keywords = effective_keywords(state, cid)
            if ({'exalted', 'decayed', 'flanking'}.intersection(keywords)
                    or any(keyword.startswith(('bushido ', 'rampage ')) for keyword in keywords)):
                return True
        return False

    def _finish_combat_projection(self, simulated, original):
        from ai.pending_effects import _settle_announced_stack
        for _ in range(4):
            # Use the live public-board allocation policy for both controllers;
            # unknown noncombat choices still prevent a claimed forecast.
            for _ in range(64):
                choice = simulated.pending_mechanic_choice
                if not choice or choice.get('kind') != 'combat_damage':
                    break
                self.engine.take_action(simulated, choice['player_id'], {
                    'type': 'choose_mechanic',
                    'damage_assignment': self._choose_combat_damage_allocation(simulated, choice),
                }, reject_invalid=True)
            else:
                return False
            if not _settle_announced_stack(simulated):
                return False
            # Do not rank a line using newly drawn hidden cards/library order.
            if any(simulated.players[pid].hand != player.hand or simulated.players[pid].library != player.library
                   for pid, player in original.players.items()):
                return False
            if simulated.winner is not None or simulated.step == Step.END_COMBAT:
                return True
            self.engine.next_step(simulated)
        return False

    def _project_attack_line(self, state, player_id, attackers):
        if not isinstance(state, MatchState):
            return None
        from rules_engine.combat_constraints import combat_rule_view
        if any(combat_rule_view(state, cid)['unsupported'] for player in state.players.values()
               for cid in player.battlefield if 'Creature' in effective_types(state, state.cards[cid])):
            return None
        from ai.pending_effects import _settle_announced_stack
        sim = planning_copy(state)
        opponent = 3 - player_id
        try:
            self.engine.take_action(sim, player_id, {'type': 'attack', 'attackers': list(attackers)}, reject_invalid=True)
            declared = list(sim.attackers or [])
            if not sim.attackers:
                return sim, declared
            if not _settle_announced_stack(sim):
                return None
            self.engine.next_step(sim)
            blockers = [cid for cid in sim.players[opponent].battlefield
                        if 'Creature' in effective_types(sim, sim.cards[cid]) and not sim.cards[cid].tapped]
            blocks = {}
            if blockers:
                blocks = self._search_block_assignments(sim,
                    [{'id': cid, 'name': sim.cards[cid].name} for cid in sim.attackers],
                    [{'id': cid, 'name': sim.cards[cid].name} for cid in blockers])
                if blocks is None:
                    return None
            self.engine.take_action(sim, opponent, {'type': 'block', 'blocks': blocks}, reject_invalid=True)
            if not _settle_announced_stack(sim):
                return None
            self.engine.next_step(sim)
            if not self._finish_combat_projection(sim, state):
                return None
            if any(line.startswith('Oracle effect not inferred') for line in sim.log):
                return None
            return sim, declared
        except (ValueError, KeyError):
            return None

    def _tactical_combat_setup_action(self, state, legal_moves, player_id):
        """One setup/response action plus bounded combat; unknown is not a win."""
        response_window = (getattr(state, 'step', None) == Step.DECLARE_BLOCKERS
                           and getattr(state, 'blockers_declared', False))
        if (not isinstance(state, MatchState) or self.difficulty not in {'master', 'master_plus'} or state.active_player != player_id
                or (state.step != Step.PRECOMBAT_MAIN and not response_window) or state.stack or state.pregame_pending):
            return None
        candidates = [move for move in legal_moves
                      if move.get('type') in {'cast_spell', 'equip', 'activate_ability', 'activate_loyalty'}]
        if not candidates or len(candidates) > 16:
            return None
        own_creatures = [cid for cid in state.players[player_id].battlefield if 'Creature' in effective_types(state, state.cards[cid])]
        opposing_creatures = [cid for cid in state.players[3-player_id].battlefield if 'Creature' in effective_types(state, state.cards[cid])]
        # A setup action can create the first attackers (for example hasty tokens).
        if len(own_creatures) > 3 or len(opposing_creatures) > 2:
            return None
        if self._setup_combat_forecast(planning_copy(state), player_id) is True:
            return {'type': 'pass_priority'}
        for move in candidates:
            for action in self._combat_target_actions(state, move, player_id):
                sim = planning_copy(state)
                try:
                    self.engine.take_action(sim, player_id, action, reject_invalid=True)
                    if self._setup_combat_forecast(sim, player_id) is True:
                        return action
                except (ValueError, KeyError):
                    continue
        return None

    def _combat_target_actions(self, state, move, player_id):
        action = self._materialize_action(state, move, player_id)
        if action.get('_invalid_ai_choice'):
            return []
        actions = [action]
        targets = action.get('targets') or {}
        hints = move.get('target_hints') or {}
        for field, groups in [('target_card_id', ['creature_targets', 'permanent_targets',
                                                'artifact_targets', 'enchantment_targets']),
                              ('target_stack_id', ['stack_targets'])]:
            if not targets.get(field) or targets.get('target_card_ids'):
                continue
            seen = {targets[field]}
            for group in groups:
                for option in hints.get(group, []):
                    target = option.get('id')
                    if target is not None and target not in seen:
                        seen.add(target)
                        actions.append({**action, 'targets': {**targets, field: target}})
        return actions

    def _setup_combat_forecast(self, sim, player_id):
        from ai.pending_effects import _settle_announced_stack
        visible_hands = {pid: tuple(player.hand) for pid, player in sim.players.items()}
        libraries = {pid: tuple(player.library) for pid, player in sim.players.items()}
        public_cards = {cid for player in sim.players.values()
                        for cid in player.battlefield + player.graveyard + player.exile}
        for _ in range(4):
            if any(line.startswith('Oracle effect not inferred') for line in sim.log):
                return None
            if not _settle_announced_stack(sim):
                return None
            if any(line.startswith('Oracle effect not inferred') for line in sim.log):
                return None
            # Public bounce/return adds known cards without learning the existing
            # hidden hand. Draws, removals/reordering and library changes remain unknown.
            if any(tuple(player.hand[:len(visible_hands[pid])]) != visible_hands[pid]
                   or any(cid not in public_cards for cid in player.hand[len(visible_hands[pid]):])
                   or tuple(player.library) != libraries[pid] for pid, player in sim.players.items()):
                return None
            if sim.winner is not None:
                return sim.winner == player_id
            if sim.step == Step.DECLARE_BLOCKERS and sim.blockers_declared:
                original = planning_copy(sim)
                if not self._finish_combat_projection(sim, original):
                    return None
                if any(line.startswith('Oracle effect not inferred') for line in sim.log):
                    return None
                return sim.winner == player_id
            if sim.step == Step.DECLARE_ATTACKERS:
                attack = next((move for move in self.engine.legal_moves(sim, player_id) if move['type'] == 'attack'), None)
                selected = self._search_attack_assignments(sim, (attack or {}).get('options', []), player_id, force=True)
                if not selected:
                    return False if selected is not None else None
                outcome = self._project_attack_line(sim, player_id, selected)
                return outcome[0].winner == player_id if outcome is not None else None
            self.engine.next_step(sim)
        return None

    def _search_attack_assignments(self, state: MatchState, candidates: list[str], player_id: int, *, force=False) -> list[str] | None:
        """Search small-board attack subsets through the defender's best legal blocks."""
        if self.difficulty not in {"master", "master_plus"}:
            return None
        if not force and int(getattr(state, "turn", 1) or 1) < 5 and not self._combat_keyword_board(state, player_id):
            return None
        candidate_ids = [cid for cid in candidates if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])]
        if not candidate_ids or len(candidate_ids) > 3:
            return None
        opponent = 1 if player_id == 2 else 2
        available_blockers = [
            cid
            for cid in state.players[opponent].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        ]
        # Block search already has its own combinatorial bound. Keep attack
        # search below that bound as well so full matchup matrices stay usable.
        if len(available_blockers) > 2:
            return None
        subsets: list[tuple[str, ...]] = [()]
        for size in range(1, len(candidate_ids) + 1):
            subsets.extend(combinations(candidate_ids, size))
        if len(subsets) > 128:
            return None

        best: tuple[float, tuple[str, ...], list[str]] | None = None
        for subset in subsets:
            outcome = self._project_attack_line(state, player_id, subset)
            if outcome is None:
                continue
            sim, actual_attackers = outcome

            score = evaluate_board(sim, player_id)
            score += (sim.players[opponent].life - state.players[opponent].life) * -2.0
            score += (sim.players[player_id].life - state.players[player_id].life) * 1.5
            if sim.winner == player_id:
                score += 1000.0
            elif sim.winner is not None:
                score -= 1000.0
            score += sum(max(0, _effective_combat_stats(sim, cid)[0]) for cid in actual_attackers) * 0.05
            candidate = (score, tuple(subset), actual_attackers)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        return best[2] if best is not None else None

    def _creature_threat_score(self, state: MatchState, creature_id: str | None, player_id: int) -> float:
        if not creature_id or creature_id not in state.cards:
            return -999.0
        card = state.cards[creature_id]
        if "Creature" not in (effective_types(state, card) or []):
            return -500.0
        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        power = max(0, _eff_pow(state, creature_id))
        toughness = max(0, _eff_tgh(state, creature_id))
        kws = set(effective_keywords(state, creature_id))
        score = (power * 1.2 + toughness * 0.35 + recurring_engine_value(state, creature_id)
                 + repeatable_mana_value(state, creature_id))
        if "flying" in kws or "trample" in kws or "menace" in kws:
            score += 1.8
        if "deathtouch" in kws:
            score += 1.2
        if "lifelink" in kws:
            score += 1.0
        if "ward" in (getattr(card, "oracle_text", "") or "").lower() or "hexproof" in kws:
            score += 1.0
        # Prefer removing immediate lethal/race pressure.
        me = state.players[player_id]
        if power >= me.life:
            score += 5.0
        return score

    def _remove_high_risk_attackers(self, state: MatchState, chosen: list[str], candidates: list[str], player_id: int) -> list[str]:
        opp_id = 1 if player_id == 2 else 2
        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        def _crackback_risk(attackers: list[str]) -> int:
            # Approximate worst-case next turn damage by untapped opposing creatures.
            # We discount by likely defenders we keep back after this attack.
            our_remaining = [
                cid
                for cid in state.players[player_id].battlefield
                if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and cid not in attackers
            ]
            our_block_value = sum(max(0, _eff_pow(state, cid)) for cid in our_remaining if not state.cards[cid].tapped)
            opp_attack_value = sum(
                max(0, _eff_pow(state, cid))
                for cid in state.players[opp_id].battlefield
                if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
            )
            return max(0, opp_attack_value - int(our_block_value * 0.6))

        my_life = int(state.players[player_id].life or 0)
        current = list(chosen)
        while current:
            risk = _crackback_risk(current)
            if risk < my_life:
                return current
            # pull back weakest attacker first
            weakest = min(current, key=lambda cid: (_eff_pow(state, cid), _eff_tgh(state, cid)))
            current.remove(weakest)
        return []

    def _choose_variable_life_x(self, state: MatchState, player_id: int, card) -> int:
        from rules_engine.oracle_effects import ALL_CREATURES_X_DEBUFF_RE
        from rules_engine.replacement import can_pay_life

        if not ALL_CREATURES_X_DEBUFF_RE.search(getattr(card, "oracle_text", "") or ""):
            return 0
        opponent = 1 if player_id == 2 else 2
        creatures = [
            (pid, cid, effective_toughness(state, cid))
            for pid in (player_id, opponent)
            for cid in state.players[pid].battlefield
            if "Creature" in effective_types(state, state.cards[cid])
        ]
        if not creatures:
            return 0
        max_x = min(max(0, state.players[player_id].life - 1), max(t for _, _, t in creatures))
        best = (0.0, 0)
        for x in range(1, max_x + 1):
            if not can_pay_life(state, player_id, x):
                continue
            score = -0.35 * x - 1.0
            if state.players[player_id].life - x <= 5:
                score -= 3.0
            for pid, cid, toughness in creatures:
                if toughness <= x:
                    value = max(1.0, self._creature_threat_score(state, cid, opponent if pid == player_id else player_id))
                    score += -value if pid == player_id else value
            if score > best[0]:
                best = (score, x)
        return best[1]

    def _choose_x_value(self, state: MatchState, player_id: int, mana_cost: str, card=None, restricted_x_color: str | None = None) -> int:
        pool_total = sum((state.players[player_id].mana_pool or {}).values())
        untapped_lands = sum(
            1
            for cid in state.players[player_id].battlefield
            if "Land" in effective_types(state, state.cards.get(cid, type("X", (), {"types": []})())) and not state.cards[cid].tapped
        )
        upper = max(0, pool_total + untapped_lands)
        floor = self._minimum_useful_x_value(state, player_id, card, mana_cost)
        spell_types = set(effective_types(state, card) or []) if card is not None else None
        card_name = str(getattr(card, "name", "") or "") if card is not None else ""
        scored: list[tuple[float, int]] = []
        for x in range(upper, 0, -1):
            if x >= floor and can_pay_with_pool_and_lands(
                state, player_id, mana_cost, card_name=card_name, spell_types=spell_types,
                oracle_text=getattr(card, "oracle_text", "") or "", x_value=x,
                restricted_x_color=restricted_x_color,
            ):
                scored.append((self._score_x_value(state, player_id, card, mana_cost, x, upper, floor), x))
        if not scored:
            text = _oracle_text(card)
            interactive_x = any(k in text for k in ["target", "destroy", "exile", "counter", "tap"])
            if interactive_x:
                for x in range(1, upper + 1):
                    if can_pay_with_pool_and_lands(
                        state, player_id, mana_cost, card_name=card_name, spell_types=spell_types,
                        oracle_text=getattr(card, "oracle_text", "") or "", x_value=x,
                        restricted_x_color=restricted_x_color,
                    ):
                        return x
            for x in range(max(1, floor), upper + 1):
                if can_pay_with_pool_and_lands(
                    state, player_id, mana_cost, card_name=card_name, spell_types=spell_types,
                    oracle_text=getattr(card, "oracle_text", "") or "", x_value=x,
                    restricted_x_color=restricted_x_color,
                ):
                    return x
            return 0
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][1]

    def _score_x_value(self, state: MatchState, player_id: int, card, mana_cost: str, x_value: int, upper: int, floor: int) -> float:
        text = _oracle_text(card)
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        opp = state.players[opp_id]
        me = state.players[player_id]
        opp_creatures = sum(
            1
            for cid in opp.battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        my_creatures = sum(
            1
            for cid in me.battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
        )
        score = 0.0
        if ALL_CREATURES_X_DEBUFF_RE.search(getattr(card, "oracle_text", "") or ""):
            defeated = sum(
                max(1.0, self._creature_threat_score(state, cid, player_id))
                for cid in opp.battlefield
                if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
                and effective_toughness(state, cid) <= x_value
            )
            lost = sum(
                max(1.0, self._creature_threat_score(state, cid, opp_id))
                for cid in me.battlefield
                if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
                and effective_toughness(state, cid) <= x_value
            )
            score += defeated - lost - 0.35 * x_value
        elif "create x" in text and "token" in text:
            # Token makers should scale with pressure, but seasoned pilots avoid
            # dumping the entire mana pool into low-value early boards.
            score += x_value * 0.75
            if self.archetype in {"Control", "Counter-heavy"}:
                score += 0.35 if x_value >= 2 else -0.5
                if turn < 6:
                    score -= max(0.0, (x_value - 2) * 0.45)
                    if x_value >= 4 and opp_creatures == 0 and my_creatures == 0:
                        score -= (x_value - 3) * 0.8
                if opp_creatures == 0 and my_creatures == 0:
                    score -= 0.8 if x_value > 2 else 0.0
            elif self.archetype in {"Aggro", "Tokens", "Tribal", "Tempo"}:
                score += 0.45 if x_value >= 2 else -0.25
                if opp_creatures > my_creatures:
                    score += 0.4
            if opp_life := int(getattr(opp, "life", 20) or 20):
                if opp_life <= 6:
                    score += min(1.4, x_value * 0.25)
                elif turn < 6 and opp_life > 10:
                    score -= max(0.0, (x_value - 2) * 0.3)
        elif "draw x" in text:
            score += x_value * 0.55
            if self.archetype in {"Control", "Counter-heavy"}:
                score += 0.7 if x_value >= 2 else -0.5
                if turn < 6:
                    score -= max(0.0, (x_value - 1) * 0.35)
            if len(getattr(me, "hand", []) or []) <= 2 and turn >= 6:
                score += min(1.0, x_value * 0.2)
        elif "x damage to each creature and each player" in text:
            if me.life <= x_value:
                return -100.0
            if opp.life <= x_value:
                return 100.0
            defeated = sum(1 for cid in opp.battlefield if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
                           and effective_toughness(state, cid) <= x_value)
            lost = sum(1 for cid in me.battlefield if cid in state.cards and "Creature" in effective_types(state, state.cards[cid])
                       and effective_toughness(state, cid) <= x_value)
            score += 3.0 * (defeated - lost) - 0.25 * x_value
        elif "deal x damage" in text or "deals x damage" in text or "lose x life" in text:
            opp_life = int(getattr(opp, "life", 20) or 20)
            score += x_value * 0.85
            if opp_life <= x_value:
                score += 2.0
            if self.archetype in {"Burn", "Aggro", "Tempo"}:
                score += 0.35 if x_value >= 2 else -0.2
            elif self.archetype in {"Control", "Counter-heavy"}:
                score += 0.15 if x_value >= 2 else -0.1
        else:
            score += x_value * 0.4

        if x_value == upper:
            score -= 0.2 if upper > 2 else 0.0
        if x_value <= floor + 1:
            score += 0.15
        return score

    def _minimum_useful_x_value(self, state: MatchState, player_id: int, card, mana_cost: str) -> int:
        text = _oracle_text(card)
        turn = int(getattr(state, "turn", 1) or 1)
        if "create x" in text and "token" in text:
            return 3 if self.archetype in {"Control", "Counter-heavy"} and turn < 7 else 2
        if "draw x" in text:
            return 3 if turn < 6 else 2
        if "mill x" in text or "search your library for x" in text:
            return 2
        if "x damage to each creature and each player" in text:
            return 1
        if "deals x damage" in text or "deal x damage" in text or "lose x life" in text:
            opp_id = 1 if player_id == 2 else 2
            opp_life = int(getattr(state.players.get(opp_id), "life", 20) or 20)
            return 1 if opp_life <= 3 else 2
        if "{x}" in mana_cost.lower():
            if self.archetype in {"Control", "Counter-heavy"} and turn < 5:
                return 2
            return 1
        return 1

    def _is_unplayable_x_action(self, action: dict) -> bool:
        if action.get("type") != "cast_spell":
            return False
        targets = action.get("targets") or {}
        if "x_value" not in targets:
            return False
        try:
            xv = int(targets.get("x_value", 0) or 0)
        except Exception:
            xv = 0
        return xv <= 0

    def _rollout_delta(self, state: MatchState, move: dict, player_id: int) -> float:
        # Lightweight rollout approximation for deeper tactical planning.
        try:
            sim = planning_copy(state)
            self.engine.take_action(sim, player_id, move)
        except Exception:
            return 0.0
        if sim.winner == player_id:
            return 100.0
        if sim.winner is not None and sim.winner != player_id:
            return -100.0
        total = 0.0
        samples = 3
        plies = 6
        for _ in range(samples):
            branch = planning_copy(sim)
            total += self._rollout_playout(branch, player_id, plies)
        return total / samples

    def _approximate_resolution_for_activated_action(self, state: MatchState, move: dict, player_id: int) -> None:
        """Resolve simulated abilities only when the opponent has no response."""
        if move.get("type") not in {"activate_ability", "cycle_card"}:
            return
        for _ in range(8):
            if not getattr(state, "stack", []):
                return
            priority_pid = state.priority_player
            legal = self.engine.legal_moves(state, priority_pid)
            non_pass = [m for m in legal if m.get("type") != "pass_priority"]
            if priority_pid != player_id and non_pass:
                return
            self.engine.take_action(state, priority_pid, {"type": "pass_priority"})

    def _rollout_playout(self, state: MatchState, eval_for_player: int, plies: int) -> float:
        for _ in range(max(0, plies)):
            if state.winner is not None:
                break
            pid = state.priority_player
            legal = self.engine.legal_moves(state, pid)
            if not legal:
                break
            chosen = self._pick_rollout_move(state, legal, pid)
            try:
                self.engine.take_action(state, pid, chosen)
            except Exception:
                break
        if state.winner == eval_for_player:
            return 40.0
        if state.winner is not None and state.winner != eval_for_player:
            return -40.0
        return evaluate_board(state, eval_for_player) * 0.05

    def _pick_rollout_move(self, state: MatchState, legal: list[dict], player_id: int) -> dict:
        # Fast rollout policy (no nested simulations).
        has_cast = any(m.get("type") == "cast_spell" for m in legal)

        def quick_score(move: dict) -> float:
            mtype = move.get("type")
            base = 0.0
            if mtype == "cast_spell":
                tags = self._spell_tags(_card_for_move(state, move))
                if "counter" in tags and getattr(state, "stack", []):
                    base += 3 + self._best_stack_threat_score(state, player_id) * 0.5
                if "burn" in tags:
                    base += 4
            elif mtype == "attack":
                base += 3
            elif mtype == "play_land":
                base += 2
            elif mtype == "tap_land_for_mana":
                base += 0.2 if has_cast else -2.5
            elif mtype == "activate_loyalty":
                base += 2.5
            elif mtype == "cycle_card":
                base += 1.5 + min(2.0, float(move.get("x_value", 0) or 0) * 0.15)
            elif mtype == "pass_priority":
                base -= 0.2
            return base

        ranked = sorted(legal, key=lambda mv: (quick_score(mv), self._move_sort_key(mv)), reverse=True)
        top = ranked[: min(3, len(ranked))]
        return top[0]

    def _surveil_graveyard_choices(self, state, options, player_id):
        player = state.players[player_id]
        known = player.hand + options
        lands = sum('Land' in effective_types(state, state.cards[cid]) for cid in player.hand + player.battlefield)
        goal = max([3, *(mana_value(state.cards[cid].mana_cost) for cid in known if 'Land' not in effective_types(state, state.cards[cid]))])
        demand = self._color_demand(state, player_id)
        for cid in options:
            if 'Land' not in effective_types(state, state.cards[cid]):
                for color, count in _fixed_color_pips(state.cards[cid].mana_cost).items():
                    demand[color] = demand.get(color, 0) + count
        sources = self._current_color_sources(state, player_id)
        for cid in player.hand:
            if 'Land' in effective_types(state, state.cards[cid]):
                for color in self._land_colors(state.cards[cid], state):
                    sources[color] = sources.get(color, 0) + 1
        reanimation = any(re.fullmatch(r'return target creature card from your graveyard to the battlefield\.',
                                   _oracle_text(state.cards[cid]))
                         and self._can_pay_card_cost(state, player_id, state.cards[cid]) for cid in player.hand)
        graveyard = []
        for cid in self._choose_library_search(state, options, len(options), player_id):
            card = state.cards[cid]
            if 'Land' in effective_types(state, card):
                fixing = any(demand.get(color, 0) and not sources.get(color, 0) for color in self._land_colors(card, state))
                if lands >= goal + 1 and not fixing:
                    graveyard.append(cid)
                else:
                    lands += 1
                    for color in self._land_colors(card, state):
                        sources[color] = sources.get(color, 0) + 1
            elif (reanimation and 'Creature' in effective_types(state, card) and not self._can_pay_card_cost(state, player_id, card)
                  and graveyard_destination(state, card) == 'graveyard'):
                graveyard.append(cid)
        return list(reversed(graveyard))

    def _choose_library_search(self, state: MatchState, options: list[str], count: int, player_id: int, *, free_battlefield: bool = False, destination: str = "hand") -> list[str]:
        demand = self._color_demand(state, player_id)
        sources = self._current_color_sources(state, player_id)
        available_mana = len(state.players[player_id].battlefield)
        selected: list[str] = []
        candidates = [cid for cid in options if cid in state.cards]
        while candidates and len(selected) < count:
            def score(cid: str) -> tuple[float, str]:
                card = state.cards[cid]
                if destination == "graveyard":
                    text = str(getattr(card, "oracle_text", "") or "").lower()
                    if graveyard_destination(state, card) != "graveyard":
                        return (-self._closure_spell_score(card, text, state=state, player_id=player_id), card.name)
                    if "Creature" in effective_types(state, card):
                        return (self._graveyard_creature_reanimation_score(state, cid, player_id), card.name)
                    if any(keyword in text for keyword in ("flashback", "escape", "jump-start", "retrace")):
                        return (3.0 + self._closure_spell_score(card, text, state=state, player_id=player_id), card.name)
                    return (-1.0 if "Land" in effective_types(state, card) else 0.0, card.name)
                if "Land" in effective_types(state, card):
                    colors = self._land_colors(card, state)
                    fixing = sum((3.5 if sources.get(color, 0) == 0 else 0.0) +
                                 0.4 * demand.get(color, 0) for color in colors if demand.get(color, 0))
                    return (2.0 + fixing + 0.1 * len(colors), card.name)
                cost = mana_value(card.mana_cost)
                text = str(getattr(card, "oracle_text", "") or "").lower()
                value = self._closure_spell_score(card, text, state=state, player_id=player_id)
                if free_battlefield:
                    value += 1.5 + 0.35 * cost
                else:
                    value += 2.0 if cost <= available_mana + 1 else -0.5 * (cost - available_mana - 1)
                return (value, card.name)

            chosen = max(candidates, key=lambda cid: (score(cid), cid))
            selected.append(chosen)
            card = state.cards[chosen]
            if "Land" in effective_types(state, card):
                for color in self._land_colors(card, state):
                    sources[color] = sources.get(color, 0) + 1
            candidates.remove(chosen)
        return selected

    def _sacrifice_loss(self, state: MatchState, cid: str, player_id: int) -> float:
        card = state.cards[cid]
        types = set(effective_types(state, card))
        if "Land" in types:
            demand = self._color_demand(state, player_id)
            sources = self._current_color_sources(state, player_id)
            unique_color_need = sum(
                demand.get(color, 0) for color in self._land_colors(card, state)
                if sources.get(color, 0) <= 1
            )
            return 20.0 + unique_color_need
        if "Creature" in types:
            power, toughness = _effective_combat_stats(state, cid)
            value = 3.0 + max(0, power) * 1.2 + max(0, toughness) * 0.35
        else:
            value = 5.0 + mana_value(card.mana_cost) * 0.6
        if is_token_card(card):
            value -= 4.0
        if getattr(card, "oracle_text", ""):
            value += 1.0
            value += recurring_engine_value(state, cid)
            value += repeatable_mana_value(state, cid)
        return value

    def _hand_retention_value(self, state: MatchState, cid: str, player_id: int, archetype: str | None = None) -> float:
        card = state.cards[cid]
        archetype = archetype or self.archetype
        if "Land" in effective_types(state, card):
            return self._land_retention_value(state, player_id)
        return self._nonland_retention_value(state, player_id, card.mana_cost,
            effective_types(state, card), card.oracle_text, archetype)

    def _nonland_retention_value(self, state, player_id, mana_cost, types, oracle_text, archetype=None):
        archetype = archetype or self.archetype
        lands_in_play = sum('Land' in effective_types(state, state.cards[cid])
                            for cid in state.players[player_id].battlefield)
        cost = mana_value(mana_cost)
        value = 5.0 - max(0, cost - lands_in_play - 1) * 0.8
        if archetype == "Reanimator" and "Creature" in types and cost > lands_in_play + 2:
            value -= 2.0
        if archetype in {"Control", "Counter-heavy"} and _has_counter_spell_text(oracle_text):
            value += 1.5
        return value

    def _draw_trade_value(self, state, player_id, draws, discarded):
        from ai.information import draw_resource_forecast
        forecast = draw_resource_forecast(state, player_id, draws)
        if forecast is None:
            return draws * 5.0
        nonlands = sum(row['count'] * self._nonland_retention_value(
            state, player_id, row['mana_cost'], row['type_line'].split(), row['oracle_text'])
            for row in forecast['nonland_inventory'])
        spell_value = draws * nonlands / forecast['population'] if forecast['population'] else 0.0
        return spell_value + forecast['expected_lands'] * self._land_retention_value(
            state, player_id, excluded_card_ids=discarded)

    def _land_retention_value(self, state: MatchState, player_id: int, *, excluded_card_ids=()) -> float:
        player = state.players[player_id]
        lands_in_play = sum('Land' in effective_types(state, state.cards[cid]) for cid in player.battlefield)
        lands_in_hand = sum('Land' in effective_types(state, state.cards[cid])
                            for cid in player.hand if cid not in excluded_card_ids)
        if lands_in_play < 3:
            return 9.0 if lands_in_hand <= 2 else 5.0
        return 0.0 if lands_in_play >= 5 and lands_in_hand >= 2 else 3.0

    def _best_land_move(self, state: MatchState, land_moves: list[dict], player_id: int) -> dict:
        demand = self._color_demand(state, player_id)
        current_sources = self._current_color_sources(state, player_id)
        from rules_engine.land_types import land_type_instructions
        compare_resources = any(land_type_instructions(state.cards[move['card_id']].oracle_text)
                                for move in land_moves if move.get('card_id') in state.cards)

        def score_land(move: dict) -> float:
            cid = move.get("card_id")
            if not cid or cid not in state.cards:
                return -999.0
            card = state.cards[cid]
            if getattr(card, "layout", "") == "modal_dfc":
                from rules_engine.card_faces import select_cast_face
                card = select_cast_face(card, move.get("selected_face_index", 0))
            produced = self._land_colors(card, state)
            if not produced:
                return 0.0
            score = 0.0
            for color, need in demand.items():
                if need > 0 and color in produced:
                    score += 1.5 + need * 0.2
            for color in produced:
                if current_sources.get(color, 0) == 0 and demand.get(color, 0) > 0:
                    score += 3.5
            score += len(produced) * 0.15
            from ai.mana_resource_policy import resource_change_plan
            resource_plan = resource_change_plan(self, state, move, player_id,
                                                 include_normal_land=compare_resources)
            if resource_plan is not None:
                score += resource_plan['score']
            if move.get("entry_choice") == "pay_two_life":
                score += 0.25 if self._should_pay_two_life_for_land(state, player_id, cid) else -0.25
            return score

        return max(land_moves, key=lambda mv: (score_land(mv), self._move_sort_key(mv)))

    def _should_pay_two_life_for_land(self, state: MatchState, player_id: int, card_id: str | None) -> bool:
        if not card_id or card_id not in state.cards or state.players[player_id].life <= 4:
            return False
        simulated = planning_copy(state)
        player = simulated.players[player_id]
        if card_id in player.hand:
            player.hand.remove(card_id)
        if card_id in player.library:
            player.library.remove(card_id)
        if card_id in player.graveyard:
            player.graveyard.remove(card_id)
        if card_id in player.exile:
            player.exile.remove(card_id)
        if card_id not in player.battlefield:
            player.battlefield.append(card_id)
        simulated.cards[card_id].zone = Zone.BATTLEFIELD
        simulated.cards[card_id].controller = player_id
        simulated.cards[card_id].tapped = False
        main_phase = (_step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}
                      and state.active_player == player_id and not state.stack)
        for cid in player.hand:
            spell = simulated.cards.get(cid)
            if not spell or "Land" in effective_types(state, spell):
                continue
            if not main_phase and "Instant" not in effective_types(state, spell) and "flash" not in spell.keywords:
                continue
            if not self._can_pay_card_cost(state, player_id, state.cards[cid]) and self._can_pay_card_cost(simulated, player_id, spell):
                return True
        return False

    def _remaining_land_plays(self, state: MatchState, player_id: int) -> int:
        player = state.players[player_id]
        max_land_plays = compute_max_land_plays_this_turn(state, player_id)
        if getattr(player, "last_land_play_turn", 0) == state.turn:
            used = max(
                int(getattr(player, "lands_played_this_turn", 0)),
                int(getattr(player, "land_plays_recorded_on_turn", 0)),
            )
        else:
            used = 0
        return max(0, int(max_land_plays) - int(used))

    def _should_break_stall(self, state: MatchState, legal_moves: list[dict], player_id: int) -> bool:
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "stack", []) or []:
            return False
        non_pass = [m for m in legal_moves if m.get("type") != "pass_priority"]
        if not non_pass:
            return False
        if any(m.get("type") == "play_land" for m in non_pass):
            return True
        # Control-style decks may pass to hold interaction, but once mana/turn grows
        # they should proactively advance board/card advantage.
        if self.archetype in {"Control", "Counter-heavy"}:
            hand_size = len(getattr(state.players[player_id], "hand", []))
            if getattr(state, "turn", 1) < 6 and hand_size < 6 and not self._should_force_proactive_control_line(state, player_id):
                return False
        return True

    def _should_force_proactive_control_line(self, state: MatchState, player_id: int) -> bool:
        """Push control decks to convert resources instead of over-passing in developed boards."""
        if self.archetype not in {"Control", "Counter-heavy"}:
            return False
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "stack", []) or []:
            return False
        turn = int(getattr(state, "turn", 1) or 1)
        hand_size = len(getattr(state.players[player_id], "hand", []))
        untapped_lands = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Land" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        )
        # Late game or near hand-cap should proactively deploy card advantage/threats.
        return turn >= 6 and (hand_size >= 6 or untapped_lands >= 5)

    def _is_burn_matchup(self) -> bool:
        own = (self.archetype or "").strip().lower()
        opp = (self.opponent_archetype or "").strip().lower()
        return own in {"control", "counter-heavy"} and opp in {"burn", "aggro", "tempo"}

    def _should_force_inevitability_plan(self, state: MatchState, player_id: int) -> bool:
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "stack", []) or []:
            return False
        if not should_force_inevitability_line(
            int(getattr(state, "turn", 1) or 1),
            self.archetype,
            self.opponent_archetype,
        ):
            return False
        me = state.players[player_id]
        opp_id = 1 if player_id == 2 else 2
        opp = state.players[opp_id]
        my_long = len(getattr(me, "library", []) or []) + len(getattr(me, "hand", []) or []) + len(getattr(me, "graveyard", []) or [])
        opp_long = len(getattr(opp, "library", []) or []) + len(getattr(opp, "hand", []) or []) + len(getattr(opp, "graveyard", []) or [])
        my_life = int(getattr(me, "life", 20) or 20)
        opp_life = int(getattr(opp, "life", 20) or 20)
        return my_long >= opp_long - 2 and my_life >= opp_life - 4

    def _choose_forced_inevitability_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if not self._should_force_inevitability_plan(state, player_id):
            return None
        scored: list[tuple[float, dict]] = []
        for mv in legal_moves:
            mtype = mv.get("type")
            if mtype not in {"cast_spell", "activate_loyalty", "attack"}:
                continue
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            score = 0.0
            if mtype == "activate_loyalty":
                score += 4.8
            if mtype == "attack":
                attackers = list(mat.get("attackers") or [])
                if not attackers:
                    continue
                score += 1.6 + min(2.0, float(len(attackers)) * 0.5)
            if mtype == "cast_spell":
                cid = mat.get("card_id")
                card = state.cards.get(cid) if cid else None
                if not card:
                    continue
                tags = self._spell_tags(card)
                if "draw" in tags:
                    score += 4.0
                if "discard" in tags or "mill" in tags:
                    score += 3.0
                if "counter" in tags:
                    score -= 2.4
                if "removal" in tags:
                    opp_id = 1 if player_id == 2 else 2
                    opp_creatures = sum(
                        1
                        for ocid in state.players[opp_id].battlefield
                        if ocid in state.cards and "Creature" in effective_types(state, state.cards[ocid])
                    )
                    score += 2.2 if opp_creatures > 0 else -1.3
                if "Planeswalker" in set(effective_types(state, card) or []):
                    score += 3.6
                if "Creature" in set(effective_types(state, card) or []):
                    power = int(getattr(card, "power", 0) or 0)
                    score += min(2.8, power * 0.5)
            scored.append((score, mat))
        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        top = scored[0][1]
        if top.get("type") == "attack" and not (top.get("attackers") or []):
            return None
        return top

    def _choose_forced_tempo_noncontrol_closure_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.archetype != "Tempo":
            return None
        opp = (self.opponent_archetype or "").strip()
        if opp in {"Control", "Counter-heavy"}:
            return None
        if getattr(state, "active_player", player_id) != player_id:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if turn < 8:
            return None
        ranked = self._rank_moves(state, legal_moves, player_id)
        for mv in ranked:
            if mv.get("type") == "attack":
                mat = self._materialize_action(state, mv, player_id)
                if mat.get("attackers"):
                    return mat
        for mv in ranked:
            if mv.get("type") != "cast_spell":
                continue
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            cid = mat.get("card_id")
            card = state.cards.get(cid) if cid else None
            tags = self._spell_tags(card) if card else set()
            # Prefer threat/removal/draw conversion, avoid empty-stack hold-up counters.
            if "counter" in tags and not (getattr(state, "stack", []) or []):
                continue
            return mat
        return None

    def _best_proactive_non_pass(self, ranked_moves: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        non_pass = [m for m in ranked_moves if m.get("type") not in {"pass_priority", "tap_land_for_mana", "tap_lands_bulk"}]
        if not non_pass:
            return None
        burn_convert = self._best_burn_conversion_cast(non_pass, state, player_id)
        if burn_convert is not None:
            return burn_convert
        tempo_convert = self._best_tempo_threat_first_cast(non_pass, state, player_id)
        if tempo_convert is not None:
            return tempo_convert
        cheap = self._best_cheap_proactive_cast(non_pass, state, player_id)
        if cheap is not None:
            return cheap
        if getattr(state, "stack", []) or []:
            for move in non_pass:
                if move.get("type") == "cast_spell":
                    cid = move.get("card_id")
                    card = _card_for_move(state, move)
                    if card and self._is_counter_card(card):
                        return move
            return non_pass[0]
        for move in non_pass:
            if move.get("type") != "cast_spell":
                return move
            cid = move.get("card_id")
            card = _card_for_move(state, move)
            text = _oracle_text(card) if card else ""
            if _has_counter_spell_text(text):
                continue
            return move
        return non_pass[0]

    def _avoid_pass_with_main_phase_options(self, state: MatchState, legal_moves: list[dict], player_id: int, chosen: dict) -> dict:
        if chosen.get("type") != "pass_priority":
            return chosen
        if getattr(state, "active_player", player_id) != player_id:
            return chosen
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return chosen
        if getattr(state, "stack", []) or []:
            return chosen

        meaningful = [m for m in legal_moves if m.get("type") in {"play_land", "cast_spell", "cycle_card", "activate_loyalty", "attack"}]
        if not meaningful:
            return chosen

        # Cross-archetype anti-stall: repeated same-board main-phase passes with options
        # should force resource conversion.
        if self._should_force_conversion_after_repeated_main_pass(state, player_id):
            ranked = self._rank_moves(state, legal_moves, player_id)
            proactive = self._best_proactive_non_pass(ranked, state, player_id)
            if proactive is not None:
                proactive = self._materialize_action(state, proactive, player_id)
                if (
                    not proactive.get("_invalid_ai_choice")
                    and not self._is_unplayable_x_action(proactive)
                    and not self._is_action_obviously_illegal(state, proactive, player_id)
                    and (proactive.get("type") != "attack" or bool(proactive.get("attackers") or []))
                ):
                    return proactive

        ranked = self._rank_moves(state, legal_moves, player_id)
        early_cheap = self._best_cheap_proactive_cast(
            [m for m in ranked if m.get("type") not in {"pass_priority", "tap_land_for_mana", "tap_lands_bulk"}],
            state,
            player_id,
        )
        if early_cheap is not None:
            early_cheap = self._materialize_action(state, early_cheap, player_id)
            if (
                not early_cheap.get("_invalid_ai_choice")
                and not self._is_unplayable_x_action(early_cheap)
                and not self._is_action_obviously_illegal(state, early_cheap, player_id)
            ):
                return early_cheap
        if ranked and ranked[0].get("type") == "pass_priority":
            return chosen
        proactive = self._best_proactive_non_pass(ranked, state, player_id)
        if proactive is None:
            return chosen
        proactive = self._materialize_action(state, proactive, player_id)
        if proactive.get("_invalid_ai_choice") or self._is_unplayable_x_action(proactive):
            return chosen
        if self._is_action_obviously_illegal(state, proactive, player_id):
            return chosen
        if proactive.get("type") == "attack" and not (proactive.get("attackers") or []):
            return chosen
        return proactive

    def _should_force_conversion_after_repeated_main_pass(self, state: MatchState, player_id: int) -> bool:
        hand = [str(getattr(state.cards.get(cid), "name", cid)) for cid in (getattr(state.players[player_id], "hand", []) or [])]
        hand_key = tuple(sorted(hand)[:4])
        my_lands = sum(
            1
            for cid in (getattr(state.players[player_id], "battlefield", []) or [])
            if cid in state.cards and "Land" in (effective_types(state, state.cards[cid]) or [])
        )
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in (getattr(state.players[opp_id], "battlefield", []) or [])
            if cid in state.cards and "Creature" in (effective_types(state, state.cards[cid]) or [])
        )
        sig = (player_id, int(getattr(state, "turn", 1) or 1), hand_key, my_lands, opp_creatures)
        cur = int(self._main_pass_signature_counts.get(sig, 0) or 0) + 1
        self._main_pass_signature_counts[sig] = cur
        return cur >= 2

    def _best_cheap_proactive_cast(self, non_pass: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        turn = int(getattr(state, "turn", 1) or 1)
        if turn > 4:
            return None
        # If opponent is mostly tapped early, value proactive cheap development.
        me = getattr(state, "active_player", None)
        pid = player_id if player_id in {1, 2} else (me if me in {1, 2} else 1)
        opp_id = 1 if pid == 2 else 2
        opp_untapped_lands = sum(
            1
            for cid in (getattr(state.players[opp_id], "battlefield", []) or [])
            if cid in state.cards and "Land" in (effective_types(state, state.cards[cid]) or []) and not state.cards[cid].tapped
        )
        if opp_untapped_lands > 2:
            return None
        scored: list[tuple[float, dict]] = []
        for mv in non_pass:
            if mv.get("type") != "cast_spell":
                continue
            cid = mv.get("card_id")
            card = _card_for_move(state, mv)
            if not card:
                continue
            mana_text = str(getattr(card, "mana_cost", "") or "")
            if "{X}" in mana_text.upper():
                continue
            mana_req = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=False)
            cmc = mana_value(getattr(card, "mana_cost", ""), is_land=False)
            if cmc > 2:
                continue
            tags = self._spell_tags(card)
            score = 0.0
            if "Creature" in set(effective_types(state, card) or []):
                score += 3.2
            if "draw" in tags:
                score += 2.4
            if "token" in tags:
                score += 2.2
            if "counter" in tags and not (getattr(state, "stack", []) or []):
                score -= 3.0
            if "removal" in tags:
                opp_creatures = sum(
                    1
                    for x in (getattr(state.players[opp_id], "battlefield", []) or [])
                    if x in state.cards and "Creature" in (effective_types(state, state.cards[x]) or [])
                )
                score += 1.2 if opp_creatures > 0 else -1.5
            scored.append((score, mv))
        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        return scored[0][1]

    def _best_tempo_threat_first_cast(self, non_pass: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        if self.archetype not in {"Tempo"}:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if turn > 5:
            return None
        choices: list[tuple[float, dict]] = []
        for mv in non_pass:
            if mv.get("type") != "cast_spell":
                continue
            cid = mv.get("card_id")
            card = _card_for_move(state, mv)
            if not card:
                continue
            types = set(effective_types(state, card) or [])
            mana_req = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=False)
            cmc = mana_req["generic"] + sum(mana_req[c] for c in ["W", "U", "B", "R", "G"])
            if "Creature" in types and cmc <= 2:
                choices.append((4.0 - cmc * 0.2, mv))
            else:
                tags = self._spell_tags(card)
                if "counter" in tags and not (getattr(state, "stack", []) or []):
                    choices.append((-2.5, mv))
        if not choices:
            return None
        choices.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        top_score, top = choices[0]
        return top if top_score > 0 else None

    def _best_burn_conversion_cast(self, non_pass: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        if self.archetype not in {"Burn"}:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        pid = player_id if player_id in {1, 2} else getattr(state, "active_player", 1)
        opp_id = 1 if pid == 2 else 2
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        burn_spells: list[tuple[float, dict]] = []
        for mv in non_pass:
            if mv.get("type") != "cast_spell":
                continue
            cid = mv.get("card_id")
            card = _card_for_move(state, mv)
            if not card:
                continue
            text = _oracle_text(card)
            dmg = self._burn_damage_estimate(text)
            if dmg <= 0:
                continue
            score = float(dmg)
            if opp_life <= dmg:
                score += 10.0  # immediate lethal
            elif opp_life <= dmg + 3:
                score += 3.5   # two-turn clock compression
            burn_spells.append((score, mv))
        if not burn_spells:
            return None
        burn_spells.sort(key=lambda x: x[0], reverse=True)
        return burn_spells[0][1]

    def _burn_damage_estimate(self, text: str) -> int:
        # A printed fixed player-damage clause, not a card-name damage table.
        matches = re.findall(r"\bdeals?\s+(\d+)\s+damage to\s+(?:any target|target (?:player|opponent)|each (?:player|opponent))\b",
                             without_reminder_text(text).lower())
        return max((int(amount) for amount in matches), default=0)

    def _is_action_obviously_illegal(self, state: MatchState, action: dict, player_id: int) -> bool:
        kind = action.get("type")
        if kind == "play_land":
            cid = action.get("card_id")
            if not cid:
                return True
            player = state.players[player_id]
            if cid not in player.hand:
                return True
            card = state.cards.get(cid)
            if not card or "Land" not in (effective_types(state, card) or []):
                return True
            if getattr(state, "active_player", player_id) != player_id:
                return True
            if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
                return True
            if (getattr(state, "stack", []) or []):
                return True
            if self._remaining_land_plays(state, player_id) <= 0:
                return True
        return False

    def _is_major_threat_card(self, card) -> bool:
        types = set(getattr(card, "types", []) or [])
        if "Planeswalker" in types:
            return True
        if "Creature" in types:
            power = int(getattr(card, "power", 0) or 0)
            cmc = mana_value(getattr(card, "mana_cost", ""), is_land=False)
            return power >= 4 or cmc >= 5
        return False

    def _can_deploy_major_threat(self, state: MatchState, player_id: int) -> bool:
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if getattr(state, "stack", []) or []:
            return False
        turn = int(getattr(state, "turn", 1) or 1)
        for cid in getattr(state.players[player_id], "hand", []):
            card = state.cards.get(cid)
            if not card or not self._is_major_threat_card(card):
                continue
            if can_pay_with_pool_and_lands(
                state, player_id, getattr(card, "mana_cost", ""),
                card_name=getattr(card, "name", ""), spell_types=set(effective_types(state, card) or []),
                oracle_text=getattr(card, "oracle_text", "") or "",
            ):
                opp_id = 1 if player_id == 2 else 2
                opp_creatures = sum(
                    1
                    for oid in getattr(state.players[opp_id], "battlefield", [])
                    if oid in state.cards and "Creature" in effective_types(state, state.cards[oid])
                )
                # Preserve early-game hold-up discipline, but deploy sooner when the board is clear.
                if turn >= 5:
                    return True
                if turn >= 4 and opp_creatures <= 1:
                    return True
        return False

    def _color_demand(self, state: MatchState, player_id: int) -> dict[str, int]:
        demand = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for cid in state.players[player_id].hand:
            card = state.cards.get(cid)
            if not card or "Land" in effective_types(state, card):
                continue
            mana_cost = getattr(card, "mana_cost", "") or ""
            cost = _fixed_color_pips(mana_cost)
            cmc = mana_value(getattr(card, "mana_cost", ""), is_land=False)
            weight = 2 if cmc <= 2 else (1 if cmc <= 4 else 0)
            for c in ["W", "U", "B", "R", "G"]:
                if cost[c] > 0:
                    demand[c] += weight * cost[c]
            for symbol in re.findall(r"\{([^{}]+/[^{}]+)\}", mana_cost.upper()):
                if not _supported_hybrid_symbol(symbol):
                    continue
                parts = symbol.split("/")
                options = [part for part in parts if part in demand]
                if len(options) == 2:
                    for color in options:
                        demand[color] += weight * 0.5
                elif len(options) == 1:
                    demand[options[0]] += weight * 0.25
        return demand

    def _opening_color_sources_from_hand(self, hand: list) -> dict[str, int]:
        sources = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for c in hand:
            if not _card_looks_like_land(c):
                continue
            for sym in self._land_colors(c):
                if sym in sources:
                    sources[sym] += 1
        return sources

    def _board_role(self, state: MatchState, player_id: int) -> str:
        opp_id = 1 if player_id == 2 else 2
        my_life = int(getattr(state.players[player_id], "life", 20) or 20)
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        my_power = sum(
            max(0, _effective_combat_stats(state, cid)[0])
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not getattr(state.cards[cid], "tapped", False)
        )
        opp_power = sum(
            max(0, _effective_combat_stats(state, cid)[0])
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not getattr(state.cards[cid], "tapped", False)
        )
        my_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not getattr(state.cards[cid], "tapped", False)
        )
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in effective_types(state, state.cards[cid]) and not getattr(state.cards[cid], "tapped", False)
        )
        hand_delta = len(getattr(state.players[player_id], "hand", []) or []) - len(getattr(state.players[opp_id], "hand", []) or [])
        if opp_life <= 7 or (my_power >= opp_life and opp_life <= 10):
            return "race"
        if my_life <= 8 and opp_power > my_power + 1:
            return "stabilize"
        if opp_power >= my_power + 3 and opp_creatures >= my_creatures and my_life <= 12:
            return "stabilize"
        if my_power >= opp_power + 2 and my_creatures >= opp_creatures and my_life > 8:
            return "convert"
        if hand_delta >= 2 and opp_power <= my_power and my_life > 10:
            return "control"
        if my_life <= 8 and opp_power > my_power:
            return "defend"
        return "normal"

    def _current_color_sources(self, state: MatchState, player_id: int) -> dict[str, int]:
        sources = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for cid in state.players[player_id].battlefield:
            card = state.cards.get(cid)
            if not card or "Land" not in effective_types(state, card):
                continue
            for c in self._land_colors(card, state):
                if c in sources:
                    sources[c] += 1
        return sources

    def _land_colors(self, card, state=None) -> set[str]:
        from rules_engine.mana import _land_colors, land_mana_colors
        if isinstance(card, CardInstance) and (state is not None or card.zone == Zone.BATTLEFIELD):
            return land_mana_colors(card, state)
        return _land_colors(getattr(card, "name", ""), getattr(card, "type_line", ""), getattr(card, "oracle_text", ""))

    def _is_counter_card(self, card) -> bool:
        text = _oracle_text(card)
        return _has_counter_spell_text(text)

    def _noncreature_permanent_threat_score(self, state: MatchState, card_id: str | None, player_id: int) -> float:
        if not card_id or card_id not in state.cards:
            return 0.0
        card = state.cards[card_id]
        opp_id = 1 if player_id == 2 else 2
        controller = getattr(card, "controller", None)
        if controller == player_id:
            return -10.0
        score = 0.0
        types = set(effective_types(state, card) or [])
        text = _oracle_text(card)
        if "Planeswalker" in types:
            score += 8.0
        if "Artifact" in types:
            score += 3.0
        if "Enchantment" in types:
            score += 3.0
        if any(k in text for k in ["you can't", "players can't", "your opponents can't"]):
            score += 4.0
        if any(k in text for k in ["draw", "at the beginning of", "whenever"]):
            score += 1.5
        if any(k in text for k in ["creatures you control get", "+1/+1", "anthem"]):
            score += 2.2
        if any(k in text for k in ["sacrifice", "exile", "destroy"]):
            score += 1.0
        if any(k in text for k in ["treasure", "add {", "create token"]):
            score += 1.3
        # Matchup-aware importance boosts.
        if self.archetype in {"Aggro", "Burn", "Tempo"} and any(k in text for k in ["lifelink", "gain life", "can't lose life"]):
            score += 3.2
        if self.archetype in {"Control", "Counter-heavy"} and any(k in text for k in ["draw", "search your library", "return target"]):
            score += 2.2
        if self.archetype in {"Tokens", "Tribal"} and any(k in text for k in ["creatures you control get", "token"]):
            score += 2.2
        # If permanent belongs to opponent battlefield, it's usually a real target.
        if card_id in getattr(state.players[opp_id], "battlefield", []):
            score += 0.8
        return score

    def _graveyard_creature_reanimation_score(self, state: MatchState, card_id: str | None, player_id: int) -> float:
        if not card_id or card_id not in state.cards:
            return 0.0
        card = state.cards[card_id]
        score = float(getattr(card, "power", 0) or 0) * 0.9 + float(getattr(card, "toughness", 0) or 0) * 0.3
        if "legendary" in " ".join(effective_types(state, card)).lower():
            score += 0.5
        text = _oracle_text(card)
        if any(k in text for k in ["draw", "counter", "remove", "destroy", "exile", "return"]):
            score += 0.4
        return score

    def _choose_best_stack_target_id(self, state: MatchState, player_id: int, candidates: list[dict], *, allow_friendly: bool = False, allow_protected: bool = True) -> str | None:
        best_id = None
        best_score = (-1, -999.0)
        best_tiebreak = ""
        for c in candidates:
            sid = c.get("id")
            if not sid:
                continue
            item = next((item for item in getattr(state, "stack", []) if item.id == sid), None)
            if item is None or (getattr(item, "controller", None) == player_id and not allow_friendly):
                continue
            protected = (isinstance(state, MatchState) and stack_object_kind(state, item) == "spell"
                         and spell_cant_be_countered(state, item))
            if protected and not allow_protected:
                continue
            score = (int(not protected), self._stack_item_threat_score(state, sid, player_id))
            tiebreak = str(c.get("label") or c.get("name") or sid)
            if score > best_score or (score == best_score and (best_id is None or tiebreak < best_tiebreak)):
                best_score = score
                best_id = sid
                best_tiebreak = tiebreak
        return best_id

    def _best_stack_threat_score(self, state: MatchState, player_id: int) -> float:
        items = getattr(state, "stack", []) or []
        if not items:
            return 0.0
        return max(self._stack_item_threat_score(state, it.id, player_id) for it in items)

    def _stack_item_threat_score(self, state: MatchState, stack_item_id: str, player_id: int) -> float:
        item = next((x for x in (getattr(state, "stack", []) or []) if getattr(x, "id", None) == stack_item_id), None)
        if item is None:
            return 0.0
        from rules_engine.targeting import stack_source_card
        source = stack_source_card(state, item)
        if source is None:
            return 1.0
        score = 0.0
        types = set(effective_types(state, source) or [])
        if "Planeswalker" in types:
            score += 8.0
        if "Artifact" in types:
            score += 2.8
        if "Enchantment" in types:
            score += 2.8
        if "Creature" in types:
            p = int(getattr(source, "power", 0) or 0)
            t = int(getattr(source, "toughness", 0) or 0)
            score += min(7.0, p * 0.9 + t * 0.3)
        mana_cost = parse_mana_cost(getattr(source, "mana_cost", ""), is_land=False)
        cmc = mana_value(getattr(source, "mana_cost", ""), is_land=False)
        score += min(5.0, cmc * 0.45)
        text = _oracle_text(source)
        if any(k in text for k in ["destroy all", "exile all"]) or "sweeper" in self._spell_tags(source):
            score += 6.0
        if "draw" in self._spell_tags(source):
            score += 2.2
        if _has_counter_spell_text(text):
            score += 1.4
        if any(k in text for k in ["you can't", "players can't", "your opponents can't"]):
            score += 4.0
        if any(k in text for k in ["creatures you control get", "+1/+1"]):
            score += 2.0
        if any(k in text for k in ["at the beginning of", "whenever", "draw"]):
            score += 1.4
        controller = getattr(item, "controller", None)
        if (isinstance(state, MatchState) and controller != player_id
                and not (getattr(item, 'payload', None) or {}).get('uncounterable')
                and not (stack_object_kind(state, item) == 'spell' and spell_cant_be_countered(state, item))):
            from ai.pending_effects import pending_counter_gain
            gain = pending_counter_gain(state, player_id, stack_item_id)
            if gain is not None:
                # Threat depends on the resolved target/board, not just spell cost.
                score = max(0.0, gain)
        if controller == player_id:
            score -= 10.0
        return score


def _step_key(step) -> str:
    value = getattr(step, "value", step)
    s = str(value or "").strip()
    if s.startswith("Step."):
        s = s.split(".", 1)[1]
    return s.lower()
