"""Canonical granted-action AI interfaces, not numerical NN or policy quality."""
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from training.decision_frame import build_decision_frame, encode_action, encode_state
from training.environment import decision_inputs_from_view
from tests.test_saga_land_entry import position, add, act, settle


@pytest.fixture(autouse=True)
def owned_media_cache(monkeypatch, tmp_path):
    from card_data import placeholders, token_images, sync
    owned = tmp_path/'images'
    for module in (placeholders, token_images, sync):
        monkeypatch.setattr(module, 'CACHE_DIR', owned)
    monkeypatch.setattr(token_images, '_INDEX_FILE', owned/'token-index.json')
    monkeypatch.setattr(token_images, '_TOKEN_IMAGE_CACHE', {})


def saga_position(seat, chapter):
    state = position(seat)
    # Controlled initial canonical relocation only; conserve the entire corpus.
    count = len(state.cards)
    for cid in list(state.players[seat].battlefield)[2:]:
        state.players[seat].battlefield.remove(cid)
        state.players[seat].library.append(cid)
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    assert len(state.cards) == count
    saga = add(state, "Urza's Saga", seat, Zone.HAND)
    state = act(state, seat, {'type': 'play_land', 'card_id': saga})
    assert state.cards[saga].counters.get('__lore') == 1
    assert any(item.source_card_id == saga and item.payload.get('__chapter_number') == 1
               for item in state.stack)
    state = settle(state)
    if chapter == 2:
        for _ in range(240):
            if any(item.source_card_id == saga and item.payload.get('__chapter_number') == 2
                   for item in state.stack):
                break
            assert not (state.pending_mechanic_choice or state.pending_replacement_choice)
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        else:
            raise AssertionError('Native chapter II was not reached')
        assert state.cards[saga].counters.get('__lore') == 2
        state = settle(state)
    assert state.priority_player == seat
    assert state.cards[saga].oracle_text.startswith('(As this Saga enters')
    return state, saga


def selected_grant(state, seat, saga, chapter):
    legal = RulesEngine().legal_moves(state, seat)
    kind = 'activate_mana_ability' if chapter == 1 else 'activate_ability'
    offered = [move for move in legal if move['type'] == kind and move.get('card_id') == saga]
    assert len(offered) == 1, 'The genuine resolved grant must be natively offered'
    hint = offered[0]
    assert hint['ability_index'] == (100 if chapter == 1 else 99)
    if chapter == 1:
        action = {key: deepcopy(hint[key]) for key in
                  ('type', 'card_id', 'ability_index', 'color', 'output_bundle')}
    else:
        action = {'type': kind, 'card_id': saga, 'ability_index': hint['ability_index'], 'targets': {}}
    return legal, action


def frame_action(state, seat, legal, action):
    view, supplied = decision_view(state, seat, legal)
    view_before, moves_before = serialize_match_snapshot(view), deepcopy(supplied)
    observation, prompts, context = decision_inputs_from_view(view, supplied, seat)
    before = deepcopy((observation, prompts, context))
    frame, bindings = build_decision_frame(observation, prompts, public_context=context)
    aliased = bindings.action(action)
    assert bindings.actual_action(aliased) == action
    assert aliased['ability_index'] == action['ability_index']
    assert any(p['hint'].get('type') == action['type']
               and p['hint'].get('card_id') == aliased['card_id']
               and p['hint'].get('ability_index') == action['ability_index'] for p in frame['prompts'])
    encoded_state, encoded_action = encode_state(frame), encode_action(frame, aliased)
    assert encoded_state and encoded_action
    assert (observation, prompts, context) == before
    assert serialize_match_snapshot(view) == view_before and supplied == moves_before
    return frame, aliased, encoded_state, encoded_action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('chapter', [1, 2])
def test_genuine_granted_action_frame_binding_and_symbolic_encoding(seat, chapter):
    state, saga = saga_position(seat, chapter)
    before, rng, local = serialize_match_snapshot(state), random.getstate(), state.rng.getstate()
    legal, action = selected_grant(state, seat, saga, chapter)
    saved_legal, saved_action = deepcopy(legal), deepcopy(action)
    first = frame_action(state, seat, legal, action)
    checked_action(state, RulesEngine(), seat, action)
    restored = deserialize_match_snapshot(deepcopy(before))
    repeated_legal, repeated_action = selected_grant(restored, seat, saga, chapter)
    assert repeated_action == action
    assert frame_action(restored, seat, repeated_legal, repeated_action) == first
    assert legal == saved_legal and action == saved_action
    assert serialize_match_snapshot(state) == before
    assert random.getstate() == rng and state.rng.getstate() == local


@pytest.mark.parametrize('seat', [1, 2])
def test_public_nonn_agent_accepts_genuine_chapter_II_state_without_mutation(seat):
    state, saga = saga_position(seat, 2)
    before, rng, local = serialize_match_snapshot(state), random.getstate(), state.rng.getstate()
    legal, _ = selected_grant(state, seat, saga, 2)
    saved_legal = deepcopy(legal)
    # Derive the actual public mask; choose_action independently applies this route.
    public, supplied = decision_view(state, seat, legal)
    public_before, supplied_before = serialize_match_snapshot(public), deepcopy(supplied)
    agent = AIAgent('master', 'Midrange', learned_binding=None)
    decision = agent.choose_action(state, legal, seat)
    assert agent.learned_binding is None and isinstance(decision.action, dict)
    checked_action(state, RulesEngine(), seat, decision.action)
    assert serialize_match_snapshot(public) == public_before and supplied == supplied_before
    assert legal == saved_legal and serialize_match_snapshot(state) == before
    assert random.getstate() == rng and state.rng.getstate() == local
