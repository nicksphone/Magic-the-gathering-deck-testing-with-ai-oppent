"""Canonical reward/response families, real payment and public-tail witnesses."""
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.test_paid_trigger_ai_integration_audit import (
    RULES, actual_choice, add, advance, branch, cards, record, require_pending, step)


DIRECTORY = Path(__file__).parent / 'fixtures/paid_optional_policy'
RAW = {r['name']: r for r in map(json.loads, (DIRECTORY / 'canonical.jsonl').read_text().splitlines())}
RAW.update({r['name']: r for r in map(json.loads, (DIRECTORY / 'lifegain.jsonl').read_text().splitlines())})
cards.ROWS.update(RAW)
CASES = [
    ('Lunar Mystic', 'Counterspell', 2, 3, False),
    ('Faith of the Devoted', 'Counterspell', 2, 1, False),
    ('Faith of the Devoted', 'Counterspell', 2, 2, True),
    ('Drake Haven', 'Negate', 2, 3, False),
    ('Drake Haven', 'Dispel', 1, 3, False),
    ('Drake Haven', 'Counterspell', 3, 3, True),
    ('Drake Haven', 'Counterspell', 2, 4, True),
]


def position(seat, source_name, answer_name, lands, life, land_name='Island'):
    state = cards.position(seat)
    state.active_player = state.priority_player = 3-seat
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state.players[seat].life = life
    source = add(state, source_name, seat)
    source.owner = 3-seat
    counter = add(state, answer_name, seat, Zone.HAND)
    bolt = add(state, 'Lightning Bolt', 3-seat, Zone.HAND)
    add(state, 'Swamp', 3-seat, Zone.HAND)
    for _ in range(lands):
        add(state, land_name, seat)
    for _ in range(4):
        add(state, 'Island', seat, Zone.LIBRARY)
    state.players[3-seat].mana_pool = {'R': 1}
    state.players[seat].mana_pool = {'R' if source_name == 'Lunar Mystic' else 'U': 1}
    state = step(state, 3-seat, cards.cast(bolt, targets={'target_player': seat}))
    bolt_id = state.stack[-1].id
    state = step(state, 3-seat, {'type': 'pass_priority'})
    if source_name == 'Lunar Mystic':
        own = add(state, 'Lightning Bolt', seat, Zone.HAND)
        state = step(state, seat, cards.cast(own, targets={'target_player': 3-seat}))
    else:
        sandbar = add(state, 'Lonely Sandbar', seat, Zone.HAND)
        state = step(state, seat, {'type': 'cycle_card', 'card_id': sandbar.id})
    state = advance(state, lambda s: bool(s.pending_trigger_order))
    require_pending(state, source)
    return state, counter, bolt_id


def response_window(state, bolt_id, seat):
    state = advance(state, lambda s: len(s.stack) == 1 and s.stack[0].id == bolt_id)
    if state.priority_player != seat:
        state = step(state, state.priority_player, {'type': 'pass_priority'})
    return state


def finish_response(state, seat):
    for _ in range(12):
        if not state.stack or state.winner is not None:
            return state
        if state.pending_trigger_order:
            move = next(m for m in RULES.legal_moves(state, seat)
                        if m['type'] == 'choose_optional_effect' and not m['accept'])
            state = step(state, seat, move)
        else:
            state = step(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Exact response witness did not finish')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name,answer_name,lands,life,accept', CASES)
def test_actual_family_choice_with_complete_checked_response_witness(
        request, monkeypatch, seat, source_name, answer_name, lands, life, accept):
    state, counter, bolt_id = position(seat, source_name, answer_name, lands, life)
    decision = actual_choice(state, seat, monkeypatch)
    no = response_window(branch(state, seat, False), bolt_id, seat)
    counter_action = cards.cast(counter, targets={'target_stack_id': bolt_id})
    safe = finish_response(step(no, seat, counter_action), seat)
    assert safe.winner is None and safe.players[seat].life == life
    yes = response_window(branch(state, seat, True), bolt_id, seat)
    if lands == 3:
        answered = finish_response(step(yes, seat, counter_action), seat)
        assert answered.winner is None and answered.players[seat].life == life
    else:
        from rules_engine.action_validation import ActionRejected
        with cards.unchanged_root(yes), pytest.raises(ActionRejected):
            step(yes, seat, counter_action)
    paid_unanswered = advance(yes, lambda s: not s.stack)
    if source_name == 'Faith of the Devoted' and life == 2:
        assert paid_unanswered.winner is None and paid_unanswered.players[seat].life == 1
    elif life == 4:
        assert paid_unanswered.winner is None and paid_unanswered.players[seat].life == 1
    else:
        assert paid_unanswered.winner == 3-seat
    result = branch(state, seat, decision.action['accept'])
    record(request, seat=seat, source_name=source_name, answer_name=answer_name,
           pending=serialize_match_snapshot(state), decision=decision.action,
           decline_known_response=serialize_match_snapshot(safe),
           paid_unanswered=serialize_match_snapshot(paid_unanswered),
           actual_immediate=serialize_match_snapshot(result), expected_accept=accept,
           root_private_rng_unchanged=True)
    assert decision.action['accept'] is accept


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_dredge_prefix_remains_unknown_and_root_pure(seat):
    from ai.paid_optional_policy import _response_window
    state, _, _ = position(seat, 'Drake Haven', 'Counterspell', 2, 3)
    add(state, 'Life from the Loam', seat, Zone.GRAVEYARD)
    view, _ = decision_view(state, seat, RULES.legal_moves(state, seat))
    no = branch(view, seat, False)
    before = serialize_match_snapshot(no)
    assert _response_window(no, seat) is None
    assert serialize_match_snapshot(no) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_preserve_real_lifegain_response_not_only_counters(request, monkeypatch, seat):
    from rules_engine.action_validation import ActionRejected
    state, answer, bolt_id = position(seat, 'Drake Haven', "Whitesun's Passage", 2, 3, 'Plains')
    decision = actual_choice(state, seat, monkeypatch)
    no = response_window(branch(state, seat, False), bolt_id, seat)
    safe = finish_response(step(no, seat, cards.cast(answer)), seat)
    assert safe.winner is None and safe.players[seat].life == 5
    yes = response_window(branch(state, seat, True), bolt_id, seat)
    with cards.unchanged_root(yes), pytest.raises(ActionRejected):
        step(yes, seat, cards.cast(answer))
    doomed = advance(yes, lambda s: not s.stack)
    assert doomed.winner == 3-seat
    record(request, seat=seat, decision=decision.action,
           pending=serialize_match_snapshot(state), decline_lifegain=serialize_match_snapshot(safe),
           paid_unanswered=serialize_match_snapshot(doomed), known_original_answer_id=answer.id)
    assert decision.action['accept'] is False


def test_additional_raw_records_are_unchanged_and_pinned():
    for source, manifest in [('canonical.jsonl', 'provenance.json'), ('lifegain.jsonl', 'lifegain-provenance.json')]:
        provenance = json.loads((DIRECTORY / manifest).read_text())
        assert not provenance['facts_modified'] and provenance['http_requests'] == 0
        assert hashlib.sha256((DIRECTORY / source).read_bytes()).hexdigest() == provenance['canonical_jsonl_sha256']
        for name, pin in provenance['rows'].items():
            assert hashlib.sha256(json.dumps(RAW[name], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == pin['raw_sha256']
