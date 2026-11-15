"""Retained physical identity and supported layer-one values, not live counters."""
from copy import deepcopy

FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
          'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')
PHYSICAL = (*FIELDS, 'card_faces', 'layout', 'selected_face_index', 'image_uri')
DEFENSE_FIELDS = (*FIELDS, 'printed_defense')
DEFENSE_PHYSICAL = (*DEFENSE_FIELDS, 'card_faces', 'layout', 'selected_face_index', 'image_uri')


def _valid(values):
    return (type(values) is dict and set(values) == set(FIELDS)
        and all(type(values[key]) is str for key in ('name', 'mana_cost', 'type_line', 'oracle_text'))
        and all(type(values[key]) is list and all(type(v) is str for v in values[key])
                for key in ('types', 'keywords'))
        and (values['colors'] is None or type(values['colors']) is list
             and all(type(v) is str for v in values['colors']))
        and all(values[key] is None or type(values[key]) is int for key in ('power', 'toughness', 'loyalty'))
        and all(values[key] is None or type(values[key]) is str for key in ('printed_power', 'printed_toughness')))


def _battle(descriptor):
    from rules_engine.card_types import printed_card_types
    return ('Battle' in descriptor.get('types', [])
            or 'Battle' in printed_card_types(descriptor.get('type_line', '')))


def _defense_valid(value):
    return value is None or (type(value) is str and value.isascii() and value.isdecimal())


def _descriptor_valid(descriptor, extended):
    fields = DEFENSE_FIELDS if extended else FIELDS
    if type(descriptor) is not dict or set(descriptor) != set(fields):
        return False
    if not _valid({key: descriptor[key] for key in FIELDS}):
        return False
    if extended:
        return (_defense_valid(descriptor['printed_defense'])
                and (not _battle(descriptor) or descriptor['printed_defense'] is not None))
    # Old Battle records omitted a copiable characteristic. Do not invent it.
    return not _battle(descriptor)


def _fresh_record(physical, current, extended):
    record = {'version': 3 if extended else 1, 'physical': deepcopy(physical), 'values': deepcopy(current)}
    if extended:
        record.update(base=deepcopy(current), effects=[], added_printed_fields=[])
    return record


def initialize(card):
    extended = card.printed_defense is not None or _battle(vars(card))
    fields, physical_fields = (DEFENSE_FIELDS, DEFENSE_PHYSICAL) if extended else (FIELDS, PHYSICAL)
    physical = {key: deepcopy(getattr(card, key)) for key in physical_fields}
    current = {key: deepcopy(physical[key]) for key in fields}
    current['types'] = [kind for kind in current['types'] if kind != 'Token']
    card.characteristic_record = _fresh_record(physical, current, extended)


def values(card):
    return deepcopy(_record(card)['values'])


def _record(card):
    from rules_engine.action_validation import ActionRejected
    record = getattr(card, 'characteristic_record', None)
    keys = {'version', 'physical', 'values'}
    if type(record) is dict and record.get('version') in {2, 3}:
        keys |= {'base', 'effects', 'added_printed_fields'}
    extended = type(record) is dict and record.get('version') == 3
    fields, physical_fields = (DEFENSE_FIELDS, DEFENSE_PHYSICAL) if extended else (FIELDS, PHYSICAL)
    if (type(record) is not dict or set(record) != keys
            or type(record['version']) is not int or record['version'] not in {1, 2, 3}
            or type(record['physical']) is not dict or set(record['physical']) != set(physical_fields)
            or not _descriptor_valid({key: record['physical'][key] for key in fields}, extended)
            or not _descriptor_valid(record['values'], extended)):
        raise ActionRejected('Copy requires retained physical and copiable characteristics')
    if record['version'] in {2, 3}:
        effects, added = record['effects'], record['added_printed_fields']
        if (not _descriptor_valid(record['base'], extended) or type(effects) is not list
                or record['version'] == 2 and not effects
                or any(type(effect) is not dict or set(effect) != {'values', 'until_end_of_turn'}
                       or type(effect['until_end_of_turn']) is not bool or not _descriptor_valid(effect['values'], extended)
                       for effect in effects)
                or type(added) is not list or any(type(key) is not str or key not in fields for key in added)
                or len(added) != len(set(added))
                or record['values'] != (effects[-1]['values'] if effects else record['base'])
                or not effects and added):
            raise ActionRejected('Invalid retained copy history')
    return record


def _extended_descriptor(descriptor):
    from rules_engine.action_validation import ActionRejected
    if set(descriptor) == set(DEFENSE_FIELDS):
        if not _descriptor_valid(descriptor, True):
            raise ActionRejected('Unknown printed defense in copy descriptor')
        return deepcopy(descriptor)
    if not _descriptor_valid(descriptor, False):
        raise ActionRejected('Legacy Battle copy lacks printed defense')
    return {**deepcopy(descriptor), 'printed_defense': None}


def _extend_record(record):
    if record['version'] == 3:
        return record
    record['physical']['printed_defense'] = None
    record['values'] = _extended_descriptor(record['values'])
    if record['version'] == 1:
        record.update(base=deepcopy(record['values']), effects=[], added_printed_fields=[])
    else:
        record['base'] = _extended_descriptor(record['base'])
        for effect in record['effects']:
            effect['values'] = _extended_descriptor(effect['values'])
    record['version'] = 3
    return record


def record_form(card, *, preserve_effects=True, printed_fields=()):
    record = deepcopy(getattr(card, 'characteristic_record', None))
    if not record:
        return
    _record(card)
    extended = record['version'] == 3 or card.printed_defense is not None or _battle(vars(card))
    if extended:
        record = _extend_record(record)
    fields = DEFENSE_FIELDS if extended else FIELDS
    current = {key: deepcopy(getattr(card, key)) for key in fields}
    current['types'] = [kind for kind in current['types'] if kind != 'Token']
    if record['version'] in {2, 3}:
        if not preserve_effects:
            card.characteristic_record = _fresh_record(record['physical'], current, extended)
            return
        record['base'] = current
        record['added_printed_fields'] = [key for key in record['added_printed_fields'] if key not in printed_fields]
        record['values'] = deepcopy(record['effects'][-1]['values'] if record['effects'] else current)
        card.characteristic_record = record
        _assign(card, record['values'], mark_printed=False)
        return
    record['values'] = current
    card.characteristic_record = record


def project(card, descriptor):
    from rules_engine.action_validation import ActionRejected
    if not (_descriptor_valid(descriptor, False) or _descriptor_valid(descriptor, True)):
        raise ActionRejected('Invalid copiable-value projection')
    projected = deepcopy(card)
    apply(projected, descriptor, entering=True)
    return projected


def _assign(card, descriptor, *, entering=False, mark_printed=True):
    physical = card.characteristic_record['physical']
    live_loyalty = card.loyalty
    if mark_printed:
        card.printed_characteristics = deepcopy(card.printed_characteristics)
    fields = DEFENSE_FIELDS if 'printed_defense' in descriptor else FIELDS
    for key in fields:
        if mark_printed:
            card.printed_characteristics.setdefault(key, deepcopy(physical[key]))
        if key != 'loyalty' or entering or card.zone.value != 'battlefield':
            setattr(card, key, deepcopy(descriptor[key]))
    if not entering and card.zone.value == 'battlefield':
        # Loyalty is a live counter even while its object is not a planeswalker.
        card.loyalty = live_loyalty if live_loyalty is not None else (0 if 'Planeswalker' in descriptor['types'] else None)
    from rules_engine.bestow import refresh_bestow
    refresh_bestow(card)
    from rules_engine.type_effects import rebase_type_effects
    rebase_type_effects(card)


def apply(card, descriptor, *, entering=False, until_end_of_turn=False):
    from rules_engine.action_validation import ActionRejected
    if (not (_descriptor_valid(descriptor, False) or _descriptor_valid(descriptor, True))
            or type(until_end_of_turn) is not bool):
        raise ActionRejected('Invalid copiable values')
    if until_end_of_turn and card.zone.value != 'battlefield':
        raise ActionRejected('Temporary copy requires a battlefield object')
    record = deepcopy(_record(card))
    if record['version'] == 3 or 'printed_defense' in descriptor:
        newly_extended = record['version'] != 3
        record = _extend_record(record)
        descriptor = _extended_descriptor(descriptor)
        if not record['effects']:
            record['added_printed_fields'] = [key for key in DEFENSE_FIELDS if key not in card.printed_characteristics]
        elif newly_extended and 'printed_defense' not in card.printed_characteristics:
            record['added_printed_fields'].append('printed_defense')
    if record['version'] == 1:
        # Preserve the recorded current base; old formats did not retain history.
        record.update(version=2, base=deepcopy(record['values']), effects=[],
                      added_printed_fields=[key for key in FIELDS if key not in card.printed_characteristics])
    effect = {'values': deepcopy(descriptor), 'until_end_of_turn': until_end_of_turn}
    # A later complete permanent copy forever shadows older complete copies.
    record['effects'] = [*record['effects'], effect] if until_end_of_turn else [effect]
    record['values'] = deepcopy(descriptor)
    card.characteristic_record = record
    _assign(card, descriptor, entering=entering)


def expire_temporary_copies(state):
    for card in state.cards.values():
        record = getattr(card, 'characteristic_record', None)
        if card.zone.value != 'battlefield' or type(record) is not dict or record.get('version') not in {2, 3}:
            continue
        record = deepcopy(_record(card))
        effects = [effect for effect in record['effects'] if not effect['until_end_of_turn']]
        if len(effects) == len(record['effects']):
            continue
        descriptor = deepcopy(effects[-1]['values'] if effects else record['base'])
        record.update(effects=effects, values=descriptor)
        if effects:
            card.characteristic_record = record
        else:
            for key in record['added_printed_fields']:
                if card.printed_characteristics.get(key) == record['physical'][key]:
                    card.printed_characteristics.pop(key, None)
            card.characteristic_record = _fresh_record(record['physical'], descriptor, record['version'] == 3)
        _assign(card, descriptor, mark_printed=False)


def restore(card):
    from rules_engine.action_validation import ActionRejected
    try:
        values(card)
    except ActionRejected:
        return
    record = getattr(card, 'characteristic_record', None)
    if record and type(record) is dict and 'physical' in record:
        # The existing printed restoration owns assignment timing and physical faces.
        extended = record['version'] == 3
        current = {key: deepcopy(record['physical'][key]) for key in (DEFENSE_FIELDS if extended else FIELDS)}
        current['types'] = [kind for kind in current['types'] if kind != 'Token']
        card.characteristic_record = _fresh_record(record['physical'], current, extended)
