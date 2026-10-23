"""Real four-card admission and later banding loss; no substitute rule actions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, MatchState, Zone
from rules_engine.continuous import has_keyword
from tests import browser_positive83_canonical as canonical
from tests import test_attack_bands as original


FIXTURES = Path(__file__).parent / 'fixtures'
COPY_FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
               'printed_power', 'printed_toughness', 'loyalty', 'oracle_text',
               'keywords', 'colors')
SCENE = (('hero', 'Benalish Hero', 1), ('angel', 'Serra Angel', 1),
         ('elf', 'Llanowar Elves', 1), ('bears', 'Grizzly Bears', 2))
RAW_SOURCES = {
    'Benalish Hero': ('browser_inline26/canonical.jsonl', 21, 64,
        '3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd',
        '356d1650da2b8e59dfa746ecc75ced900b52fd4ca8aa7ecbb9dc4f8be8a9c720'),
    'Serra Angel': ('browser_inline26/canonical.jsonl', 20, 66,
        '3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd',
        'c4db702f81d92880abb48c0dc1170bb863c8666ce5b5087c7dde8e0c49c61e97'),
    'Llanowar Elves': ('knowledge_profiles/seed155-scryfall.jsonl', 58, 71,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '20502422d100f66319395df76ac611f2bec8935eb35f01dc41ef9ebc0bf6e569'),
    'Grizzly Bears': ('ai_terminal_draw/grizzly-bears.raw.json', None, 66,
        '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c',
        '51502b289cb9e4a4d728f79c701295f3dc36b52fb84fad902af79af9fe33afa0'),
}


def official(name):
    path, line, fields, file_sha, object_sha = RAW_SOURCES[name]
    data = (FIXTURES / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == file_sha
    raw = json.loads(data.splitlines()[line - 1] if line else data)
    assert (raw['object'], raw['name'], len(raw)) == ('card', name, fields)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == object_sha
    return raw


def printed(raw):
    return {
        'name': raw['name'], 'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
        'types': ['Creature'], 'power': int(raw['power']), 'toughness': int(raw['toughness']),
        'printed_power': raw['power'], 'printed_toughness': raw['toughness'], 'loyalty': None,
        'oracle_text': raw['oracle_text'], 'keywords': [k.lower() for k in raw['keywords']],
        'colors': raw['colors'], 'card_faces': raw.get('card_faces', []), 'layout': raw['layout'],
        'selected_face_index': None, 'image_uri': None,
    }


def assert_record(card, expected):
    assert type(card.characteristic_record['version']) is int
    assert card.characteristic_record == {
        'version': 1, 'physical': expected,
        'values': {key: expected[key] for key in COPY_FIELDS},
    }


def test_all_four_original_band_inputs_have_full_print_before_birth_and_action(monkeypatch):
    raws = {name: official(name) for _, name, _ in SCENE}
    expected = {name: printed(raw) for name, raw in raws.items()}
    poses = {name: dict(id=cid, owner=seat, controller=seat, zone=Zone.BATTLEFIELD,
                       summoning_sick=False) for cid, name, seat in SCENE}
    read_raw, normalize = canonical.raw_card, ScryfallSyncService._normalize_payload
    factory, birth = MatchFactory.from_decks, CardInstance.__post_init__
    allocate, materialize, checked = MatchState.allocate_object_id, original.canonical_card, original.checked_action
    roots, admissions, normalized, samples, allocations, preserved = [], [], {}, {}, [], {}
    template_births = {name: [] for name in raws}
    pose_births = {name: [] for name in raws}
    sample_name = None

    class BeforeAction(BaseException):
        pass

    def observe_raw(name):
        raw = read_raw(name)
        assert raw == raws[name] and len(raw) == RAW_SOURCES[name][2]
        admissions.append(name)
        return raw

    def observe_normalizer(cls, incoming, image_uri, rulings=None):
        name = incoming.get('name')
        if name in raws:
            assert incoming == raws[name] and admissions.count(name) == 1
            assert image_uri == 'unused:browser-fixture-display' and name not in normalized
        result = normalize(incoming, image_uri, rulings)
        if name in raws:
            assert result['scryfall_id'] == raws[name]['id']
            normalized[name] = deepcopy(result)
        return result

    def observe_factory(first, second, *args, **kwargs):
        nonlocal sample_name
        name = first[0].get('card_name') if first else None
        if name not in raws:
            assert not roots and first == second == [{'quantity': 60, 'card_name': 'Island'}]
            assert args == () and kwargs == {'seed': 81}
            state = factory(first, second, *args, **kwargs)
            roots.append(state)
            return state
        entry = {**raws[name], **normalized[name], 'card_name': name, 'quantity': 8,
                 'image_uri': None, 'colors': raws[name]['colors'],
                 'card_faces': raws[name].get('card_faces', [])}
        assert first == [entry] and second == [] and args == () and kwargs == {'seed': 0}
        assert sample_name is None and name not in samples
        sample_name = name
        try:
            state = factory(first, second, *args, **kwargs)
        finally:
            sample_name = None
        assert len(state.cards) == len(template_births[name]) == 8
        assert len(state.players[1].library) == 1
        for card in state.cards.values():
            assert_record(card, expected[name])
        samples[name] = state
        return state

    def observe_birth(card):
        name = card.name
        if name not in raws:
            return birth(card)
        assert {key: getattr(card, key) for key in expected[name]} == expected[name]
        if sample_name == name:
            assert card.characteristic_record is None and card.zone == Zone.LIBRARY
            assert card.owner == card.controller == 1 and card.summoning_sick
        else:
            assert name in samples and len(template_births[name]) == 8
            assert all(getattr(card, key) == value for key, value in poses[name].items())
            assert_record(card, expected[name])
        birth(card)
        assert_record(card, expected[name])
        (template_births if sample_name == name else pose_births)[name].append(card.id)

    def observe_allocate(state):
        result = allocate(state)
        if roots and state is roots[0]:
            allocations.append(result)
        return result

    def preserve_root(name, **pose):
        assert len(roots) == 1 and pose == poses[name] and name not in preserved
        before = pickle.dumps(roots[0], protocol=5)
        prior_allocations = list(allocations)
        card = materialize(name, **pose)
        assert pickle.dumps(roots[0], protocol=5) == before and allocations == prior_allocations
        preserved[name] = card
        return card

    def before_action(state, rules, player_id, action):
        assert len(roots) == 1 and state is roots[0] and player_id == 1
        assert action == {'type': 'attack', 'attackers': ['hero', 'angel'], 'bands': [['hero', 'angel']]}
        assert admissions == [name for _, name, _ in SCENE] and allocations == []
        assert set(normalized) == set(samples) == set(preserved) == set(raws)
        for cid, name, seat in SCENE:
            card = state.cards[cid]
            assert card is preserved[name] and card.owner == card.controller == seat
            assert card.id == cid and card.zone == Zone.BATTLEFIELD
            assert state.players[seat].battlefield.count(cid) == 1
            assert {key: getattr(card, key) for key in expected[name]} == expected[name]
            assert_record(card, expected[name])
            assert not card.summoning_sick and not card.tapped and not card.is_token
            assert card.counters == card.counter_timestamps == card.printed_characteristics == {}
            assert card.keyword_effects == card.base_stat_effects == card.type_effects == card.control_effects == []
            assert card.instance_order == card.static_order == card.effect_timestamp == 0
            assert card.entered_turn == card.zone_change_sequence == 0
            assert card.battlefield_incarnation is None and card.knowledge_snapshot == {}
            assert len(template_births[name]) == 8 and pose_births[name] == [cid]
        raise BeforeAction()

    with monkeypatch.context() as patch:
        patch.setattr(canonical, 'raw_card', observe_raw)
        patch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_normalizer))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        patch.setattr(CardInstance, '__post_init__', observe_birth)
        patch.setattr(MatchState, 'allocate_object_id', observe_allocate)
        patch.setattr(original, 'canonical_card', preserve_root)
        patch.setattr(original, 'checked_action', before_action)
        with pytest.raises(BeforeAction):
            original.test_attack_band_survives_snapshot_and_propagates_block_to_flyer()
    assert original.canonical_card is materialize and original.checked_action is checked
    assert canonical.raw_card is read_raw and CardInstance.__post_init__ is birth
    assert MatchFactory.from_decks is factory and MatchState.allocate_object_id is allocate
    assert all(official(name) == raw for name, raw in raws.items())


def test_original_band_survives_real_keyword_loss_and_real_blocker_operation(monkeypatch):
    raw = official('Benalish Hero')
    expected = printed(raw)
    declare = original.combat.declare_blockers
    observed = []

    def observe_blockers(state, blockers):
        hero = state.cards['hero']
        assert blockers == {'hero': ['bears']} and state.attack_bands == [['hero', 'angel']]
        assert hero.keywords == [] and not has_keyword(state, 'hero', 'banding')
        assert hero.oracle_text == raw['oracle_text']
        assert_record(hero, expected)
        record = deepcopy(hero.characteristic_record)
        result = declare(state, blockers)
        assert state.blocks == {'hero': ['bears'], 'angel': ['bears']}
        assert hero.characteristic_record == record and not has_keyword(state, 'hero', 'banding')
        observed.append(state)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(original.combat, 'declare_blockers', observe_blockers)
        original.test_band_persists_when_banding_lost_after_declaration()
    assert len(observed) == 1 and original.combat.declare_blockers is declare
    assert official('Benalish Hero') == raw
