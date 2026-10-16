"""Genuine Factory input context, before any printed-characteristic capture."""
from copy import deepcopy

import pytest

from effects.handlers import return_permanent_to_hand, transform_card
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_keyword_zone4f86_fidelity import deck_entry, raw_card
import tests.test_zone_object_reset as original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit_front', [False, True])
def test_genuine_factory_implicit_and_explicit_front_survive_cast_transform_bounce(
        seat, explicit_front):
    printed = raw_card('Delver of Secrets')
    entry = deck_entry('Delver of Secrets', 8)
    if explicit_front:
        entry['selected_face_index'] = 0
    selector = 0 if explicit_front else None
    raw_before = deepcopy(printed)
    other = deck_entry('Forest', 8)
    decks = ([entry], [other]) if seat == 1 else ([other], [entry])
    state = MatchFactory.from_decks(*decks, seed=17)
    source = next(card for card in state.cards.values()
                  if card.owner == seat and card.zone == Zone.HAND)
    assert source.selected_face_index == selector
    assert source.printed_characteristics['selected_face_index'] == selector
    assert source.characteristic_record['physical']['selected_face_index'] == selector
    assert source.name == printed['card_faces'][0]['name']
    assert [face['name'] for face in source.card_faces] == [
        face['name'] for face in printed['card_faces']]

    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].mana_pool['U'] = 1
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move['card_id'] == source.id)
    state = checked_action(state, engine, seat, move)
    assert state.players[seat].mana_pool['U'] == 0
    assert resolve_top_of_stack(state)
    source = state.cards[source.id]
    assert source.zone == Zone.BATTLEFIELD
    transform_card(state, seat, {'target_card_id': source.id, 'face_index': 1})
    assert source.selected_face_index == 1
    assert source.name == printed['card_faces'][1]['name']
    return_permanent_to_hand(state, 3-seat, {'target_card_id': source.id})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state)).cards[source.id]
    front = printed['card_faces'][0]
    assert restored.zone == Zone.HAND and restored.selected_face_index == selector
    assert (restored.name, restored.oracle_text, restored.mana_cost, restored.type_line,
            restored.power, restored.toughness) == (
        front['name'], front['oracle_text'], front['mana_cost'], front['type_line'],
        int(front['power']), int(front['toughness']))
    assert [face['name'] for face in restored.card_faces] == [
        face['name'] for face in printed['card_faces']]
    assert printed == raw_before == raw_card('Delver of Secrets')


def test_original_birth_requests_explicit_front_before_factory_capture(monkeypatch):
    state = original._state()
    real_factory = MatchFactory.from_decks
    observed = []

    def capture(deck_a, deck_b, *args, **kwargs):
        assert not deck_b and len(deck_a) == 1
        entry = deck_a[0]
        observed.append(deepcopy(entry))
        assert entry['card_name'] == 'Delver of Secrets // Insectile Aberration'
        assert entry.get('selected_face_index') == 0
        assert [face['name'] for face in entry['card_faces']] == [
            face['name'] for face in raw_card('Delver of Secrets')['card_faces']]
        sample = real_factory(deck_a, deck_b, *args, **kwargs)
        for card in sample.cards.values():
            assert card.selected_face_index == 0
            assert card.printed_characteristics['selected_face_index'] == 0
            assert card.characteristic_record['physical']['selected_face_index'] == 0
        return sample

    class BirthCaptured(BaseException):
        pass

    class Cards(dict):
        def __setitem__(self, key, value):
            assert key == 'delver' and value.selected_face_index == 0
            assert value.printed_characteristics['selected_face_index'] == 0
            raise BirthCaptured

    state.cards = Cards(state.cards)
    monkeypatch.setattr(original, '_state', lambda: state)
    monkeypatch.setattr(MatchFactory, 'from_decks', capture)
    with pytest.raises(BirthCaptured):
        original.test_transformed_card_returns_to_printed_front_face_after_bounce()
    assert len(observed) == 1
