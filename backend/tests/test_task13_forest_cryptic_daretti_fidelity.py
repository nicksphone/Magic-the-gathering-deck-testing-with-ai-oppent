"""Full real prints before birth; no substitution for original gameplay tests."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES = {
    'Forest': ('knowledge_profiles/seed155-scryfall.jsonl', 39, 61,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '602b1fe3c5c18846061929fee422e97c8e9c2c431e57e8c6c810f2da7643fad3'),
    'Cryptic Command': ('browser_inline26/canonical.jsonl', 32, 65,
        '3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd',
        'fc9c7da365cf96777fcc285fcbc741fb1ad98e2627f063013618ead70897ac2a'),
    'Daretti, Scrap Savant': ('entry_unadapted_two641/daretti-scrap-savant.json', None, 65,
        '4fc9d73aded6d4c3cacd7f72d745f670d032b8ee6c8c36a15ac40204ac3506cc',
        '40c721cccd657d51226a787f9b397aad54d19a6c24b94e3adbc232daaec4a570'),
}
COPY_FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
               'printed_power', 'printed_toughness', 'loyalty', 'oracle_text',
               'keywords', 'colors')


def official(name):
    path, line, fields, file_sha, object_sha = SOURCES[name]
    data = (FIXTURES / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == file_sha
    raw = json.loads(data.splitlines()[line - 1] if line else data)
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) == fields
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == object_sha
    return raw


class BeforeScene(Exception):
    pass


@pytest.mark.parametrize('module,name,object_id,seat,loyalty', (
    ('test_attachments', 'Forest', 'land', 1, None),
    ('test_ai_counterability', 'Cryptic Command', 'cryptic', 1, None),
    ('test_canonical_daretti_full_body_contract', 'Daretti, Scrap Savant', 'daretti', 1, 3),
    ('test_canonical_daretti_full_body_contract', 'Daretti, Scrap Savant', 'daretti', 2, 10),
))
def test_original_selected_input_has_full_print_before_native_birth(
        monkeypatch, module, name, object_id, seat, loyalty):
    original = importlib.import_module('tests.' + module)
    raw = official(name)
    expected = {
        'name': name, 'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
        'types': [{'Forest': 'Land', 'Cryptic Command': 'Instant',
                   'Daretti, Scrap Savant': 'Planeswalker'}[name]],
        'power': None, 'toughness': None, 'printed_power': None, 'printed_toughness': None,
        'loyalty': int(raw['loyalty']) if 'loyalty' in raw else None,
        'oracle_text': raw['oracle_text'], 'keywords': [], 'colors': raw['colors'],
        'card_faces': [], 'layout': raw['layout'], 'selected_face_index': None, 'image_uri': None,
    }
    assert raw['keywords'] == [] and raw.get('card_faces', []) == []
    admitted, private_births, scene_births = [], [], []
    inside_private = False
    previous_factory = MatchFactory.from_decks
    previous_birth = CardInstance.__post_init__

    def assert_record(card):
        assert card.characteristic_record == {
            'version': 1, 'physical': expected,
            'values': {key: expected[key] for key in COPY_FIELDS},
        }

    def factory(first, second, *args, **kwargs):
        nonlocal inside_private
        selected = bool(first and first[0].get('object') == 'card'
                        and first[0].get('name') == name)
        if not selected:
            return previous_factory(first, second, *args, **kwargs)
        assert len(first) == 1 and first[0]['quantity'] == 8 and second == []
        assert args == () and kwargs == {'seed': 0}
        assert all(first[0].get(key) == value for key, value in raw.items())
        admitted.append(name)
        inside_private = True
        try:
            return previous_factory(first, second, *args, **kwargs)
        finally:
            inside_private = False

    def birth(card):
        selected = card.name == name and (inside_private or card.id == object_id)
        if selected:
            assert admitted == [name]
            assert {key: getattr(card, key) for key in expected} == expected
        previous_birth(card)
        if selected:
            assert_record(card)
            (private_births if inside_private else scene_births).append(card.id)

    def check_scene(state):
        card = state.cards[object_id]
        current = dict(expected, loyalty=loyalty) if loyalty is not None else expected
        assert {key: getattr(card, key) for key in current} == current
        assert_record(card)
        assert card.id == object_id and card.owner == card.controller == seat
        assert card.zone == (Zone.HAND if name == 'Cryptic Command' else Zone.BATTLEFIELD)
        assert card.id in getattr(state.players[seat], card.zone.value)
        assert card.summoning_sick is True and card.tapped is False
        assert card.counters == {} and card.knowledge_snapshot == {}
        assert admitted == [name] and len(private_births) == 8 and scene_births == [object_id]
        assert card.colors is not card.characteristic_record['physical']['colors']
        assert card.characteristic_record['physical']['colors'] is not card.characteristic_record['values']['colors']

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        patch.setattr(CardInstance, '__post_init__', birth)
        if name == 'Forest':
            prior_state = original._state
            baseline = []

            def state():
                result = prior_state()
                baseline.append((result.rng.getstate(), result.next_object_id))
                return result

            def consume(state, *_args, **_kwargs):
                check_scene(state)
                assert (state.rng.getstate(), state.next_object_id) == baseline[0]
                raise BeforeScene

            patch.setattr(original, '_state', state)
            patch.setattr(original, 'build_cast_hints', consume)
            with pytest.raises(BeforeScene):
                original.test_aura_target_restrictions_are_exposed_and_carried_to_stack_payload()
        elif name == 'Cryptic Command':
            state, _ = original.prepare()
            before = deepcopy(state)
            card = original.add_cryptic(state)
            check_scene(state)
            assert card is state.cards['cryptic']
            assert state.rng.getstate() == before.rng.getstate()
            assert state.next_object_id == before.next_object_id
            before.cards[card.id] = deepcopy(card)
            before.players[1].hand.append(card.id)
            before.players[1].mana_pool.update({'U': 3, 'C': 1})
            before.players[1].lands_played_this_turn = 1
            assert serialize_match_snapshot(state) == serialize_match_snapshot(before)
        else:
            state = original.board(seat, loyalty=loyalty)
            check_scene(state)
            assert state.next_object_id == 1
            assert state.players[seat].battlefield == ['daretti']
            assert all(len(player.library) == 8 for player in state.players.values())
