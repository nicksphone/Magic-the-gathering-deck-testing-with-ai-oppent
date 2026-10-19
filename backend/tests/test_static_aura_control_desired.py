"""NEW desired lifecycle checks; controlled boards, genuine canonical paid spells."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_source_linked_exile import (
    position, activate, action, cast, next_main, raw_card, BOOMERANG,
    reference, exile_permission, snap, deserialize_match_snapshot, Zone,
    resolve_top_of_stack,
)
from rules_engine import events
from rules_engine.engine import RulesEngine
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.type_effects import effective_types
from game_state.state import Step
from rules_engine.action_validation import checked_action

HERE = Path(__file__).parent
SOURCE = HERE.parents[1]
data = (HERE / 'fixtures/static_aura_control_desired/facts.json').read_bytes()
assert hashlib.sha256(data).hexdigest() == '27c507f0e9aafc8fc68d3d8c7267833223031eaaf6e690fbbe63a582af5ff2e3'
ROWS = {row['name']: row for row in json.loads(data)}
COMBAT = {row['name']: row for row in map(json.loads,
    (SOURCE/'backend/tests/fixtures/combat_graveyard_caller/canonical.jsonl').read_text().splitlines())}
SONG = next(row for row in json.loads((SOURCE/'backend/tests/fixtures/aura_costs.json').read_bytes())
            if row['name'] == 'Song of the Dryads')
RESOURCE_ROWS = json.loads((SOURCE/'backend/tests/fixtures/source_linked_exile/nadu-facts.json').read_bytes())


def resource_position(seat):
    state, source = position(seat)
    # Six blue-producing lands cover Confiscate plus both genuine bounce costs.
    for actor in (1, 2):
        raw_card(state, RESOURCE_ROWS['Island'], actor, Zone.BATTLEFIELD)
    return state, source


def completed_cleanup(state):
    for _ in range(400):
        if state.step == Step.CLEANUP and not state.cleanup_pending and not state.pending_mechanic_choice:
            return state
        actor = state.pending_mechanic_choice['player_id'] if state.pending_mechanic_choice else state.priority_player
        if state.pending_mechanic_choice:
            move = deepcopy(next(m for m in RulesEngine().legal_moves(state, actor)
                                 if m['type'] == 'choose_mechanic'))
            move['card_ids'] = list(state.pending_mechanic_choice['options'])[:state.pending_mechanic_choice['count']]
        else:
            move = {'type': 'pass_priority'}
        state = checked_action(state, RulesEngine(), actor, move)
    raise AssertionError('Real cleanup transition exceeded bound')


@pytest.fixture
def receipts(monkeypatch):
    result = []
    original = events._collect_triggers
    def observe(state, event, payload):
        triggers = original(state, event, payload)
        result.append((event, deepcopy(payload)))
        return triggers
    monkeypatch.setattr(events, '_collect_triggers', observe)
    return result


def assert_pure_queries(state, cid):
    before = snap(state)
    for seat in (1, 2):
        RulesEngine().legal_moves(state, seat)
    effective_types(state, cid)
    printed_abilities_suppressed(state, cid)
    assert snap(state) == before, 'Legal/type/ability queries must not reconcile by mutating'


def restart(state):
    before = snap(state)
    restored = deserialize_match_snapshot(deepcopy(before))
    assert snap(restored) == before
    return restored


def controlled(state, cid, seat, receipts, previous=None):
    assert_pure_queries(state, cid)
    card = state.cards[cid]
    assert card.controller == seat
    assert state.players[seat].battlefield.count(cid) == 1
    assert cid not in state.players[3-seat].battlefield
    if previous is not None:
        assert card.summoning_sick and card.entered_turn == state.turn
        changes = [payload for event, payload in receipts if event == 'control_changed'
                   and payload['card_id'] == cid]
        assert changes and changes[-1] == {'card_id': cid, 'previous_controller': previous,
                                          'controller': seat}


def paid_aura(state, seat, cid):
    aura = raw_card(state, ROWS['Confiscate'], seat, Zone.HAND)
    state = cast(state, seat, aura.id, {'target_card_id': cid})
    assert state.cards[aura.id].attached_to == cid
    assert state.cards[aura.id].oracle_text == ROWS['Confiscate']['oracle_text']
    return state, aura.id


def paid_bounce(state, seat, cid):
    bounce = raw_card(state, BOOMERANG, seat, Zone.HAND)
    return cast(state, seat, bounce.id, {'target_card_id': cid})


def paid_agent(state, seat, cid):
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    agent = raw_card(state, ROWS['Agent of Treachery'], seat, Zone.HAND)
    state = cast(state, seat, agent.id)
    assert state.pending_trigger_order and state.pending_trigger_order['phase'] == 'targets'
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'choose_trigger_target' and move.get('target_card_id') == cid)
    state = action(state, seat, deepcopy(move))
    assert resolve_top_of_stack(state)
    return restart(state)


def retained_emblem(state, old):
    assert state.loyalty_permissions[0] == old
    seat = old['controller']
    for card in old['cards']:
        assert exile_permission(state, seat, card['id'])
        assert not exile_permission(state, 3-seat, card['id'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', [
    'old-emblem', 'bounce-aura', 'bounce-target', 'two-auras',
    'agent-underneath', 'newer-agent', 'source-type-suppression',
])
def test_paid_static_control_lifecycle(seat, case, receipts):
    state, source = resource_position(seat)
    state = activate(state, seat, source, 0)
    old = deepcopy(state.loyalty_permissions[0])
    ref = reference(state.cards[source])
    state = next_main(state, seat)
    state = next_main(state, 3-seat)
    assert not state.cards[source].summoning_sick
    if case == 'agent-underneath':
        state = paid_agent(state, 3-seat, source)
        controlled(state, source, 3-seat, receipts, seat)
        state = next_main(state, seat)
        state, aura = paid_aura(state, seat, source)
        controlled(state, source, seat, receipts, 3-seat)
        state = paid_bounce(restart(state), seat, aura)
        controlled(state, source, 3-seat, receipts, seat)
        assert state.cards[source].controller != state.cards[source].owner
    else:
        state, aura = paid_aura(state, 3-seat, source)
        controlled(state, source, 3-seat, receipts, seat)
        state = restart(state)
        if case == 'old-emblem':
            retained_emblem(state, old)
            state = activate(state, 3-seat, source, 0)
            assert len(state.loyalty_permissions[0]['cards']) == 4
            assert state.loyalty_permissions[0]['controller'] == seat
            assert all(exile_permission(state, seat, r['id']) and
                       not exile_permission(state, 3-seat, r['id'])
                       for r in state.loyalty_permissions[0]['cards'])
            assert reference(state.cards[source]) == ref
            return
        if case == 'bounce-aura':
            state = paid_bounce(state, 3-seat, aura)
            controlled(state, source, seat, receipts, 3-seat)
            assert state.cards[aura].zone == Zone.HAND
        elif case == 'bounce-target':
            state = paid_bounce(state, 3-seat, source)
            assert state.cards[source].zone == Zone.HAND
            assert state.cards[source].controller == state.cards[source].owner == seat
            assert state.cards[aura].zone == Zone.GRAVEYARD
            assert state.cards[source].last_known_battlefield['controller'] == 3-seat
            assert reference(state.cards[source]) != ref
        elif case == 'two-auras':
            state = next_main(state, seat)
            state, newer = paid_aura(state, seat, source)
            controlled(state, source, seat, receipts, 3-seat)
            state = paid_bounce(restart(state), seat, newer)
            controlled(state, source, 3-seat, receipts, seat)
            state = paid_bounce(state, seat, aura)
            controlled(state, source, seat, receipts, 3-seat)
        elif case == 'newer-agent':
            state = next_main(state, seat)
            state = paid_agent(state, seat, source)
            controlled(state, source, seat, receipts, 3-seat)
            state = paid_bounce(restart(state), seat, aura)
            controlled(state, source, seat, receipts)
        elif case == 'source-type-suppression':
            song = raw_card(state, SONG, 3-seat, Zone.HAND)
            state = cast(state, 3-seat, song.id, {'target_card_id': aura})
            assert effective_types(state, aura) == ['Land']
            assert printed_abilities_suppressed(state, aura)
            assert state.cards[aura].attached_to is None
            controlled(state, source, seat, receipts, 3-seat)
    retained_emblem(state, old)
    if state.cards[source].zone == Zone.BATTLEFIELD:
        assert state.cards[source].owner == seat and reference(state.cards[source]) == ref
    state = restart(state)
    retained_emblem(state, old)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['newer-temporary', 'temporary-under-aura'])
def test_paid_temporary_control_interaction(seat, case, receipts):
    state, _ = position(seat)
    bear = raw_card(state, COMBAT['Grizzly Bears'], seat, Zone.HAND)
    state = cast(state, seat, bear.id)
    state = next_main(state, 3-seat)
    if case == 'temporary-under-aura':
        theft = raw_card(state, COMBAT['Act of Treason'], 3-seat, Zone.HAND)
        state = cast(state, 3-seat, theft.id, {'target_card_id': bear.id})
        controlled(state, bear.id, 3-seat, receipts, seat)
        state, aura = paid_aura(state, 3-seat, bear.id)
        controlled(state, bear.id, 3-seat, receipts)
        state = next_main(restart(state), seat)
        controlled(state, bear.id, 3-seat, receipts)
        state = paid_bounce(state, seat, aura)
        controlled(state, bear.id, seat, receipts, 3-seat)
    else:
        state, aura = paid_aura(state, 3-seat, bear.id)
        controlled(state, bear.id, 3-seat, receipts, seat)
        state = next_main(state, seat)
        theft = raw_card(state, COMBAT['Act of Treason'], seat, Zone.HAND)
        state = cast(state, seat, theft.id, {'target_card_id': bear.id})
        controlled(state, bear.id, seat, receipts, 3-seat)
        state = completed_cleanup(restart(state))
        controlled(state, bear.id, 3-seat, receipts, seat)
        state = next_main(state, 3-seat)
        state = paid_bounce(state, 3-seat, aura)
        controlled(state, bear.id, seat, receipts, 3-seat)
    assert state.cards[bear.id].owner == seat
    restart(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_paid_queries_are_root_pure(seat):
    state, source = position(seat)
    assert_pure_queries(state, source)
    restart(state)
