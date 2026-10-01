"""Bounded public dependencies for simultaneous token/team-buff triggers."""


def preferred_trigger_order(group, controller):
    """Return bottom-to-top stack order; leave unknown/mixed groups untouched.

    Snapshot team buffs affect only creatures present when they resolve. For
    an entirely friendly token/buff group, create the relevant bodies first.
    This is a dependency rule, not a general trigger search or card-name policy.
    """
    creators, buffs = [], []
    for trigger in group:
        payload = trigger.get('payload') or {}
        if trigger.get('effect_key') == 'create_token':
            if (int(payload.get('controller', controller)) != controller
                    or 'Creature' not in payload.get('types', ['Creature', 'Token'])
                    or int(payload.get('amount', 1)) <= 0 or int(payload.get('toughness', 1)) <= 0):
                return list(group)
            creators.append(trigger)
        elif trigger.get('effect_key') == 'temporary_pt_buff_all':
            if (not payload.get('controller_only') or int(payload.get('power', 0)) < 0
                    or int(payload.get('toughness', 0)) < 0):
                return list(group)
            buffs.append(trigger)
        else:
            return list(group)
    if not creators or not buffs:
        return list(group)
    for buff in buffs:
        required = {value.lower() for value in buff['payload'].get('creature_subtypes', [])}
        for creator in creators:
            line = creator['payload'].get('type_line', '').replace('\u2014', '-')
            subtypes = set(line.partition('-')[2].lower().split())
            if required and not required.intersection(subtypes):
                return list(group)
    return buffs + creators
