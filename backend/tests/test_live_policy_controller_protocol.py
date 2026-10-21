"""Controller metadata/routing protocols, not trained-policy inference or App proof."""
from copy import deepcopy
from dataclasses import fields
import inspect
import json
from types import SimpleNamespace

import pytest

from tests.temporary_characteristics_http_fixture import (
    source_default_identity, source_lease,
)


VERSION = 'mtg.live-policy.v1'
RECORD_KEYS = {
    'version', 'requested', 'effective', 'checkpoint_sha256', 'contract',
    'fallback_reason',
}


def wire(value):
    return json.loads(json.dumps(value))


@pytest.fixture
def api(monkeypatch):
    # Use the existing owned-source lease BEFORE Main's genuine media import.
    root = source_lease()
    default_before = source_default_identity()
    import main
    assert main.Path(main.__file__).resolve().parent == root / 'backend'
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})

    def no_session(*args, **kwargs):
        pytest.fail('Controller protocol unexpectedly requested SQL')

    monkeypatch.setattr(main, 'Session', no_session)
    yield main
    assert source_default_identity() == default_before


@pytest.fixture(scope='module')
def checkpoint_binding():
    # Actual loader and same-buffer identity; numerical fixture, NOT fitted weights.
    from ai import learned_qv
    from ai.learned_policy import bind_live_policy
    from tests.test_learned_qv import blank_checkpoint
    from training.environment import _engine_hash

    payload = blank_checkpoint(learned_qv)
    payload['contract'] = {
        'dataset_version': 'mtg.dataset.v2', 'action_version': 'mtg.action.v1:',
        'decision_version': 'mtg.decision.v2', 'feature_version': 'mtg.features.v2',
        'feature_schema_sha256':
            '9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06',
        'engine_hash': _engine_hash(),
    }
    payload['provenance']['updates'] = 1
    payload['provenance']['samples'] = 1
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return bind_live_policy(raw), raw


@pytest.fixture(params=(1, 2), ids=('seat1', 'seat2'))
def scene(api, request, checkpoint_binding):
    from ai.agent import AIAgent
    from game_state.state import MatchFactory
    from tests.browser_positive83_canonical import entry
    from training.environment import _engine_hash
    from rules_engine.copiable_values import PHYSICAL, FIELDS

    decks = {1: [entry('Island', 60)], 2: [entry('Mountain', 60)]}
    state = MatchFactory.from_decks(decks[1], decks[2], seed=917)
    assert len(state.cards) == 120
    for seat in (1, 2):
        player = state.players[seat]
        assert len(player.hand) == 7 and len(player.library) == 53
        for cid in player.hand:
            card = state.cards[cid]
            assert card.owner == seat and card.zone.value == 'hand'
            record = card.characteristic_record
            assert type(record) is dict and set(record) == {'version', 'physical', 'values'}
            assert type(record['version']) is int and record['version'] == 1
            assert record['physical'] == {key: deepcopy(getattr(card, key)) for key in PHYSICAL}
            assert record['values'] == {key: deepcopy(record['physical'][key]) for key in FIELDS}
            for key in ('name', 'mana_cost', 'type_line', 'oracle_text',
                        'colors', 'card_faces', 'layout', 'image_uri'):
                assert record['physical'][key] == decks[seat][0][key]
    controller = api.MatchController(
        state=state, rules=api.RulesEngine(), controllers={1: 'ai', 2: 'ai'},
        ai={seat: AIAgent(difficulty='strong', archetype='Control')
            for seat in (1, 2)},
        mode='ai_vs_ai', deck_ids=(None, None), mainboards=deepcopy(decks),
        sideboards={1: [], 2: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=3,
        root_seed=917,
    )
    record = {
        'version': VERSION, 'requested': 'learned_qv', 'effective': 'learned_qv',
        'checkpoint_sha256': checkpoint_binding[0].checkpoint_sha256,
        'contract': {
            'decision_version': 'mtg.decision.v2',
            'feature_version': 'mtg.features.v2',
            'feature_schema_sha256':
                '9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06',
            'dataset_version': 'mtg.dataset.v2',
            'action_version': 'mtg.action.v1:', 'engine_hash': _engine_hash(),
        },
        'fallback_reason': None,
    }
    return SimpleNamespace(controller=controller, seat=request.param, record=record,
                           binding=checkpoint_binding[0], raw_checkpoint=checkpoint_binding[1])


def declared(scene):
    scene.controller.policy_provenance = {scene.seat: deepcopy(scene.record)}
    return scene.controller


def stored_row(api, controller, policy=None):
    from game_state.serializers import serialize_match_snapshot
    config = api._controller_snapshot(controller)
    if policy is not None:
        config['policy_provenance'] = {str(pid): deepcopy(value)
                                       for pid, value in policy.items()}
    return SimpleNamespace(id=controller.state.id,
        state_json=json.dumps(serialize_match_snapshot(controller.state)),
        controller_json=json.dumps(config))


def restore(api, row, bindings=None):
    assert not api.ACTIVE_MATCHES, 'Only the fixture-owned cold registry is used'
    repo = SimpleNamespace(get_active_match=lambda mid: row if mid == row.id else None)
    kwargs = {}
    if bindings is not None and 'policy_bindings' in inspect.signature(
            api._restore_active_matches).parameters:
        kwargs['policy_bindings'] = bindings
    # Baseline still calls the genuine old wrapper, yielding assertion REDs,
    # not a missing-keyword setup TypeError.
    api._restore_active_matches(repo, row.id, **kwargs)
    assert row.id in api.ACTIVE_MATCHES, 'Policy metadata must not lose the game'
    return api.ACTIVE_MATCHES[row.id]


def saved_record(api, controller, seat):
    records = api._controller_snapshot(controller).get('policy_provenance', {})
    assert str(seat) in records, 'Gate8 controller policy provenance is missing'
    assert set(records[str(seat)]) == RECORD_KEYS
    return records[str(seat)]


def trusted_binding(scene):
    from ai.agent import AIAgent
    agent = AIAgent(difficulty='strong', archetype='Control', learned_binding=scene.binding)
    return {'agent': agent, 'provenance': deepcopy(scene.record)}


def test_controller_declares_independent_optional_empty_field(api):
    field = next((item for item in fields(api.MatchController)
                  if item.name == 'policy_provenance'), None)
    assert field is not None, 'Explicit controller policy field is missing'
    left, right = field.default_factory(), field.default_factory()
    assert left == right == {} and left is not right


def test_default_snapshot_is_exact_legacy_shape_and_omits_policy(api, scene):
    match = scene.controller
    expected = {
        'controllers': {'1': 'ai', '2': 'ai'}, 'mode': 'ai_vs_ai',
        'deck_ids': [None, None],
        'mainboards': {str(pid): deck for pid, deck in match.mainboards.items()},
        'sideboards': {'1': [], '2': []}, 'game_number': 1,
        'current_game_recorded': False, 'match_complete': False, 'best_of': 3,
        'root_seed': 917, 'play_draw_chooser': 1, 'sideboarded_players': [],
        'seen_opponent_types': {'1': [], '2': []}, 'auto_sideboard': True,
        'difficulties': {'1': 'strong', '2': 'strong'},
        'archetypes': {'1': 'Control', '2': 'Control'},
        'revision': 0, 'mutation_receipts': {},
    }
    assert api._controller_snapshot(match) == expected
    assert 'policy_provenance' not in api._controller_snapshot(match)


def test_snapshot_keeps_closed_seat_binding_and_copies_nested_contract(api, scene):
    match = declared(scene)
    snapshot = api._controller_snapshot(match)
    assert snapshot.get('policy_provenance') == {str(scene.seat): scene.record}
    match.policy_provenance[scene.seat]['contract']['engine_hash'] = 'b' * 64
    assert snapshot['policy_provenance'][str(scene.seat)] == scene.record
    snapshot['policy_provenance'][str(scene.seat)]['checkpoint_sha256'] = 'c' * 64
    assert match.policy_provenance[scene.seat]['checkpoint_sha256'] == scene.record['checkpoint_sha256']


def test_legacy_restore_preserves_natural_pregame_and_has_no_policy(api, scene):
    row = stored_row(api, scene.controller)
    restored = restore(api, row)
    from game_state.serializers import serialize_match_snapshot
    assert wire(serialize_match_snapshot(restored.state)) == json.loads(row.state_json)
    assert restored.state.pregame_pending
    assert 'policy_provenance' not in api._controller_snapshot(restored)


def test_restore_without_binding_preserves_origin_and_marks_fallback(api, scene):
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row)
    expected = {**scene.record, 'effective': 'heuristic',
                'fallback_reason': 'restore_requires_opt_in'}
    assert saved_record(api, restored, scene.seat) == expected
    from game_state.serializers import serialize_match_snapshot
    assert wire(serialize_match_snapshot(restored.state)) == json.loads(row.state_json)


def test_matching_explicit_binding_routes_to_supplied_agent(api, scene):
    binding = trusted_binding(scene)
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row, {scene.seat: binding})
    assert restored.ai[scene.seat] is binding['agent'], 'Trusted runtime agent was not restored'
    assert restored.ai[3 - scene.seat] is not binding['agent']
    assert saved_record(api, restored, scene.seat) == scene.record


@pytest.mark.parametrize('mismatch', ('checkpoint', 'engine', 'feature'),
                         ids=('checkpoint', 'engine', 'feature'))
def test_mismatched_binding_cannot_replace_requested_origin(api, scene, mismatch):
    binding = trusted_binding(scene)
    if mismatch == 'checkpoint':
        binding['provenance']['checkpoint_sha256'] = 'b' * 64
    elif mismatch == 'engine':
        binding['provenance']['contract']['engine_hash'] = 'b' * 64
    else:
        binding['provenance']['contract']['feature_schema_sha256'] = 'b' * 64
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row, {scene.seat: binding})
    assert restored.ai[scene.seat] is not binding['agent']
    assert saved_record(api, restored, scene.seat) == {
        **scene.record, 'effective': 'heuristic',
        'fallback_reason': 'restore_requires_opt_in',
    }


def test_binding_for_other_seat_does_not_activate_requested_seat(api, scene):
    binding = trusted_binding(scene)
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row, {3 - scene.seat: binding})
    assert restored.ai[scene.seat] is not binding['agent']
    assert saved_record(api, restored, scene.seat)['effective'] == 'heuristic'
    assert saved_record(api, restored, scene.seat)['fallback_reason'] == 'restore_requires_opt_in'


def test_fallback_resnapshot_can_rebind_exact_original_not_new_checkpoint(api, scene):
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    fallback = restore(api, row)
    assert saved_record(api, fallback, scene.seat)['effective'] == 'heuristic'
    second_row = stored_row(api, fallback)
    api.ACTIVE_MATCHES.clear()  # Fixture-owned mapping, simulating a cold restore.
    binding = trusted_binding(scene)
    restored = restore(api, second_row, {scene.seat: binding})
    assert restored.ai[scene.seat] is binding['agent']
    assert saved_record(api, restored, scene.seat) == scene.record


def test_policy_record_never_reads_or_depends_on_hidden_library_order(api, scene):
    from game_state.serializers import serialize_match_snapshot
    match = declared(scene)
    before = serialize_match_snapshot(match.state)
    first = saved_record(api, match, scene.seat)
    assert serialize_match_snapshot(match.state) == before
    for player in match.state.players.values():
        player.library.reverse()
        player.hand.reverse()
    changed = serialize_match_snapshot(match.state)
    assert changed != before
    assert saved_record(api, match, scene.seat) == first == scene.record
    assert serialize_match_snapshot(match.state) == changed
    assert 'policy_provenance' not in changed


@pytest.mark.parametrize('field,value', (
    ('checkpoint_path', '/not-an-authorized-model-input/checkpoint.json'),
    ('weights', [[0.5]]), ('observation', {'opponent_hand': ['inert-secret']}),
    ('fallback_reason', 'unbounded exception text is not a reason code'),
), ids=('path', 'weights', 'frame', 'error-text'))
def test_snapshot_rejects_nonprotocol_payload_without_changing_game(api, scene, field, value):
    from game_state.serializers import serialize_match_snapshot
    match = declared(scene)
    match.policy_provenance[scene.seat][field] = deepcopy(value)
    before = serialize_match_snapshot(match.state)
    with pytest.raises(ValueError):
        api._controller_snapshot(match)
    assert serialize_match_snapshot(match.state) == before


def test_explicit_wrapper_forwards_binding_under_existing_lock(api, monkeypatch):
    calls = []
    bindings = {1: object()}

    def locked(repo, match_id=None, *, policy_bindings=None):
        calls.append((repo, match_id, policy_bindings, api.MATCH_LOAD_LOCK._is_owned()))

    monkeypatch.setattr(api, '_restore_active_matches_locked', locked)
    repo = object()
    kwargs = {'policy_bindings': bindings} if 'policy_bindings' in inspect.signature(
        api._restore_active_matches).parameters else {}
    api._restore_active_matches(repo, 'protocol-only-id', **kwargs)
    assert calls == [(repo, 'protocol-only-id', bindings, True)]
