"""Value checked public resource changes, without predicting hidden spells."""
import re

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
        oracle_text=card.oracle_text if card else '')


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
    costs = {(card.mana_cost, card.oracle_text, tuple(effective_types(before, card))): card
             for card in held if card.mana_cost and '{X}' not in card.mana_cost.upper()}
    access = sum(int(_can_pay(new, player_id, card.mana_cost, card))
                 - int(_can_pay(old, player_id, card.mana_cost, card)) for card in costs.values())
    return new_value - old_value + enemy_old - enemy_new + 3.0 * access


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
