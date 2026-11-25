"""Inert schedule, reporting, dispatch, and registry controls for the H2H plan."""
import pytest

from scripts import archetype_budget_h2h_v3 as h2h
from scripts.archetype_plan_v3 import build_plan, validate_plan
from scripts.archetype_trace_v3 import digest

REVISION = 'a' * 40
RUNTIME = 'b' * 64


def plan():
    return build_plan(REVISION, h2h.RUN_ID, kind=h2h.KIND, runtime_sha256=RUNTIME)


def test_exact_preregistered_schedule_and_worker_budget():
    packet = plan()
    validate_plan(packet)
    cells = packet['cells']
    assert len(cells) == len({row['cell_id'] for row in cells}) == 216
    assert h2h.schedule_digest(cells) == '205d23c90e200fddbdba77cd10daec2aceb61d2727f72101cc72db7d55e11cf9'
    assert [row['deck_a_seat'] for row in cells[:4]] == [1, 2, 1, 2]
    assert [row['deck_a'] for row in cells[:4]] == ['Blue Control'] * 2 + ['Dimir Control'] * 2
    assert cells[-1]['seed'] == 2026112612
    assert packet['policy']['workers'] == 8
    cap = h2h.Budget(started=0, prior_charged_seconds=139140, workers=8, wall_seconds=6000)
    assert cap.can_launch(now=0, unstarted=1, pending_deadlines=[])
    assert not cap.can_launch(now=1, unstarted=1, pending_deadlines=[])
    packet['cells'][0], packet['cells'][1] = packet['cells'][1], packet['cells'][0]
    with pytest.raises(ValueError):
        validate_plan(packet)


def valid_row(cell, winner, *, pause=False):
    return {'cell_id': cell['cell_id'], 'status': 'error' if pause else 'resolved',
            'termination': h2h.PAUSE if pause else 'life',
            'winner': None if pause else winner, 'child_handles_reaped': True,
            'cpu_attribution_complete': True, 'cpu_seconds': 3., 'parity_checked': True,
            'run_invalid': False, 'trace_bytes': 100}


def test_pause_stays_unresolved_and_integrity_errors_fail_the_campaign():
    packet = plan()
    rows = [valid_row(cell, cell['deck_a_seat'], pause=i < 18)
            for i, cell in enumerate(packet['cells'])]
    report = h2h.report(rows, packet)
    assert report['complete'] and report['usable']
    assert report['comparison']['resolved'] == 198
    assert report['comparison']['unresolved'] == report['pauses'] == 18
    assert report['comparison']['score_bounds'] == [198 / 216, 1.]
    assert not h2h.report(rows[:-1], packet)['usable']
    rows[0]['termination'] = 'rejected_action'
    assert not h2h.report(rows, packet)['usable']
    with pytest.raises(ValueError):
        h2h.report(rows + rows[:1], packet)


def test_only_the_assigned_seat_uses_the_explicit_budget(monkeypatch):
    from types import SimpleNamespace

    from ai import interactive_budget
    from ai.agent import AIAgent
    from scripts.archetype_budget_h2h_worker_v3 import choose_for_cell
    from tests.test_archetype_game_v3 import decks

    def controlled_choice(self, state, offers, seat):
        assert self.difficulty == 'master'
        for _ in range(129):
            interactive_budget.checkpoint()
        return SimpleNamespace(action={'type': 'pass_priority'})

    monkeypatch.setattr(AIAgent, 'choose_action', controlled_choice)
    monkeypatch.setenv('MTG_AI_INTERACTIVE_NODES', '0')
    for seat in (1, 2):
        choose = choose_for_cell((decks(), decks()), {'deck_a_seat': seat})
        bounded = choose(object(), [], seat)
        unlimited = choose(object(), [], 3-seat)
        assert bounded.decision is None and bounded.cutoff == 'node limit'
        assert unlimited.decision.action == {'type': 'pass_priority'} and unlimited.cutoff is None
        assert not bounded.retained and not unlimited.retained


def test_paused_fixture_has_no_invented_action_and_replays_selected_parity(tmp_path):
    from copy import deepcopy
    from scripts.archetype_game_v3 import BudgetDecision, TraceDivergence, replay_trace
    from scripts.archetype_handler_v3 import HandlerChecks
    from scripts.archetype_trace_v3 import CpuAccounting, read_records
    from scripts.archetype_worker_v3 import game_phase, verify_phase
    from tests.test_archetype_game_v3 import choose, decks, rechained

    packet = plan()
    cell = packet['cells'][1]
    identity = {'cell_id': cell['cell_id'], 'budgeted_seat': 2}
    pair = (decks(), decks())

    def choose_then_stop(state, offers, actor):
        if actor == 2:
            return BudgetDecision(None, 'deadline', True)
        return BudgetDecision(choose(state, offers, actor))

    produced = game_phase(pair, cell, packet['policy'], identity, tmp_path, CpuAccounting(),
                          choose=choose_then_stop, trace_max_bytes=packet['trace_policy']['max_bytes'])
    result = produced['outcome']
    assert result['termination'] == h2h.PAUSE and result['winner'] is None
    assert result['accepted_actions'] == 1
    observed = []

    with HandlerChecks(tmp_path/'handler.sqlite3') as handler:
        def parity_boundary(initial, row):
            observed.append(row['step'])
            assert row['action']['type'] == 'keep_hand'
            assert initial['identity'] == identity
            return handler(initial, row)

        checked = verify_phase(pair, cell, packet['policy'], identity, tmp_path, CpuAccounting(),
                               accepted_actions=1, trace_sha256=produced['trace_sha256'],
                               boundary=parity_boundary, trace_max_bytes=packet['trace_policy']['max_bytes'])
    assert checked['replay']['outcome'] == result and observed == [0]
    assert checked['handler_boundaries'][0]['sqlite_roundtrip']
    assert checked['budget_decisions'] == produced['budget_decisions']
    assert checked['budget_decisions']['budgeted']['cutoffs']['deadline'] == 1
    assert checked['budget_decisions']['budgeted']['retained_available'] == 1
    with (tmp_path/'trace.jsonl').open('rb') as stream:
        rows = list(read_records(stream))
    assert [row['kind'] for row in rows] == ['initial', 'action', 'decision_pause', 'final']
    assert 'action' not in rows[2]
    assert rows[2]['before_sha256'] == rows[1]['after_sha256'] == rows[3]['snapshot_sha256']
    for field, value in [('actor', 1), ('before_sha256', '0'*64), ('budget_decision', {})]:
        corrupt = deepcopy(rows)
        corrupt[2][field] = value
        with pytest.raises(TraceDivergence):
            replay_trace(iter(rechained(corrupt)))


def test_separate_campaign_charge_preserves_original_active_bytes_and_host_exclusion(tmp_path):
    from scripts.archetype_registry_v3 import claim_run
    from scripts.archetype_trace_v3 import load_json

    root = tmp_path/'registry'
    identity = {'plan_sha256': 'c'*64, 'revision': REVISION, 'runtime_sha256': RUNTIME,
                'output': str(tmp_path/'output')}
    pilot_id = 'archetype-pilot-20261116-v3-registry-test'
    with claim_run(root, run_id=pilot_id, **identity) as legacy:
        legacy.finish(charged_worker_seconds=720, report_sha256='d'*64)
    active = root/'active.json'
    old_run = root/'runs'/f'{pilot_id}.json'
    previous = active.read_bytes()
    previous_run = old_run.read_bytes()
    with claim_run(root, kind=h2h.KIND, run_id=h2h.RUN_ID, **identity) as budget:
        assert budget.prior_charged_seconds == 0
        assert load_json(active.read_bytes())['run_id'] == h2h.RUN_ID
        with pytest.raises(ValueError, match='owns the host slots'):
            with claim_run(root, run_id='archetype-pilot-20261116-v3-locked', **identity):
                pytest.fail('Second controller acquired the active lease')
        record = budget.finish(charged_worker_seconds=50, report_sha256='e'*64)
        assert record['charged_campaign_worker_seconds'] == 50
        assert record['campaign_worker_seconds'] == 52*3600
    assert active.read_bytes() == previous and old_run.read_bytes() == previous_run
    assert (root/'runs'/f'{h2h.RUN_ID}.prior-active').read_bytes() == previous
    with pytest.raises(FileExistsError):
        with claim_run(root, kind=h2h.KIND, run_id=h2h.RUN_ID, **identity):
            pytest.fail('Consumed run was readmitted')


def test_unproved_closure_leaves_global_guard_for_prior_checkouts(tmp_path):
    from scripts.archetype_registry_v3 import claim_run

    identity = {'plan_sha256': 'c'*64, 'revision': REVISION, 'runtime_sha256': RUNTIME,
                'output': str(tmp_path/'output')}
    root = tmp_path/'registry'
    with claim_run(root, kind=h2h.KIND, run_id=h2h.RUN_ID, **identity):
        pass
    with pytest.raises(ValueError, match='closure is unproven'):
        with claim_run(root, run_id='archetype-pilot-20261116-v3-after-crash', **identity):
            pytest.fail('Unproved closure was ignored')


def test_worker_admission_binds_cell_role_and_extended_cpu_limit():
    import os
    from pathlib import Path
    from scripts import archetype_worker_v3 as worker
    from scripts.archetype_matrix_pilot import file_sha

    packet = plan()
    root = Path(worker.__file__).resolve().parents[2]
    files = ['backend/scripts/archetype_worker_v3.py', 'backend/scripts/archetype_budget_h2h_worker_v3.py']
    request = {'schema': 3, 'mode': 'game', 'plan': packet, 'cell': packet['cells'][1],
               'cpu': min(os.sched_getaffinity(0)), 'cpu_seconds': 4800, 'wall_seconds': 6000.,
               'memory_bytes': 2*1024**3, 'runtime_sha256': RUNTIME,
               'source': {'root': str(root), 'revision': REVISION,
                          'files': {path: file_sha(root/path) for path in files}},
               'trace_sha256': None, 'accepted_actions': None}
    worker.validate_request(request, kind=h2h.KIND)
    assert worker.request_identity(request)['budgeted_seat'] == 2
    with pytest.raises(ValueError):
        worker.validate_request(request, kind='strength')
    with pytest.raises(ValueError):
        worker.validate_request({**request, 'cpu_seconds': 4801}, kind=h2h.KIND)
    with pytest.raises(ValueError):
        worker.validate_request({**request, 'cell': {**request['cell'], 'deck_a_seat': 1}}, kind=h2h.KIND)


def test_controller_accounts_for_all_authored_cells_and_closes_separately(tmp_path, monkeypatch):
    from test_archetype_pilot_v3 import controller_boundary
    from scripts.archetype_trace_v3 import load_json

    controller = controller_boundary(monkeypatch, tmp_path)
    monkeypatch.setattr(controller.os, 'sched_getaffinity', lambda _: set(range(9)))
    monkeypatch.setattr(controller, 'available_memory', lambda: 17 * 1024**3)
    packet = build_plan(REVISION, h2h.RUN_ID, kind=h2h.KIND,
                        runtime_sha256=digest(controller.runtime_identity()))
    pause_id = packet['cells'][0]['cell_id']

    def authored_cell(plan, cell, directory, *, kind, cpu, **kwargs):
        assert kind == h2h.KIND and cpu in range(8)
        return valid_row(cell, cell['deck_a_seat'], pause=cell['cell_id'] == pause_id)

    monkeypatch.setattr(controller, 'run_cell', authored_cell)
    occupied = tmp_path/'occupied'
    occupied.mkdir()
    with pytest.raises(ValueError, match='must be absent'):
        h2h.run_budget_comparison(packet, occupied)
    assert not controller.STATE_ROOT.exists()
    result = h2h.run_budget_comparison(packet, tmp_path/'authored')
    assert result['budget_passed'] and result['accounted'] == 216 and result['pauses'] == 1
    receipt = controller.STATE_ROOT/'runs'/f'{h2h.RUN_ID}.json'
    record = load_json(receipt.read_bytes())
    assert record['state'] == 'closed' and record['child_handles_reaped'] is True
    assert record['report_sha256'] == controller.file_sha(tmp_path/'authored'/'BUDGET-H2H-COMPLETE.json')
    assert not (controller.STATE_ROOT/'active.json').exists()
