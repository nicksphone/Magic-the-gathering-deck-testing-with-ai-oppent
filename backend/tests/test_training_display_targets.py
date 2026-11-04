"""Native canonical equip hints are presentation lists, not selected actions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from ai.information import decision_view
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.engine import RulesEngine
from training import decision_frame
from training.environment import decision_inputs_from_view


@pytest.fixture(scope='module')
def printed():
    path = Path(__file__).parent / 'fixtures/source_linked_exile/nadu-facts.json'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '0294012420cdfe63ebb65de78f6d8b783d6f160103af1c7360923776de4bd742'
    rows = json.loads(raw)
    selected = {name: rows[name] for name in ('Forest', 'Elvish Mystic', 'Shuko')}
    assert all(row['object'] == 'card' and row['oracle_id'] and len(row) > 40
               for row in selected.values())
    return selected


def position(printed, seat):
    deck = []
    for name, count in (('Forest', 54), ('Elvish Mystic', 3), ('Shuko', 3)):
        raw = printed[name]
        normalized = ScryfallSyncService._normalize_payload(raw, 'canonical-display-target-test')
        deck.append({**deepcopy(raw), **normalized, 'card_name': name, 'quantity': count,
                     'image_uri': None, 'card_faces': deepcopy(raw.get('card_faces', []))})
    state = MatchFactory.from_decks(deck, deck, seed=831)
    state.pregame_pending, state.kept_hands = False, {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
    placed = {}
    for name in ('Elvish Mystic', 'Shuko'):
        player = state.players[seat]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        card = state.cards[cid]
        card.move_to_zone(Zone.BATTLEFIELD)
        card.summoning_sick = False
        player.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        assert card.oracle_text == printed[name]['oracle_text']
        placed[name] = cid
    # Trusted canonical fixture relocation; all hints below are native-generated.
    assert len(state.cards) == 120
    return state, placed['Shuko'], placed['Elvish Mystic']


@pytest.mark.parametrize('seat', [1, 2])
def test_native_canonical_equip_target_list_frames_and_selected_action_roundtrips(printed, seat):
    state, equipment, creature = position(printed, seat)
    before, rng = serialize_match_snapshot(state), random.getstate()
    legal = RulesEngine().legal_moves(state, seat)
    hint = next(move for move in legal if move['type'] == 'equip' and move['card_id'] == equipment)
    assert type(hint['targets']) is list and hint['targets']
    assert creature in {target['id'] for target in hint['targets']}
    view, supplied = decision_view(state, seat, legal)
    observation, prompts, context = decision_inputs_from_view(view, supplied, seat)
    original = deepcopy((observation, prompts, context))
    frame, bindings = decision_frame.build_decision_frame(observation, prompts, public_context=context)
    mapped = next(prompt['hint'] for prompt in frame['prompts'] if prompt['hint']['type'] == 'equip')
    assert type(mapped['targets']) is list and len(mapped['targets']) == len(hint['targets'])
    chosen = {'type': 'equip', 'card_id': equipment, 'target_card_id': creature}
    aliased = bindings.action(chosen)
    assert bindings.actual_action(aliased) == chosen
    assert aliased['target_card_id'] in {target['id'] for target in mapped['targets']}
    assert decision_frame.encode_state(frame) and decision_frame.encode_action(frame, aliased)
    assert (observation, prompts, context) == original
    assert serialize_match_snapshot(state) == before and random.getstate() == rng


@pytest.mark.parametrize('value,expected', [
    ({}, 0), ({'targets': None}, 0), ({'targets': {}}, 0),
    ({'targets': []}, 0), ({'targets': [{'id': 'presentation-only'}]}, 0),
    ({'targets': {'selected_face_index': 1}}, 1),
    ({'selected_face_index': 0, 'targets': {'selected_face_index': 1}}, 0),
    ({'selected_face_index': 1, 'targets': [{'id': 'presentation-only'}]}, 1),
])
def test_face_reader_preserves_selected_scalar_and_mapping_precedence(value, expected):
    before = deepcopy(value)
    assert decision_frame._selected_face(value) == expected
    assert value == before


@pytest.mark.parametrize('targets', [False, 0, '', 'not-targets', ('not', 'JSON')])
def test_bare_face_reader_does_not_hide_other_malformed_target_types(targets):
    # Explicit malformed protocol controls, not printed card data or native hints.
    with pytest.raises(ValueError, match='target'):
        decision_frame._selected_face({'targets': targets})


@pytest.mark.parametrize('targets', [[], [{'id': 'presentation-only'}], False, 0, '', None])
def test_complete_selected_action_never_accepts_a_display_list_or_scalar(targets):
    action = {'type': 'cast_spell', 'card_id': 'protocol-only-source', 'targets': targets}
    before = deepcopy(action)
    with pytest.raises(ValueError, match='Complete action schema mismatch'):
        decision_frame._normalize(action)
    assert action == before


@pytest.mark.parametrize('location', ['top', 'nested'])
@pytest.mark.parametrize('face', [True, '1', 1.0, -1])
def test_complete_selected_face_schema_remains_strict(location, face):
    action = {'type': 'cast_spell', 'card_id': 'protocol-only-source', 'targets': {}}
    if location == 'top':
        action['selected_face_index'] = face
    else:
        action['targets']['selected_face_index'] = face
    with pytest.raises(ValueError, match='Complete action schema mismatch'):
        decision_frame._normalize(action)
