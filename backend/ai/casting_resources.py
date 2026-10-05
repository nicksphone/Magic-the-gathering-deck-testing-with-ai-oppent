"""Bounded, public/own-information payment alternatives; rules remain authoritative."""
from copy import deepcopy
import json
import re

from ai.pending_effects import planning_copy
from ai.heuristics import evaluate_board, repeatable_mana_value
from game_state.state import Step
from rules_engine.action_validation import ActionRejected, validate_action
from rules_engine.casting_resources import resource_candidates, resource_keywords, resource_payment
from rules_engine.card_faces import select_cast_face
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.oracle_text import without_reminder_text
from rules_engine.type_effects import effective_types
from rules_engine.query_context import rule_query_scope, query_cache


def graveyard_permission_opportunity(state, player_id, spell_id, option):
    """Estimate scarce-slot loss using only other cards in our graveyard."""
    key = option.get('graveyard_permission_key')
    if not key:
        return 0.0
    from rules_engine.costs import collect_cost_options
    loss = 0.0
    for cid in state.players[player_id].graveyard:
        if cid == spell_id or 'Land' in effective_types(state, state.cards[cid]):
            continue
        alternatives = collect_cost_options(state, player_id, state.cards[cid])
        keys = {cost.graveyard_permission_key for cost in alternatives}
        if key in keys and None not in keys:
            loss += 1.0 / len(keys)
    return loss


def _graveyard_loss(agent, state, cid, player_id):
    from rules_engine.graveyard_permissions import ordinary_graveyard_cast, graveyard_land_permission, limited_graveyard_casts
    card = state.cards[cid]
    text = without_reminder_text(card.oracle_text or '').lower()
    loss = 0.1
    land_face = ('Land' in effective_types(state, card) or (getattr(card, 'layout', '') == 'modal_dfc'
                 and any('Land' in face.get('type_line', '') for face in getattr(card, 'card_faces', []))))
    if (re.search(r'\b(flashback|escape|disturb|aftermath|jump-start|retrace|dredge)\b', text)
            or ordinary_graveyard_cast(state, player_id, cid)
            or limited_graveyard_casts(state, player_id, card)
            or (land_face and graveyard_land_permission(state, player_id, cid))):
        loss += 3 + max(0, agent._hand_retention_value(state, cid, player_id)) * 0.3
    engines = [without_reminder_text(state.cards[other].oracle_text or '').lower() for other in
               state.players[player_id].hand + state.players[player_id].battlefield]
    if any(re.search(r'\b(?:return|cast|play)\s+(?:a|an|target|all|each|any|one|creature|permanent|cards)\b'
                     r'[^.\n]*\bfrom your graveyard\b', oracle)
           and not re.search(r'\b(?:instant|sorcery) cards?\b', oracle)
           for oracle in engines) and 'Creature' in effective_types(state, card):
        loss += max(0, agent._graveyard_creature_reanimation_score(state, cid, player_id))
    return loss


def _tap_loss(agent, state, cid, player_id):
    card = state.cards[cid]
    if 'Creature' not in effective_types(state, card):
        return 0.1 + repeatable_mana_value(state, cid) * 0.3
    opponent = state.players[3-player_id]
    incoming = any('Creature' in effective_types(state, state.cards[other])
                   for other in opponent.battlefield)
    already_blocking = cid in {other for group in state.blocks.values()
                              for other in (group if isinstance(group, list) else [group])}
    before_combat = (state.active_player == player_id and state.step in
                     {Step.UNTAP, Step.UPKEEP, Step.DRAW, Step.PRECOMBAT_MAIN, Step.BEGIN_COMBAT})
    attacking = before_combat and (not card.summoning_sick or has_keyword(state, cid, 'haste')) and cid not in state.attackers
    combat_loss = (max(0, effective_power(state, cid)) * 0.7
                   + max(0, effective_toughness(state, cid)) * 0.35)
    return (combat_loss if attacking or incoming and not already_blocking else 0.1) + repeatable_mana_value(state, cid) * 0.3


def _token_reward(effect_key, data):
    if effect_key != 'create_token':
        return 0
    return data.get('amount', 1) * (max(0, data.get('power', 0)) * 0.7
                                  + max(0, data.get('toughness', 0)) * 0.35)


def _tap_reward(state, cid):
    from rules_engine.resource_events import collect_tap_triggers
    return sum(_token_reward(trigger['effect_key'], trigger['payload'])
               for trigger in collect_tap_triggers(state, {'card_id': cid}))


def _requirements(state, card, action, player_id):
    from rules_engine.hooks import CostContext, apply_cost_modifiers
    from rules_engine.costs import collect_cost_options
    from rules_engine.mana import _payment_requirements
    from rules_engine.attachments import is_aura
    option = next((option for option in collect_cost_options(state, player_id, card)
                   if option.id == (action.get('cost_choice') or {}).get('id')), None)
    context = apply_cost_modifiers(CostContext(
        player_id=player_id, card_name=card.name, mana_cost=option.mana_cost if option else card.mana_cost,
        state=state, spell_types=set(effective_types(state, card)), spell_is_aura=is_aura(card),
        spell_kicked=bool(option and option.kicked), oracle_text=card.oracle_text,
        source_card_id=card.id, target_card_id=(action.get('targets') or {}).get('target_card_id')))
    return _payment_requirements(context.mana_cost, False, int((action.get('targets') or {}).get('x_value', 0)),
                                 context.generic_reduction, context.generic_increase,
                                 action.get('hybrid_choices'), floored_reductions=context.floored_reductions)


def _choices(agent, state, card, action, player_id):
    candidates = resource_candidates(state, player_id, card)
    objects = [(cid, 'delve', ['generic']) for cid in candidates['delve']]
    objects += [(row['card_id'], 'convoke', row['pay_as']) for row in candidates['convoke']]
    objects += [(cid, 'improvise', ['generic']) for cid in candidates['improvise']]
    loss = {cid: _graveyard_loss(agent, state, cid, player_id) if keyword == 'delve'
            else _tap_loss(agent, state, cid, player_id) - _tap_reward(state, cid)
            for cid, keyword, _ in objects}
    ordered = sorted(objects, key=lambda row: (loss[row[0]], row[0], row[1]))
    yield None  # Always retain the engine's ordinary legal fallback.
    yield {}    # Deliberately preserve all non-mana resources when affordable.
    seen = {json.dumps({}, sort_keys=True)}
    for req in _requirements(state, card, action, player_id):
        selected = {}
        for cid, keyword, colors in ordered:
            plan = resource_payment(state, player_id, card, req, selected)
            if plan is None:
                break
            if cid in set(selected.get('delve', []) + selected.get('improvise', [])) | {
                    row['card_id'] for row in selected.get('convoke', [])}:
                continue
            colors = [color for color in colors if plan.remaining.get(color, 0)]
            if not colors:
                continue
            color = max(colors, key=lambda color: (color != 'generic', plan.remaining[color], color))
            value = {'card_id': cid, 'pay_as': color} if keyword == 'convoke' else cid
            selected.setdefault(keyword, []).append(value)
            key = json.dumps(selected, sort_keys=True)
            if key not in seen:
                seen.add(key)
                yield deepcopy(selected)
            if len(seen) >= 16:
                return


def _score(agent, before, after, player_id):
    value = evaluate_board(after, player_id)
    for cid in before.players[player_id].battlefield:
        if not before.cards[cid].tapped and after.cards[cid].tapped:
            value -= _tap_loss(agent, before, cid, player_id)
    for cid in before.players[player_id].graveyard:
        if cid not in after.players[player_id].graveyard:
            value -= _graveyard_loss(agent, before, cid, player_id)
    followups = []
    for cid in after.players[player_id].hand:
        card = after.cards[cid]
        if agent._can_pay_card_cost(after, player_id, card):
            followups.append(max(0, agent._hand_retention_value(after, cid, player_id)) *
                             (0.5 if 'Instant' in effective_types(after, card) else 0.25))
    value += sum(sorted(followups, reverse=True)[:2])
    for item in after.stack:
        if item.controller == player_id and item.effect_key == 'create_token' and item.payload.get('__trigger_event'):
            value += _token_reward(item.effect_key, item.payload)
    return value


def choose_resource_payment(agent, state, action, player_id):
    if action.get('type') != 'cast_spell' or action.get('_invalid_ai_choice') or 'resource_payment' in action:
        return action
    source = state.cards.get(action.get('card_id'))
    if source is None:
        return action
    card = select_cast_face(source, action.get('selected_face_index', (action.get('targets') or {}).get('selected_face_index')))
    if not resource_keywords(card):
        return action
    with rule_query_scope(state):
        cache = query_cache(state)
        key = ('ai_cast_resources', agent, player_id, agent.archetype, json.dumps(action, sort_keys=True))
        if key in cache:
            return {**action, **deepcopy(cache[key])}
        best, score = action, float('-inf')
        for choice in _choices(agent, state, card, action, player_id):
            candidate = dict(action)
            if choice is not None:
                candidate['resource_payment'] = choice
            projected = planning_copy(state)
            try:
                validate_action(projected, agent.engine, player_id, candidate)
                agent.engine.take_action(projected, player_id, candidate, reject_invalid=True)
            except ActionRejected:
                continue
            value = _score(agent, state, projected, player_id)
            if value > score:
                best, score = candidate, value
        cache[key] = {'resource_payment': deepcopy(best['resource_payment'])} if 'resource_payment' in best else {}
        return best
