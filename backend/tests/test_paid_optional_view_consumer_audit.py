"""Actual optional legal views; never invent cost/affordability producer fields."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from api_contracts import OptionalEffectChoice
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from training.environment import TrainingEnvironment
from tests.test_paid_optional_triggers import PATH, ROWS, position, queued, require_pending, reward, private_root
from tests.test_paid_trigger_ai_integration_audit import actual_choice
from tests.test_death_cycle_ordering_http_audit import act, frozen, install, offline_client, restore


@pytest.fixture(autouse=True, scope='module')
def own_local_source():
    root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve()
    assert root == Path(__file__).resolve().parents[2]
    if not str(root).startswith('/home/nick/.hermes/cache/scratch/mtg-paid-view-audit-'):
        from tests.ci_input_contracts import assert_github_owned_source
        assert_github_owned_source()
    assert not (root / 'backend/mtg_lab.db').is_symlink()


def record(request, **fields):
    target = Path(os.environ['MTG_PAID_VIEW_EVIDENCE'])
    path = target / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    path.write_text(json.dumps({'node': request.node.nodeid, **fields}, indent=2, sort_keys=True) + '\n')


def pending(seat, family, funding):
    root, watcher, discarded, secret, _, action = position(seat, family, 'cycle', funding)
    assert watcher.oracle_text == ROWS[family]['oracle_text']
    state = queued(root, seat, watcher, action)
    assert state.stack[-1].payload['__optional_payment_cost'] == '{1}'
    resolve_top_of_stack(state)
    require_pending(state, watcher)
    assert watcher.owner == 3-seat and watcher.controller == seat
    assert state.players[seat].mana_pool.get('U', 0) == 0
    assert state.players[seat].mana_pool.get('C', 0) == int(funding == 'pool')
    return state, watcher, secret


def environment(state):
    result = TrainingEnvironment()
    result._state = deepcopy(state)
    return result


def test_full_canonical_rows_and_provenance_remain_exact():
    assert hashlib.sha256(PATH.read_bytes()).hexdigest() == '03a372fe6a2e9a121d10e3f855d6186ac5a85d44f3f771ca45e5a1f324905b38'
    assert set(ROWS) == {'Drake Haven', 'Faith of the Devoted'}
    provenance = json.loads((PATH.parent / 'provenance.json').read_text())
    assert provenance['fixture_sha256'] == hashlib.sha256(PATH.read_bytes()).hexdigest()
    assert provenance['facts_modified'] is False and provenance['offline'] is True
    for row in ROWS.values():
        assert row['id'] and row['oracle_id'] and row['scryfall_uri']
        assert row['oracle_text'].startswith('Whenever you cycle or discard')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Drake Haven', 'Faith of the Devoted'])
@pytest.mark.parametrize('funding', ['pool', 'none'])
def test_actual_whole_views_typed_ai_private_root_and_snapshot_replay(request, seat, family, funding, monkeypatch):
    state, watcher, secret = pending(seat, family, funding)
    before = serialize_match_snapshot(state)
    env = environment(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert {move['accept'] for move in moves} == ({True, False} if funding == 'pool' else {False})
    assert not RulesEngine().legal_moves(state, 3-seat)
    hints = [prompt['hint'] for prompt in env.prompts(seat)]
    assert hints == moves
    assert secret.id not in env.observe(seat)['known_cards']
    private_root(state, seat, secret)
    replay = environment(deserialize_match_snapshot(before))
    attempts = []
    for move, hint in zip(moves, hints):
        assert set(move) == {'type', 'stack_id', 'accept'}
        action = OptionalEffectChoice.model_validate(move).model_dump()
        original = deepcopy(move)
        assert env.lookup_intent(move, seat) == env.lookup(action, seat)
        assert env.lookup_intent(move) == env.lookup(action, seat)
        assert env.lookup_intent(hint, seat) == replay.lookup_intent(move, seat)
        assert move == original and serialize_match_snapshot(env._state) == before
        result = checked_action(state, RulesEngine(), seat, action)
        reward(result, seat, family, action['accept'])
        attempts.append({'view': move, 'typed_action': action, 'result': serialize_match_snapshot(result)})
    ai = actual_choice(state, seat, monkeypatch)
    assert env.lookup_intent(ai.action, seat) == env.lookup(ai.action, seat)
    outcome = checked_action(state, RulesEngine(), seat, ai.action)
    reward(outcome, seat, family, ai.action['accept'])
    env.step(moves[-1], seat)
    completed = serialize_match_snapshot(env._state)
    with pytest.raises(ActionRejected):
        env.lookup_intent(moves[-1], seat)
    assert serialize_match_snapshot(env._state) == completed
    assert serialize_match_snapshot(state) == before
    record(request, snapshot=before, actual_views=moves, training_hints=hints,
           actual_display_fields=sorted(set(moves[0]) - set(OptionalEffectChoice.model_fields)),
           attempts=attempts, ai_action=ai.action, root_private_replay_equal=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Drake Haven', 'Faith of the Devoted'])
@pytest.mark.parametrize('funding', ['pool', 'none'])
def test_unsupported_metadata_malformed_choices_wrong_actor_no_root_mutation(request, seat, family, funding, monkeypatch):
    state, _, _ = pending(seat, family, funding)
    env = environment(state)
    before = serialize_match_snapshot(env._state)
    view = RulesEngine().legal_moves(state, seat)[-1]
    # Not produced today: do not declare these guessed values legitimate metadata.
    extras = [{'cost_text': '{1}'}, {'affordable': funding == 'pool'},
              {'unknown': None}, {'payment_options': None},
              {'targets': {'accept': True}}, {'optional_choice': None}]
    def forbidden(_):
        pytest.fail('Unrecognized display/client continuation reached completion')
    with monkeypatch.context() as patch:
        patch.setattr('ai.action_contract.complete_action', forbidden)
        for extra in extras:
            intent = {**view, **extra}
            original = deepcopy(intent)
            with pytest.raises(ActionRejected):
                env.lookup_intent(intent, seat)
            assert intent == original and serialize_match_snapshot(env._state) == before
    for value in (None, 0, 1, 'true', [], {}):
        with pytest.raises(ActionRejected):
            env.lookup_intent({**view, 'accept': value}, seat)
        assert serialize_match_snapshot(env._state) == before
    for invalid in ({'type': view['type'], 'stack_id': view['stack_id']},
                    {**view, 'stack_id': None}, {**view, 'stack_id': 'stale-source-stack'}):
        with pytest.raises(ActionRejected):
            env.lookup_intent(invalid, seat)
        assert serialize_match_snapshot(env._state) == before
    with pytest.raises(ActionRejected):
        env.lookup_intent(view, 3-seat)
    assert serialize_match_snapshot(env._state) == before
    if funding == 'none':
        with pytest.raises(ActionRejected):
            env.lookup_intent({**view, 'accept': True}, seat)
        assert serialize_match_snapshot(env._state) == before
    record(request, actual_view=view, unsupported_client_extras=extras,
           malformed_rejected=True, root_equal=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Drake Haven', 'Faith of the Devoted'])
@pytest.mark.parametrize('funding', ['pool', 'none'])
def test_actual_api_wholeview_raw_extras_private_sql_restore_typed_acceptance(request, offline_client, seat, family, funding):
    state, _, secret = pending(seat, family, funding)
    match = install(state, request, seat, private=True)
    before = frozen(match)
    identifier = state.id
    response = offline_client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert response.status_code == 200
    moves = response.json()['moves']
    assert moves == RulesEngine().legal_moves(state, seat)
    assert all(set(move) == {'type', 'stack_id', 'accept'} for move in moves)
    response = offline_client.get(f'/matches/{identifier}/legal-moves?player_id={3-seat}')
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert not response.json()['moves']
    public = offline_client.get(f'/matches/{identifier}').json()
    assert secret.name not in json.dumps(public['players'][str(3-seat)]['hand'])
    assert frozen(match) == before
    action = moves[0]
    env = environment(state)
    assert env.lookup_intent(action, seat) == env.lookup(OptionalEffectChoice.model_validate(action).model_dump(), seat)
    invalids = [{**action, 'cost_text': '{1}'}, {**action, 'affordable': True},
                {**action, 'unknown': None}, {**action, 'accept': None},
                {**action, 'targets': {'accept': False}}, {**action, 'stack_id': 'stale-stack'}]
    if funding == 'none':
        invalids.append({**action, 'accept': True})
    for invalid in invalids:
        rejected = act(offline_client, match, seat, invalid)
        assert rejected.status_code == 422 and frozen(match) == before
    rejected = act(offline_client, match, 3-seat, action)
    assert rejected.status_code in (403, 422) and frozen(match) == before
    match = restore(identifier)
    assert frozen(match) == before
    accepted = act(offline_client, match, seat, action)
    assert accepted.status_code == 200, accepted.text
    import main
    match = main.ACTIVE_MATCHES[identifier]
    reward(match.state, seat, family, action['accept'])
    after = frozen(match)
    rejected = act(offline_client, match, seat, action)
    assert rejected.status_code == 422 and frozen(match) == after
    match = restore(identifier)
    assert frozen(match) == after
    record(request, actual_api_views=moves, request_action=action,
           snapshot_before=before[0], snapshot_after=after[0],
           invalid_raw_statuses=[422] * len(invalids),
           exact_sql_root_restore_equal=True, asgi_transport=True)
