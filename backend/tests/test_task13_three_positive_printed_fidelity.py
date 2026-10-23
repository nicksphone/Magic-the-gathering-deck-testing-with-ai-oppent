"""Native birth/retained-print witnesses, stopping before the scene's consumer."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
RAW_SOURCES = {
    'Teferi, Hero of Dominaria': (
        'knowledge_profiles/seed155-scryfall.jsonl', 100,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '41d7b9bf8bd192b82472ed60b779993ed7f8f759105db9e019a5c3d809535cd7'),
    'Soul Warden': (
        'hand_entry_bookkeeping/canonical.jsonl', 3,
        '99a897459c994dedb916a59104c0023cab4e9d96aac274d60fd3f7603c44cfc0',
        'aab93dc473e3b17311b364feedfdca3e4cad793ea7ed5197fee8522f5826295d'),
    'Grizzly Bears': (
        'ai_terminal_draw/grizzly-bears.raw.json', None,
        '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c',
        '51502b289cb9e4a4d728f79c701295f3dc36b52fb84fad902af79af9fe33afa0'),
}


def official(name):
    path, line, file_sha, row_sha = RAW_SOURCES[name]
    encoded = (FIXTURES / path).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == file_sha
    raw = json.loads(encoded.splitlines()[line - 1] if line else encoded)
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) == 66
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == row_sha
    return raw


def printed(raw):
    type_words = raw['type_line'].split(' — ')[0].split()
    kinds = ('Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Land',
             'Planeswalker', 'Sorcery')
    return {
        'name': raw['name'], 'mana_cost': raw['mana_cost'],
        'type_line': raw['type_line'], 'types': [kind for kind in kinds if kind in type_words],
        'oracle_text': raw['oracle_text'], 'colors': raw['colors'], 'keywords': [],
        'power': int(raw['power']) if 'power' in raw else None,
        'toughness': int(raw['toughness']) if 'toughness' in raw else None,
        'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
        'loyalty': int(raw['loyalty']) if 'loyalty' in raw else None,
    }


class BeforeConsumer(BaseException):
    pass


@pytest.mark.parametrize('module,test,name,object_id,seat,consumer,loyalty', [
    ('test_attack_group_tokens', 'test_human_chooses_attacking_token_defender_after_snapshot',
     'Teferi, Hero of Dominaria', 'teferi', 2, 'assign_static_order_on_battlefield_entry', 1),
    ('test_attack_group_tokens', 'test_multiple_attacking_tokens_choose_separate_defenders',
     'Teferi, Hero of Dominaria', 'teferi', 2, 'assign_static_order_on_battlefield_entry', 3),
    ('test_events_apnap', 'test_create_token_emits_enters_battlefield_for_etb_triggers',
     'Soul Warden', 'p1', 1, 'create_token', None),
    ('test_land_and_adventure_faces',
     'test_adventure_with_a_missing_target_does_not_resolve_or_grant_permission',
     'Grizzly Bears', 'bear', 2, 'stomp', None),
])
def test_selected_positive_is_canonical_before_birth_and_consumer(
        monkeypatch, module, test, name, object_id, seat, consumer, loyalty):
    original = importlib.import_module('tests.' + module)
    raw = official(name)
    expected = printed(raw)
    births = []
    previous_birth = CardInstance.__post_init__
    previous_consumer = getattr(original, consumer)

    def assert_retained(card):
        record = card.characteristic_record
        assert record is not None and record['version'] == 1
        for key, value in expected.items():
            assert record['physical'][key] == value, key
            assert record['values'][key] == value, key
        assert record['physical']['layout'] == raw['layout']
        assert record['physical']['card_faces'] == raw.get('card_faces', [])
        assert record['physical']['selected_face_index'] is None
        # Display policy is not a printed-art fidelity assertion.
        assert record['physical']['image_uri'] == card.image_uri

    def birth(card):
        if card.name == name and card.id == object_id:
            for key, value in expected.items():
                assert getattr(card, key) == value, key
            assert card.layout == raw['layout']
            assert card.card_faces == raw.get('card_faces', [])
        previous_birth(card)
        if card.name == name and card.id == object_id:
            assert_retained(card)
            births.append(card.id)

    def consume(state, *args, **kwargs):
        if object_id not in state.cards or state.cards[object_id].name != name:
            return previous_consumer(state, *args, **kwargs)
        card = state.cards[object_id]
        assert births and object_id in births
        assert_retained(card)
        assert card.id == object_id and card.owner == card.controller == seat
        assert card.zone == Zone.BATTLEFIELD and object_id in state.players[seat].battlefield
        assert card.summoning_sick and not card.tapped and card.counters == {}
        assert card.instance_order == card.static_order == card.effect_timestamp == 0
        assert card.loyalty == loyalty
        for key, value in expected.items():
            if key != 'loyalty':
                assert getattr(card, key) == value, key
        raise BeforeConsumer()

    with monkeypatch.context() as patch:
        patch.setattr(CardInstance, '__post_init__', birth)
        patch.setattr(original, consumer, consume)
        with pytest.raises(BeforeConsumer):
            getattr(original, test)()
    assert births
