"""Canonical owned continuation context never becomes client execution input."""
from copy import deepcopy
import json

import pytest

from game_state.serializers import deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_library_choice_intent_audit import PHASES, position, explicit
from tests.test_private_choice_intent_boundary import environment, owned_disposable_source_only
from tests.test_library_choice_http_audit import server, fixture
from tests.test_private_choice_http_restart import stable


CONTEXT = ('controller', 'amount', 'bottom_ids', 'effect_key',
           'continuation_controller', 'continuation_effects',
           'counter_continuation_queue', 'draw_continuation_queue')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
@pytest.mark.parametrize('key', CONTEXT)
@pytest.mark.parametrize('value', [None, {'unsupported_nested_alias': None}, True, 2.0])
def test_forged_null_nested_and_wrong_json_types_reject_before_helper(name, order, seat, key, value, monkeypatch):
    state, _, _, _ = position(name, seat, order)
    env = environment(state)
    before = env.snapshot()
    view = RulesEngine().legal_moves(deepcopy(state), seat)[0]
    request = {**view, **explicit(state), key: deepcopy(value)}
    original = deepcopy(request)
    # This matrix deliberately uses no legitimate pending value as a negative.
    assert key not in state.pending_mechanic_choice or json.dumps(value, sort_keys=True) != json.dumps(state.pending_mechanic_choice[key], sort_keys=True)

    def forbidden(_):
        pytest.fail('Forged continuation reached complete_action')

    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert request == original and env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
def test_exact_sparse_context_canonical_json_and_explicit_choices(name, order, seat):
    state, _, _, _ = position(name, seat, order)
    env = environment(state)
    before = env.snapshot()
    chosen = explicit(state)
    context = {key: deepcopy(state.pending_mechanic_choice[key]) for key in CONTEXT if key in state.pending_mechanic_choice}
    request = {**context, **chosen, 'choice_id': None, 'damage_assignment': None}
    original = deepcopy(request)
    assert env.lookup_intent(request, seat) == env.lookup(chosen, seat)
    assert env.lookup_intent(dict(reversed(list(request.items()))), seat) == env.lookup(chosen, seat)
    assert request == original and env.snapshot() == before
    for key, value in context.items():
        assert env.lookup_intent({**chosen, key: value}, seat) == env.lookup(chosen, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
def test_current_owned_view_wrong_controller_stale_and_no_guesses(name, order, seat, monkeypatch):
    state, _, outside, foreign = position(name, seat, order)
    env = environment(state)
    view = RulesEngine().legal_moves(deepcopy(state), seat)[0]
    chosen = explicit(state)
    before = env.snapshot()
    observed, other = env.observe(seat), env.observe(3-seat)
    assert foreign not in json.dumps(observed)
    assert all(cid not in observed['known_cards'] for cid in outside)
    assert all(cid not in other['known_cards'] for cid in view['options'])
    assert not other['pending_choice'].get('prompts', [])
    with pytest.raises(ActionRejected):
        env.lookup_intent(view, seat)
    assert env.snapshot() == before

    def forbidden(_):
        pytest.fail('Wrong actor/context or stale view reached complete_action')

    with monkeypatch.context() as patch:
        patch.setattr('ai.action_contract.complete_action', forbidden)
        for request, actor in (({**view, **chosen}, 3-seat),
                               ({**view, **chosen}, True),
                               ({**view, **chosen, 'controller': 3-seat}, seat),
                               ({**view, **chosen, 'continuation_controller': 3-seat}, seat)):
            with pytest.raises(ActionRejected):
                env.lookup_intent(request, actor)
            assert env.snapshot() == before
    env.step(chosen, seat)
    after = env.snapshot()
    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent({**view, **chosen}, seat)
    assert env.snapshot() == after


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
def test_real_http_full_context_tampering_rejects_root_db_and_restore(server, name, order, seat):
    data = fixture(server, name, seat, order)
    identifier = data['id']
    base = f'/matches/{identifier}'
    intent = f'/fixture/private-choice/{identifier}/intent?seat={seat}'
    before = server.audit(identifier)
    _, legal = server.call(base + f'/legal-moves?player_id={seat}')
    view = legal['moves'][0]
    chosen = explicit(deserialize_match_snapshot(before['state']))
    request = {**view, **chosen}
    for key in CONTEXT:
        for value in (None, {'unsupported_nested_alias': None}, True, 2.0):
            status, _ = server.call(intent, {**request, key: value})
            assert status == 422 and stable(server.audit(identifier)) == stable(before)
    status, _ = server.call(f'/fixture/private-choice/{identifier}/intent?seat={3-seat}', request)
    assert status == 422 and stable(server.audit(identifier)) == stable(before)
    before = server.restart(identifier, before)
    assert stable(server.audit(identifier)) == stable(before)
    status, result = server.call(intent, request)
    assert status == 200 and result['action'] == chosen
    assert stable(server.audit(identifier)) == stable(before)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': request})
    assert status == 422 and stable(server.audit(identifier)) == stable(before)
