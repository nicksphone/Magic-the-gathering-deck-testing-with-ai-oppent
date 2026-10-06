"""Strict two-family audit: canonical views are not guessed human selections."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from training.environment import TrainingEnvironment
from tests.test_activated_top_selection import position as officer_position, activate, resolve_activation, card
from tests.test_optional_reveal_transform import pending as delver_pending
from tests.test_api_input_contracts import game, persist, snapshot


@pytest.fixture(autouse=True)
def owned_disposable_source_only():
    root = Path(__file__).resolve().parents[2]
    marker = root / '.private-choice-audit-source'
    assert not (root / '.git').exists(), 'Never run this audit against tracked/live SQLite'
    assert marker.is_file() and marker.read_text() == str(root), 'Use a marked isolated source copy'


def position(family, seat):
    if family == 'delver':
        state, source, top = delver_pending(seat)
        foreign = next(c for c in state.cards.values() if c.owner == 3-seat and c.name == 'Island')
        state.players[3-seat].library.remove(foreign.id)
        foreign.move_to_zone(Zone.HAND)
        state.players[3-seat].hand.append(foreign.id)
        inspected = [top]
    else:
        state, source, _, top = officer_position(seat)
        foreign = card(state, 'forest', 3-seat, Zone.HAND)
        state = resolve_activation(activate(state, source, seat))
        inspected = list(reversed(top))
    return state, inspected, foreign.id


def environment(state):
    # Explicit retained canonical position, not a built-in deck/provenance claim.
    result = TrainingEnvironment()
    result._state = deepcopy(state)
    return result


def selected(state, family, decline):
    choice = 'decline' if family == 'delver' and decline else 'reveal' if family == 'delver' else '__none__' if decline else state.pending_mechanic_choice['options'][0]
    return {'type': 'choose_mechanic', 'card_ids': [choice]}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('decline', [False, True])
def test_whole_actual_owned_legal_view_preserves_explicit_choice(family, seat, decline):
    state, _, _ = position(family, seat)
    env = environment(state)
    view = RulesEngine().legal_moves(state, seat)[0]
    action = selected(state, family, decline)
    before = env.snapshot()
    normalized = env.lookup_intent({**view, **action}, seat)['action']
    assert normalized == action
    assert env.snapshot() == before
    replay = environment(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert env.step(normalized, seat) == replay.step(action, seat)
    assert env.snapshot() == replay.snapshot()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
def test_private_observations_owned_context_and_minimal_actions(family, seat):
    state, inspected, foreign = position(family, seat)
    env = environment(state)
    before = env.snapshot()
    actor = env.observe(seat)
    other = env.observe(3-seat)
    assert foreign not in json.dumps(actor)
    assert all(cid in actor['known_cards'] for cid in inspected)
    assert all(cid not in other['known_cards'] for cid in inspected)
    assert not other['pending_choice'].get('prompts', [])
    assert not any(key in json.dumps(actor['pending_choice']) for key in ('effect_payload', 'top_reference', 'resolving_item', 'followup_effect'))
    action = selected(state, family, True)
    assert env.lookup_intent(action, seat)['action'] == action
    with pytest.raises(ActionRejected):
        env.lookup_intent(action, 3-seat)
    view = RulesEngine().legal_moves(state, seat)[0]
    context_only = {key: view[key] for key in ('player_id', 'effect_controller', 'resolving_item', 'followup_effect') if key in view}
    assert env.lookup_intent({**context_only, **action}, seat)['action'] == action
    if 'player_id' in context_only:
        with pytest.raises(ActionRejected):
            env.lookup_intent({**context_only, **action, 'player_id': 3-seat}, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('decline', [False, True])
def test_minimal_explicit_selection_replays_and_stale_rejects(family, seat, decline):
    state, _, _ = position(family, seat)
    env = environment(state)
    action = selected(state, family, decline)
    before = env.snapshot()
    normalized = env.lookup_intent(action, seat)['action']
    assert normalized == action and env.snapshot() == before
    replay = environment(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert env.step(normalized, seat) == replay.step(action, seat)
    assert env.snapshot() == replay.snapshot()
    after = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(action, seat)
    assert env.snapshot() == after


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('context', [{'player_id': None}, {'resolving_item': {'unsupported_nested_alias': None}}])
def test_forged_context_rejects_before_helper_without_leaking(family, seat, context, monkeypatch):
    from ai import action_contract
    state, _, _ = position(family, seat)
    env = environment(state)
    before = env.snapshot()
    calls = []
    original = action_contract.complete_action

    def spy(intent):
        calls.append(True)
        return original(intent)

    monkeypatch.setattr(action_contract, 'complete_action', spy)
    with pytest.raises(ActionRejected):
        env.lookup_intent({**selected(state, family, True), **context}, seat)
    assert not calls and env.snapshot() == before


BAD_FIELDS = [
    {'unknown': None}, {'targets': {'card_ids': ['decline']}},
    {'card_ids': None}, {'card_ids': {'choice_id': 'decline'}},
    {'choice_id': None}, {'damage_assignment': None},
]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('extra', BAD_FIELDS)
def test_bad_alias_or_null_rejects_before_completion_helper(family, seat, extra, monkeypatch):
    from ai import action_contract
    state, _, _ = position(family, seat)
    env = environment(state)
    before = env.snapshot()
    calls = []
    original = action_contract.complete_action

    def spy(intent):
        calls.append(deepcopy(intent))
        return original(intent)

    monkeypatch.setattr(action_contract, 'complete_action', spy)
    if extra in ({'choice_id': None}, {'damage_assignment': None}):
        action = selected(state, family, True)
        assert env.lookup_intent({**action, **extra}, seat)['action'] == action
        assert len(calls) == 1 and env.snapshot() == before
        return
    with pytest.raises(ActionRejected):
        env.lookup_intent({**selected(state, family, True), **extra}, seat)
    assert not calls, 'Invalid fields reached complete_action before rejection'
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('decline', [False, True])
def test_raw_http_strict_action_wrong_actor_and_database_root(family, seat, decline, game):
    client, controller = game
    state, inspected, _ = position(family, seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    endpoint = f'/matches/{state.id}/action'
    action = selected(state, family, decline)
    before = snapshot(controller)
    foreign = client.get(f'/matches/{state.id}/legal-moves?player_id={3-seat}').json()
    assert not foreign['moves'] and not any(cid in json.dumps(foreign) for cid in inspected)
    wrong = client.post(endpoint, json={'player_id': 3-seat, 'action': action})
    assert wrong.status_code in (403, 422) and snapshot(controller) == before
    view = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}').json()['moves'][0]
    rejected = client.post(endpoint, json={'player_id': seat, 'action': {**view, **action}})
    assert rejected.status_code == 422 and snapshot(controller) == before
    accepted = client.post(endpoint, json={'player_id': seat, 'action': action})
    assert accepted.status_code == 200, accepted.text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('extra', BAD_FIELDS)
def test_raw_http_bad_alias_null_never_reaches_engine(family, seat, extra, game, monkeypatch):
    client, controller = game
    state, _, _ = position(family, seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    before = snapshot(controller)
    calls = []
    original = RulesEngine.take_action

    def spy(self, *args, **kwargs):
        calls.append(True)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(RulesEngine, 'take_action', spy)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': {**selected(state, family, True), **extra}})
    if extra in ({'choice_id': None}, {'damage_assignment': None}):
        assert response.status_code == 200, response.text
        assert calls and not controller.state.pending_mechanic_choice
        assert not controller.state.stack
        if family == 'officer':
            assert not controller.state.players[seat].hand
        else:
            source = state.pending_mechanic_choice['effect_payload']['target_card_id']
            assert not controller.state.cards[source].selected_face_index
            assert controller.state.players[seat].library == state.players[seat].library
        return
    assert response.status_code == 422, response.text
    assert not calls
    assert snapshot(controller) == before
