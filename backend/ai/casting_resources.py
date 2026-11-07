"""Bounded, public/own-information payment alternatives; rules remain authoritative."""
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
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


_automatic_effect_cost_context = ContextVar('automatic_effect_cost_context', default=None)


@contextmanager
def _automatic_effect_cost_scope(state, player_id, card_id):
    """Carry the trusted effect caller's waiver, never an action-dict flag."""
    grant = {'state': state, 'player_id': player_id, 'card_id': card_id, 'active': True}
    token = _automatic_effect_cost_context.set(grant)
    try:
        yield
    finally:
        # Copied contexts share this grant and must observe revocation too.
        grant['active'] = False
        _automatic_effect_cost_context.reset(token)


def _materialization_without_mana(state, player_id, card_id):
    context = _automatic_effect_cost_context.get()
    return ((state.pending_mechanic_choice or {}).get('kind') in {'effect_cast', 'suspend_cast'}
            or (context is not None and context['active'] is True and context['state'] is state
                and context['player_id'] == player_id and context['card_id'] == card_id))


def complete_fixed_cost_choice(agent, state, action, player_id, offered, explicit=None):
    """Keep a payable preference; otherwise complete only unspecified fixed costs."""
    if action.get('_invalid_ai_choice') or not any(
            offered.get(count) and not offered.get(exhaustive)
            for count, exhaustive in (('discard_cards', 'discard_all'),
                                       ('sacrifice_creatures', 'sacrifice_all'),
                                       ('discard_x', 'discard_all'))):
        return action
    from rules_engine.costs import collect_cost_options, check_cost_option_available, additional_cost_selection, additional_cost_candidates, casting_method
    from rules_engine.spell_cost_witness import fixed_cost_selections, escape_payment_condition
    from rules_engine.alternative_casts import spell_cast_view
    from rules_engine.attachments import is_aura
    from rules_engine.mana import can_pay_with_pool_and_lands
    card = state.cards[action['card_id']]
    targets = action.get('targets') or {}
    card = select_cast_face(card, action.get('selected_face_index', targets.get('selected_face_index')))
    if casting_method(action['cost_choice']['id']) == 'bestow':
        from rules_engine.bestow import bestow_cast_view
        card = bestow_cast_view(card)
    free = _materialization_without_mana(state, player_id, action['card_id'])
    option = next((o for o in collect_cost_options(state, player_id, card, without_mana=free,
                    action_targets=targets) if o.id == action['cost_choice']['id']), None)
    if option is None:
        return {**action, '_invalid_ai_choice': True}
    x = int(targets.get('x_value', 0) or 0)
    preferred = action['cost_choice']
    explicit = {k: v for k, v in (explicit or {}).items() if v is not None}
    keys = ('discard_card_ids', 'sacrifice_card_ids', 'exile_card_ids')
    if any(k in explicit and (not isinstance(explicit[k], list)
            or any(not isinstance(cid, str) for cid in explicit[k])) for k in keys):
        return {**action, '_invalid_ai_choice': True}

    view = spell_cast_view(card, casting_method(option.id))
    resources = action.get('resource_payment')
    if resources is not None:
        # Validate shape, enabled keywords and object eligibility independently
        # of the fixed subset. Actual amounts/reservations remain payable()'s job.
        size = sum(len(ids) for ids in resources.values() if isinstance(ids, list)) if isinstance(resources, dict) else 0
        if resource_payment(state, player_id, view,
                {key: size for key in ('generic', 'W', 'U', 'B', 'R', 'G', 'C', 'S')}, resources) is None:
            return {**action, '_invalid_ai_choice': True}
    branches = action.get('hybrid_choices')
    if branches is not None:
        from rules_engine.mana import hybrid_payment_symbols
        symbols = hybrid_payment_symbols(option.mana_cost)
        if (not symbols or not isinstance(branches, list) or len(branches) != len(symbols)
                or any(branch not in symbol['choices'] for branch, symbol in zip(branches, symbols))):
            return {**action, '_invalid_ai_choice': True}

    def payable(choice):
        if not check_cost_option_available(state, player_id, card, option, x_value=x,
                target_card_id=targets.get('target_card_id'), cost_choice=choice,
                escape_exile_ids=action.get('escape_exile_ids')):
            return False
        if action.get('hybrid_choices') is None and action.get('resource_payment') is None:
            return True
        # The general availability API searches resource branches. Honor an
        # explicitly supplied branch as well, using the same native mana check.
        selected = additional_cost_selection(state, player_id, option, card.id, choice, x_value=x)
        reserved = {card.id, *selected.get('exile_card_ids', [])}
        for key, exhaustive in (('discard_card_ids', option.discard_all),
                                ('sacrifice_card_ids', option.sacrifice_all)):
            if not exhaustive:
                reserved.update(selected[key])
        condition = None
        if casting_method(option.id) == 'escape':
            ids = action.get('escape_exile_ids')
            condition = escape_payment_condition(player_id, card.id, option.exile_graveyard, ids)
            reserved.update(ids or [])
        view = spell_cast_view(card, casting_method(option.id))
        return can_pay_with_pool_and_lands(state, player_id, option.mana_cost,
            is_land='Land' in effective_types(state, view), card_name=view.name,
            x_value=x, spell_types=set(effective_types(state, view)), spell_is_aura=is_aura(view),
            spell_kicked=option.kicked, oracle_text=view.oracle_text or '',
            source_card_id=view.id, target_card_id=targets.get('target_card_id'),
            reserved_life=option.pay_life + (x if option.pay_life_x else 0),
            reserved_card_ids=reserved, cast_resource_card=view,
            hybrid_choices=action.get('hybrid_choices'), resource_choices=action.get('resource_payment'),
            additional_generic_reduction=len(selected.get('exile_card_ids', []))*option.hand_exile_generic_reduction,
            post_payment_condition=condition)

    if payable(preferred):
        return action
    counts = {'discard_card_ids': 0 if option.discard_all else option.discard_cards + (x if option.discard_x else 0),
              'sacrifice_card_ids': 0 if option.sacrifice_all else option.sacrifice_creatures}
    selectable = {key for key, count in counts.items() if count}
    if option.hand_exile_color:
        selectable.add('exile_card_ids')
    if selectable <= explicit.keys():
        return {**action, '_invalid_ai_choice': True}
    candidates = additional_cost_candidates(state, player_id, card.id, option)
    for key in keys:
        if key not in explicit:
            continue
        ids = explicit[key]
        if (len(set(ids)) != len(ids) or any(cid not in candidates.get(key, []) for cid in ids)
                or key in counts and len(ids) != counts[key]
                or key == 'exile_card_ids' and not option.hand_exile_color):
            return {**action, '_invalid_ai_choice': True}
    losses = {}
    def loss(key, cid):
        kind = 'sacrifice' if key == 'sacrifice_card_ids' else 'hand'
        cache_key = (kind, cid)
        if cache_key not in losses:
            rank = agent._sacrifice_loss if kind == 'sacrifice' else agent._hand_retention_value
            losses[cache_key] = rank(state, cid, player_id)
        return losses[cache_key]
    # Ignoring cross-resource exclusions is optimistic: reaching this additive
    # floor proves that no later native witness can have a lower resource loss.
    floor = sum(sum(loss(key, cid) for cid in explicit[key]) if key in explicit
                else sum(sorted(loss(key, cid) for cid in candidates[key])[:count])
                for key, count in counts.items() if count or key in explicit)
    if option.hand_exile_color:
        floor += sum(loss('exile_card_ids', cid) for cid in explicit['exile_card_ids']) if 'exile_card_ids' in explicit else sum(
            min(0, loss('exile_card_ids', cid)) for cid in candidates['exile_card_ids'])
    best, best_loss = None, float('inf')
    for alternative in fixed_cost_selections(state, player_id, card.id, option, x):
        if any(k in explicit and set(alternative.get(k, [])) != set(explicit[k]) for k in keys):
            continue
        choice = dict(preferred)
        for key in keys:
            if key not in explicit and (alternative.get(key) or key in preferred):
                choice[key] = alternative.get(key, [])
        value = sum(loss(key, cid) for key in keys for cid in choice.get(key, []))
        if value < best_loss and payable(choice):
            best, best_loss = choice, value
            if best_loss <= floor:
                return {**action, 'cost_choice': best}
    return ({**action, 'cost_choice': best} if best is not None
            else {**action, '_invalid_ai_choice': True})


def complete_cast_hybrid_choices(agent, state, action, player_id):
    """Make the selected cast's first payable native branch explicit, on copies."""
    if (action.get('type') != 'cast_spell' or action.get('_invalid_ai_choice')
            or action.get('hybrid_choices') is not None):
        return action
    choice = (action.get('cost_choice') or {}).get('id')
    if not choice:
        return action  # Cost selection belongs to the caller, not this completion.
    options = action.get('cost_options')
    if options is None:
        from dataclasses import asdict
        from rules_engine.costs import collect_cost_options, casting_method
        source = state.cards.get(action.get('card_id'))
        if source is None:
            return action
        card = select_cast_face(source, action.get('selected_face_index',
                                (action.get('targets') or {}).get('selected_face_index')))
        if casting_method(choice) == 'bestow':
            from rules_engine.bestow import bestow_cast_view
            card = bestow_cast_view(card)
        free = _materialization_without_mana(state, player_id, action['card_id'])
        options = [asdict(option) for option in collect_cost_options(
            state, player_id, card, without_mana=free, action_targets=action.get('targets') or {})]
    option = next((option for option in options if option['id'] == choice), None)
    from rules_engine.mana import hybrid_payment_symbols, _payment_requirements
    symbols = hybrid_payment_symbols(option['mana_cost']) if option is not None else []
    if not symbols:
        return action
    # Bound enumeration before native expansion; never use a truncated branch set.
    branch_count = 1
    for symbol in symbols:
        branch_count *= len(symbol['choices'])
        if branch_count > 64:
            return {**action, '_invalid_ai_choice': True}
    branches = []
    _payment_requirements(option['mana_cost'], False, 0, 0, 0, branch_output=branches)
    from ai.action_contract import complete_action
    from ai.pending_effects import simulation_checked_action
    for selected in branches:
        candidate = {**action, 'hybrid_choices': selected}
        try:
            simulation_checked_action(state, agent.engine, player_id, complete_action(candidate))
        except ActionRejected:
            continue
        return candidate
    return {**action, '_invalid_ai_choice': True}


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
    automatic = (state.pending_mechanic_choice is None
                 and _materialization_without_mana(state, player_id, card.id))

    def trial(candidate):
        projected = planning_copy(state)
        if automatic:
            from rules_engine.effect_casts import admit_cast
            admit_cast(projected, player_id, candidate, {'target_card_id': card.id})
        else:
            validate_action(projected, agent.engine, player_id, candidate)
            agent.engine.take_action(projected, player_id, candidate, reject_invalid=True)
        return projected

    with rule_query_scope(state):
        cache = query_cache(state)
        key = ('ai_cast_resources', agent, player_id, agent.archetype, automatic, json.dumps(action, sort_keys=True))
        if key in cache:
            return {**action, **deepcopy(cache[key])}
        best, score = action, float('-inf')
        for choice in _choices(agent, state, card, action, player_id):
            candidate = dict(action)
            if choice is not None:
                candidate['resource_payment'] = choice
            try:
                projected = trial(candidate)
                if choice is None:
                    # Preserve the native fallback, but publish its actual payment.
                    old_stack_ids = {item.id for item in state.stack}
                    payment = next((item.payload.get('__casting_resource_payment')
                                    for item in projected.stack
                                    if item.id not in old_stack_ids
                                    and item.source_card_id == card.id
                                    and item.controller == player_id
                                    and item.payload.get('__casting_resource_payment') is not None), None)
                    if payment is None:
                        payment = next((frame['data']['payment_details'].get('resource_payment')
                                        for frame in (projected.mana_continuation or {}).get('frames', [])
                                        if frame.get('tag') == 'owner' and frame.get('op') == 'cast'
                                        and frame.get('payer') == player_id
                                        and frame['data']['source']['card_id'] == card.id), None)
                    if payment is None:
                        continue
                    candidate['resource_payment'] = deepcopy(payment)
                    # Score the explicit proposal, never an unservable default.
                    projected = trial(candidate)
            except ActionRejected:
                continue
            value = _score(agent, state, projected, player_id)
            if value > score:
                best, score = candidate, value
        if 'resource_payment' not in best:
            return {**best, '_invalid_ai_choice': True}
        cache[key] = {'resource_payment': deepcopy(best['resource_payment'])}
        return best
