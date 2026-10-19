"""Paid canonical choice diagnostics, not natural matches or strength certification."""
import hashlib
import json
import os
import random
from copy import deepcopy
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.deck_analysis import analyze_deck
from ai.information import decision_view, is_unknown
from nadu_support import Position, snapshot, restored, conservation
from rules_engine.engine import RulesEngine
from rules_engine.granted_target_triggers import _capture_grants, _reference_key
from rules_engine.targeting import capture_announced_target_references


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write(name, value):
    root = Path(os.environ['NADU_EVIDENCE'])
    data = json.dumps(value, sort_keys=True, indent=2).encode()
    assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) + len(data) + 1024**2 <= 16*1024**2
    (root / name).write_bytes(data)


def prepare(seat, phase):
    p = Position(seat, 'ai_' + phase, branch='nonland')
    p.shock_pay = False  # A declared choice through the real land-entry continuation.
    p.equip(p.ids['nadu'])
    p.equip(p.ids['nadu'])
    p.equip(p.ids['elf'])
    if phase == 'spent':
        p.equip(p.ids['elf'])
    p.state = restored(p.state)
    assert p.state.cards[p.ids['shuko']].attached_to == p.ids['elf']
    announced = {'target_card_id': p.ids['elf']}
    capture = _capture_grants(p.state, announced,
        capture_announced_target_references(p.state, announced), stack_kind='activated')
    assert len(capture['receipts']) == 1
    receipt = capture['receipts'][0]
    identity = [_reference_key(receipt['recipient_ref']), _reference_key(receipt['grant_source_ref']),
                receipt['clause_instance']]
    prefix = 'granted-target:' + json.dumps([p.state.turn, identity], separators=(',', ':'))
    used = sum(f'{prefix}:{slot}' in p.state.trigger_once_seen_this_turn
               for slot in range(receipt['trigger_limit']))
    assert used == (1 if phase == 'one_slot' else 2)
    assert receipt['compiled_instruction'] == ['Land', 'battlefield', 'hand']
    return p, receipt, used


def choose(state, seat, board):
    offered = RulesEngine().legal_moves(state, seat)
    before = snapshot(state)
    moves_before = deepcopy(offered)
    rng = random.getstate()
    archetype = analyze_deck(board)['primary_archetype']
    agent = AIAgent(difficulty='master_plus', archetype=archetype, opponent_archetype=archetype)
    decision = agent.choose_action(state, offered, seat)
    assert snapshot(state) == before and offered == moves_before
    assert random.getstate() == rng
    action = decision.action
    assert any(m['type'] == action['type'] and
               (not action.get('card_id') or m.get('card_id') == action['card_id']) for m in offered)
    if action['type'] == 'equip':
        move = next(m for m in offered if m['type'] == 'equip' and m['card_id'] == action['card_id'])
        assert action['target_card_id'] in {t['id'] for t in move['targets']}
    return action, {'archetype': archetype, 'difficulty': 'master_plus', 'offered': offered,
                    'selected': action, 'reasoning': decision.reasoning,
                    'input_snapshot_sha256': digest(before), 'root_rng_private_inputs_unchanged': True}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('phase', ['one_slot', 'spent'])
@pytest.mark.parametrize('kind', ['desired_choice', 'privacy_counterfactual'])
def test_actual_paid_ai_equip_boundary(seat, phase, kind):
    p, receipt, used = prepare(seat, phase)
    evidence = {'seat': seat, 'phase': phase, 'kind': kind, 'remaining_slots': 2-used,
                'descriptor': receipt, 'canonical_paid_setup': True,
                'source_gameplay_injection': False, 'setup_actions': p.actions,
                'paid_casts': [r for r in p.trace if 'paid_cast' in r],
                'setup_trace_sha256': digest(p.trace), 'claims_strength': False}
    name = f'ai-{seat}-{phase}-{kind}.json'
    try:
        action, decision = choose(p.state, seat, p.board)
        evidence['decision'] = decision
        if kind == 'privacy_counterfactual':
            counterfactual = deepcopy(p.state)
            library = counterfactual.players[seat].library
            view, _ = decision_view(p.state, seat, RulesEngine().legal_moves(p.state, seat))
            candidates = [cid for cid in library if is_unknown(view.cards[cid])]
            first = candidates[-1]
            second = next(cid for cid in candidates if
                          ('Land' in p.state.cards[cid].types) != ('Land' in p.state.cards[first].types))
            a, b = library.index(first), library.index(second)
            library[a], library[b] = library[b], library[a]
            conservation(counterfactual)
            second_view, _ = decision_view(counterfactual, seat,
                                          RulesEngine().legal_moves(counterfactual, seat))
            public_a, public_b = snapshot(view), snapshot(second_view)
            # Physical opaque IDs/order are not public library observations.
            for public in (public_a, public_b):
                for player in public['players'].values():
                    player['library'] = sorted(player['library'])
            assert public_a == public_b, 'Public-equivalent opaque input required'
            alternative, second_decision = choose(counterfactual, seat, p.board)
            evidence['counterfactual'] = {'label': 'test-only hidden library permutation, NOT gameplay',
                                          'decision': second_decision, 'input_pair_public_equivalent': True}
            assert alternative == action, 'Unknown library identity must not select a different action'
        before_library = list(p.state.players[seat].library)
        before_quota = set(p.state.trigger_once_seen_this_turn)
        p.act(seat, action)
        generated = [i for i in p.state.stack if i.effect_key == 'reveal_top_conditional']
        evidence['actual_published_granted_receipts'] = [i.payload for i in generated]
        p.settle()
        evidence['actual_action_resolved'] = True
        evidence['library_delta'] = len(before_library) - len(p.state.players[seat].library)
        evidence['quota_delta'] = len(p.state.trigger_once_seen_this_turn - before_quota)
        evidence['final_snapshot_sha256'] = digest(snapshot(p.state))
        if kind == 'desired_choice' and phase == 'one_slot':
            assert action == {'type': 'equip', 'card_id': p.ids['shuko'], 'target_card_id': p.ids['elf']}, \
                'Productive zero-cost already-attached equip must be selected over passing'
            assert len(generated) == 1 and evidence['quota_delta'] == 1 and evidence['library_delta'] == 1
        if kind == 'desired_choice' and phase == 'spent':
            assert action['type'] != 'equip', 'No payoff-free equip after all own recipients spent quota'
            assert not generated and evidence['quota_delta'] == 0
        evidence['assertions_passed'] = True
    except BaseException as error:
        evidence['failure'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        write(name, evidence)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('phase', ['one_slot', 'spent'])
def test_actual_paid_legal_counterfactual_payoff(seat, phase):
    p, receipt, used = prepare(seat, phase)
    offered = RulesEngine().legal_moves(p.state, seat)
    move = next(m for m in offered if m['type'] == 'equip' and m['card_id'] == p.ids['shuko'])
    assert p.ids['elf'] in {target['id'] for target in move['targets']}
    before = snapshot(p.state)
    trace_start = len(p.trace)
    top = p.state.players[seat].library[-1]
    p.equip(p.ids['elf'], expected_trigger=phase == 'one_slot')
    evidence = {'seat': seat, 'phase': phase, 'kind': 'actual_paid_legal_counterfactual',
                'label': 'explicit unchosen legal comparison, NOT substituted AI action',
                'remaining_slots': 2-used, 'descriptor': receipt,
                'before_sha256': digest(before), 'after_sha256': digest(snapshot(p.state)),
                'offered_equip': move, 'actual_action': {'type': 'equip', 'card_id': p.ids['shuko'],
                                                       'target_card_id': p.ids['elf']},
                'actual_publication_receipts': [row for row in p.trace[trace_start:]
                                               if row.get('actual_equip_receipt')],
                'library_delta': len(before['players'][str(seat)]['library']) - len(p.state.players[seat].library),
                'original_top_destination': p.state.cards[top].zone.value,
                'final_attachment': p.state.cards[p.ids['shuko']].attached_to,
                'paid_casts': [row for row in p.trace if 'paid_cast' in row],
                'no_gameplay_state_injection': True, 'assertions_passed': True}
    write(f'counterfactual-{seat}-{phase}.json', evidence)
