"""Native printed-support witnesses; not split-spell or AI outcome certificates."""
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.engine import RulesEngine
from tests import test_split_card_casts as original


TESTS = Path(__file__).parent
RAW_SOURCES = {
    'Island': (
        'fixtures/knowledge_profiles/seed155-scryfall.jsonl', 50, 60,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '932ef67074504645e2ddf2ceefcb9e65aa3b6938c6f6c42cb226dbdbe5b30d6b',
        '1335d293-3dd2-4f13-bd2c-22181f4528ee', 'b2c6aa39-2d2a-459c-a555-fb48ba993373'),
    'Grizzly Bears': (
        'vraska_full/fixtures/grizzly-bears-scryfall-raw.json', None, 66,
        '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c',
        '51502b289cb9e4a4d728f79c701295f3dc36b52fb84fad902af79af9fe33afa0',
        '409f9b88-f03e-40b6-9883-68c14c37c0de', '14c8f55d-d177-4c25-a931-ebeb9e6062a0'),
}


def official(name):
    path, line, fields, file_sha, row_sha, identifier, oracle_id = RAW_SOURCES[name]
    encoded = (TESTS / path).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == file_sha
    raw = json.loads(encoded.splitlines()[line - 1] if line else encoded)
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id'], len(raw)) == (
        'card', name, identifier, oracle_id, fields)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == row_sha
    return raw


@pytest.mark.parametrize('function,name,identifier,args', [
    ('test_ice_half_taps_target_and_draws_with_blue_mana', 'Island', 'target-island', ()),
    ('test_opponent_turn_only_offers_instant_half', 'Grizzly Bears', 'target-creature', ()),
    ('test_fire_rejects_more_than_two_announced_recipients', 'Grizzly Bears', 'third-target', ()),
    ('test_ai_materializes_a_castable_split_half', 'Island', 'target-island',
     ('Fire', {'C': 1, 'R': 1})),
    ('test_ai_materializes_a_castable_split_half', 'Island', 'target-island',
     ('Ice', {'C': 1, 'U': 1})),
])
def test_original_support_has_full_print_before_birth_and_menu(
        monkeypatch, function, name, identifier, args):
    raw = official(name)
    expected = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors')}
    expected.update(types=['Land'] if name == 'Island' else ['Creature'], keywords=[],
                    power=int(raw['power']) if 'power' in raw else None,
                    toughness=int(raw['toughness']) if 'toughness' in raw else None,
                    printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                    loyalty=None)
    normalizer = ScryfallSyncService._normalize_payload
    factory, birth = MatchFactory.from_decks, CardInstance.__post_init__
    materialize, legal = original.canonical_card, RulesEngine.legal_moves
    states, raw_seen, births, preserved = [], [], [], []

    class BeforeMenu(BaseException):
        pass

    def observe_raw(cls, incoming, image_uri, rulings=None):
        if incoming.get('name') == name:
            assert incoming == raw
            raw_seen.append(raw['id'])
        return normalizer(incoming, image_uri, rulings)

    def observe_factory(*positional, **keywords):
        state = factory(*positional, **keywords)
        states.append(state)
        return state

    def retained(card):
        record = card.characteristic_record
        assert record is not None and record['version'] == 1
        assert record['values'] == expected
        assert {key: record['physical'][key] for key in expected} == expected
        assert record['physical']['layout'] == raw['layout']
        assert record['physical']['card_faces'] == raw.get('card_faces', [])
        assert record['physical']['selected_face_index'] is None
        # The existing canonical helper owns display policy, not the original pose.
        assert record['physical']['image_uri'] == card.image_uri

    def observe_birth(card):
        target = card.id == identifier and card.name == name
        if target:
            assert {key: getattr(card, key) for key in expected} == expected
            assert card.layout == raw['layout'] and card.card_faces == raw.get('card_faces', [])
            assert raw_seen == [raw['id']]
        birth(card)
        if target:
            retained(card)
            births.append(card.id)

    def preserve_state(card_name, **pose):
        assert card_name == name and pose == dict(
            id=identifier, owner=2, controller=2, zone=Zone.BATTLEFIELD)
        assert len(states) == 1
        before = pickle.dumps(states[0], protocol=5)
        card = materialize(card_name, **pose)
        assert pickle.dumps(states[0], protocol=5) == before
        preserved.append(True)
        return card

    def before_menu(engine, state, player_id):
        if identifier not in state.cards or state.cards[identifier].name != name:
            return legal(engine, state, player_id)
        assert state is states[0]
        card = state.cards[identifier]
        retained(card)
        assert {key: getattr(card, key) for key in expected} == expected
        assert card.owner == card.controller == 2 and card.zone == Zone.BATTLEFIELD
        assert identifier in state.players[2].battlefield
        assert card.summoning_sick and not card.tapped and not card.is_token
        assert card.counters == card.counter_timestamps == {}
        assert card.instance_order == card.static_order == card.effect_timestamp == 0
        assert card.entered_turn == card.zone_change_sequence == 0
        assert raw_seen == [raw['id']] and births == [identifier] and preserved == [True]
        raise BeforeMenu()

    with monkeypatch.context() as patch:
        patch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_raw))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        patch.setattr(CardInstance, '__post_init__', observe_birth)
        patch.setattr(original, 'canonical_card', preserve_state)
        patch.setattr(RulesEngine, 'legal_moves', before_menu)
        with pytest.raises(BeforeMenu):
            getattr(original, function)(*args)
    assert official(name) == raw
