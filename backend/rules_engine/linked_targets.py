"""Complete controller-linked damage announcements and captured recipients."""
import re

from game_state.state import Zone, object_incarnation
from rules_engine.type_effects import effective_types


def linked_damage_instruction(text, name):
    source = rf'(?:{re.escape(name)}|this spell)'
    match = re.fullmatch(
        source + r' deals (\d+) damage to target player or planeswalker and (\d+) damage to '
        r"target creature that player or that planeswalker's controller controls\.\s*"
        r'Landfall\s*[\u2014-]\s*If you had a land enter the battlefield under your control this turn, '
        + source + r' deals (\d+) damage to that player or planeswalker and (\d+) damage to that creature instead\.',
        text.strip(), re.I)
    if match is None or match[1] != match[2] or match[3] != match[4]:
        return None
    return {'ordinary_amount': int(match[1]), 'landfall_amount': int(match[3])}


def _shield_free(state, card, controller, selected):
    from rules_engine.targeting import validate_hexproof_shroud_targets, validate_protection_targets
    return (validate_hexproof_shroud_targets(state, controller, selected, card)[0]
            and validate_protection_targets(state, card, selected)[0])


def linked_target_hints(state, card, controller):
    creatures = [target for target in state.cards.values()
                 if target.zone == Zone.BATTLEFIELD and 'Creature' in effective_types(state, target)
                 and _shield_free(state, card, controller, {'target_card_id': target.id})]
    pairs = []
    for pid, player in state.players.items():
        if _shield_free(state, card, controller, {'target_player': pid}):
            for creature in creatures:
                if creature.controller == pid:
                    pairs.append({'primary_kind': 'player', 'primary_id': pid,
                                  'primary_name': player.name, 'creature_id': creature.id,
                                  'creature_name': creature.name,
                                  'targets': {'target_player': pid, 'target_card_id': creature.id}})
    for walker in state.cards.values():
        if (walker.zone != Zone.BATTLEFIELD or 'Planeswalker' not in effective_types(state, walker)
                or not _shield_free(state, card, controller, {'target_card_id': walker.id})):
            continue
        for creature in creatures:
            if creature.controller == walker.controller:
                pairs.append({'primary_kind': 'planeswalker', 'primary_id': walker.id,
                              'primary_name': walker.name, 'creature_id': creature.id,
                              'creature_name': creature.name,
                              'targets': {'target_card_ids': [walker.id, creature.id]}})
    return {'linked_target_pairs': pairs,
            'creature_targets': [{'id': c.id, 'name': c.name} for c in creatures],
            'player_targets': [{'id': pid, 'name': state.players[pid].name}
                               for pid in state.players if any(p['primary_id'] == pid for p in pairs)],
            'planeswalker_targets': [{'id': pair['primary_id'], 'name': pair['primary_name']}
                                    for pair in pairs if pair['primary_kind'] == 'planeswalker']}


def validate_linked_choice(hints, targets):
    selected = {key: targets[key] for key in ('target_player', 'target_card_id', 'target_card_ids',
                'target_stack_id', 'target_distribution', 'mode_targets') if targets.get(key) is not None}
    if any(pair['targets'] == selected for pair in hints['linked_target_pairs']):
        return True, ''
    return False, 'Announce one player or planeswalker and a creature controlled by that target\'s controller.'


def _reference(state, cid, kind):
    card = state.cards[cid]
    return {'kind': kind, 'id': cid, 'target_card_id': cid,
            '__target_incarnation': object_incarnation(card),
            '__target_zone_sequence': card.zone_change_sequence}


def linked_damage_effect(state, card, targets):
    instruction = linked_damage_instruction(card.oracle_text, card.name)
    if instruction is None:
        return None
    if targets.get('target_player') is not None and targets.get('target_card_id') in state.cards:
        packets = [{'kind': 'player', 'id': targets['target_player']},
                   _reference(state, targets['target_card_id'], 'creature')]
    else:
        ids = targets.get('target_card_ids') or []
        if len(ids) != 2 or any(cid not in state.cards for cid in ids):
            return 'noop', {}
        packets = [_reference(state, ids[0], 'planeswalker'), _reference(state, ids[1], 'creature')]
    return 'linked_landfall_damage', {**instruction, 'target_instances': packets,
                                      '__linked_target_instances': True}


def _same_object(state, packet):
    card = state.cards.get(packet['id'])
    return (card is not None and card.zone == Zone.BATTLEFIELD
            and object_incarnation(card) == packet['__target_incarnation']
            and card.zone_change_sequence == packet['__target_zone_sequence'])


def linked_copy_options(state, copied, index):
    from rules_engine.targeting import stack_source_card
    source = stack_source_card(state, copied)
    if source is None:
        return {'keep': 'Keep the original target'}
    primary, secondary = copied.payload['target_instances']
    old = [primary, secondary][index]
    candidates = {'keep': f"Keep {state.players[old['id']].name if old['kind'] == 'player' else state.cards[old['id']].name}"}
    if index == 0:
        for pid, player in state.players.items():
            if (not (old['kind'] == 'player' and old['id'] == pid)
                    and _shield_free(state, source, copied.controller, {'target_player': pid})):
                candidates[f'target_player:{pid}'] = player.name
        for target in state.cards.values():
            if (target.zone == Zone.BATTLEFIELD and 'Planeswalker' in effective_types(state, target)
                    and not (old['kind'] == 'planeswalker' and old['id'] == target.id and _same_object(state, old))
                    and _shield_free(state, source, copied.controller, {'target_card_id': target.id})):
                candidates[f'target_card_id:{target.id}'] = target.name
    else:
        controller = (primary['id'] if primary['kind'] == 'player' else
                      state.cards[primary['id']].controller if _same_object(state, primary) else None)
        for target in state.cards.values():
            if (target.zone == Zone.BATTLEFIELD and 'Creature' in effective_types(state, target)
                    and target.controller == controller
                    and not (old['id'] == target.id and _same_object(state, old))
                    and _shield_free(state, source, copied.controller, {'target_card_id': target.id})):
                candidates[f'target_card_id:{target.id}'] = target.name
    return candidates


def offer_linked_copy_target_choice(state, copied, index=0):
    for slot in range(index, 2):
        options = linked_copy_options(state, copied, slot)
        if len(options) > 1:
            state.pending_mechanic_choice = {
                'kind': 'copy_target', 'player_id': copied.controller, 'count': 1,
                'stack_id': copied.id, 'linked_target_index': slot,
                'target_slot_number': slot+1, 'options': list(options), 'option_labels': options,
                'label': f'Choose linked target {slot+1} for {copied.label} or keep its target',
            }
            return


def choose_linked_copy_target(state, copied, pending, chosen):
    index = pending['linked_target_index']
    if index not in (0, 1) or chosen not in linked_copy_options(state, copied, index):
        return False
    if chosen != 'keep':
        references = copied.payload.get('__announced_target_references')
        old_paths = ([('target_card_ids', 0), ('target_card_ids', 1)]
                     if 'target_card_ids' in copied.payload.get('__announced_targets', {})
                     else [None, ('target_card_id',)])
        key, value = chosen.split(':', 1)
        copied.payload['target_instances'][index] = (
            {'kind': 'player', 'id': int(value)} if key == 'target_player' else
            _reference(state, value, 'planeswalker' if index == 0 else 'creature'))
        primary, secondary = copied.payload['target_instances']
        announced = copied.payload.setdefault('__announced_targets', {})
        for key in ('target_player', 'target_card_id', 'target_card_ids'):
            announced.pop(key, None)
        announced.update({'target_player': primary['id'], 'target_card_id': secondary['id']}
                         if primary['kind'] == 'player' else
                         {'target_card_ids': [primary['id'], secondary['id']]})
        if references is not None:
            from rules_engine.targeting import replace_announced_target_reference
            new_paths = ([('target_card_ids', 0), ('target_card_ids', 1)]
                         if primary['kind'] != 'player' else [None, ('target_card_id',)])
            copied.payload['__announced_target_references'] = replace_announced_target_reference(
                state, references, announced, [new_paths[index]], remapped_slots={
                    new_path: old_path for slot, (new_path, old_path) in enumerate(zip(new_paths, old_paths))
                    if slot != index and new_path is not None})
        copied.targets = [str(primary['id']), secondary['id']]
        copied.payload.pop('legal_recipients', None)
        state.log.append(f'{state.players[copied.controller].name} changes a target of {copied.label}.')
    state.pending_mechanic_choice = None
    offer_linked_copy_target_choice(state, copied, index+1)
    return True


def legal_linked_recipients(state, item):
    from rules_engine.action_validation import ActionRejected
    from rules_engine.targeting import stack_source_card
    source = stack_source_card(state, item)
    primary, secondary = item.payload['target_instances']
    if primary['kind'] == 'player':
        dependency_controller = primary['id']
        primary_legal = primary['id'] in state.players and _shield_free(
            state, source, item.controller, {'target_player': primary['id']})
    else:
        same = _same_object(state, primary)
        walker = state.cards.get(primary['id'])
        dependency_controller = walker.controller if same else None
        primary_legal = (same and 'Planeswalker' in effective_types(state, walker)
                         and _shield_free(state, source, item.controller, {'target_card_id': walker.id}))
    secondary_legal = (_same_object(state, secondary)
                       and 'Creature' in effective_types(state, state.cards[secondary['id']])
                       and _shield_free(state, source, item.controller, {'target_card_id': secondary['id']}))
    if secondary_legal and dependency_controller is None:
        raise ActionRejected('Departed planeswalker linked-target dependency needs authoritative LKI coverage')
    secondary_legal = secondary_legal and state.cards[secondary['id']].controller == dependency_controller
    return [packet for packet, legal in [(primary, primary_legal), (secondary, secondary_legal)] if legal]


def resolve_linked_damage(state, controller, payload):
    from effects.registry import resolve_effect
    from rules_engine.land_history import landfall_status
    from rules_engine.landfall import require_known_history
    require_known_history(state, controller)
    amount = payload['landfall_amount'] if landfall_status(state, controller) else payload['ordinary_amount']
    recipients = [{'amount': amount, 'target_player' if packet['kind'] == 'player' else 'target_card_id': packet['id']}
                  for packet in payload.get('legal_recipients', payload['target_instances'])]
    resolve_effect(state, controller, 'deal_damage_batch', {
        'recipients': recipients, **{key: value for key, value in payload.items() if key.startswith('__')}})
