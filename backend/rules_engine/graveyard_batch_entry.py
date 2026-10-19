"""One retained, owner-controlled all-graveyard entry operation."""
from copy import deepcopy
import re

from game_state.state import Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.type_effects import effective_types


KEY = 'return_graveyard_permanents_batch'
CLAUSE = 'graveyard_batch_clause'
PLAN = '__graveyard_batch_plan'
ATTACHMENTS = '__graveyard_batch_attachments'
BODY = re.compile(r"Return all artifact and enchantment cards from all graveyards "
                  r"to the battlefield under their owners['\u2019] control\.?", re.I)


def compile_instruction(text):
    if not isinstance(text, str):
        return None
    raw = text.strip()
    reminder = '(Auras with nothing to enchant remain in graveyards.)'
    if BODY.fullmatch(raw.removesuffix(reminder).rstrip()):
        return KEY, {CLAUSE: raw}
    # Broad stripping identifies malformed candidates only; it never admits one
    # or lets an unknown tail fall through to the general reward parser.
    from rules_engine.oracle_text import without_reminder_text
    if BODY.match(' '.join(without_reminder_text(raw).split())):
        raise ActionRejected('Unsupported complete graveyard batch instruction')
    return None


def _leaves(payload):
    pending = list(payload.get('effects', [])) if isinstance(payload, dict) else []
    while pending:
        item = pending.pop()
        if not isinstance(item, dict):
            continue
        if item.get('effect_key') == 'effect_sequence':
            pending.extend(item.get('payload', {}).get('effects', []))
        else:
            yield item


def contains_batch_instruction(payload):
    return any(item.get('effect_key') == KEY for item in _leaves(payload))


def _frame_matches(controller, payload):
    from rules_engine.loyalty_instructions import native_frame_matches
    frame = payload.get('__resolving_item')
    clause = payload.get(CLAUSE)
    if (not native_frame_matches(frame, controller) or compile_instruction(clause) is None
            or frame['source_card_id'] != payload.get('__source_card_id')):
        return False
    if frame['effect_key'] == KEY:
        return frame['payload'].get(CLAUSE) == clause
    return (frame['effect_key'] == 'effect_sequence' and sum(
        item.get('effect_key') == KEY and item.get('payload', {}).get(CLAUSE) == clause
        for item in _leaves(frame['payload'])) == 1)


def _eligible(state, cid):
    from rules_engine.graveyard_permissions import battlefield_entry_prohibited
    from rules_engine.zone_actions import is_departed_token
    card = state.cards.get(cid)
    return (card is not None and card.owner in state.players and card.zone == Zone.GRAVEYARD
        and cid in state.players[card.owner].graveyard and not is_departed_token(card)
        and bool(set(effective_types(state, card)) & {'Artifact', 'Enchantment'})
        and not battlefield_entry_prohibited(state, cid))


def _entry_roster(state):
    from rules_engine.attachments import is_aura
    from rules_engine.loyalty_instructions import aura_entry_options
    entries = []
    for owner in (state.active_player, 3-state.active_player):
        for cid in state.players[owner].graveyard:
            if not _eligible(state, cid):
                continue
            card = state.cards[cid]
            entries.append({'id': cid, 'owner': owner, 'reference': {
                'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence},
                'admitted': not is_aura(card, state) or bool(aura_entry_options(state, card, owner))})
    return entries


def plan_matches(state, controller, payload):
    from rules_engine.attachments import is_aura
    from rules_engine.loyalty_instructions import aura_entry_options, reference_matches
    plan = payload.get(PLAN)
    if (not _frame_matches(controller, payload) or not isinstance(plan, dict)
            or set(plan) != {'controller', 'active_player', 'frame', 'entries'}
            or type(plan['controller']) is not int or plan['controller'] != controller
            or type(plan['active_player']) is not int
            or plan['active_player'] != state.active_player
            or plan['frame'] != payload['__resolving_item'] or not isinstance(plan['entries'], list)):
        return False
    seen = set()
    for row in plan['entries']:
        if (not isinstance(row, dict) or set(row) != {'id', 'owner', 'reference', 'admitted'}
                or not isinstance(row['id'], str) or row['id'] in seen
                or type(row['owner']) is not int or type(row['admitted']) is not bool
                or not _eligible(state, row['id'])):
            return False
        seen.add(row['id'])
        card = state.cards[row['id']]
        reference = row['reference']
        if (not isinstance(reference, dict) or set(reference) != {'incarnation', 'zone_change_sequence'}
                or any(type(value) is not int or value < 0 for value in reference.values())
                or card.owner != row['owner'] or reference != {
                'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}):
            return False
    if plan['entries'] != _entry_roster(state):
        return False
    attachments = payload.get(ATTACHMENTS, {})
    if not isinstance(attachments, dict):
        return False
    aura_ids = {row['id'] for row in plan['entries'] if row['admitted'] and is_aura(state.cards[row['id']], state)}
    if not set(attachments) <= aura_ids:
        return False
    for cid, choice in attachments.items():
        if (not isinstance(choice, dict) or set(choice) != {'id', 'reference'}
                or choice['id'] not in aura_entry_options(state, state.cards[cid], state.cards[cid].owner)):
            return False
        if choice['id'].startswith('player:'):
            if choice['reference'] is not None:
                return False
        elif not reference_matches(state, choice['id'], choice['reference']):
            return False
    return True


def _retain(state, controller, payload):
    if not _frame_matches(controller, payload):
        raise ActionRejected('Graveyard batch requires its genuine resolving frame and clause')
    return {**payload, PLAN: {'controller': controller, 'active_player': state.active_player,
        'frame': deepcopy(payload['__resolving_item']), 'entries': _entry_roster(state)}}


def _pause(state, owner, pending):
    state.pending_mechanic_choice = {**pending, 'player_id': owner, 'graveyard_batch': True}
    state.priority_player = owner
    state.passed_priority = set()


def _entry_seeds(state, cards, *, controllers=None):
    from rules_engine.entry_counters import prospective_entry_ability_view
    from rules_engine.oracle_effects import _parse_count_token
    seeds = {}
    for card in cards:
        counts = {}
        controller = (controllers or {}).get(card.id, card.owner)
        view = prospective_entry_ability_view(state, card, controller)
        text = '' if view['printed_suppressed'] else card.oracle_text
        for amount, kind in re.findall(
                r'^This (?:creature|artifact|enchantment|permanent) enters with '
                r'(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+) '
                r'([+-]\d+/[+-]\d+|[a-z][a-z -]*) counters? on it\.$', text, re.I | re.M):
            counts[kind.lower()] = counts.get(kind.lower(), 0) + _parse_count_token(amount.lower())
        seeds[card.id] = {'counters': counts}
    return seeds


def resolve(state, controller, payload):
    from rules_engine.attachments import attach_if_legal, is_aura
    from rules_engine.entry import apply_entry_choice, pause_for_land_entries
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    from rules_engine.loyalty_instructions import aura_entry_options, card_reference
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    from rules_engine.events import emit_event_batch
    data = dict(payload) if PLAN in payload else _retain(state, controller, payload)
    if not plan_matches(state, controller, data):
        raise ActionRejected('Stale graveyard batch entry plan')
    cards = [state.cards[row['id']] for row in data[PLAN]['entries'] if row['admitted']]
    if not cards:
        return
    from rules_engine.entry_copy import prepare as prepare_copies, projections, commit as commit_copies
    if prepare_copies(state, controller, cards, KEY, data,
                      controllers={card.id: card.owner for card in cards}):
        return
    projected = projections(state, data)
    prepared = deepcopy(data.get('__graveyard_batch_counter_results', {}))
    if (not isinstance(prepared, dict) or not set(prepared) <= {card.id for card in cards}
            or any(not isinstance(counts, dict) or any(type(amount) is not int or amount < 0
                       for amount in counts.values()) for counts in prepared.values())):
        raise ActionRejected('Invalid prepared graveyard batch counters')
    preparing = data.pop('__graveyard_batch_preparing_owner', None)
    if preparing is not None:
        ready = data.pop('__entry_counters_by_id', None)
        recipients = {card.id for card in cards if card.owner == preparing}
        if (type(preparing) is not int or preparing not in state.players
                or not isinstance(ready, dict) or set(ready) != recipients
                or set(ready) & set(prepared)):
            raise ActionRejected('Invalid owner-bound entry-counter completion')
        prepared.update(deepcopy(ready))
    elif '__entry_counters_by_id' in data:
        raise ActionRejected('Entry-counter results lack their retained owner')
    data['__graveyard_batch_counter_results'] = prepared
    # Each owner finishes all kinds of entry choices before the next owner.
    # The shared preparer returns packets only; no owner commits early.
    for owner in (data[PLAN]['active_player'], 3-data[PLAN]['active_player']):
        owned = [card for card in cards if card.owner == owner]
        if all(card.id in prepared for card in owned):
            continue
        for card in owned:
            view = projected.get(card.id, card)
            if is_aura(view, state) and card.id not in data.get(ATTACHMENTS, {}):
                options = aura_entry_options(state, view, owner)
                _pause(state, owner, {'kind': 'loyalty_attachment',
                    'options': options, 'label': 'Choose a legal attachment for the returning Aura',
                    'entry_card_id': card.id, 'effect_key': KEY, 'effect_payload': deepcopy(data),
                    'option_references': {cid: card_reference(state, cid) for cid in options
                                          if not cid.startswith('player:')}})
                return
        controllers = {card.id: owner for card in owned}
        if pause_for_land_entries(state, controller, [card.id for card in owned], KEY, data,
                                  controllers=controllers, projections=projected):
            state.pending_mechanic_choice['graveyard_batch'] = True
            return
        if prepare_counter_entries(state, controller, owned, KEY,
                {**data, '__graveyard_batch_preparing_owner': owner},
                controllers=controllers, projections=projected,
                entry_payloads=_entry_seeds(state, [projected.get(card.id, card) for card in owned])):
            return
    data['__entry_counters_by_id'] = prepared
    if not plan_matches(state, controller, data):
        raise ActionRejected('Graveyard batch changed before commit')
    departures = capture_graveyard_departures(state, [card.id for card in cards])
    commit_copies(state, data, [card.id for card in cards])
    for card in cards:
        apply_entry_choice(state, card.owner, card,
                           choice=data.get('__entry_choices', {}).get(card.id, 'tapped'))
    # Attachment legality belongs to the pre-entry battlefield. All choices
    # are finished; do not recompute it against partially co-entered statics.
    for card in cards:
        choice = data.get(ATTACHMENTS, {}).get(card.id)
        if choice:
            card.controller = card.owner
            if choice['id'].startswith('player:'):
                card.attached_to = choice['id']
            elif not attach_if_legal(state, card.id, choice['id']):
                raise ActionRejected('Retained graveyard Aura attachment became unavailable')
    for card in cards:
        state.players[card.owner].graveyard.remove(card.id)
        card.move_to_zone(Zone.BATTLEFIELD)
        card.controller = card.owner
        card.summoning_sick = True
        card.entered_turn = state.turn
        state.players[card.owner].battlefield.append(card.id)
        assign_static_order_on_battlefield_entry(state, card.id)
    counter_events = []
    for card in cards:
        commit_entry_counters(state, card, data, _event_receipts=counter_events)
        if card.id in data.get(ATTACHMENTS, {}):
            card.counters['__attached_to'] = 0
    emit_graveyard_departures(state, departures)
    emit_event_batch(state, 'saga_lore_added', counter_events)
    emit_event_batch(state, 'enters_battlefield', [
        {'card_id': card.id, 'controller': card.owner} for card in cards])


def finish_choice(state, actor, action):
    from rules_engine.entry import land_entry_options
    from rules_engine.loyalty_instructions import aura_entry_options, card_reference
    from rules_engine.stack_engine import resume_paused_resolution
    pending = state.pending_mechanic_choice
    if not pending or pending.get('graveyard_batch') is not True or pending.get('player_id') != actor:
        return False
    data = pending.get('effect_payload')
    if not isinstance(data, dict):
        return False
    controller = data.get(PLAN, {}).get('controller')
    cid, choice = pending.get('entry_card_id'), action.get('choice_id')
    if (not plan_matches(state, controller, data) or cid not in state.cards
            or state.cards[cid].owner != actor or choice not in pending['options']
            or pending.get('resolving_item') != data.get('__resolving_item')):
        return False
    if pending['kind'] == 'loyalty_attachment':
        from rules_engine.loyalty_instructions import reference_matches
        if (choice not in aura_entry_options(state, state.cards[cid], actor)
                or not choice.startswith('player:') and not reference_matches(
                    state, choice, pending.get('option_references', {}).get(choice))):
            return False
        data = {**data, ATTACHMENTS: {**data.get(ATTACHMENTS, {}), cid: {
            'id': choice, 'reference': None if choice.startswith('player:') else card_reference(state, choice)}}}
    elif pending['kind'] == 'land_entry':
        from rules_engine.entry_copy import projections
        if choice not in land_entry_options(state, actor, projections(state, data).get(cid, state.cards[cid])):
            return False
        data = {**data, '__entry_choices': {**data.get('__entry_choices', {}), cid: choice}}
    else:
        return False
    state.pending_mechanic_choice = None
    resolve(state, controller, data)
    resume_paused_resolution(state, pending)
    return True
