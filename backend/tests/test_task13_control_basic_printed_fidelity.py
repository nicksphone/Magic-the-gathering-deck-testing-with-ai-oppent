"""Observe real printed admission and scene records; stop before scene effects."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, MatchFactory, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
RAW_SOURCES = {
    'Grizzly Bears': ('ai_terminal_draw/grizzly-bears.raw.json', None, 66,
        '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c',
        '51502b289cb9e4a4d728f79c701295f3dc36b52fb84fad902af79af9fe33afa0'),
    'Forest': ('knowledge_profiles/seed155-scryfall.jsonl', 39, 61,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '602b1fe3c5c18846061929fee422e97c8e9c2c431e57e8c6c810f2da7643fad3'),
    'Island': ('knowledge_profiles/seed155-scryfall.jsonl', 50, 60,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '932ef67074504645e2ddf2ceefcb9e65aa3b6938c6f6c42cb226dbdbe5b30d6b'),
}
CASES = (
    ('test_control_changes', 'test_temporary_control_does_not_follow_reanimated_new_permanent',
     'Grizzly Bears', 'creature', 2, 'resolve_effect'),
    ('test_control_changes', 'test_lethal_spell_damage_ends_temporary_control_before_reanimation',
     'Grizzly Bears', 'creature', 2, 'resolve_effect'),
    ('test_attack_group_tokens', 'test_attacking_token_count_is_frozen_before_sequential_choices',
     'Forest', 'forest', 1, 'create_token'),
    ('test_attack_group_tokens', 'test_attacking_token_count_is_frozen_before_sequential_choices',
     'Island', 'island', 1, 'create_token'),
)
COPY_FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
               'printed_power', 'printed_toughness', 'loyalty', 'oracle_text',
               'keywords', 'colors')


def official(name):
    path, line, fields, file_sha, row_sha = RAW_SOURCES[name]
    data = (FIXTURES / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == file_sha
    raw = json.loads(data.splitlines()[line - 1] if line else data)
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) == fields
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == row_sha
    return raw


def printed(raw):
    assert raw['layout'] == 'normal' and raw['keywords'] == []
    return {
        'name': raw['name'], 'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
        'types': ['Creature'] if raw['name'] == 'Grizzly Bears' else ['Land'],
        'power': int(raw['power']) if 'power' in raw else None,
        'toughness': int(raw['toughness']) if 'toughness' in raw else None,
        'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
        'loyalty': None, 'oracle_text': raw['oracle_text'], 'keywords': [],
        'colors': raw['colors'], 'card_faces': [], 'layout': raw['layout'],
        'selected_face_index': None, 'image_uri': None,
    }


class BeforeSceneEffect(BaseException):
    pass


@pytest.mark.parametrize('module,test,name,object_id,seat,consumer', CASES)
def test_original_control_and_basic_inputs_have_full_native_printing(
        monkeypatch, module, test, name, object_id, seat, consumer):
    original = importlib.import_module('tests.' + module)
    raw = official(name)
    expected = printed(raw)
    admitted, births, consumed = [], [], []
    previous_factory = MatchFactory.from_decks
    previous_birth = CardInstance.__post_init__
    previous_consumer = getattr(original, consumer)

    def assert_record(card):
        assert card.characteristic_record == {
            'version': 1, 'physical': expected,
            'values': {key: expected[key] for key in COPY_FIELDS},
        }

    def factory(first, second, *args, **kwargs):
        if first and first[0].get('object') == 'card' and first[0].get('name') == name:
            assert len(first) == 1 and first[0]['quantity'] == 8
            assert second == [] and args == () and kwargs == {'seed': 0}
            assert all(first[0].get(key) == value for key, value in raw.items())
            admitted.append(name)
        return previous_factory(first, second, *args, **kwargs)

    def birth(card):
        target = card.id == object_id and card.name == name
        if target:
            assert admitted == [name]
            assert {key: getattr(card, key) for key in expected} == expected
        previous_birth(card)
        if target:
            assert_record(card)
            births.append(card.id)

    def consume(state, *args, **kwargs):
        if object_id not in state.cards or state.cards[object_id].name != name:
            return previous_consumer(state, *args, **kwargs)
        card = state.cards[object_id]
        assert admitted == [name] and births == [object_id]
        assert {key: getattr(card, key) for key in expected} == expected
        assert_record(card)
        assert card.owner == card.controller == seat and card.zone == Zone.BATTLEFIELD
        assert object_id in state.players[seat].battlefield
        assert card.summoning_sick is True and card.tapped is False
        assert card.counters == {} and card.counter_timestamps == {}
        assert card.instance_order == card.static_order == card.effect_timestamp == 0
        assert card.entered_turn == card.zone_change_sequence == 0
        assert card.battlefield_incarnation is None and card.knowledge_snapshot == {}
        if module == 'test_control_changes':
            assert args[:2] == (1, 'change_control')
        else:
            assert {'forest', 'island'} <= set(state.players[1].battlefield)
        consumed.append(card.id)
        raise BeforeSceneEffect()

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        patch.setattr(CardInstance, '__post_init__', birth)
        patch.setattr(original, consumer, consume)
        with pytest.raises(BeforeSceneEffect):
            getattr(original, test)()
    assert admitted == [name] and births == consumed == [object_id]
