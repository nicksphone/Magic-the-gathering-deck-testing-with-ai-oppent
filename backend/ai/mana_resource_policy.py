"""Value checked public resource changes, without predicting hidden spells."""
import re
import random

from ai.pending_effects import planning_copy, _projection_copy, _settle_announced_stack, _decision_projection
from game_state.state import MatchState
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.land_types import land_type_instructions
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.oracle_text import without_reminder_text
from rules_engine.type_effects import effective_types


def _ready_board(state, player_id):
    # A resource-retention comparison, not a simulated next turn: no draws,
    # untap-step guarantees, expiry, new land drops or opponents' responses.
    ready = planning_copy(state)
    player = ready.players[player_id]
    player.mana_pool.clear()
    player.snow_mana_pool.clear()
    player.restricted_mana_pool.clear()
    for cid in player.battlefield:
        ready.cards[cid].tapped = False
        ready.cards[cid].summoning_sick = False
    return ready


def _can_pay(state, player_id, cost, card=None):
    return can_pay_with_pool_and_lands(
        state, player_id, cost, card_name=card.name if card else '',
        spell_types=set(effective_types(state, card)) if card else set(),
        oracle_text=card.oracle_text if card else '',
        source_card_id=getattr(card, 'id', None), cast_resource_card=card)


def _resource_value(state, player_id, known_cards, *, public_only=False):
    ready = _ready_board(state, player_id)
    demand = ''.join(card.mana_cost or '' for card in known_cards)
    # Independent payment probes do not claim these costs can all be paid
    # together. Bounded capacity/flexibility weights remain heuristic.
    value = sum(_can_pay(ready, player_id, '{' + str(n) + '}') for n in range(1, 9)) * .25
    for color in 'WUBRGC':
        weight = 1.25 if '{' + color + '}' in demand else .15 if public_only else 0.0
        value += weight * _can_pay(ready, player_id, '{' + color + '}')
        if demand.count('{' + color + '}') >= 2:
            value += .75 * _can_pay(ready, player_id, '{' + color + '}{' + color + '}')
    return ready, value


def resource_delta(before, after, player_id, *, excluded_card_ids=()):
    """Compare retained mana and mana access for the same known own cards."""
    if not isinstance(before, MatchState) or not isinstance(after, MatchState):
        return 0.0
    held = [before.cards[cid] for cid in before.players[player_id].hand
            if cid not in excluded_card_ids and 'Land' not in effective_types(before, before.cards[cid])]
    public = {pid: [before.cards[cid] for zone in ('battlefield', 'graveyard', 'exile')
                    for cid in getattr(before.players[pid], zone)
                    if cid not in excluded_card_ids
                    # Ownership alone does not authorize looking at face-down exile.
                    and not before.cards[cid].exile_face_down
                    and 'Land' not in effective_types(before, before.cards[cid])]
              for pid in (player_id, 3-player_id)}
    old, old_value = _resource_value(before, player_id, held + public[player_id])
    new, new_value = _resource_value(after, player_id, held + public[player_id])
    _, enemy_old = _resource_value(before, 3-player_id, public[3-player_id], public_only=True)
    _, enemy_new = _resource_value(after, 3-player_id, public[3-player_id], public_only=True)
    # Do not inspect hidden zones, or reward newly drawn unknowns.
    costs = {}
    for card in held:
        if card.mana_cost and '{X}' not in card.mana_cost.upper():
            key = (card.mana_cost, card.oracle_text, tuple(effective_types(before, card)))
            costs.setdefault(key, []).append(card.id)

    def has_access(state, hand, card_ids):
        # Only original held instances that survive in this projection count.
        return any(_can_pay(state, player_id, state.cards[cid].mana_cost, state.cards[cid])
                   for cid in card_ids if cid in hand)

    old_hand = set(old.players[player_id].hand)
    new_hand = set(new.players[player_id].hand)
    access = sum(int(has_access(new, new_hand, card_ids))
                 - int(has_access(old, old_hand, card_ids)) for card_ids in costs.values())
    return new_value - old_value + enemy_old - enemy_new + 3.0 * access


_LAND_PROFILE_MAX_PROBES = 1024


def _unmodeled_land_capability(card):
    from rules_engine.costs import ActivatedCost, parse_activated_cost
    from rules_engine.cycling import cycling_cost
    from rules_engine.keyword_actions import ninjutsu_cost
    from rules_engine.move_generator import _extract_equip_cost
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE, extract_activated_abilities, extract_loyalty_abilities, crew_value
    from rules_engine.suspend import instruction as suspend_instruction
    # These native resource domains are not represented by spell-payment bits.
    # Abstain even when an ability is not payable or has no target right now.
    return bool(extract_activated_abilities(card) or extract_loyalty_abilities(card)
                or cycling_cost(card.oracle_text, allow_variable=True)
                or _extract_equip_cost(card.oracle_text) or crew_value(card) is not None
                or ninjutsu_cost(card) or suspend_instruction(card)
                or any(parse_activated_cost(match[1]) != ActivatedCost(tap_source=True)
                       for match in ACTIVATED_ABILITY_RE.finditer(without_reminder_text(card.oracle_text))))


def _known_land_costs(state, player_id):
    from ai.information import is_unknown
    from rules_engine.card_faces import exile_candidates, exile_permission
    from rules_engine.costs import collect_cost_options
    from rules_engine.foretell import can_look
    from rules_engine.mana import MANA_SYMBOL_RE, parse_mana_cost
    costs, demand = [], dict.fromkeys('WUBRGCS', 0)
    demand['generic'] = 0
    for zone in ('hand', 'graveyard', 'exile', 'battlefield'):
        candidates = exile_candidates(state, player_id) if zone == 'exile' else getattr(state.players[player_id], zone)
        for cid in candidates:
            card = state.cards[cid]
            if zone == 'exile' and not exile_permission(state, player_id, cid):
                continue
            if card.exile_face_down and not can_look(card, player_id):
                return None
            if is_unknown(card):
                return None
            if _unmodeled_land_capability(card):
                return None
            if zone == 'battlefield' or 'Land' in effective_types(state, card):
                continue
            options = tuple(collect_cost_options(state, player_id, card))
            if not options:
                if zone == 'hand':
                    return None
                continue
            requirements = []
            for option in options:
                symbols = MANA_SYMBOL_RE.findall(option.mana_cost.upper())
                if (''.join('{' + symbol + '}' for symbol in symbols) != option.mana_cost.upper()
                        or any(not symbol.isdecimal() and symbol not in set('WUBRGCS') for symbol in symbols)
                        or option.pay_life_x or option.discard_x or option.discard_cards
                        or option.discard_all or option.sacrifice_all or option.sacrifice_creatures
                        or option.exile_graveyard or option.hand_exile_color):
                    return None
                requirements.append(parse_mana_cost(option.mana_cost))
            costs.append((cid, options))
            # Options on one card are alternatives; different physical cards
            # still compete for the same finite mana sources.
            for color in 'WUBRGCS':
                demand[color] += max(req[color] for req in requirements)
            demand['generic'] += max(sum(req.values()) for req in requirements)
    return costs, demand


def _land_coverage(state, player_id, costs, demand):
    from game_state.state import Zone
    from rules_engine.alternative_casts import spell_cast_view
    from rules_engine.card_faces import exile_permission
    from rules_engine.costs import casting_method, check_cost_option_available, collect_cost_options
    ready = _ready_board(state, player_id)
    profile = []
    for cid, options in costs:
        card = state.cards[cid]
        # Availability alone does not validate a spell's zone or permission.
        # In particular a modal spell consumed as a land is no retained spell.
        if (card.zone not in {Zone.HAND, Zone.GRAVEYARD, Zone.EXILE}
                or 'Land' in effective_types(state, card)
                or (card.zone == Zone.EXILE and not exile_permission(state, player_id, cid))
                or tuple(collect_cost_options(state, player_id, card)) != options):
            return None
        for option in options:
            for resources in (state, ready):
                profile.append(check_cost_option_available(resources, player_id, resources.cards[cid], option))
                source = spell_cast_view(resources.cards[cid], casting_method(option.id))
                for color in 'WUBRGCS':
                    profile.extend(_can_pay(resources, player_id, ('{' + color + '}') * n, source)
                                   for n in range(1, demand[color] + 1))
                profile.extend(_can_pay(resources, player_id, '{' + str(n) + '}', source)
                               for n in range(1, demand['generic'] + 1))
    return tuple(profile)


def prefer_nonregressive_land(agent, state, player_id, selected, alternatives):
    """Bounded cast-resource improvement; unmodeled known abilities retain Q."""
    from ai.information import decision_view
    from game_state.state import Zone
    if (not isinstance(state, MatchState) or selected.get('type') != 'play_land'
            or state.winner is not None or state.pregame_pending or state.stack
            or state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order
            or state.active_player != player_id or state.priority_player != player_id):
        return selected
    choices = [action for action in alternatives if action.get('type') == 'play_land']
    if selected not in choices or len(choices) < 2:
        return selected
    rng = random.getstate()
    try:
        view = state
        if getattr(view, 'ai_information_player', None) != player_id:
            view, _ = decision_view(state, player_id, choices)
        base = _projection_copy(view)
        universe = _known_land_costs(base, player_id)
        if universe is None or not universe[0]:
            return selected
        costs, demand = universe
        # Additional resource-selection costs abstain above, so availability
        # makes at most one native payment probe per option per board. Count every
        # current/ready capacity probe for every admitted candidate up front.
        probes = len(choices) * sum(len(options) for _, options in costs) * (
            2 + 2 * sum(demand.values()))
        if probes > _LAND_PROFILE_MAX_PROBES:
            return selected

        def project(action):
            cid = action.get('card_id')
            if cid not in base.players[player_id].hand or base.cards[cid].zone != Zone.HAND:
                return None
            projected = checked_action(_projection_copy(base), RulesEngine(), player_id, action)
            if (random.getstate() != rng or projected.winner is not None or projected.stack
                    or projected.pending_mechanic_choice or projected.pending_replacement_choice or projected.pending_trigger_order
                    or (projected.turn, projected.step, projected.active_player, projected.priority_player)
                       != (base.turn, base.step, base.active_player, base.priority_player)):
                return None
            # Opaque private-zone equality is only a preservation check;
            # no opposing hand or library card is used for valuation.
            for pid, before in base.players.items():
                after = projected.players[pid]
                expected_hand = [card_id for card_id in before.hand if card_id != cid] if pid == player_id else before.hand
                if (after.hand != expected_hand or after.library != before.library
                        or after.graveyard != before.graveyard or after.exile != before.exile
                        or after.life != before.life):
                    return None
            return projected

        selected_state = project(selected)
        if selected_state is None:
            return selected
        current = _land_coverage(selected_state, player_id, *universe)
        if current is None:
            return selected
        improving = []
        for action in choices:
            if action == selected:
                continue
            projected = project(action)
            if projected is None:
                return selected
            coverage = _land_coverage(projected, player_id, *universe)
            if coverage is None or len(coverage) != len(current):
                return selected
            if all(new >= old for old, new in zip(current, coverage)) and any(new > old for old, new in zip(current, coverage)):
                improving.append(action)
        result = agent._best_land_move(base, improving, player_id) if improving else selected
        return result if random.getstate() == rng and result in choices else selected
    except (ActionRejected, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return selected
    finally:
        random.setstate(rng)


def resource_change_plan(agent, state, move, player_id, *, include_normal_land=False):
    """Return an unanswered, paid/settled resource estimate or unknown."""
    scope = _decision_projection.get()
    key = ('mana_resource_plan', id(move), player_id, include_normal_land)
    cache = scope[2] if scope and scope[0] is state and scope[1] == player_id else None
    if cache is not None and key in cache:
        return cache[key][1]
    result = _resource_change_plan(agent, state, move, player_id, include_normal_land)
    if cache is not None:
        cache[key] = (move, result)
    return result


def _resource_change_plan(agent, state, move, player_id, include_normal_land):
    card = state.cards.get(move.get('card_id'))
    if card is None or state.stack or move.get('type') not in {'cast_spell', 'play_land'}:
        return None
    if move.get('selected_face_index') is not None:
        from rules_engine.card_faces import select_cast_face
        card = select_cast_face(card, move['selected_face_index'])
    if not land_type_instructions(getattr(card, 'oracle_text', '') or '') and not (include_normal_land and move['type'] == 'play_land'):
        return None
    action = agent._materialize_action(state, move, player_id)
    if action.get('_invalid_ai_choice'):
        return None
    projected = _projection_copy(state)
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    enemy_hand = tuple(state.players[3-player_id].hand)
    try:
        projected = checked_action(projected, RulesEngine(), player_id, action)
        if not _settle_announced_stack(projected):
            return None
    except ActionRejected:
        return None
    if (projected.winner is not None or projected.pending_mechanic_choice
            or any(tuple(player.library) != libraries[pid] for pid, player in projected.players.items())
            or tuple(projected.players[3-player_id].hand) != enemy_hand):
        return None
    score = resource_delta(state, projected, player_id, excluded_card_ids={card.id})
    lines = without_reminder_text(card.oracle_text).splitlines()
    pure_fixing = ('Creature' not in effective_types(state, card)
                  and all(land_type_instructions(line) or re.fullmatch(r'Enchant land\.?', line, re.I)
                          for line in lines if line.strip()))
    return {'action': action, 'score': score, 'defer': pure_fixing and score < 1.0}
