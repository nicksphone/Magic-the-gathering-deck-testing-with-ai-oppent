"""Second original Lockdown birth; genuine first entry, stop before second entry."""
from copy import deepcopy

import pytest

from game_state.state import CardInstance, Zone
from tests import test_linked_exile as original
from tests.test_linked_lockdown_birth_fidelity import exact, official, physical


def test_second_original_lockdown_has_full_print_before_native_capture(monkeypatch):
    raw = official()
    assert len(raw) == 65
    expected = physical(raw)
    # Preserve this second permanent's original display policy, unlike the first.
    expected['image_uri'] = None
    copiable = {key: value for key, value in expected.items()
                if key not in {'card_faces', 'layout', 'selected_face_index', 'image_uri'}}
    read_raw, birth, resolve_entry = original.raw_card, CardInstance.__post_init__, original._resolve_entry
    admitted, born, entries, states = [], [], [], []

    class BeforeSecondEntry(BaseException):
        pass

    def observe_raw(name):
        result = read_raw(name)
        exact(result, raw, 'admitted_raw')
        assert len(result) == 65
        admitted.append(result)
        return result

    def assert_print(card, *, captured):
        exact({key: getattr(card, key) for key in expected}, expected, 'second_live')
        if captured:
            exact(card.characteristic_record,
                  {'version': 1, 'physical': expected, 'values': copiable}, 'second_record')
        else:
            assert card.characteristic_record is None
        assert card.id == 'second-lockdown' and card.owner == card.controller == 2
        assert card.zone == Zone.BATTLEFIELD
        assert card.summoning_sick and not card.tapped and not card.is_token
        assert card.counters == card.counter_timestamps == {}
        assert card.instance_order == card.entered_turn == card.zone_change_sequence == 0
        assert card.printed_characteristics == card.knowledge_snapshot == {}

    def observe_birth(card):
        target = card.id == 'second-lockdown'
        if target:
            assert entries == ['first-returned'] and len(admitted) == 2 and len(states) == 1
            assert 'second-lockdown' not in states[0].cards
            assert_print(card, captured=False)
            assert card.static_order == card.effect_timestamp == 0
            assert card.battlefield_incarnation is None
            assert card.colors is not admitted[1]['colors']
            assert card.keywords is not admitted[1]['keywords']
        birth(card)
        if target:
            assert_print(card, captured=True)
            for key in ('colors', 'keywords', 'card_faces'):
                assert card.characteristic_record['physical'][key] is not getattr(card, key)
            born.append(card)

    def observe_entry(state, source):
        if not entries:
            assert source.id == 'lockdown' and len(admitted) == 1 and not born
            assert 'second-lockdown' not in state.cards
            states.append(state)
            result = resolve_entry(state, source)
            assert state.cards['first-held'].zone == Zone.EXILE
            assert len(state.linked_exiles) == 1
            assert set(state.linked_exiles[0]['card_ids']) == {'first-held'}
            entries.append('first-returned')
            return result
        assert entries == ['first-returned'] and state is states[0]
        assert len(born) == 1 and source is born[0] and state.cards[source.id] is source
        assert_print(source, captured=True)
        assert source.id in state.players[2].battlefield
        assert source.static_order == source.effect_timestamp == source.battlefield_incarnation > 0
        assert state.cards['lockdown'].zone == Zone.BATTLEFIELD
        assert state.cards['first-held'].zone == Zone.EXILE
        assert state.cards['second-held'].zone == Zone.BATTLEFIELD
        assert len(state.linked_exiles) == 1 and len(admitted) == 2
        for admitted_raw in admitted:
            exact(admitted_raw, raw, 'raw_unchanged')
        entries.append('second-stopped')
        raise BeforeSecondEntry()

    with monkeypatch.context() as patch:
        patch.setattr(original, 'raw_card', observe_raw)
        patch.setattr(CardInstance, '__post_init__', observe_birth)
        patch.setattr(original, '_resolve_entry', observe_entry)
        with pytest.raises(BeforeSecondEntry):
            original.test_two_sources_leaving_together_return_both_sets()
    assert entries == ['first-returned', 'second-stopped'] and len(born) == 1
    assert original.raw_card is read_raw and CardInstance.__post_init__ is birth
    assert original._resolve_entry is resolve_entry
    exact(official(), raw, 'official_unchanged')
