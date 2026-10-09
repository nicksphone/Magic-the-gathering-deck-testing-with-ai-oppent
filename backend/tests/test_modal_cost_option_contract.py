"""Actual canonical move views; callback controls are protocol, not paid-rule proof."""
import pytest
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.card_faces import select_cast_face
from rules_engine import casting_resources, move_generator
from tests.modal_contract_support import canonical_fixture

@pytest.mark.parametrize('face_kind', ['', 'adventure'])
def test_actual_face_cost_options_use_public_wire_view(face_kind):
    state = canonical_fixture(face_kind)
    before = serialize_match_snapshot(state)
    moves = [m for m in RulesEngine().legal_moves(state, 2)
             if m['type'] == 'cast_spell' and m.get('selected_face_index') == 1]
    assert moves
    for move in moves:
        face = select_cast_face(state.cards[move['card_id']], 1)
        for option in move['cost_options']:
            assert option['mana_cost'] == face.mana_cost
            assert option['discard_cards'] == option['sacrifice_creatures'] == 0
            assert 'hand_exile_color' not in option
            assert 'hand_exile_generic_reduction' not in option
            assert isinstance(option['hybrid_symbols'], list)
    assert serialize_match_snapshot(state) == before

@pytest.mark.parametrize('face_kind', ['', 'adventure'])
def test_cost_view_callbacks_read_selected_face_without_mutating_source(face_kind, monkeypatch):
    state = canonical_fixture(face_kind)
    before = serialize_match_snapshot(state)
    original_view = move_generator._cost_option_view
    original_keywords = casting_resources.resource_keywords
    observed = []
    def traced(option, *args, **kwargs):
        with monkeypatch.context() as context:
            def keywords(card):
                observed.append((card.id, card.name, card.oracle_text))
                return original_keywords(card)
            context.setattr(casting_resources, 'resource_keywords', keywords)
            return original_view(option, *args, **kwargs)
    monkeypatch.setattr(move_generator, '_cost_option_view', traced)
    moves = [m for m in RulesEngine().legal_moves(state, 2)
             if m['type'] == 'cast_spell' and m.get('selected_face_index') == 1]
    assert moves
    for move in moves:
        face = select_cast_face(state.cards[move['card_id']], 1)
        assert (face.id, face.name, face.oracle_text) in observed
    assert serialize_match_snapshot(state) == before
