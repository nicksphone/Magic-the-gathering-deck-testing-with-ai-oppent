"""Green baseline witnesses, explicitly not extra-turn/phase certification."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys

import pytest
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.extra_sequence_support import (
    FIXTURE, RAW, FAMILIES, action, add, canonical, observe, position, resume, submit,
)

TRACE = []


def test_full_canonical_intake_precedes_tests_and_hashes():
    proof = json.loads((FIXTURE / 'provenance.json').read_text())
    assert proof['facts_modified'] is False and proof['intake_before_tests'] is True
    assert proof['engine_execution_certified'] is False
    assert proof['canonical_sha256'] == hashlib.sha256((FIXTURE / 'canonical.json').read_bytes()).hexdigest()
    for name, raw in RAW.items():
        row = proof['rows'][name]
        assert row['id'] == raw['id'] and row['oracle_id'] == raw['oracle_id']
        assert row['raw_sha256'] == hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert raw['type_line'] == canonical(name)['type_line']
        assert raw.get('oracle_text') == canonical(name).get('oracle_text')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_metadata_ready_is_not_execution_admission(seat, name):
    state = position(seat)
    source = add(state, name, seat, Zone.HAND if name == 'Time Warp' else Zone.BATTLEFIELD)
    before = pickle.dumps(state)
    info = observe(state, source)
    assert pickle.dumps(state) == before
    assert info['metadata_ready'] is True
    assert info['known_gaps'] == ['extra-turn scheduling' if name == 'Time Warp' else 'extra-phase scheduling']
    assert info['execution_certified'] is False
    if name == 'Time Warp':
        assert info['spell']['used_fallback'] is True
        assert info['spell']['effect']['key'] == 'noop'
        assert {p['id'] for p in info['spell']['target_hints']['player_targets']} == {1, 2}
    else:
        ability = info['activated'][0]
        assert ability['mana_cost'] == '{3}{R}{R}' and ability['activation_zone'] == 'battlefield'
        assert ability['text'] == RAW[name]['oracle_text'].split(': ', 1)[1]
        assert info['ability']['effect']['key'] == 'noop' and info['ability']['used_fallback']
        # No spell effect is correct for casting an enchantment; activation is separate.
        assert info['spell']['used_fallback'] is False
    TRACE.append(info)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_relation', ['self', 'opponent'])
def test_time_warp_actual_rejection_restore_normal_turns(seat, target_relation):
    target = seat if target_relation == 'self' else 3 - seat
    state = position(seat)
    source = add(state, 'Time Warp', seat, Zone.HAND)
    creature = add(state, 'Grizzly Bears', target)
    land = add(state, 'Island', target)
    creature.tapped = land.tapped = True
    before = pickle.dumps(state)
    mana = sum(state.players[seat].mana_pool.values())
    with pytest.raises(ActionRejected, match='Unsupported spell resolution: extra-turn scheduling'):
        submit(state, source, target)
    assert pickle.dumps(state) == before
    assert sum(state.players[seat].mana_pool.values()) == mana
    assert not state.stack
    snapshot = serialize_match_snapshot(state)
    state = resume(state)
    assert serialize_match_snapshot(state) == snapshot
    assert state.cards[source.id].zone == Zone.HAND
    assert state.turn == 5 and state.active_player == seat
    assert state.cards[creature.id].tapped and state.cards[land.id].tapped
    seen = []
    hand_before = len(state.players[target].hand)
    for _ in range(36):
        seen.append([state.turn, state.active_player, state.step.value])
        RulesEngine().next_step(state)
        if state.turn == 7 and state.step == Step.DRAW:
            break
    assert state.turn == 7 and state.step == Step.DRAW
    assert {(t, p) for t, p, _ in seen} == {(5, seat), (6, 3 - seat), (7, seat)}
    assert len(state.players[target].hand) == hand_before + 1
    assert not state.cards[creature.id].tapped and not state.cards[land.id].tapped
    assert not state.cards[creature.id].summoning_sick
    TRACE.append({'kind': 'rejected-before-payment', 'seat': seat, 'target': target, 'source': source.id,
                  'mana_spent': 0, 'snapshot_equal': True, 'ordinary_progression': seen,
                  'extra_turn_certified': False})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('step', [Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN, Step.UPKEEP])
def test_assault_not_offered_or_payable_and_original_root_unchanged(seat, step):
    state = position(seat, step)
    source = add(state, 'Aggravated Assault', seat)
    creature = add(state, 'Grizzly Bears', seat)
    opponent = add(state, 'Grizzly Bears', 3 - seat)
    creature.tapped = opponent.tapped = True
    before = pickle.dumps(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert not any(m['type'] == 'activate_ability' and m.get('card_id') == source.id for m in moves)
    assert pickle.dumps(state) == before
    with pytest.raises(ActionRejected, match='not currently legal'):
        submit(state, source)
    assert pickle.dumps(state) == before
    restored = resume(state)
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(state)
    assert restored.cards[creature.id].tapped and restored.cards[creature.id].summoning_sick
    assert restored.cards[opponent.id].tapped
    TRACE.append({'kind': 'activation-withheld', 'seat': seat, 'step': step.value,
                  'source': source.id, 'root_unchanged': True,
                  'payment_untap_phase_execution': 'blocked by admission'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_fresh_process_http_restart_witness(seat, name, tmp_path):
    root = tmp_path / 'restart'
    root.mkdir()
    worker = Path(__file__).with_name('extra_sequence_restart_worker.py')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
           'PYTHONDONTWRITEBYTECODE': '1'}
    for phase in ('seed', 'restore'):
        proc = subprocess.run([sys.executable, str(worker), phase, str(seat), name, str(root)],
                              env=env, capture_output=True, text=True, timeout=60)
        (root / (phase + '.log')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    first = json.loads((root / 'seed-evidence.json').read_text())
    second = json.loads((root / 'restore-evidence.json').read_text())
    assert first['pid'] != second['pid']
    assert second['restored_snapshot_config_rng_receipts_exact'] is True
    assert second['extra_sequence_execution_certified'] is False
    TRACE.extend([first, second])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['missing-target', 'invalid-seat', 'insufficient-mana'])
def test_time_warp_real_rejected_controls_have_no_cost_or_root_mutation(seat, invalid):
    state = position(seat)
    source = add(state, 'Time Warp', seat, Zone.HAND)
    request = action(source)
    if invalid == 'missing-target':
        request['targets'] = {}
    elif invalid == 'invalid-seat':
        request['targets']['target_player'] = 3
    else:
        state.players[seat].mana_pool = {}
    before = pickle.dumps(state)
    from rules_engine.action_validation import checked_action
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, request)
    assert pickle.dumps(state) == before


def test_write_bounded_audit_trace():
    destination = os.environ.get('EXTRA_SEQUENCE_TRACE')
    if destination:
        Path(destination).write_text(json.dumps(TRACE, indent=2, sort_keys=True, default=str) + '\n')
