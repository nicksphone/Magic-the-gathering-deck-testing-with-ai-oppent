"""Real native construction witnesses, not certificates of a genuine death."""
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from game_state.state import CardInstance, MatchFactory, Zone
from tests import test_events_apnap as original


RAW_PATH = Path(__file__).parent / 'fixtures/task13_seal_of_removal/seal-of-removal.raw.json'
RAW_SHA = '6b02efedebb98eebb89bb16b9fdcb80305623dc29cf74de4a5fbf571cdc7b793'


@pytest.mark.parametrize('seat,function', [
    (1, 'test_permanent_dies_trigger_matches_noncreature_permanent'),
    (2, 'test_permanent_dies_trigger_does_not_match_opponent_permanent'),
])
def test_seal_support_has_full_print_before_native_birth_and_event(monkeypatch, seat, function):
    encoded = RAW_PATH.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == RAW_SHA
    raw = json.loads(encoded)
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id'], len(raw)) == (
        'card', 'Seal of Removal', '6dfc7060-e374-486f-8029-d3fdfe4b61e7',
        'f0801029-bcf7-4bdb-84bf-e88dcaa9dc03', 66)
    expected = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors', 'layout')}
    expected.update(types=['Enchantment'], keywords=[], power=None, toughness=None,
                    printed_power=None, printed_toughness=None, loyalty=None,
                    card_faces=[], selected_face_index=None)
    factory, post_init = MatchFactory.from_decks, CardInstance.__post_init__
    materialize, event = original._seal_of_removal_card, original.emit_event
    states, raw_seen, births, state_preserved = [], [], [], []

    class BeforeEvent(BaseException):
        pass

    def capture_factory(first, second, *args, **kwargs):
        full = bool(first and first[0].get('object') == 'card')
        if full:
            assert all(first[0].get(key) == value for key, value in raw.items())
            assert len(first) == 1 and first[0]['quantity'] == 8
            assert second == [] and args == () and kwargs == {'seed': 0}
            raw_seen.append(raw['id'])
        result = factory(first, second, *args, **kwargs)
        if not full:
            states.append(result)
        return result

    def retained(card):
        assert card.characteristic_record is not None
        assert {key: card.characteristic_record['physical'][key] for key in expected} == expected
        copiable = {key: value for key, value in expected.items()
                    if key not in {'layout', 'card_faces', 'selected_face_index'}}
        assert card.characteristic_record['values'] == copiable

    def capture_birth(card):
        target = card.id == 'dead' and card.name == raw['name']
        if target:
            assert {key: getattr(card, key) for key in expected} == expected
            assert raw_seen == [raw['id']]
        post_init(card)
        if target:
            retained(card)
            births.append(card.id)

    def preserve_original(owner):
        assert owner == seat and len(states) == 1
        before = pickle.dumps(states[0])
        card = materialize(owner)
        assert pickle.dumps(states[0]) == before
        state_preserved.append(True)
        return card

    def before_event(state, kind, payload):
        if kind != 'permanent_dies' or payload.get('card_id') != 'dead':
            return event(state, kind, payload)
        card = state.cards['dead']
        retained(card)
        assert {key: getattr(card, key) for key in expected} == expected
        assert card.owner == card.controller == seat and card.zone == Zone.GRAVEYARD
        assert card.summoning_sick and not card.tapped and card.counters == {}
        assert card.instance_order == card.static_order == card.effect_timestamp == 0
        assert card.image_uri is None and births == ['dead'] and state_preserved == [True]
        # Preserve this original direct-event unit pose; do not fabricate a death.
        assert 'dead' not in state.players[seat].graveyard
        raise BeforeEvent()

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(capture_factory))
        patch.setattr(CardInstance, '__post_init__', capture_birth)
        patch.setattr(original, '_seal_of_removal_card', preserve_original)
        patch.setattr(original, 'emit_event', before_event)
        with pytest.raises(BeforeEvent):
            getattr(original, function)()
    assert RAW_PATH.read_bytes() == encoded
