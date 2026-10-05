"""Conservative fixed-Suspend decisions; admission and resolution belong to rules."""
from copy import deepcopy

from ai.action_contract import complete_action
from ai.information import decision_view
from ai.pending_effects import planning_copy, settled_public_position
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import collect_cost_options
from rules_engine.mana import can_pay_with_pool_and_lands, mana_value
from rules_engine.suspend import instruction


def optional_cast(agent, state, moves, player_id):
    """Return a complete admitted cast or an admitted decline, never a display move."""
    state, moves = decision_view(state, player_id, moves)
    pending = state.pending_mechanic_choice or {}
    if pending.get('kind') != 'suspend_cast' or pending.get('player_id') != player_id:
        return None
    decline = complete_action({'type': 'choose_mechanic', 'card_ids': ['decline']})
    baseline = checked_action(state, agent.engine, player_id, decline)
    baseline = settled_public_position(baseline, player_id, opaque_draw_counts=True)
    if baseline is None:
        return decline
    best_score = agent._strategic_position_score(baseline, player_id)
    best = decline
    for move in moves:
        if move.get('type') != 'cast_spell':
            continue
        for option in move.get('cost_options', []):
            offered = deepcopy(move)
            offered['cost_options'] = [deepcopy(option)]
            offered['cost_choice'] = {'id': option['id']}
            hints = option.get('target_hints', move.get('target_hints', {})) or {}
            if hints.get('x_value_max') == 0:
                offered['targets'] = {**offered.get('targets', {}), 'x_value': 0}
            try:
                # Materialization can query caches: give it its own planning copy.
                action = complete_action(agent._materialize_action(
                    planning_copy(state), offered, player_id, allow_zero_x=True))
            except (ActionRejected, ValueError, KeyError):
                continue
            variants = [action]
            # Enumerate offered single targets; admission rejects incompatible forms.
            # Multi-target/mode/distribution choices retain existing materialization.
            targets = action.get('targets', {})
            if not any(key in targets for key in ('mode_text', 'mode_texts', 'mode_targets',
                                                  'target_card_ids', 'target_distribution', 'target_stack_id')):
                for key, rows in [('target_player', hints.get('player_targets', [])),
                                  ('target_card_id', hints.get('creature_targets', [])
                                   + hints.get('permanent_targets', [])
                                   + hints.get('planeswalker_targets', []))]:
                    for row in rows:
                        retained = {key: value for key, value in targets.items()
                                    if key not in {'target_player', 'target_card_id', 'target_card_name'}}
                        variants.append({**action, 'targets': {**retained, key: row['id']}})
            for action in variants:
                try:
                    action = complete_action(action)
                    projected = checked_action(state, agent.engine, player_id, action)
                    projected = settled_public_position(projected, player_id, opaque_draw_counts=True)
                except (ActionRejected, ValueError, KeyError):
                    continue
                if projected is None or projected.winner == 3 - player_id:
                    continue
                score = (float('inf') if projected.winner == player_id
                         else agent._strategic_position_score(projected, player_id))
                if score > best_score + 0.05:
                    best, best_score = action, score
    return best


def idle_suspend(agent, state, moves, player_id):
    """Spend otherwise idle mana, not a selected deployment or reserved answer."""
    state, moves = decision_view(state, player_id, moves)
    if (state.stack or state.pending_mechanic_choice or state.active_player != player_id
            or state.step not in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}):
        return None
    from rules_engine.graveyard_permissions import zone_cast_prohibited
    if zone_cast_prohibited(state, player_id, Zone.EXILE):
        return None
    from rules_engine.continuous import effective_power
    from rules_engine.type_effects import effective_types
    pressure = sum(max(0, effective_power(state, cid) or 0)
                   for cid in state.players[3 - player_id].battlefield
                   if 'Creature' in effective_types(state, state.cards[cid]))
    # Conservative pressure guard, not a lethal-combat proof (blockers may exist).
    if pressure >= state.players[player_id].life:
        return None
    answers = []
    for cid in state.players[player_id].hand:
        card = state.cards[cid]
        if {'counter', 'removal'} & agent._spell_tags(card):
            for option in collect_cost_options(state, player_id, card):
                if can_pay_with_pool_and_lands(state, player_id, option.mana_cost,
                                              spell_types=card.types, source_card_id=cid):
                    answers.append((cid, option.mana_cost, card.types))
    candidates = []
    for move in moves:
        if move.get('type') != 'suspend':
            continue
        cid = move['card_id']
        card = state.cards[cid]
        printed = instruction(card)
        if not printed:
            continue
        delay, cost = printed
        # Bounded policy: long delays are early-game investments, not late answers.
        if state.turn + delay > 9 or state.players[player_id].life <= 5:
            continue
        if any(answer[0] == cid for answer in answers):
            continue
        if any(m.get('type') == 'cast_spell' and m.get('card_id') == cid for m in moves):
            continue
        value = agent._hand_retention_value(state, cid, player_id)
        saving = mana_value(card.mana_cost) - mana_value(cost)
        if value <= 0 or (card.mana_cost and saving <= 0):
            continue
        try:
            action = complete_action(move)
            projected = checked_action(state, agent.engine, player_id, action)
        except (ActionRejected, ValueError):
            continue
        if any(not can_pay_with_pool_and_lands(projected, player_id, price,
                                              spell_types=types, source_card_id=source)
               for source, price, types in answers):
            continue
        candidates.append(((value + max(0, saving)) / (delay + 1), cid, action))
    return max(candidates, key=lambda row: row[:2])[2] if candidates else None
