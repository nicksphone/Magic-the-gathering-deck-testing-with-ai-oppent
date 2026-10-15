"""Desired rules behavior on canonical paid boards, not natural games or AI evidence."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot as snap, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.agent_control_facts import ROWS
from tests.test_linked_damage_targets import raw_card
from tests.test_source_linked_exile import FACTS, BOOMERANG

HERE = Path(__file__).parent
STIFLE = json.loads((HERE/'fixtures/agent_self_entry/stifle.json').read_bytes())


def action(state, seat, value, journal=None):
    if journal is not None:
        journal.append((seat, deepcopy(value)))
    return checked_action(state, RulesEngine(), seat, value)


def pass_once(state, journal=None):
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice
    assert not state.pending_trigger_order, 'No invented target/order response in this episode'
    return action(state, state.priority_player, {'type':'pass_priority'}, journal)


def resolve_real_top(state):
    item = state.stack[-1].id
    for _ in range(8):
        if not any(value.id == item for value in state.stack):
            return state
        state = pass_once(state)
    raise AssertionError('Checked priority passes did not resolve the actual top stack item')


def paid_spell(state, seat, row, targets=None):
    card = raw_card(state, row, seat, Zone.HAND)
    if state.priority_player != seat:
        state = action(state, state.priority_player, {'type':'pass_priority'})
    before = {cid for cid in state.players[seat].battlefield if not state.cards[cid].tapped}
    state = action(state, seat, {'type':'cast_spell', 'card_id':card.id, 'targets':targets or {}})
    assert state.cards[card.id].zone == Zone.STACK
    assert any(state.cards[cid].tapped for cid in before), 'Physical canonical lands paid the spell'
    return resolve_real_top(state), card.id


def position(seat, foreign_count, variant='canonical'):
    island = FACTS['Island']
    deck = [{**island, 'card_name':island['name'], 'quantity':60}]
    state = MatchFactory.from_decks(deck, deck, seed=72153)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.priority_stops = {pid:set(Step) for pid in (1, 2)}
    # Controlled resource board; every theft/bounce/counter below is genuinely paid.
    for pid in (1, 2):
        state.players[pid].mana_pool = {}
        for _ in range(24):
            raw_card(state, island, pid, Zone.BATTLEFIELD)
    targets = [raw_card(state, FACTS['Forest'], 3-seat, Zone.BATTLEFIELD).id for _ in range(foreign_count)]
    for cid in targets[1:]:
        state, _ = paid_spell(state, seat, ROWS['Confiscate'], {'target_card_id':cid})
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    row = deepcopy(ROWS['Agent of Treachery'])
    if variant == 'renamed':
        row['name'] = 'Independent Ownership Draw Source'
    elif variant in ('tail', 'parenthetical'):
        row['oracle_text'] += ' Unknown instruction.' if variant == 'tail' else ' (Unknown instruction.)'
    source = raw_card(state, row, seat, Zone.HAND)
    if state.priority_player != seat:
        state = action(state, state.priority_player, {'type':'pass_priority'})
    untapped = {cid for cid in state.players[seat].battlefield if not state.cards[cid].tapped}
    state = action(state, seat, {'type':'cast_spell', 'card_id':source.id, 'targets':{}})
    assert state.cards[source.id].zone == Zone.STACK
    assert any(state.cards[cid].tapped for cid in untapped)
    # Actual spell resolution publishes its actual ETB; no StackItem is injected.
    for _ in range(8):
        if state.pending_trigger_order:
            break
        state = action(state, state.priority_player, {'type':'pass_priority'})
    assert state.pending_trigger_order and state.pending_trigger_order['phase'] == 'targets'
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'choose_trigger_target' and move.get('target_card_id') == targets[0])
    state = action(state, seat, deepcopy(move))
    assert state.stack[-1].effect_key == 'change_control'
    state = resolve_real_top(state)
    assert all(state.cards[cid].owner == 3-seat and state.cards[cid].controller == seat for cid in targets)
    assert len([cid for cid in state.players[seat].battlefield if state.cards[cid].owner != seat]) == foreign_count
    return state, source.id, targets


def end_step(state, source, journal=None):
    for _ in range(80):
        if state.step == Step.END_STEP:
            return state
        state = pass_once(state, journal)
    raise AssertionError('Checked turn/phase actions did not reach the current end step')


def record(request, state, source, **details):
    path = os.environ.get('MTG_OWNERSHIP_DRAW_EVIDENCE')
    if path:
        file = Path(path)/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()+'.json')
        with file.open('x') as stream:
            json.dump({'node':request.node.nodeid, 'constructed_fixture_not_game':True,
                       'step':state.step.value, 'source_zone':state.cards[source].zone.value,
                       'stack':[{'id':item.id, 'source':item.source_card_id, 'controller':item.controller,
                                 'effect_key':item.effect_key, 'payload_keys':sorted(item.payload)} for item in state.stack],
                       'pending_trigger_phase':(state.pending_trigger_order or {}).get('phase'), **details}, stream, indent=2)


def test_complete_canonical_rows_and_retained_provenance():
    directory = HERE/'fixtures/agent_self_entry'
    provenance = json.loads((directory/'provenance.json').read_text())
    for name in ('facts.json', 'stifle.json'):
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest() == provenance['pins'][name]
    assert ROWS['Agent of Treachery']['oracle_id'] == '4cd82c7a-86df-4d29-b578-c009208c0d4b'
    assert ROWS['Agent of Treachery']['oracle_text'].splitlines()[1] == (
        "At the beginning of your end step, if you control three or more permanents you don't own, draw three cards.")


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [2, 3])
def test_real_end_step_has_trigger_only_at_ownership_threshold(request, seat, count):
    state, source, _ = position(seat, count)
    state = end_step(state, source)
    trigger = [item for item in state.stack if item.source_card_id == source and item.payload.get('__trigger_event') == 'begin_step']
    record(request, state, source, phase='trigger', foreign_count=count)
    if count == 2:
        assert trigger == [], 'Intervening-if is checked before publishing a trigger'
    else:
        assert len(trigger) == 1
        assert trigger[0].controller == seat
        assert trigger[0].effect_key != 'noop', 'Complete canonical conditional draw must not disappear'
        assert not state.pending_trigger_order, 'The printed draw has no selected target'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['normal', 'lost_one', 'source_left', 'countered', 'snapshot', 'replay'])
def test_actual_trigger_resolution_lifecycle(request, seat, case):
    state, source, targets = position(seat, 3)
    origin = snap(state)
    journal = []
    state = end_step(state, source, journal)
    triggers = [item for item in state.stack if item.source_card_id == source and item.payload.get('__trigger_event') == 'begin_step']
    assert len(triggers) == 1
    trigger = triggers[0].id
    if case == 'replay':
        replay = deserialize_match_snapshot(deepcopy(origin))
        for actor, move in journal:
            replay = action(replay, actor, deepcopy(move))
        assert snap(replay) == snap(state)
        state = replay
    elif case == 'snapshot':
        before = snap(state)
        state = deserialize_match_snapshot(deepcopy(before))
        assert snap(state) == before
    elif case == 'lost_one':
        state, _ = paid_spell(state, seat, BOOMERANG, {'target_card_id':targets[-1]})
        assert state.cards[targets[-1]].zone == Zone.HAND
    elif case == 'source_left':
        state, _ = paid_spell(state, seat, BOOMERANG, {'target_card_id':source})
        assert state.cards[source].zone == Zone.HAND
    elif case == 'countered':
        state, _ = paid_spell(state, seat, STIFLE, {'target_stack_id':trigger})
        assert all(item.id != trigger for item in state.stack)
    record(request, state, source, phase='resolution', case=case)
    hand, library = len(state.players[seat].hand), len(state.players[seat].library)
    if case != 'countered':
        assert any(item.id == trigger and item.controller == seat for item in state.stack)
        state = resolve_real_top(state)
    expected = 0 if case in ('lost_one', 'countered') else 3
    assert len(state.players[seat].hand) == hand+expected
    assert len(state.players[seat].library) == library-expected
    assert all(item.id != trigger for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', ['renamed', 'tail', 'parenthetical'])
def test_complete_clause_not_name_or_partial_suffix(request, seat, variant):
    state, source, _ = position(seat, 3, variant)
    state = end_step(state, source)
    record(request, state, source, phase='complete_clause', variant=variant)
    hand, library = len(state.players[seat].hand), len(state.players[seat].library)
    triggers = [item for item in state.stack if item.source_card_id == source]
    if triggers:
        assert len(triggers) == 1
        state = resolve_real_top(state)
    expected = 3 if variant == 'renamed' else 0
    assert len(state.players[seat].hand) == hand+expected
    assert len(state.players[seat].library) == library-expected
