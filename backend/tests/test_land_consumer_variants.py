"""Ordinary desired assertions, including real whole-view consumer boundaries."""
from copy import deepcopy
import json

import pytest

from api_contracts import LandAction
from game_state.serializers import serialize_card_view, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from training.environment import decode_action
from tests.land_consumer_variant_support import ENGINE, VARIANTS, setup, environment
from tests.test_private_choice_intent_boundary import owned_disposable_source_only
from tests.test_training_land_priority_intent_guard import observe_helper


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('surface', ['typed', 'engine', 'api'])
def test_exact_current_whole_view_keeps_explicit_entry_origin_and_source(seat, variant, surface):
    env, action, hint, ids = setup(variant, seat)
    packet = action if surface == 'typed' else {**hint, **action}
    if surface == 'api':
        packet['card_view'] = serialize_card_view(deepcopy(env._state), ids['land'])
    before, original = env.snapshot(), deepcopy(packet)
    assert hint is not None
    if not variant.startswith('shock'):
        assert hint['graveyard_permission_name'] == ('Crucible of Worlds' if variant == 'crucible' else 'Ramunap Excavator')
        assert 'graveyard_permission_key' not in hint  # Static unrestricted grant, no invented key.
    normalized = env.lookup_intent(packet, seat)
    assert normalized['action'] == action and decode_action(normalized['id']) == action
    assert env.snapshot() == before and packet == original
    actor, other = env.observe(seat), env.observe(3-seat)
    assert ids['foreign_hand'] not in json.dumps(actor)
    assert all(cid not in actor['known_cards'] for cid in ids['unseen'])
    if variant.startswith('shock'):
        assert ids['land'] not in other['known_cards']
    replay = environment(deserialize_match_snapshot(serialize_match_snapshot(env._state)))
    assert env.step(normalized['action'], seat) == replay.step(action, seat)
    assert env.snapshot() == replay.snapshot()
    result = env._state
    assert result.cards[ids['land']].zone == Zone.BATTLEFIELD
    assert result.players[seat].lands_played_this_turn == 1
    assert ids['first'] in getattr(result.players[seat], 'hand' if variant.startswith('shock') else 'graveyard')
    assert result.players[seat].life == (18 if variant == 'shock_pay' else 20)
    assert result.cards[ids['land']].tapped == (variant == 'shock_tapped')
    after = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(packet, seat)
    assert env.snapshot() == after


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('extra', [{'land_card_id': None}, {'origin': None}, {'permission': None},
    {'targets': None}, {'player_id': None}, {'card_view': None},
    {'graveyard_permission_name': None}, {'from_graveyard': None}, {'from_exile': 1},
    {'card_id': None}, {'entry_choice': {'choice': 'tapped'}}])
def test_null_alias_malformed_context_reject_before_helper(seat, variant, extra, monkeypatch):
    env, action, hint, ids = setup(variant, seat)
    packet = {**hint, **action, **extra}
    before, original = env.snapshot(), deepcopy(packet)
    calls = observe_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(packet, seat)
    assert not calls and env.snapshot() == before and packet == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', VARIANTS)
def test_changed_nested_display_wrong_actor_unoffered_key_and_stale_before_helper(seat, variant, monkeypatch):
    env, action, hint, ids = setup(variant, seat)
    view = {**hint, **action, 'card_view': serialize_card_view(deepcopy(env._state), ids['land'])}
    before = env.snapshot()
    calls = observe_helper(monkeypatch)
    for packet, actor in (({**view, 'card_view': {**view['card_view'], 'unknown_choice': None}}, seat),
                          ({**view, 'graveyard_permission_key': 'unoffered-source-key'}, seat),
                          (view, 3-seat), ({**view, 'card_id': ids['foreign_hand']}, seat)):
        with pytest.raises(ActionRejected):
            env.lookup_intent(packet, actor)
        assert not calls and env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', VARIANTS)
def test_missing_explicit_choice_or_origin_not_inferred(seat, variant):
    env, action, hint, ids = setup(variant, seat)
    packet = {**hint, **action}
    packet.pop('entry_choice' if variant.startswith('shock') else 'from_graveyard')
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(packet, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [1, 2])
def test_shock_payment_offered_bounds_come_from_engine(seat, life):
    env, action, hint, ids = setup('shock_pay', seat, life)
    before = env.snapshot()
    if life == 1:
        assert hint is None
        with pytest.raises(ActionRejected):
            checked_action(env._state, ENGINE, seat, action)
        assert env.snapshot() == before
    else:
        assert hint is not None
        result = checked_action(env._state, ENGINE, seat, action)
        assert result.players[seat].life == 0 and result.cards[ids['land']].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('actor_form', ['bool', 'float'])
def test_invalid_actor_scalar_rejects_before_helper_even_when_python_equal(seat, variant, actor_form, monkeypatch):
    env, action, hint, ids = setup(variant, seat)
    actor = True if actor_form == 'bool' else float(seat)
    packet = {**hint, **action, 'card_view': serialize_card_view(deepcopy(env._state), ids['land'])}
    before = env.snapshot()
    calls = observe_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(packet, actor)
    assert env.snapshot() == before
    assert not calls, 'Malformed actor must reject before normalization helper'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', VARIANTS)
def test_stale_actual_api_view_rejects_before_helper(seat, variant, monkeypatch):
    env, action, hint, ids = setup(variant, seat)
    packet = {**hint, **action, 'card_view': serialize_card_view(deepcopy(env._state), ids['land'])}
    env.step(action, seat)
    before = env.snapshot()
    calls = observe_helper(monkeypatch)
    with pytest.raises(ActionRejected):
        env.lookup_intent(packet, seat)
    assert not calls and env.snapshot() == before
