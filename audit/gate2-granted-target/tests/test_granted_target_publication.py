"""32 synthetic boundary states using real publishers/actions; canonical paid proof is separate24."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot as snap, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.granted_target_triggers import _capture_grants, _record_target_selection, execution_gaps
from rules_engine.targeting import capture_announced_target_references, replace_announced_target_reference
from rules_engine.stack_engine import add_to_stack
from rules_engine.ward import mark_stack_targets
from effects.registry import resolve_effect
from tests.test_ai_recurring_engines import fixture, add, resolve

FACTS = json.loads((Path(__file__).resolve().parents[1] / 'nadu-facts.json').read_text())
CARDS = {name: {'power': None, 'toughness': None, **raw} for name, raw in FACTS.items()}
CASES = ['pure_lki', 'empty_frozen', 'missing_no_fallback', 'recipient_departure', 'grant_departure',
         'duplicate_slots', 'duplicate_clauses', 'repeat_scan_snapshot_turn', 'two_instances',
         'grant_reentry', 'control_transfer', 'counter_consumes', 'copy_fresh', 'stale_copy',
         'retarget_return', 'invalid_payment']


def board(seat, grant=True):
    state = fixture()
    state.active_player = state.priority_player = seat
    cards = {}
    for key, name in [('target', 'Elvish Mystic'), ('other', 'Elvish Mystic'), ('equipment', 'Shuko')]:
        cards[key] = add(state, name, seat, cards=CARDS)
        assign_static_order_on_battlefield_entry(state, cards[key].id)
    if grant:
        cards['grant'] = add(state, 'Nadu, Winged Wisdom', seat, cards=CARDS)
        assign_static_order_on_battlefield_entry(state, cards['grant'].id)
    return state, cards


def capture(state, target, announced=None):
    announced = announced or {'target_card_id': target.id}
    refs = capture_announced_target_references(state, announced)
    return announced, refs, _capture_grants(state, announced, refs, stack_kind='activated')


def announce(state, cards, packet=None, *, omitted=False):
    announced, refs, receipt = packet or capture(state, cards['target'])
    payload = {'equipment_id': cards['equipment'].id, 'target_card_id': announced.get('target_card_id'),
               '__announced_targets': announced, '__announced_target_references': refs,
               'source_timestamp': cards['equipment'].battlefield_incarnation,
               'target_timestamp': cards['target'].battlefield_incarnation,
               '__ability_target_text': 'Attach this Equipment to target creature you control.'}
    if not omitted:
        payload['__granted_target_capture'] = receipt
    item = add_to_stack(state, cards['equipment'].id, cards['equipment'].controller,
                        'Boundary equipment activation', 'equip_attachment', payload, is_spell=False)
    return item


def triggers(state):
    return [item for item in state.stack if item.effect_key == 'reveal_top_conditional']


def depart(state, card):
    state.players[card.controller].battlefield.remove(card.id)
    card.move_to_zone(Zone.GRAVEYARD)
    state.players[card.owner].graveyard.append(card.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', CASES)
def test_real_publication_boundary(case, seat):
    state, cards = board(seat, grant=case not in {'empty_frozen', 'missing_no_fallback'})
    announced, refs, frozen = capture(state, cards['target'])
    if case == 'pure_lki':
        before = snap(state)
        _, _, receipt = capture(state, cards['target'])
        assert snap(state) == before and not state.trigger_once_seen_this_turn
        cards['target'].controller = 3-seat
        cards['target'].counters['+1/+1'] = 3
        assert receipt['receipts'][0]['trigger_controller'] == seat
        assert receipt['receipts'][0]['recipient_source_lki']['power'] == 1
        assert receipt['receipts'][0]['recipient_source_lki']['counters'] == {}
        return
    if case in {'empty_frozen', 'missing_no_fallback'}:
        source = add(state, 'Nadu, Winged Wisdom', seat, cards=CARDS)
        assign_static_order_on_battlefield_entry(state, source.id)
        item = announce(state, cards, (announced, refs, frozen), omitted=case == 'missing_no_fallback')
        assert not triggers(state) and not state.trigger_once_seen_this_turn
        status = item.payload['__granted_target_capture']
        assert status['status'] == ('unqualified' if case == 'missing_no_fallback' else 'captured')
        if case == 'missing_no_fallback':
            assert status['reason'] == 'missing_capture' and status['captured'] is False
        mark_stack_targets(state, item)
        assert not triggers(state)
        return
    if case in {'recipient_departure', 'grant_departure'}:
        old_ref = deepcopy(frozen['receipts'][0]['recipient_ref'])
        depart(state, cards['target' if case == 'recipient_departure' else 'grant'])
        announce(state, cards, (announced, refs, frozen))
        trigger = triggers(state)[0]
        assert trigger.source_card_id == cards['target'].id and trigger.controller == seat
        assert trigger.payload['__granted_target_receipt']['recipient_ref'] == old_ref
        assert trigger.payload['__source_lki']['controller'] == seat
        library_size = len(state.players[seat].library)
        state = resolve(state)
        assert len(state.players[seat].library) == library_size-1
        return
    if case == 'duplicate_slots':
        packet = capture(state, cards['target'], {'target_card_ids': [cards['target'].id]*2})
        announce(state, cards, packet)
        assert len(triggers(state)) == 1 and len(state.trigger_once_seen_this_turn) == 1
        return
    if case == 'duplicate_clauses':
        cards['grant'].oracle_text += '\n' + cards['grant'].oracle_text.splitlines()[1]
        item = announce(state, cards)
        assert len(triggers(state)) == 2 and len(state.trigger_once_seen_this_turn) == 2
        assert len({t.payload['__granted_target_receipt']['clause_instance'] for t in triggers(state)}) == 2
        mark_stack_targets(state, item)
        assert len(triggers(state)) == 2
        return
    if case == 'two_instances':
        second = add(state, 'Nadu, Winged Wisdom', seat, cards=CARDS)
        assign_static_order_on_battlefield_entry(state, second.id)
        announce(state, cards)
        assert len(triggers(state)) == 2
        assert len({t.payload['__granted_target_receipt']['grant_source_ref']['card_id'] for t in triggers(state)}) == 2
        return
    if case == 'invalid_payment':
        cards['equipment'].oracle_text = cards['equipment'].oracle_text.replace('Equip {0}', 'Equip {99}')
        state.players[seat].mana_pool = {}
        before = snap(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, {'type': 'equip', 'card_id': cards['equipment'].id,
                                                       'target_card_id': cards['target'].id})
        assert snap(state) == before and not state.trigger_once_seen_this_turn
        return
    item = announce(state, cards)
    assert len(triggers(state)) == 1 and len(state.trigger_once_seen_this_turn) == 1
    if case == 'repeat_scan_snapshot_turn':
        state = deserialize_match_snapshot(snap(state))
        item = next(x for x in state.stack if x.id == item.id)
        before = snap(state)
        mark_stack_targets(state, item)
        assert snap(state) == before
        state.turn += 1
        state.trigger_once_seen_this_turn.clear()
        mark_stack_targets(state, item)
        assert len(triggers(state)) == 1 and not state.trigger_once_seen_this_turn
    elif case == 'control_transfer':
        cards['target'].controller = 3-seat
        state.players[seat].battlefield.remove(cards['target'].id)
        state.players[3-seat].battlefield.append(cards['target'].id)
        cards['grant'].controller = 3-seat
        state.players[seat].battlefield.remove(cards['grant'].id)
        state.players[3-seat].battlefield.append(cards['grant'].id)
        announce(state, cards)
        announce(state, cards)
        assert len(triggers(state)) == 2 and len(state.trigger_once_seen_this_turn) == 2
        assert [x.controller for x in triggers(state)] == [seat, 3-seat]
    elif case == 'grant_reentry':
        announce(state, cards)
        announce(state, cards)
        assert len(triggers(state)) == 2
        depart(state, cards['grant'])
        state.players[seat].graveyard.remove(cards['grant'].id)
        cards['grant'].move_to_zone(Zone.BATTLEFIELD)
        state.players[seat].battlefield.append(cards['grant'].id)
        assign_static_order_on_battlefield_entry(state, cards['grant'].id)
        announce(state, cards)
        assert len(triggers(state)) == 3
        assert triggers(state)[0].payload['__granted_target_receipt']['grant_source_ref'] != triggers(state)[-1].payload['__granted_target_receipt']['grant_source_ref']
    elif case == 'counter_consumes':
        resolve_effect(state, seat, 'counter_ability', {'target_stack_id': triggers(state)[0].id})
        assert not triggers(state) and len(state.trigger_once_seen_this_turn) == 1
        announce(state, cards)
        announce(state, cards)
        assert len(triggers(state)) == 1 and len(state.trigger_once_seen_this_turn) == 2
    elif case in {'copy_fresh', 'stale_copy'}:
        if case == 'stale_copy':
            depart(state, cards['target'])
            state.players[seat].graveyard.remove(cards['target'].id)
            cards['target'].move_to_zone(Zone.BATTLEFIELD)
            state.players[seat].battlefield.append(cards['target'].id)
            assign_static_order_on_battlefield_entry(state, cards['target'].id)
        resolve_effect(state, seat, 'copy_ability', {'target_stack_id': item.id})
        copied = next(x for x in state.stack if x.payload.get('__copied_from_stack_id') == item.id)
        assert copied.payload['__granted_target_published_capture']['status'] == 'captured'
        assert copied.payload['__granted_target_revision'] == 0
        assert copied.payload['__announced_target_references'] == refs
        mark_stack_targets(state, copied)
        assert len(triggers(state)) == (2 if case == 'copy_fresh' else 1)
        before = snap(state)
        mark_stack_targets(state, copied)
        assert snap(state) == before
    elif case == 'retarget_return':
        for target in [cards['other'], cards['target']]:
            item.payload['target_card_id'] = target.id
            item.payload['__announced_targets']['target_card_id'] = target.id
            item.payload['__announced_target_references'] = replace_announced_target_reference(
                state, item.payload['__announced_target_references'], item.payload['__announced_targets'], [('target_card_id',)])
            _record_target_selection(state, item)
            mark_stack_targets(state, item)
        assert len(triggers(state)) == 3 and item.payload['__granted_target_revision'] == 2
        assert len({tuple(t.payload['__granted_target_receipt']['targeting_occurrence']) for t in triggers(state)}) == 3
