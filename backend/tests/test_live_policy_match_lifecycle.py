"""Main configuration/finalization protocols, NOT SQL/startup or fitted-model proof."""
import ast
from copy import deepcopy
import inspect
import json
from textwrap import dedent

import pytest

from tests.test_live_policy_controller_protocol import (
    api, checkpoint_binding, scene, restore, saved_record, stored_row, trusted_binding,
)


PREFIX = 'AI POLICY PROVENANCE '


@pytest.fixture
def startup(api, monkeypatch):
    for key, value in (('new_match_policy_binding', None),
                       ('new_match_policy_configured', False),
                       ('new_match_policy_frozen', False)):
        monkeypatch.setattr(api.app.state, key, value, raising=False)
    return api


def configure(api, binding):
    function = getattr(api, 'configure_new_match_policy', None)
    assert callable(function), 'Missing explicit pre-lifespan policy configuration'
    return function(binding)


class RecordingSession:
    """Repository serialization boundary double; never a database connection."""
    def __init__(self):
        self.rows = []
        self.commits = 0

    def add(self, row):
        self.rows.append(row)

    def commit(self):
        self.commits += 1

    def refresh(self, row):
        assert row in self.rows


class PublicRows:
    """Full pinned RAW lookup double, not a substitute Factory or Oracle."""
    def __init__(self):
        from knowledge.models import CardKnowledge
        from tests.browser_positive83_canonical import raw_card

        self.raw = {name: raw_card(name) for name in ('Island', 'Mountain')}
        self.rows = {
            name.casefold(): CardKnowledge(name=name, scryfall_id=raw['id'],
                oracle_source='scryfall', profiles_json=json.dumps({'card_data': raw}))
            for name, raw in self.raw.items()
        }

    def get_cached_cards_by_names(self, names):
        return {}

    def get_card_knowledge_by_names(self, names):
        return {name.casefold(): self.rows[name.casefold()] for name in names}


def create_match(api, monkeypatch, controllers):
    rows, persisted = PublicRows(), []
    before = {name: row.model_dump(mode='json') for name, row in rows.rows.items()}
    # Persistence routing double only. Hydration, Factory and serializer stay real.
    monkeypatch.setattr(api, '_persist_active_match',
                        lambda repo, match: persisted.append(api._controller_snapshot(match)))
    payload = api.StartMatchRequest(
        deck_a=[{'card_name': 'Island', 'quantity': 60}],
        deck_b=[{'card_name': 'Mountain', 'quantity': 60}],
        controller_a=controllers[0], controller_b=controllers[1],
        ai_difficulty='master', mode='ai_vs_ai' if controllers == ('ai', 'ai') else 'player_vs_ai',
        seed=9351,
    )
    response = api._create_match(payload, rows, None, 'unit-persistence-routing-only')
    assert len(api.ACTIVE_MATCHES) == 1
    match = next(iter(api.ACTIVE_MATCHES.values()))
    assert response['id'] == match.state.id
    assert len(match.state.cards) == 120 and match.state.pregame_pending
    for seat, name in ((1, 'Island'), (2, 'Mountain')):
        player = match.state.players[seat]
        assert len(player.hand) == 7 and len(player.library) == 53
        for cid in player.hand + player.library:
            card = match.state.cards[cid]
            physical = card.characteristic_record['physical']
            assert card.owner == seat and card.zone.value in ('hand', 'library')
            for key in ('name', 'type_line', 'oracle_text', 'layout'):
                assert physical[key] == rows.raw[name][key]
            assert physical['card_faces'] == rows.raw[name].get('card_faces', [])
            assert physical['colors'] == rows.raw[name]['colors']
    assert {name: row.model_dump(mode='json') for name, row in rows.rows.items()} == before
    assert persisted == [api._controller_snapshot(match)]
    return match


def finish_with_actual_draw_consumers(scene):
    from game_state.state import draw_card, pregame_actor
    from rules_engine.state_based_actions import apply_state_based_actions

    match = scene.controller
    # Real keep-hand actions and draw/SBA consumers, not assigned winners or fake events.
    for _ in range(2):
        seat = pregame_actor(match.state)
        assert seat in (1, 2)
        match.rules.take_action(match.state, seat, {'type': 'keep_hand'}, reject_invalid=True)
    assert not match.state.pregame_pending and match.state.winner is None
    loser = 3 - scene.seat
    draw_card(match.state, loser, len(match.state.players[loser].library) + 1)
    apply_state_based_actions(match.state)
    assert match.state.winner == scene.seat and len(match.state.cards) == 120
    match.deck_ids = (101, 202)  # Inert history foreign keys, no SQL rows claimed.
    return match


def test_restore_attaches_binding_without_replacing_saved_agent_profile(api, scene):
    from ai.agent import AIAgent

    binding = trusted_binding(scene)
    binding['agent'] = AIAgent(difficulty='casual', archetype='Aggro',
        opponent_archetype='Ramp', learned_binding=scene.binding)
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row, {scene.seat: binding})
    agent = restored.ai[scene.seat]
    assert agent is not binding['agent']
    assert agent.learned_binding is scene.binding
    assert (agent.difficulty, agent.archetype, agent.opponent_archetype) == ('strong', 'Control', 'Control')
    assert saved_record(api, restored, scene.seat) == scene.record


@pytest.mark.parametrize('controllers', (('ai', 'ai'), ('human', 'ai'), ('ai', 'human')),
                         ids=('both-ai', 'human1', 'human2'))
def test_default_new_match_keeps_exact_heuristic_policy_absence(startup, monkeypatch, controllers):
    match = create_match(startup, monkeypatch, controllers)
    assert 'policy_provenance' not in startup._controller_snapshot(match)
    assert all(agent.learned_binding is None for agent in match.ai.values())


@pytest.mark.parametrize('controllers', (('ai', 'ai'), ('human', 'ai'), ('ai', 'human')),
                         ids=('both-ai', 'human1', 'human2'))
def test_explicit_new_match_configuration_binds_only_ai_and_keeps_native_profiles(
        startup, checkpoint_binding, monkeypatch, controllers):
    binding, _ = checkpoint_binding
    assert configure(startup, binding) is None
    match = create_match(startup, monkeypatch, controllers)
    record = startup._controller_snapshot(match)['policy_provenance']
    for seat in (1, 2):
        agent = match.ai[seat]
        expected = binding if controllers[seat - 1] == 'ai' else None
        assert agent.learned_binding is expected
        assert agent.difficulty == 'master'
        assert agent.archetype == startup.guess_archetype(match.mainboards[seat])
        assert agent.opponent_archetype == startup.guess_archetype(match.mainboards[3 - seat])
        if expected is None:
            assert str(seat) not in record
        else:
            assert record[str(seat)] == {
                'version': 'mtg.live-policy.v1', 'requested': 'learned_qv', 'effective': 'learned_qv',
                'checkpoint_sha256': binding.checkpoint_sha256, 'contract': binding.contract,
                'fallback_reason': None,
            }
    assert match.ai[1] is not match.ai[2]


@pytest.mark.parametrize('closed', ('configured', 'lifespan'), ids=('second-call', 'after-freeze'))
def test_configuration_is_one_shot_and_closed_after_lifespan_boundary(
        startup, checkpoint_binding, monkeypatch, closed):
    binding, _ = checkpoint_binding
    if closed == 'configured':
        configure(startup, binding)
    else:
        monkeypatch.setattr(startup.app.state, 'new_match_policy_frozen', True)
    before = startup.app.state.new_match_policy_binding
    with pytest.raises(RuntimeError):
        configure(startup, None)
    assert startup.app.state.new_match_policy_binding is before


def test_lifespan_freeze_is_wired_before_storage_admission(api):
    # Static wiring proof only; this unit scope never starts the App or SQL owner.
    tree = ast.parse(dedent(inspect.getsource(api.lifespan.__wrapped__)))
    body = tree.body[0].body
    assignments = [node for node in body if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == 'app_instance.state.new_match_policy_frozen'
                for target in node.targets)]
    assert len(assignments) == 1
    assert isinstance(assignments[0].value, ast.Constant) and assignments[0].value.value is True
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and ast.unparse(node.func) in ('_prepare_simulation_admission', 'DatabaseOwner')]
    assert calls and assignments[0].lineno < min(node.lineno for node in calls)


@pytest.mark.parametrize('mode', ('learned', 'fallback', 'default'))
def test_terminal_history_keeps_closed_configuration_once_in_original_string_schema(api, scene, mode):
    from persistence.repository import Repository

    if mode != 'default':
        record = deepcopy(scene.record)
        if mode == 'fallback':
            record.update(effective='heuristic', fallback_reason='restore_requires_opt_in')
        scene.controller.policy_provenance = {scene.seat: record}
    match = finish_with_actual_draw_consumers(scene)
    policy = api._controller_snapshot(match).get('policy_provenance')
    before = list(match.state.log)
    session = RecordingSession()
    repo = Repository(session)
    api._post_step_finalize(match, repo)
    assert len(session.rows) == session.commits == 1
    log = json.loads(session.rows[0].log_json)
    assert type(log) is list and all(type(line) is str for line in log)
    assert log == match.state.log
    lines = [line for line in log if line.startswith(PREFIX)]
    if policy:
        assert lines == [PREFIX + json.dumps(policy, sort_keys=True, separators=(',', ':'), allow_nan=False)]
        assert json.loads(lines[0][len(PREFIX):]) == policy
    else:
        p1, p2 = match.state.players[1], match.state.players[2]
        assert not lines
        assert log == before + [f'Game ended summary: {p1.name} life={p1.life}, library={len(p1.library)}; '
                                f'{p2.name} life={p2.life}, library={len(p2.library)}.']
    api._post_step_finalize(match, repo)
    assert len(session.rows) == session.commits == 1 and match.state.log == log


def test_invalid_terminal_metadata_is_rejected_before_history_or_game_mutation(api, scene):
    from game_state.serializers import serialize_match_snapshot
    from persistence.repository import Repository

    match = finish_with_actual_draw_consumers(scene)
    match.policy_provenance = {scene.seat: {**scene.record, 'weights': [[0.5]]}}
    before = serialize_match_snapshot(match.state)
    session = RecordingSession()
    with pytest.raises(ValueError):
        api._post_step_finalize(match, Repository(session))
    assert not session.rows and session.commits == 0
    assert not match.current_game_recorded
    assert serialize_match_snapshot(match.state) == before


def test_new_match_default_never_retroactively_activates_legacy_restore(startup, scene):
    configure(startup, scene.binding)
    row = stored_row(startup, scene.controller)
    restored = restore(startup, row)
    assert 'policy_provenance' not in startup._controller_snapshot(restored)
    assert all(agent.learned_binding is None for agent in restored.ai.values())


@pytest.mark.parametrize('mode', ('matching', 'checkpoint', 'engine', 'absent'))
def test_startup_binding_reactivates_only_matching_recorded_policy(startup, scene, mode):
    from ai.learned_policy import bind_live_policy

    recorded = deepcopy(scene.record)
    if mode == 'checkpoint':
        # Another real validated buffer, never a caller-forged activation receipt.
        other = bind_live_policy(scene.raw_checkpoint + b'\n')
        recorded['checkpoint_sha256'] = other.checkpoint_sha256
        assert recorded['checkpoint_sha256'] != scene.binding.checkpoint_sha256
    elif mode == 'engine':
        # Historical saved source identity, not an eligible current checkpoint.
        recorded['contract']['engine_hash'] = 'b' * 64
    if mode != 'absent':
        configure(startup, scene.binding)
    row = stored_row(startup, scene.controller, {scene.seat: recorded})
    restored = restore(startup, row)  # Genuine legacy wrapper, no explicit override.
    agent = restored.ai[scene.seat]
    assert (agent.difficulty, agent.archetype, agent.opponent_archetype) == ('strong', 'Control', 'Control')
    if mode == 'matching':
        assert agent.learned_binding is scene.binding
        assert saved_record(startup, restored, scene.seat) == recorded
    else:
        assert agent.learned_binding is None
        assert saved_record(startup, restored, scene.seat) == {
            **recorded, 'effective': 'heuristic', 'fallback_reason': 'restore_requires_opt_in',
        }
