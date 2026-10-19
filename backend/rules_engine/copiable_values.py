"""Retained physical identity and supported layer-one values, not live counters."""
from copy import deepcopy

FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
          'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')
PHYSICAL = (*FIELDS, 'card_faces', 'layout', 'selected_face_index', 'image_uri')


def _valid(values):
    return (type(values) is dict and set(values) == set(FIELDS)
        and all(type(values[key]) is str for key in ('name', 'mana_cost', 'type_line', 'oracle_text'))
        and all(type(values[key]) is list and all(type(v) is str for v in values[key])
                for key in ('types', 'keywords'))
        and (values['colors'] is None or type(values['colors']) is list
             and all(type(v) is str for v in values['colors']))
        and all(values[key] is None or type(values[key]) is int for key in ('power', 'toughness', 'loyalty'))
        and all(values[key] is None or type(values[key]) is str for key in ('printed_power', 'printed_toughness')))


def initialize(card):
    physical = {key: deepcopy(getattr(card, key)) for key in PHYSICAL}
    current = {key: deepcopy(physical[key]) for key in FIELDS}
    current['types'] = [kind for kind in current['types'] if kind != 'Token']
    card.characteristic_record = {'version': 1, 'physical': physical, 'values': current}


def values(card):
    from rules_engine.action_validation import ActionRejected
    record = getattr(card, 'characteristic_record', None)
    if (type(record) is not dict or set(record) != {'version', 'physical', 'values'}
            or type(record['version']) is not int or record['version'] != 1
            or type(record['physical']) is not dict or set(record['physical']) != set(PHYSICAL)
            or not _valid({key: record['physical'][key] for key in FIELDS})
            or not _valid(record['values'])):
        raise ActionRejected('Copy requires retained physical and copiable characteristics')
    return deepcopy(record['values'])


def record_form(card):
    current = {key: deepcopy(getattr(card, key)) for key in FIELDS}
    current['types'] = [kind for kind in current['types'] if kind != 'Token']
    record = deepcopy(getattr(card, 'characteristic_record', None))
    if not record:
        return
    record['values'] = current
    card.characteristic_record = record


def project(card, descriptor):
    from rules_engine.action_validation import ActionRejected
    if not _valid(descriptor):
        raise ActionRejected('Invalid copiable-value projection')
    projected = deepcopy(card)
    apply(projected, descriptor, entering=True)
    return projected


def apply(card, descriptor, *, entering=False):
    from rules_engine.action_validation import ActionRejected
    if not _valid(descriptor):
        raise ActionRejected('Invalid copiable values')
    values(card)
    physical = card.characteristic_record['physical']
    live_loyalty = card.loyalty
    for key in FIELDS:
        card.printed_characteristics.setdefault(key, deepcopy(physical[key]))
        if key != 'loyalty' or entering or card.zone.value != 'battlefield':
            setattr(card, key, deepcopy(descriptor[key]))
    if not entering and card.zone.value == 'battlefield':
        card.loyalty = (live_loyalty if live_loyalty is not None else 0) if 'Planeswalker' in descriptor['types'] else None
    record = deepcopy(card.characteristic_record)
    record['values'] = deepcopy(descriptor)
    card.characteristic_record = record
    from rules_engine.type_effects import rebase_type_effects
    rebase_type_effects(card)


def restore(card):
    from rules_engine.action_validation import ActionRejected
    try:
        values(card)
    except ActionRejected:
        return
    record = getattr(card, 'characteristic_record', None)
    if record and type(record) is dict and 'physical' in record:
        # The existing printed restoration owns assignment timing and physical faces.
        current = {key: deepcopy(record['physical'][key]) for key in FIELDS}
        current['types'] = [kind for kind in current['types'] if kind != 'Token']
        card.characteristic_record = {**deepcopy(record), 'values': current}
