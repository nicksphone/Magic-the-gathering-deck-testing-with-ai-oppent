"""Both-seat admission witnesses; stop before snapshot, not paid-cast outcomes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, MatchState, Step, Zone, _infer_keywords
from rules_engine.copiable_values import FIELDS, PHYSICAL
from tests import test_select_query_fixture_provenance as original


SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
FILE_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
SOURCES = {
    'Memory Deluge': (62, 63, 'ca78551defc92aef72551b4b03060d3e86bd7f81fa8820c283fe8f9b518f4ac7',
                      'edcd3802-ddb3-4eb6-9b6e-a26d76557662', 'e6fd55f2-7e26-469c-a44a-ea2eb90e19a9'),
    'Negate': (66, 66, 'a6e0857a1fc161e46106b89cf0adb8d271d0ead6717da123a7a4093dcc5c5ba2',
               '52d58fe4-6070-4022-9cd7-c35a11b44525', '3407fe41-fdd3-4119-8f70-4bc4590a379f'),
}


def official(name):
    line, fields, object_sha, identifier, oracle_id = SOURCES[name]
    encoded = SEED.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == FILE_SHA
    raw = json.loads(encoded.splitlines()[line - 1])
    assert (raw['object'], raw['name'], len(raw), raw['id'], raw['oracle_id']) == (
        'card', name, fields, identifier, oracle_id)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == object_sha
    return raw


@pytest.mark.parametrize('seat', [1, 2])
def test_original_both_inputs_have_full_print_before_birth_and_snapshot(monkeypatch, seat):
    raws = {name: official(name) for name in SOURCES}
    expected = {}
    for name, raw in raws.items():
        values = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors')}
        # Use the actual Factory policy, not catalog tags such as Flashback.
        values.update(types=['Instant'], power=None, toughness=None, printed_power=None,
                      printed_toughness=None, loyalty=None, keywords=_infer_keywords(raw['oracle_text']))
        assert set(values) == set(FIELDS)
        physical = {**values, 'card_faces': raw.get('card_faces', []), 'layout': raw['layout'],
                    'selected_face_index': None, 'image_uri': None}
        assert set(physical) == set(PHYSICAL)
        expected[name] = dict(version=1, physical=physical, values=values)
    poses = {
        'Memory Deluge': dict(id='deluge', owner=seat, zone=Zone.GRAVEYARD),
        'Negate': dict(id='counter', owner=3-seat, zone=Zone.HAND),
    }
    provider, normalizer = Path.read_bytes, ScryfallSyncService._normalize_payload
    factory, birth, allocate = MatchFactory.from_decks, CardInstance.__post_init__, MatchState.allocate_object_id
    materialize, snapshot = original._paid_input_card, original.serialize_match_snapshot
    roots, admissions, normalized, samples, allocations, preserved = [], [], {}, {}, [], {}
    template_births, pose_births = {name: [] for name in raws}, {name: [] for name in raws}
    active_name = sample_name = None

    class BeforeSnapshot(BaseException):
        pass

    def retained(card, name):
        assert {key: getattr(card, key) for key in PHYSICAL} == expected[name]['physical']
        assert type(card.characteristic_record['version']) is int
        assert card.characteristic_record == expected[name]

    def observe_provider(path):
        encoded = provider(path)
        if active_name is not None and path.resolve() == SEED.resolve():
            assert hashlib.sha256(encoded).hexdigest() == FILE_SHA
            admissions.append(active_name)
        return encoded

    def observe_normalizer(cls, incoming, image_uri, rulings=None):
        name = incoming.get('name')
        if name in raws:
            assert name == active_name and incoming == raws[name]
            assert admissions.count(name) == 1 and name not in normalized
            assert image_uri == 'unused:task13-paid-input-display'
        result = normalizer(incoming, image_uri, rulings)
        if name in raws:
            assert result['scryfall_id'] == raws[name]['id']
            for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'layout'):
                assert result[key] == raws[name][key]
            normalized[name] = deepcopy(result)
        return result

    def observe_factory(first, second, *args, **kwargs):
        nonlocal sample_name
        name = first[0].get('card_name') if first else None
        if name not in raws:
            assert not roots and first == second == [{'quantity': 60, 'card_name': 'Island'}]
            assert args == () and kwargs == {'seed': 29}
            state = factory(first, second, *args, **kwargs)
            roots.append(state)
            return state
        assert name == active_name and name not in samples and sample_name is None
        entry = {**raws[name], **normalized[name], 'card_name': name, 'quantity': 8,
                 'image_uri': None, 'colors': raws[name]['colors'],
                 'card_faces': raws[name].get('card_faces', [])}
        assert first == [entry] and second == [] and args == () and kwargs == {'seed': 0}
        sample_name = name
        try:
            state = factory(first, second, *args, **kwargs)
        finally:
            sample_name = None
        assert len(state.cards) == len(template_births[name]) == 8
        assert len(state.players[1].library) == 1
        for card in state.cards.values():
            retained(card, name)
        samples[name] = state
        return state

    def observe_birth(card):
        name = card.name
        if name not in raws:
            return birth(card)
        assert name == active_name
        assert {key: getattr(card, key) for key in PHYSICAL} == expected[name]['physical']
        if sample_name == name:
            assert card.characteristic_record is None and card.zone == Zone.LIBRARY
            assert card.owner == card.controller == 1 and not card.summoning_sick
        else:
            assert name in samples and len(template_births[name]) == 8
            assert all(getattr(card, key) == value for key, value in poses[name].items())
            assert card.controller == poses[name]['owner'] and card.summoning_sick
            assert not card.tapped and card.instance_order == 0
            retained(card, name)
        birth(card)
        retained(card, name)
        (template_births if sample_name == name else pose_births)[name].append(card)

    def observe_allocate(state):
        result = allocate(state)
        if roots and state is roots[0]:
            allocations.append(result)
        return result

    def preserve_root(name, **pose):
        nonlocal active_name
        assert len(roots) == 1 and pose == poses[name] and name not in preserved and active_name is None
        before = pickle.dumps(roots[0], protocol=5)
        prior_allocations = list(allocations)
        active_name = name
        try:
            card = materialize(name, **pose)
        finally:
            active_name = None
        assert pickle.dumps(roots[0], protocol=5) == before and allocations == prior_allocations
        preserved[name] = card
        return card

    def before_snapshot(state, *args, **kwargs):
        if not roots or state is not roots[0] or 'deluge' not in state.cards or 'counter' not in state.cards:
            return snapshot(state, *args, **kwargs)
        assert admissions == list(SOURCES) and allocations == []
        assert set(normalized) == set(samples) == set(preserved) == set(raws)
        assert state.active_player == state.priority_player == seat and state.step == Step.DRAW
        assert not state.pregame_pending and state.kept_hands == {1, 2}
        assert state.players[seat].mana_pool['U'] == 7 and state.players[3-seat].mana_pool['U'] == 2
        for name, pose in poses.items():
            card = state.cards[pose['id']]
            assert card is preserved[name] and len(pose_births[name]) == 1 and card is pose_births[name][0]
            assert all(getattr(card, key) == value for key, value in pose.items())
            assert card.controller == pose['owner']
            assert getattr(state.players[pose['owner']], pose['zone'].value).count(card.id) == 1
            retained(card, name)
            assert card.summoning_sick and not card.tapped and not card.is_token
            assert card.counters == card.counter_timestamps == card.printed_characteristics == card.knowledge_snapshot == {}
            assert card.instance_order == card.static_order == card.effect_timestamp == 0
            assert card.entered_turn == card.zone_change_sequence == 0 and card.battlefield_incarnation is None
            assert len(template_births[name]) == 8
        raise BeforeSnapshot()

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_bytes', observe_provider)
        patch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_normalizer))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        patch.setattr(CardInstance, '__post_init__', observe_birth)
        patch.setattr(MatchState, 'allocate_object_id', observe_allocate)
        patch.setattr(original, '_paid_input_card', preserve_root)
        patch.setattr(original, 'serialize_match_snapshot', before_snapshot)
        with pytest.raises(BeforeSnapshot):
            original.test_actual_paid_flashback_and_counter_keep_native_announcement_after_snapshot(seat)
    assert original._paid_input_card is materialize and original.serialize_match_snapshot is snapshot
    assert CardInstance.__post_init__ is birth and MatchFactory.from_decks is factory
    assert MatchState.allocate_object_id is allocate and Path.read_bytes is provider
    assert all(official(name) == raw for name, raw in raws.items())
