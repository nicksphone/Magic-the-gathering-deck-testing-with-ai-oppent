"""Independent PRE oracle for legacy audit compatibility; never rebuild values."""
from copy import deepcopy

from game_state.state import object_incarnation


FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
          'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')
PHYSICAL = (*FIELDS, 'card_faces', 'layout', 'selected_face_index', 'image_uri')


def expected_legacy_copiable_lki(card):
    result = {'reference': [object_incarnation(card), card.zone_change_sequence],
              'controller': card.controller, 'types': list(card.types)}
    record = card.characteristic_record
    assert type(record) is dict
    if not record:
        return {**result, 'descriptor': None, 'unavailable': 'missing_copiable_characteristics'}
    assert set(record) == {'version', 'physical', 'values'}
    assert type(record['version']) is int and record['version'] == 1
    assert type(record['physical']) is dict and set(record['physical']) == set(PHYSICAL)
    assert type(record['values']) is dict and set(record['values']) == set(FIELDS)
    for values in (record['physical'], record['values']):
        assert all(type(values[k]) is str for k in ('name', 'mana_cost', 'type_line', 'oracle_text'))
        assert all(type(values[k]) is list and all(type(v) is str for v in values[k])
                   for k in ('types', 'keywords'))
        assert values['colors'] is None or (type(values['colors']) is list
                                            and all(type(v) is str for v in values['colors']))
        assert all(values[k] is None or type(values[k]) is int for k in ('power', 'toughness', 'loyalty'))
        assert all(values[k] is None or type(values[k]) is str for k in ('printed_power', 'printed_toughness'))
    descriptor = deepcopy(record['values'])
    descriptor.update(types=list(dict.fromkeys([*descriptor['types'], 'Token'])),
                      colors=descriptor['colors'] or [], image_uri=card.image_uri)
    if card.layout in {'transform', 'modal_dfc', 'double_faced_token'}:
        face = card.selected_face_index if card.selected_face_index is not None else 0
        assert len(card.card_faces) == 2 and type(face) is int and face in (0, 1)
        descriptor.update(card_faces=deepcopy(card.card_faces),
                          layout='double_faced_token', selected_face_index=face)
    return {**result, 'descriptor': descriptor}
