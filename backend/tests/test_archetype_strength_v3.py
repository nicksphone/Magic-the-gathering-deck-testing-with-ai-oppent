"""Strength design and analysis tests with authored outcomes only."""
from copy import deepcopy

import pytest


RERUN2_ID = 'archetype-strength-20261124-v3-rerun2'


def plan(run_id='archetype-strength-20261122-v3-main1'):
    from scripts.archetype_plan_v3 import build_plan
    from scripts.archetype_trace_v3 import digest
    return build_plan('a'*40, run_id, kind='strength',
                      runtime_sha256=digest({'unit_runtime': True}))


def test_strength_schedule_and_exact_plan_validation():
    from scripts.archetype_plan_v3 import validate_plan
    p = plan()
    validate_plan(p)
    assert p['seeds'] == list(range(2026112201, 2026112210))
    assert len(p['cells']) == 648
    assert len({c['cell_id'] for c in p['cells']}) == 648
    assert all(c['deck_a'] == c['deck_b'] for c in p['cells'])
    assert set(p['source_matrix']['excluded_decks']) == {'Burn', 'Mono Red Aggro'}
    for opponent in ('random', 'casual', 'strong', 'master'):
        for deck in p['source_matrix']['decks']:
            for seed in p['seeds']:
                assert {c['deck_a_seat'] for c in p['cells'] if
                        (c['opponent'], c['deck_a'], c['seed']) == (opponent, deck, seed)} == {1, 2}
    assert p['worker_hour_budget']['campaign'] == 120
    assert p['policy']['max_seconds'] == 3000
    assert p['policy']['max_cpu_seconds_per_game'] == 2400
    assert len(p['cells']) * p['trace_policy']['max_bytes'] <= 15*1024**3
    bad = deepcopy(p)
    bad['cells'][0]['opponent'] = 'strong'
    with pytest.raises(ValueError):
        validate_plan(bad)


def authored_rows(p):
    return [{'cell_id': c['cell_id'], 'status': 'resolved',
             'winner': 1 if c['opponent'] == 'master' else c['deck_a_seat'],
             'seconds': 100., 'cpu_seconds': 90., 'trace_bytes': 1,
             'parity_checked': True, 'cpu_attribution_complete': True,
             'child_handles_reaped': True, 'run_invalid': False}
            for c in p['cells']]


def test_strength_score_bounds_and_mirror_control():
    from scripts.archetype_strength_v3 import strength_report
    p = plan()
    rows = authored_rows(p)
    assert strength_report(rows, p)['strength_passed']
    rows[0].update(status='timeout', winner=None, parity_checked=False)
    r = strength_report(rows, p)['comparisons']['random']
    assert r['score'] == 1 and r['unresolved'] == 1
    assert r['score_bounds'] == [161/162, 1]
    assert r['deck_scores'][p['cells'][0]['deck_a']]['score_bounds'] == [17/18, 1]
    mirror = next(i for i,c in enumerate(p['cells']) if c['opponent'] == 'master')
    rows[mirror].update(status='timeout', winner=None, parity_checked=False)
    assert not strength_report(rows, p)['strength_passed']
    with pytest.raises(ValueError):
        strength_report([rows[0], rows[0]], p)


def test_strength_registry_carried_charges_and_legacy_record(tmp_path):
    from scripts.archetype_registry_v3 import claim_run
    p = plan()
    key = dict(plan_sha256='a'*64, revision='b'*40, runtime_sha256='c'*64, output=str(tmp_path/'out'))
    root = tmp_path/'registry'
    with pytest.raises(ValueError, match='closed health rerun charge history'):
        with claim_run(root, run_id=p['run_id'], kind='strength', **key):
            pytest.fail('fresh registry discarded the carried charges')
    with claim_run(root, run_id='archetype-health-20261116-v3-rerun1', kind='health', **key) as claim:
        claim.finish(charged_worker_seconds=62796.9, report_sha256='d'*64)
    old = (root/'runs/archetype-health-20261116-v3-rerun1.json').read_bytes()
    with claim_run(root, run_id=p['run_id'], kind='strength', **key) as claim:
        assert claim.prior_charged_seconds == 62796.9
        row = claim.finish(charged_worker_seconds=100., report_sha256=None)
    assert row['campaign_id'] == p['campaign_id']
    assert row['remaining_campaign_worker_seconds'] == 120*3600 - 62896.9
    assert row['charged_health_worker_seconds'] == 62796.9
    assert (root/'runs/archetype-health-20261116-v3-rerun1.json').read_bytes() == old
    with pytest.raises(FileExistsError):
        with claim_run(root, run_id=p['run_id'], kind='strength', **key):
            pytest.fail('consumed run ID was reused')


def test_random_offer_policy_deduplicates_and_checks_before_sampling(monkeypatch):
    from rules_engine import action_validation
    from scripts.archetype_strength_worker_v3 import random_action

    kept = {'type': 'keep_hand', 'bottom_card_ids': []}
    passed = {'type': 'pass_priority'}
    rejected = {'type': 'mulligan'}
    state, rules = object(), object()
    seen = []

    def checked(value, engine, seat, action):
        assert value is state and engine is rules and seat == 2
        seen.append(action)
        if action == rejected:
            raise action_validation.ActionRejected('authored illegal action')

    class Pick:
        def choice(self, candidates):
            assert candidates == [kept, passed]
            return candidates[1]

    monkeypatch.setattr(action_validation, 'checked_action', checked)
    offers = [[kept, kept], [rejected], [passed]]
    decision = random_action(state, offers, 2, rng=Pick(), materialize=lambda row: row, rules=rules)
    assert decision.action == passed
    assert seen == [kept, kept, rejected, passed]
    with pytest.raises(action_validation.ActionRejected):
        random_action(state, [[rejected]], 2, rng=Pick(), materialize=lambda row: row, rules=rules)


def test_strength_budget_admission_uses_120_hour_cap_with_prior_charges():
    from scripts.archetype_strength_v3 import StrengthBudget

    b = StrengthBudget(started=0., prior_charged_seconds=62796.9, wall_seconds=3000)
    assert b.remaining_campaign_seconds(0.) == pytest.approx(369203.1)
    assert b.can_launch(now=0., unstarted=648, pending_deadlines=[])
    assert b.can_launch(now=181571.5, unstarted=1, pending_deadlines=[])
    assert not b.can_launch(now=181572., unstarted=1, pending_deadlines=[])
    assert not b.can_launch(now=0., unstarted=1, pending_deadlines=[185000.])


@pytest.mark.parametrize(('run_id', 'cpu_limit', 'wall_limit'), [
    ('archetype-strength-20261122-v3-main1', 2400, 3000),
    (RERUN2_ID, 4800, 6000),
])
def test_strength_parent_and_worker_use_explicit_role_and_shared_limits(tmp_path, monkeypatch, run_id, cpu_limit, wall_limit):
    import os
    import threading
    from test_archetype_pilot_v3 import authored_phase_controller
    from scripts.archetype_matrix_pilot import file_sha
    from scripts.archetype_worker_v3 import validate_request

    core, requests, source = authored_phase_controller(monkeypatch)
    role = 'scripts.archetype_strength_worker_v3'
    role_path = 'backend/scripts/archetype_strength_worker_v3.py'
    source['files'][role_path] = file_sha(core.BACKEND.parent/role_path)
    original = core.run_process

    def child(command, **kwargs):
        assert command[3] == role
        return original(command, **kwargs)

    monkeypatch.setattr(core, 'run_process', child)
    p = plan(run_id)
    row = core.run_cell(p, p['cells'][0], tmp_path/'cell', cpu=min(os.sched_getaffinity(0)),
                        source=source, runtime={'unit_runtime': True}, stop=threading.Event(),
                        kind='strength')
    assert row['status'] == 'resolved' and row['parity_checked']
    assert [r['cpu_seconds'] for r in requests] == [cpu_limit, cpu_limit - 11]
    assert [r['wall_seconds'] for r in requests] == [wall_limit, wall_limit - 15]
    for kind in ('pilot', 'health'):
        with pytest.raises(ValueError):
            validate_request(requests[0], kind=kind)
    validate_request(requests[0], kind='strength')
    for field in ('cpu_seconds', 'wall_seconds'):
        with pytest.raises(ValueError):
            validate_request({**requests[0], field: requests[0][field] + 1}, kind='strength')
    bad = deepcopy(requests[0])
    del bad['source']['files'][role_path]
    with pytest.raises(ValueError):
        validate_request(bad, kind='strength')


def test_light_trace_retains_periodic_and_final_but_recomputes_handler_snapshots():
    from scripts.archetype_game_v3 import _checkpoints

    p = plan()['policy']
    before, after = {}, {'pending_mechanic_choice': {'kind': 'authored'}}
    assert _checkpoints({}, before, after, 0, final=False) == ['handler', 'choice']
    assert _checkpoints(p, before, after, 0, final=False) == []
    assert _checkpoints(p, before, after, 255, final=False) == ['periodic']
    assert _checkpoints(p, before, after, 256, final=True) == ['final']


def test_strength_report_never_passes_weak_or_unaccounted_results():
    from scripts.archetype_strength_v3 import strength_report

    p = plan()
    rows = authored_rows(p)
    for cell, row in zip(p['cells'], rows):
        if cell['opponent'] == 'strong':
            row['winner'] = 1
    r = strength_report(rows, p)
    assert r['comparisons']['strong']['score'] == .5
    assert r['comparisons']['strong']['ci_95'] == [.5, .5]
    assert not r['strength_passed']
    assert not strength_report(rows[:-1], p)['complete']
    rows = authored_rows(p)
    rows[0].update(child_handles_reaped=False, cpu_seconds=None)
    assert not strength_report(rows, p)['strength_passed']


@pytest.mark.parametrize(('run_id', 'campaign_hours', 'prior_worker_seconds'), [
    ('archetype-strength-20261122-v3-main1', 120, 62796.9),
    (RERUN2_ID, 200, 363883.66),
])
def test_controller_closes_full_authored_strength_schedule(tmp_path, monkeypatch, run_id, campaign_hours,
                                                            prior_worker_seconds):
    import json
    from test_archetype_pilot_v3 import controller_boundary
    from scripts.archetype_registry_v3 import claim_run
    from scripts.archetype_strength_v3 import run_strength

    core = controller_boundary(monkeypatch, tmp_path)
    p = plan(run_id)
    with claim_run(core.STATE_ROOT, run_id='archetype-health-20261116-v3-rerun1',
                   plan_sha256='a'*64, revision=p['revision'], runtime_sha256=p['runtime_sha256'],
                   output=str(tmp_path/'old'), kind='health') as prior:
        prior.finish(charged_worker_seconds=62796.9, report_sha256='d'*64)
    if run_id == RERUN2_ID:
        with claim_run(core.STATE_ROOT, run_id=plan()['run_id'], plan_sha256='a'*64,
                       revision=p['revision'], runtime_sha256=p['runtime_sha256'],
                       output=str(tmp_path/'original'), kind='strength') as prior:
            prior.finish(charged_worker_seconds=301086.76, report_sha256='e'*64)
    authored = {row['cell_id']: row for row in authored_rows(p)}

    def cell(plan, cell, directory, *, kind, **kwargs):
        assert kind == 'strength' and cell['deck_a'] == cell['deck_b']
        return authored[cell['cell_id']]

    monkeypatch.setattr(core, 'run_cell', cell)
    output = tmp_path/'strength'
    report = run_strength(p, output)
    assert report['strength_passed'] and report['accounted'] == 648
    current = json.loads((core.STATE_ROOT/'active.json').read_bytes())
    assert current['state'] == 'closed'
    assert current['charged_before_worker_seconds'] == pytest.approx(prior_worker_seconds)
    assert current['charged_campaign_worker_seconds'] > prior_worker_seconds
    assert current['campaign_worker_seconds'] == campaign_hours * 3600
    assert current['report_sha256'] == core.file_sha(output/'STRENGTH-COMPLETE.json')
    assert current['remaining_campaign_worker_seconds'] < campaign_hours * 3600 - prior_worker_seconds
    assert report['remaining_campaign_worker_seconds'] > campaign_hours * 3600 - prior_worker_seconds - 3600


@pytest.mark.parametrize('candidate', [1, 2])
def test_chooser_preserves_candidate_seat_and_baseline_roles(monkeypatch, candidate):
    from types import SimpleNamespace
    from ai import agent, deck_analysis, information
    from scripts import archetype_strength_worker_v3 as worker

    class StubAgent:
        def __init__(self, *, difficulty, archetype, opponent_archetype):
            assert archetype == opponent_archetype == 'fixture'
            self.difficulty = difficulty

        def choose_action(self, state, offers, player):
            return self.difficulty, player

    monkeypatch.setattr(agent, 'AIAgent', StubAgent)
    monkeypatch.setattr(deck_analysis, 'guess_archetype', lambda _: 'fixture')
    monkeypatch.setattr(information, 'decision_view', lambda state, seat, offers: ('visible', offers))
    monkeypatch.setattr(worker, 'random_action',
                        lambda state, offers, seat, **kw: ('random', seat))
    for opponent in ('random', 'casual', 'strong', 'master'):
        cell = {'deck_a_seat': candidate, 'deck_a': 'fixture', 'seed': 1, 'opponent': opponent}
        choose = worker.choose_for_cell(([], []), cell)
        assert choose(SimpleNamespace(), [], candidate) == ('master', candidate)
        assert choose(SimpleNamespace(), [], 3-candidate) == (opponent, 3-candidate)


def test_rerun2_frozen_schedule_limits_and_acceptance():
    from scripts.archetype_plan_v3 import validate_plan
    from scripts.archetype_strength_v3 import StrengthBudget, strength_report

    old = plan()
    p = plan(RERUN2_ID)
    validate_plan(p)
    assert p['strength_gate'] == old['strength_gate']
    assert p['campaign_id'] == old['campaign_id']
    assert p['seeds'] == list(range(2026112401, 2026112410))
    assert len(p['cells']) == 648
    assert {r['cell_id'] for r in old['cells']}.isdisjoint(r['cell_id'] for r in p['cells'])
    assert [(r['deck_a'], r['deck_b'], r['opponent'], r['deck_a_seat']) for r in p['cells']] == [
        (r['deck_a'], r['deck_b'], r['opponent'], r['deck_a_seat']) for r in old['cells']]
    assert p['worker_hour_budget']['campaign'] == 200
    assert p['policy']['max_cpu_seconds_per_game'] == 4800
    assert p['policy']['max_seconds'] == 6000
    assert p['trace_policy'] == {**old['trace_policy'], 'checkpoint_interval': 512}
    for section, field, value in (
        ('policy', 'max_cpu_seconds_per_game', 2400),
        ('policy', 'max_seconds', 3000),
        ('policy', 'snapshot_checkpoint_interval', 256),
        ('trace_policy', 'serde_every_action', False),
        ('worker_hour_budget', 'campaign', 201),
    ):
        bad = deepcopy(p)
        bad[section][field] = value
        with pytest.raises(ValueError):
            validate_plan(bad)
    rows = authored_rows(p)
    assert strength_report(rows, p)['strength_passed'] is True
    mirror = next(r for r, c in zip(rows, p['cells']) if c['opponent'] == 'master')
    mirror.update(status='timeout', winner=None, parity_checked=False)
    assert strength_report(rows, p)['strength_passed'] is False

    budget = StrengthBudget(started=0., prior_charged_seconds=363883.66,
                            wall_seconds=6000, run_id=RERUN2_ID)
    assert budget.remaining_campaign_seconds(0.) == pytest.approx(356116.34)
    assert budget.can_launch(now=0., unstarted=648, pending_deadlines=[])
    assert budget.can_launch(now=172028.16, unstarted=1, pending_deadlines=[])
    assert not budget.can_launch(now=172028.18, unstarted=1, pending_deadlines=[])


def test_rerun2_registry_retains_both_closed_predecessors(tmp_path):
    from scripts.archetype_registry_v3 import _write, claim_run

    root = tmp_path/'registry'
    key = dict(plan_sha256='a'*64, revision='b'*40, runtime_sha256='c'*64, output=str(tmp_path/'out'))
    health = 'archetype-health-20261116-v3-rerun1'
    original = plan()['run_id']
    with claim_run(root, run_id=health, kind='health', **key) as claim:
        claim.finish(charged_worker_seconds=62796.9, report_sha256='d'*64)
    with pytest.raises(ValueError, match='closed original strength'):
        with claim_run(root, run_id=RERUN2_ID, kind='strength', **key):
            pytest.fail('original history is missing')
    with claim_run(root, run_id=original, kind='strength', **key) as claim:
        closed = claim.finish(charged_worker_seconds=301086.76, report_sha256='e'*64)
    paths = [root/'runs'/f'{run_id}.json' for run_id in (health, original)]
    before = [path.read_bytes() for path in paths]
    active = root/'active.json'
    reduced = {**closed, 'charged_campaign_worker_seconds': closed['charged_campaign_worker_seconds'] - 1,
               'remaining_campaign_worker_seconds': closed['remaining_campaign_worker_seconds'] + 1,
               'charged_strength_worker_seconds': closed['charged_strength_worker_seconds'] - 1}
    _write(active, reduced, replace=True)
    with pytest.raises(ValueError, match='closed original strength'):
        with claim_run(root, run_id=RERUN2_ID, kind='strength', **key):
            pytest.fail('rerun2 accepted a lowered cumulative charge')
    _write(active, closed, replace=True)
    with claim_run(root, run_id=RERUN2_ID, kind='strength', **key) as claim:
        assert claim.prior_charged_seconds == pytest.approx(363883.66)
        assert claim.record['campaign_worker_seconds'] == 200 * 3600
        assert claim.record['charged_strength_before_worker_seconds'] == 301086.76
        row = claim.finish(charged_worker_seconds=100., report_sha256='f'*64)
    assert row['remaining_campaign_worker_seconds'] == pytest.approx(356016.34)
    assert row['charged_strength_worker_seconds'] == 301186.76
    assert [path.read_bytes() for path in paths] == before
    with pytest.raises(FileExistsError):
        with claim_run(root, run_id=RERUN2_ID, kind='strength', **key):
            pytest.fail('consumed run ID was reused')


def test_rerun2_plan_cli_selects_exact_id_without_writing(monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace
    from scripts import archetype_strength_v3 as strength

    monkeypatch.setattr(sys, 'flags', SimpleNamespace(optimize=0, dont_write_bytecode=1))
    monkeypatch.setattr(strength.subprocess, 'check_output', lambda *args, **kwargs: 'a'*40)
    monkeypatch.setattr(strength.pilot, 'source_identity', lambda revision: None)
    monkeypatch.setattr(strength.pilot, 'runtime_identity', lambda: {'unit_runtime': True})
    published = []
    monkeypatch.setattr(strength.pilot, 'publish', lambda path, value: published.append((path, value)))
    output = tmp_path/'plan.json'
    assert strength.main(['plan', str(output), '--run-id', RERUN2_ID]) == 0
    assert published == [(output, plan(RERUN2_ID))]
    with pytest.raises(SystemExit):
        strength.main(['plan', str(output), '--run-id', 'unknown-run'])
    assert not output.exists()
