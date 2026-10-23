"""Observe full Master printing before native birth and the existing Ice action."""
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone, _infer_keywords
from rules_engine.card_types import printed_card_types
from tests import test_split_card_casts as original


RAW_PATH = Path(__file__).parent / 'fixtures/task13_master_of_waves/master-of-waves.raw.json'
RAW_SHA = 'c7be64947fe52c83bc9002601f60a34b55e598b5e921c050acb071744f28c411'


def official():
    encoded = RAW_PATH.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == RAW_SHA
    raw = json.loads(encoded)
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id'], len(raw)) == (
        'card', 'Master of Waves', '14cd5387-c6aa-4430-8edb-05da6b4e2ff5',
        '07d40173-53e7-4328-a3b0-6214d93855b6', 65)
    return raw


def test_original_master_has_full_print_before_birth_and_checked_ice(monkeypatch):
    raw = official()
    expected = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors')}
    expected.update(types=printed_card_types(raw['type_line']), power=int(raw['power']),
                    toughness=int(raw['toughness']), printed_power=raw['power'],
                    printed_toughness=raw['toughness'], loyalty=None,
                    keywords=_infer_keywords(raw['oracle_text']))
    physical = {**expected, 'layout': raw['layout'], 'card_faces': raw.get('card_faces', []),
                'selected_face_index': None, 'image_uri': None}
    normalize = ScryfallSyncService._normalize_payload
    factory = MatchFactory.from_decks
    birth = CardInstance.__post_init__
    materialize = original._master_of_waves_card
    checked = original.checked_action
    states, raw_seen, admitted, born, preserved, consumed = [], [], [], [], [], []

    class BeforeCheckedIce(BaseException):
        pass

    def observe_raw(cls, incoming, image_uri, rulings=None):
        if incoming.get('name') == raw['name']:
            assert incoming == raw
            assert image_uri == 'unused:master-fixture-display'
            raw_seen.append(raw['id'])
        return normalize(incoming, image_uri, rulings)

    def observe_factory(first, second, *args, **kwargs):
        if first and first[0].get('name') == raw['name']:
            assert len(first) == 1 and first[0]['quantity'] == 8
            assert second == [] and args == () and kwargs == {'seed': 0}
            assert all(first[0].get(key) == value for key, value in raw.items())
            admitted.append(True)
        state = factory(first, second, *args, **kwargs)
        states.append(state)
        return state

    def retained(card):
        assert card.characteristic_record == {'version': 1, 'physical': physical, 'values': expected}

    def observe_birth(card):
        target = card.id == 'master' and card.name == raw['name']
        if target:
            assert raw_seen == [raw['id']] and admitted == [True]
            assert {key: getattr(card, key) for key in physical} == physical
        birth(card)
        if target:
            retained(card)
            born.append(card.id)

    def preserve_scene():
        assert len(states) == 1
        before = pickle.dumps(states[0], protocol=5)
        card = materialize()
        assert len(states) == 2 and pickle.dumps(states[0], protocol=5) == before
        preserved.append(True)
        return card

    def before_checked(state, engine, player_id, action, *args, **kwargs):
        if 'master' not in state.cards:
            return checked(state, engine, player_id, action, *args, **kwargs)
        assert state is states[0]
        card = state.cards['master']
        retained(card)
        assert {key: getattr(card, key) for key in physical} == physical
        assert card.owner == card.controller == 2 and card.zone == Zone.BATTLEFIELD
        assert 'master' in state.players[2].battlefield
        assert card.summoning_sick and not card.tapped and not card.is_token
        assert card.counters == card.counter_timestamps == {}
        assert card.instance_order == card.static_order == card.effect_timestamp == 0
        assert card.entered_turn == card.zone_change_sequence == 0
        assert card.battlefield_incarnation is None and card.knowledge_snapshot == {}
        assert player_id == 1 and action['type'] == 'cast_spell'
        assert action['selected_face_index'] == 1 and action['targets'] == {'target_card_id': 'master'}
        assert raw_seen == [raw['id']] and admitted == preserved == [True] and born == ['master']
        consumed.append(card.id)
        raise BeforeCheckedIce()

    with monkeypatch.context() as patch:
        patch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_raw))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        patch.setattr(CardInstance, '__post_init__', observe_birth)
        patch.setattr(original, '_master_of_waves_card', preserve_scene)
        patch.setattr(original, 'checked_action', before_checked)
        with pytest.raises(BeforeCheckedIce):
            original.test_split_face_color_fallback_does_not_inherit_the_other_halfs_color()
    assert consumed == ['master'] and official() == raw
