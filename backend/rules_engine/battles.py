"""Battle characteristics, intrinsic entry placement and two-player protectors."""
import re
from contextlib import contextmanager
from contextvars import ContextVar

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.query_context import rule_query_scope
from rules_engine.type_effects import effective_types

_resolving_triggers = ContextVar('resolving_battle_trigger_sources', default=())


@contextmanager
def trigger_resolution_scope(state, item):
    token = _resolving_triggers.set((*_resolving_triggers.get(), (state, item)))
    try:
        yield
    finally:
        _resolving_triggers.reset(token)


def trigger_left_stack(state, item):
    _resolving_triggers.set(tuple((owner, frame) for owner, frame in _resolving_triggers.get()
        if not (owner is state and frame.id == item.id)))


def _same_trigger_source(card, source_id, payload):
    reference = payload.get('__trigger_source_reference')
    return (source_id == card.id and type(reference) is dict
            and set(reference) == {'incarnation','zone_change_sequence'}
            and all(type(value) is int and value >= 0 for value in reference.values())
            and reference == {'incarnation': object_incarnation(card),
                              'zone_change_sequence': card.zone_change_sequence}
            and payload.get('__announced_stack_kind') != 'activated'
            and payload.get('__stack_copy_kind') in {None, 'triggered'})


def _has_pending_trigger(state, card):
    from rules_engine.targeting import stack_object_kind
    for item in state.stack:
        if stack_object_kind(state, item) == 'triggered' and _same_trigger_source(card, item.source_card_id, item.payload):
            return True
    queued = [*state.staged_triggers, *state.cleanup_deferred_triggers]
    for group in (state.pending_trigger_order or {}).get('groups', {}).values():
        queued.extend(group)
    if any(_same_trigger_source(card, row.get('source_card_id'), row.get('payload', {})) for row in queued):
        return True
    for owner, item in _resolving_triggers.get():
        if (owner is state and stack_object_kind(state, item) == 'triggered'
                and _same_trigger_source(card, item.source_card_id, item.payload)):
            return True
    for pending in (state.pending_mechanic_choice, state.pending_replacement_choice):
        frame = (pending or {}).get('resolving_item')
        if (type(frame) is dict and frame.get('payload', {}).get('__trigger_event')
                and _same_trigger_source(card, frame.get('source_card_id'), frame.get('payload', {}))):
            return True
    return False


def zero_defense_ids(state):
    return [card.id for card in state.cards.values()
            if card.zone == Zone.BATTLEFIELD and 'Battle' in effective_types(state, card)
            and defense(state, card) == 0
            and not (is_siege(state, card.id) and _has_pending_trigger(state, card))]


def collect_defeat(state, payload):
    card = state.cards.get(payload.get('card_id'))
    if (card is None or card.zone != Zone.BATTLEFIELD
            or not (type(payload.get('old_defense')) is int and payload['old_defense'] > 0)
            or payload.get('new_defense') != 0 or not is_siege(state, card.id)
            or not intrinsic_abilities_present(state, card.id)
            or payload.get('source_reference') != {'incarnation': object_incarnation(card),
                                                   'zone_change_sequence': card.zone_change_sequence}):
        return []
    return [{'source_card_id': card.id, 'controller': card.controller,
             'label': f'{card.name} defeat', 'effect_key': 'battle_defeat',
             'payload': {'target_card_id': card.id,
                         '__trigger_source_reference': dict(payload['source_reference'])}}]


def printed_defense_number(card):
    value = card.printed_defense
    if type(value) is str and value.isascii() and value.isdecimal():
        return int(value)
    return None


def _retained_defense_number(card):
    """Known absence is zero; an incomplete Battle descriptor stays unknown."""
    from rules_engine.card_types import printed_card_types
    from rules_engine.copiable_values import values
    descriptor = values(card)
    if (card.printed_defense is None and descriptor.get('printed_defense') is None
            and 'Battle' not in descriptor['types']
            and 'Battle' not in printed_card_types(descriptor['type_line'])):
        return 0
    amount = printed_defense_number(card)
    if amount is None or descriptor.get('printed_defense') != card.printed_defense:
        raise ActionRejected('Battle entry requires known retained printed defense')
    return amount


def defense(state, card):
    if 'Battle' not in effective_types(state, card):
        return None
    if card.zone == Zone.BATTLEFIELD:
        return max(0, int(card.counters.get('defense', 0)))
    try:
        return _retained_defense_number(card)
    except ActionRejected:
        return None


def is_siege(state, card_id):
    from rules_engine.land_types import effective_type_line
    card = state.cards.get(card_id)
    if card is None or 'Battle' not in effective_types(state, card):
        return False
    parts = re.split(r'\s+[—–-]\s+', effective_type_line(state, card), maxsplit=1)
    return len(parts) == 2 and 'Siege' in parts[1].split()


def intrinsic_abilities_present(state, card_id):
    from rules_engine.continuous import printed_abilities_suppressed
    card = state.cards.get(card_id)
    return (card is not None and 'Battle' in effective_types(state, card)
            and not printed_abilities_suppressed(state, card_id, include_land_types=False))


def ensure_protectors(state):
    """The existing two-player product has one legal choice for each Battle."""
    with rule_query_scope(state):
        battles = [card for card in state.cards.values()
                   if card.zone == Zone.BATTLEFIELD and 'Battle' in effective_types(state, card)]
    changed = False
    for card in battles:
        from rules_engine.combat import is_being_attacked
        if is_being_attacked(state, card.id):
            continue
        legal = ([pid for pid in state.players if pid != card.controller]
                 if is_siege(state, card.id) else [card.controller] if card.controller in state.players else [])
        if legal and (type(card.battle_protector) is not int or card.battle_protector not in legal):
            if len(legal) != 1:
                raise ActionRejected('Multiplayer Battle protector choice is not implemented')
            card.battle_protector = legal[0]
            changed = True
    return changed


def _entry_proof(state, card, controller, prospective_types):
    if 'Battle' not in prospective_types:
        return None
    from rules_engine.entry_counters import prospective_entry_ability_view
    _retained_defense_number(card)
    view = prospective_entry_ability_view(state, card, controller, include_land_types=False)
    return {'version': 2 if card.printed_defense is None else 1, 'card_id': card.id, 'owner': card.owner,
            'controller': controller, 'origin_zone': card.zone.value,
            'reference': {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence},
            'printed_defense': card.printed_defense, 'intrinsic_present': not view['printed_suppressed']}


def entry_proof_matches(state, card, controller, proof, *, prospective_types=None):
    from rules_engine.basic_land_layer import layer_four_view
    if (type(proof) is not dict or set(proof) != {
            'version','card_id','owner','controller','origin_zone','reference','printed_defense','intrinsic_present'}
            or type(proof['version']) is not int or proof['version'] not in {1, 2}
            or type(proof['card_id']) is not str or type(proof['origin_zone']) is not str
            or type(proof['owner']) is not int or type(proof['controller']) is not int
            or type(proof['intrinsic_present']) is not bool
            or (type(proof['printed_defense']) is not str if proof['version'] == 1
                else proof['printed_defense'] is not None)
            or type(proof['reference']) is not dict
            or set(proof['reference']) != {'incarnation','zone_change_sequence'}
            or any(type(v) is not int or v < 0 for v in proof['reference'].values())):
        return False
    if prospective_types is None:
        prospective_types = layer_four_view(state, entering=card, controller=controller)[2].get(card.id, card.types)
    try:
        return proof == _entry_proof(state, card, controller, prospective_types)
    except ActionRejected:
        return False


def prepare_entry_defense(state, card, controller, data, prospective_types):
    """Bind the intrinsic producer before any replacement choice or BF mutation."""
    proof = _entry_proof(state, card, controller, prospective_types)
    if '__battle_entry_counter' in data:
        if proof is None or not entry_proof_matches(state, card, controller, data['__battle_entry_counter'],
                                                   prospective_types=prospective_types):
            raise ActionRejected('Stale Battle intrinsic entry counter receipt')
    elif proof is not None:
        data['__battle_entry_counter'] = proof
    return (int(proof['printed_defense']) if proof['intrinsic_present']
            and proof['printed_defense'] is not None else 0) if proof else None


def resolve_defeat(state, controller, payload):
    """Exile the retained Siege object, then offer its own physical back."""
    from rules_engine.events import _valid_source_reference
    target = payload.get('target_card_id')
    card = state.cards.get(target) if type(target) is str else None
    reference = payload.get('__trigger_source_reference')
    if (card is None or not _valid_source_reference(reference)
            or card.zone != Zone.BATTLEFIELD or card.controller not in state.players
            or target not in state.players[card.controller].battlefield
            or reference != {'incarnation': object_incarnation(card),
                             'zone_change_sequence': card.zone_change_sequence}):
        return
    from effects.handlers import exile_permanent
    exile_permanent(state, controller, {'target_card_id': target})
    permission = {'permission_kind': 'battle_transformed', 'target_card_id': target,
                  'reference': {'incarnation': object_incarnation(card),
                                'zone_change_sequence': card.zone_change_sequence},
                  'face_index': 1}
    from rules_engine.effect_casts import validate_permission, materialize_cast, admit_cast
    if not validate_permission(state, controller, permission):
        return
    if controller in state.mechanic_choice_players:
        state.pending_mechanic_choice = {
            'kind': 'effect_cast', 'player_id': controller, 'options': ['decline'], 'count': 1,
            'label': 'Cast the transformed card, or decline', 'effect_payload': permission}
        state.priority_player = controller
        state.passed_priority = set()
        return
    try:
        action = materialize_cast(state, controller, target, permission=permission)
        admit_cast(state, controller, action, permission)
    except (ValueError, KeyError):
        state.log.append(f'{state.players[controller].name} declines the transformed cast: no payable supported announcement.')
