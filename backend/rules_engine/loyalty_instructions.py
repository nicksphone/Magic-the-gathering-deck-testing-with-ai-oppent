"""Closed loyalty instruction nodes and their ordinary resumable executors."""
import re
from copy import copy, deepcopy

COUNT = r'(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)'
LAND = r'(?:Plains|Island|Swamp|Mountain|Forest)'


def number(text):
    from rules_engine.oracle_effects import _parse_count_token
    return _parse_count_token(text.lower())


def source_matches(source, name):
    return source.casefold() in {name.casefold(), name.split(',', 1)[0].casefold(),
                                'this planeswalker', 'this permanent'}


def node(operation, **data):
    return {'effect_key': 'loyalty_' + operation, 'data': data}


def emblem_body(text):
    from rules_engine.continuous import _attached_keywords
    static = re.fullmatch(r'(Creatures|Lands) you control (?:get ([+-]\d+)/([+-]\d+) and )?have (.+)\.', text, re.I)
    if static and _attached_keywords(static[4]):
        return {'kind': 'static', 'text': text}
    trigger = re.fullmatch(r'Whenever you draw a card, exile target permanent an opponent controls\.', text, re.I)
    if trigger:
        return {'kind': 'draw_exile', 'text': text}
    return None


def companion(line):
    if re.fullmatch(r'Each opponent can cast spells only any time they could cast a sorcery\.', line, re.I):
        return 'opponent_sorcery_only'
    if re.fullmatch(r'Whenever you tap a ' + LAND + r' for mana, add an additional \{[WUBRG]\}\.', line, re.I):
        return 'land_mana_addition'
    if re.fullmatch(r'Compleated \((\{[WUBRG]/P\}) can be paid with \{[WUBRG]\} or 2 life\. '
                    r'For each \1 paid with life, this planeswalker enters with two fewer loyalty counters\.\)', line, re.I):
        symbol = re.search(r'\{([WUBRG])/P\}', line, re.I)[1]
        if re.search(r'can be paid with \{'+symbol+r'\}', line, re.I):
            return 'compleated_entry'
    return None


def compile_extended(text, name):
    """Full-match parameterized grammars; never accept a recognized prefix."""
    from rules_engine.continuous import _attached_keywords
    if any(c in text for c in '()\n;'):
        return None
    combo = re.fullmatch(r'You gain (\d+) life, draw ('+COUNT+r') cards?, then put up to ('+COUNT+r') permanent cards from your hand onto the battlefield\.', text, re.I)
    if combo:
        return [node('gain', amount=int(combo[1])), node('draw', amount=number(combo[2])),
                node('hand_entry', count=number(combo[3]))]
    emblem = re.fullmatch(r'You get an emblem with "([^\"]+)"(?:\.?\s+(.+))?', text, re.I)
    if emblem:
        compiled = emblem_body(emblem[1])
        if compiled is None:
            return None
        out = [node('emblem', **compiled)]
        if emblem[2]:
            tail = compile_extended(emblem[2], name)
            if tail is None:
                return None
            out.extend(tail)
        return out
    search = re.fullmatch(r'Search your library for any number of ('+LAND+r') cards, put them onto the battlefield tapped, then shuffle\.', text, re.I)
    if search:
        return [node('search', subtype=search[1])]
    token = re.fullmatch(r'Create (?:an?|one) X/X (white|blue|black|red|green|colorless) ([a-z]+(?: [a-z]+)*) creature token, where X is (.+?)\x27s loyalty\.', text, re.I)
    if token and source_matches(token[3], name):
        return [node('source_token', color=token[1].lower(), subtype=token[2])]
    group = re.fullmatch(r'Until end of turn, creatures you control get ([+-]\d+)/([+-]\d+) for each ('+LAND+r') you control and gain (.+)\.', text, re.I)
    if group and (keywords := _attached_keywords(group[4])):
        return [node('scaled_buff', power=int(group[1]), toughness=int(group[2]),
                     subtype=group[3], keywords=keywords)]
    animation = re.fullmatch(r'Put ('+COUNT+r') \+1/\+1 counters? on up to one target noncreature land you control\. '
                            r'Untap it\. It becomes a (\d+)/(\d+) ([a-z]+) creature with (.+) that\x27s still a land\.', text, re.I)
    if animation and (keywords := _attached_keywords(animation[5])):
        return [node('counter', amount=number(animation[1])),
                node('animate', power=int(animation[2]), toughness=int(animation[3]),
                     subtype=animation[4], keywords=keywords)]
    delayed = re.fullmatch(r'Draw ('+COUNT+r') cards?\. At the beginning of the next end step, untap up to ('+COUNT+r') lands\.', text, re.I)
    if delayed:
        return [node('draw', amount=number(delayed[1])), node('delay_untap', count=number(delayed[2]))]
    library = re.fullmatch(r'Put target nonland permanent into its owner\x27s library (first|second|third|fourth|fifth|\d+(?:st|nd|rd|th)) from the top\.', text, re.I)
    if library:
        ordinals = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5}
        return [node('library', position=ordinals.get(library[1].lower()) or int(re.match(r'\d+', library[1])[0]))]
    if re.fullmatch(r'Until your next turn, you may cast sorcery spells as though they had flash\.', text, re.I):
        return [node('flash')]
    bounce = re.fullmatch(r'Return up to one target artifact, creature, or enchantment to its owner\x27s hand\. Draw ('+COUNT+r') cards?\.', text, re.I)
    if bounce:
        return [node('bounce'), node('draw', amount=number(bounce[1]))]
    threshold = re.fullmatch(r'Destroy all creatures with power (\d+) or greater\.', text, re.I)
    if threshold:
        return [node('destroy_threshold', minimum=int(threshold[1]))]
    return None


def announcement_text(text, name):
    """Future emblem trigger targets are not targets of creating the emblem."""
    from rules_engine.closed_loyalty import compile_instruction
    steps = compile_instruction(text, name)
    targetless = {'loyalty_emblem', 'loyalty_search', 'loyalty_gain', 'loyalty_draw',
                  'loyalty_hand_entry', 'loyalty_delay_untap', 'loyalty_flash',
                  'loyalty_source_token', 'loyalty_scaled_buff', 'loyalty_destroy_threshold'}
    if steps and all(step['effect_key'] in targetless for step in steps):
        return ''
    return text


def companion_text(card):
    """Only printed companions are active before a loyalty program resolves."""
    from rules_engine.closed_loyalty import compile_body
    compiled = compile_body(card.oracle_text, card.name)
    return '\n'.join(compiled['companions']) if compiled is not None else card.oracle_text


def compile_proxy(state, card, controller, targets):
    from rules_engine.closed_loyalty import compile_instruction
    steps = compile_instruction(card.oracle_text, card.name)
    if steps is None or not any(s['effect_key'].startswith('loyalty_') for s in steps):
        return None
    from rules_engine.oracle_effects import infer_effect_from_oracle
    from game_state.state import object_incarnation
    source = state.cards.get(card.id)
    reference = {'id': card.id, 'incarnation': object_incarnation(source),
                 'sequence': source.zone_change_sequence} if source else None
    effects = []
    for step in steps:
        key = step['effect_key']
        if key.startswith('loyalty_'):
            payload = {**step['data'], 'source_reference': reference}
            if targets.get('target_card_id'):
                payload['target_card_id'] = targets['target_card_id']
        else:
            proxy = copy(card)
            proxy.loyalty_program = False
            proxy.oracle_text = step['instruction'] + '.'
            key, payload = infer_effect_from_oracle(state, proxy, controller, targets)
        effects.append({'effect_key': key, 'payload': payload})
    return 'effect_sequence', {'effects': effects}


def resolve(state, controller, payload):
    from effects import handlers
    from effects.registry import resolve_effect
    from game_state.state import CardInstance, Zone, allocate_effect_timestamp, object_incarnation
    from rules_engine.type_effects import effective_types, add_type_effect
    from rules_engine.events import emit_event, emit_event_batch
    kind = payload['loyalty_operation']
    target = state.cards.get(payload.get('target_card_id'))
    if kind in {'gain', 'draw'}:
        resolve_effect(state, controller, 'gain_life' if kind == 'gain' else 'draw_cards', payload)
    elif kind == 'emblem':
        cid = state.allocate_object_id()
        card = CardInstance(id=cid, name='Emblem', owner=controller, controller=controller,
                            zone=Zone.COMMAND, types=['Emblem'], type_line='Emblem',
                            oracle_text=payload['text'], effect_timestamp=allocate_effect_timestamp(state))
        state.cards[cid] = card
        state.emblems.append(cid)
        from game_state.observations import observe_cards
        observe_cards(state, [cid])
    elif kind == 'source_token':
        ref = payload['source_reference']
        source = state.cards.get(ref['id'])
        if source and source.zone == Zone.BATTLEFIELD and object_incarnation(source) == ref['incarnation'] and source.zone_change_sequence == ref['sequence']:
            value = int(source.loyalty or 0)
        else:
            value = int(payload.get('__source_lki', {}).get('loyalty', 0))
        colors = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}
        handlers.create_token(state, controller, {**payload, 'power': value, 'toughness': value,
            'amount': 1, 'name': payload['subtype'].title(),
            'type_line': 'Token Creature - ' + payload['subtype'].title(),
            'colors': [colors[payload['color']]] if payload['color'] in colors else [],
            'keywords': []})
    elif kind == 'scaled_buff':
        from rules_engine.land_types import has_land_type
        count = sum(has_land_type(state, state.cards[cid], payload['subtype']) for cid in state.players[controller].battlefield)
        from rules_engine.keyword_effects import add_keyword_effect
        for cid in list(state.players[controller].battlefield):
            if 'Creature' in effective_types(state, state.cards[cid]):
                handlers.temporary_pt_buff(state, controller, {'target_card_id': cid,
                    'power': payload['power'] * count, 'toughness': payload['toughness'] * count})
                add_keyword_effect(state, cid, payload['keywords'], until_end_of_turn=True)
    elif kind == 'counter':
        if target is not None:
            handlers.add_counters(state, controller, {**payload, 'counter': '+1/+1'})
    elif kind == 'animate':
        if target is not None and target.zone == Zone.BATTLEFIELD and 'Land' in effective_types(state, target):
            stamp = allocate_effect_timestamp(state)
            add_type_effect(state, target.id, ['Creature', payload['subtype'].title()], timestamp=stamp)
            handlers.set_base_stats(state, controller, {'target_card_id': target.id,
                'base_power': payload['power'], 'base_toughness': payload['toughness'],
                'until_end_of_turn': False, 'resolution_timestamp': stamp})
            from rules_engine.keyword_effects import add_keyword_effect
            from rules_engine.named_counters import untap_permanent
            add_keyword_effect(state, target.id, payload['keywords'], timestamp=stamp)
            untap_permanent(state, target.id)
    elif kind == 'delay_untap':
        state.delayed_triggers.append({'step': 'end_step', 'earliest_turn': state.turn,
            'source_card_id': payload['source_reference']['id'], 'controller': controller,
            'label': 'Delayed land untap', 'effect_key': 'loyalty_choose_untap',
            'payload': {'count': payload['count']}})
    elif kind in {'choose_untap', 'hand_entry'}:
        choose_cards(state, controller, payload, kind)
    elif kind == 'flash':
        state.loyalty_permissions.append({'controller': controller, 'created_turn': state.turn})
    elif kind == 'library':
        if target is not None and target.zone == Zone.BATTLEFIELD:
            emit_event(state, 'leaves_battlefield', {'card_id': target.id, 'controller': target.controller})
            state.players[target.controller].battlefield.remove(target.id)
            target.move_to_zone(Zone.LIBRARY)
            target.controller = target.owner
            library = state.players[target.owner].library
            library.insert(max(0, len(library) - payload['position'] + 1), target.id)
    elif kind == 'bounce':
        if target is not None:
            handlers.return_permanent_to_hand(state, controller, payload)
    elif kind == 'search':
        handlers.search_library(state, controller, {**payload, 'contains': payload['subtype'].lower(),
            'destination': 'battlefield', 'tapped': True, 'shuffle': True, 'count': 0, 'up_to': True})
    elif kind == 'destroy_threshold':
        from rules_engine.continuous import effective_power
        targets = [cid for player in state.players.values() for cid in player.battlefield
                   if 'Creature' in effective_types(state, state.cards[cid])
                   and (effective_power(state, cid) or 0) >= payload['minimum']]
        handlers._destroy_all_permanents_of_types(state, {'Creature'}, 'Threshold creatures destroyed.', target_ids=targets)


def card_reference(state, cid):
    from game_state.state import object_incarnation
    card = state.cards[cid]
    return {'incarnation': object_incarnation(card), 'sequence': card.zone_change_sequence,
            'zone': card.zone.value}


def reference_matches(state, cid, reference):
    return cid in state.cards and reference == card_reference(state, cid)


def aura_entry_options(state, card, controller):
    from rules_engine.attachments import attachment_target_is_legal
    view = copy(card)
    view.controller = controller
    candidates = [cid for p in state.players.values() for cid in p.battlefield]
    candidates += ['player:' + str(pid) for pid in state.players]
    return [cid for cid in candidates if attachment_target_is_legal(state, view, cid)]


def choice_view(pending, *, actor=False, state=None):
    keys = ['kind', 'player_id', 'label', 'count', 'min_count']
    if actor or pending['kind'] != 'loyalty_cards':
        keys += ['options', 'option_labels']
    view = {key: deepcopy(pending[key]) for key in keys if key in pending}
    if actor and state is not None:
        view['option_labels'] = {cid: state.cards[cid].name if cid in state.cards
            else (pending.get('option_labels') or {}).get(cid, cid) for cid in view.get('options', [])}
    return view


def choose_cards(state, controller, payload, kind):
    from game_state.state import Zone
    from rules_engine.type_effects import effective_types
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    from rules_engine.graveyard_permissions import battlefield_entry_prohibited
    from rules_engine.attachments import is_aura, attach_if_legal
    from rules_engine.entry import pause_for_land_entries, apply_entry_choice
    player = state.players[controller]
    if kind == 'choose_untap':
        eligible = [cid for p in state.players.values() for cid in p.battlefield
                    if 'Land' in effective_types(state, state.cards[cid])]
    else:
        eligible = [cid for cid in player.hand if state.cards[cid].zone == Zone.HAND
                    and set(effective_types(state, state.cards[cid])) &
                    {'Creature', 'Land', 'Artifact', 'Enchantment', 'Planeswalker', 'Battle'}
                    and (not is_aura(state.cards[cid], state)
                         or aura_entry_options(state, state.cards[cid], controller))]
    if 'selected_card_ids' not in payload and controller in state.mechanic_choice_players and eligible:
        state.pending_mechanic_choice = {'kind': 'loyalty_cards', 'player_id': controller,
            'options': eligible, 'count': min(payload['count'], len(eligible)), 'min_count': 0,
            'label': 'Choose up to the permitted number of cards', 'effect_payload': deepcopy(payload),
            'loyalty_operation': kind,
            'option_references': {cid: card_reference(state, cid) for cid in eligible}}
        state.priority_player = controller
        state.passed_priority = set()
        return
    chosen = payload.get('selected_card_ids', eligible[:payload['count']])
    if len(set(chosen)) != len(chosen) or len(chosen) > payload['count']:
        raise ValueError('Invalid loyalty selection')
    references = payload.get('__loyalty_selected_references')
    if references is None:
        if any(cid not in eligible for cid in chosen):
            raise ValueError('Invalid loyalty selection')
        references = {cid: card_reference(state, cid) for cid in chosen}
    chosen = [cid for cid in chosen if cid in eligible and reference_matches(state, cid, references.get(cid))]
    if kind == 'choose_untap':
        from rules_engine.named_counters import untap_permanent
        for cid in chosen:
            untap_permanent(state, cid)
        return
    chosen = [cid for cid in chosen if not battlefield_entry_prohibited(state, cid)]
    payload = {**payload, 'selected_card_ids': chosen, '__loyalty_selected_references': references}
    attachments = deepcopy(payload.get('__loyalty_attachments') or {})
    for cid in chosen:
        card = state.cards[cid]
        if not is_aura(card, state):
            continue
        targets = aura_entry_options(state, card, controller)
        selected = attachments.get(cid)
        if selected is not None:
            target = selected['id']
            if (target not in targets or (not target.startswith('player:')
                    and not reference_matches(state, target, selected['reference']))):
                chosen = [other for other in chosen if other != cid]
            continue
        if controller in state.mechanic_choice_players:
            state.pending_mechanic_choice = {'kind': 'loyalty_attachment', 'player_id': controller,
                'label': 'Choose a legal attachment for the entering Aura', 'options': targets,
                'entry_card_id': cid, 'effect_payload': {**payload, '__loyalty_attachments': attachments},
                'option_references': {target: card_reference(state, target) for target in targets
                                      if not target.startswith('player:')}}
            state.priority_player = controller
            state.passed_priority = set()
            return
        target = targets[0]
        attachments[cid] = {'id': target, 'reference': None if target.startswith('player:') else card_reference(state, target)}
    payload = {**payload, 'selected_card_ids': chosen, '__loyalty_attachments': attachments}
    if pause_for_land_entries(state, controller, chosen, 'loyalty_hand_entry', payload):
        return
    if chosen and prepare_counter_entries(state, controller, [state.cards[cid] for cid in chosen],
                                         'loyalty_hand_entry', {**payload, 'selected_card_ids': chosen}):
        return
    events = []
    from game_state.state import assign_static_order_on_battlefield_entry
    for cid in chosen:
        card = state.cards[cid]
        player.hand.remove(cid)
        player.battlefield.append(cid)
        card.move_to_zone(Zone.BATTLEFIELD)
        card.controller = controller
        apply_entry_choice(state, controller, card,
                           choice=(payload.get('__entry_choices') or {}).get(cid, 'tapped'))
        card.entered_turn = state.turn
        card.summoning_sick = True
        assign_static_order_on_battlefield_entry(state, cid)
        commit_entry_counters(state, card, payload)
        if cid in attachments:
            target = attachments[cid]['id']
            if target.startswith('player:'):
                card.attached_to = target
            elif not attach_if_legal(state, cid, target):
                raise ValueError('Previously qualified Aura attachment became unavailable')
        events.append({'card_id': cid, 'controller': controller})
    from rules_engine.events import emit_event_batch
    emit_event_batch(state, 'enters_battlefield', events)


def finish_choice(state, controller, action):
    pending = state.pending_mechanic_choice
    if action.get('type') != 'choose_mechanic' or pending['player_id'] != controller:
        return False
    if pending['kind'] == 'loyalty_attachment':
        cid = pending['entry_card_id']
        payload = pending['effect_payload']
        target = action.get('choice_id')
        if (not reference_matches(state, cid, payload['__loyalty_selected_references'].get(cid))
                or cid not in state.players[controller].hand or target not in pending['options']
                or target not in aura_entry_options(state, state.cards[cid], controller)
                or (not target.startswith('player:') and not reference_matches(state, target,
                    pending['option_references'].get(target)))):
            return False
        attachments = {**payload.get('__loyalty_attachments', {}), cid: {'id': target,
            'reference': None if target.startswith('player:') else card_reference(state, target)}}
        state.pending_mechanic_choice = None
        from effects.registry import resolve_effect
        resolve_effect(state, controller, 'loyalty_hand_entry', {**payload, '__loyalty_attachments': attachments})
        from rules_engine.stack_engine import resume_paused_resolution
        resume_paused_resolution(state, pending)
        return True
    ids = action.get('card_ids')
    if (action.get('type') != 'choose_mechanic' or pending['player_id'] != controller
            or not isinstance(ids, list) or any(not isinstance(cid, str) for cid in ids)
            or len(set(ids)) != len(ids) or len(ids) > pending['count']
            or any(cid not in pending['options'] or not reference_matches(state, cid,
                (pending.get('option_references') or {}).get(cid)) for cid in ids)
            or (pending['loyalty_operation'] == 'hand_entry'
                and any(cid not in state.players[controller].hand for cid in ids))):
        return False
    state.pending_mechanic_choice = None
    from effects.registry import resolve_effect
    resolve_effect(state, controller, 'loyalty_' + pending['loyalty_operation'],
                   {**pending['effect_payload'], 'selected_card_ids': ids,
                    '__loyalty_selected_references': {cid: pending['option_references'][cid] for cid in ids}})
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True


def land_choice_valid(state, controller, action, pending):
    from rules_engine.entry import land_entry_options
    cid = pending['entry_card_id']
    payload = pending['effect_payload']
    return (pending['player_id'] == controller and cid in state.players[controller].hand
            and reference_matches(state, cid, payload['__loyalty_selected_references'].get(cid))
            and action.get('choice_id') in land_entry_options(state, controller, state.cards[cid]))


def collect_emblem_triggers(state, event, payload):
    if event != 'draw_card':
        return []
    out = []
    for cid in state.emblems:
        card = state.cards[cid]
        parsed = emblem_body(card.oracle_text)
        if parsed and parsed['kind'] == 'draw_exile' and payload.get('player_id') == card.controller:
            out.append({'source_card_id': cid, 'controller': card.controller,
                'label': 'Emblem draw trigger', 'effect_key': 'exile',
                'payload': {'__trigger_full_clause': card.oracle_text,
                            '__trigger_resolution_text': 'Exile target permanent an opponent controls.'}})
    return out


def begin_turn(state):
    state.loyalty_permissions = [p for p in state.loyalty_permissions
        if p['controller'] != state.active_player or p['created_turn'] == state.turn]


def timing(state, card, player):
    from game_state.state import Step, Zone
    from rules_engine.type_effects import effective_types
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.closed_loyalty import compile_body
    normal = state.active_player == player and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and not state.stack
    for p in state.players.values():
        for cid in p.battlefield:
            source = state.cards[cid]
            compiled = compile_body(source.oracle_text, source.name)
            if (source.controller != player and source.zone == Zone.BATTLEFIELD
                    and not printed_abilities_suppressed(state, cid) and compiled
                    and any(companion(line) == 'opponent_sorcery_only' for line in compiled['companions'])
                    and not normal):
                return False, False
    flash = 'Sorcery' in effective_types(state, card) and any(p['controller'] == player for p in state.loyalty_permissions)
    return True, flash
