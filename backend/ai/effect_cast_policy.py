"""Choose graveyard permission targets from legal public casting opportunities."""
def usable_cast(state, controller, target):
    from ai.pending_effects import planning_copy
    from rules_engine.effect_casts import materialize_cast, admit_cast
    from rules_engine.targeting import stack_object_kind
    projected = planning_copy(state)
    projected.pending_trigger_order = None
    projected.pending_mechanic_choice = None
    try:
        action = materialize_cast(projected, controller, target)
        admit_cast(projected, controller, action, {'target_card_id': target})
    except (ValueError, KeyError):
        return None
    item = next(item for item in reversed(projected.stack) if item.source_card_id == target
                and stack_object_kind(projected, item) == 'spell')
    surveil_payoff = any(trigger['controller'] == controller and trigger['effect_key'] == 'surveil'
                        for trigger in projected.staged_triggers)
    if item.effect_key == 'look_top_select_hand' and not item.payload.get('mana_spent_to_cast') and not surveil_payoff:
        return None
    return action


def preferred_graveyard_spell(state, controller, options):
    from ai.agent import AIAgent
    agent = AIAgent(difficulty='strong')
    ranked = []
    for option in options:
        target = option['target_card_id']
        action = usable_cast(state, controller, target)
        if action is None:
            continue
        score = agent._cast_bias(state, action, controller)
        ranked.append((score, target, option))
    # The ability still requires a target even if no subsequent cast is useful.
    return max(ranked, key=lambda row: row[:2])[2] if ranked else options[0]
