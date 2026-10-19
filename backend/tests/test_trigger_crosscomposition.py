"""NEW tests only: real casts/copies, free loot and paid draw order together."""
from copy import deepcopy
import json

import pytest

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.paid_triggers import RESOLUTION_PAYER
from tests import test_multicast_subject_audit as audit
from tests.test_multicast_subject_audit import add, announce, position, restart
from tests.test_paid_optional_payment_edges import RAW as PAID_RAW
from tests.test_paid_optional_triggers import fresh_readonly_restore
from tests.test_spell_trigger_surface_audit import (
    act, cards, install, offline_http, record, restore, snapshot,
)

cards.ROWS.update(PAID_RAW)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('copy_spell', [False, True])
@pytest.mark.parametrize('pay', [False, True])
@pytest.mark.parametrize('loot', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_actual_private_http_paid_and_free_multicast_copy_order_not_conflated(
        request, offline_http, seat, copy_spell, pay, loot, reverse):
    state, source = position(seat)
    state.players[3-seat].mana_pool = {}
    for _ in range(8):
        add(state, 'Island', seat, Zone.LIBRARY)
    ascendancy = add(state, 'Jeskai Ascendancy', seat)
    mystic = add(state, 'Lunar Mystic', seat)
    mystic.owner = 3-seat
    storm = add(state, 'Storm-Kiln Artist', seat)
    goblin = add(state, 'Raging Goblin', seat)
    goblin.tapped = True
    secret = add(state, 'Raging Goblin', 3-seat, Zone.HAND)
    copying = add(state, 'Reverberate', seat, Zone.HAND) if copy_spell else None
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    match = install(state, seat, request, private=True)
    trace = []
    paid_receipts, free_choices, groups = [], [], []

    def capture(stage):
        match = restore(state.id)
        trace.append({'stage': stage, 'snapshot': serialize_match_snapshot(match.state)})
        record(request, {'trace': trace, 'paid_receipts': paid_receipts,
                         'free_choices': free_choices, 'groups': groups})
        return match

    def order_current_group():
        match = capture('before actual trigger order')
        pending = match.state.pending_trigger_order
        assert pending and 'phase' not in pending
        group = pending['groups'][str(seat)]
        assert len(group) == 4
        assert sum(row['source_card_id'] == ascendancy.id for row in group) == 2
        assert sum(row['source_card_id'] == mystic.id for row in group) == 1
        identifiers = [row['_choice_id'] for row in group]
        assert len(set(identifiers)) == 4
        chosen = list(reversed(identifiers)) if reverse else identifiers
        groups.append({'offered': deepcopy(group), 'chosen': chosen})
        frozen = snapshot(match)
        response = act(offline_http, match, 3-seat, {'type': 'choose_trigger_order', 'trigger_order': chosen})
        assert response.status_code == 403 and snapshot(match) == frozen
        response = act(offline_http, match, seat, {'type': 'choose_trigger_order', 'trigger_order': chosen[:-1]})
        assert response.status_code == 422 and snapshot(match) == frozen
        response = act(offline_http, match, seat, {'type': 'choose_trigger_order', 'trigger_order': chosen})
        assert response.status_code == 200, response.text
        return capture('after actual trigger order')

    response = act(offline_http, match, seat, {
        'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_player': 3-seat}})
    assert response.status_code == 200, response.text
    match = order_current_group()
    if copying:
        original = next(item for item in match.state.stack if item.source_card_id == source.id)
        response = act(offline_http, match, seat, {
            'type': 'cast_spell', 'card_id': copying.id, 'targets': {'target_stack_id': original.id}})
        assert response.status_code == 200, response.text
        match = order_current_group()

    for _ in range(64):
        match = capture('before actual continuation')
        current = match.state
        pending = current.pending_trigger_order
        mechanic = current.pending_mechanic_choice
        if not current.stack and not pending and not mechanic:
            break
        if pending and pending.get('phase') == 'optional':
            item = current.stack[-1]
            assert pending['current_stack_id'] == item.id
            assert pending['current_controller'] == item.controller == seat
            paid = item.payload.get('__optional_payment_cost')
            assert (item.source_card_id == mystic.id) == bool(paid)
            assert item.source_card_id in {mystic.id, ascendancy.id}
            before_money = current.players[seat].mana_pool.get('C', 0)
            before_draws = current.draws_this_turn.get(seat, 0)
            assert restart(current) is not current
            if paid and not paid_receipts:
                fresh_readonly_restore(match)
            action = {'type': 'choose_optional_effect', 'stack_id': item.id,
                      'accept': pay if paid else loot}
            frozen = snapshot(match)
            response = act(offline_http, match, 3-seat, action)
            assert response.status_code == 403 and snapshot(match) == frozen
            response = act(offline_http, match, seat, {**action, 'stack_id': 'stale'})
            assert response.status_code == 422 and snapshot(match) == frozen
            response = act(offline_http, match, seat, action)
            assert response.status_code == 200, response.text
            match = capture('after actual paid/free choice')
            after_money = match.state.players[seat].mana_pool.get('C', 0)
            assert after_money == before_money - int(bool(paid) and pay)
            assert match.state.draws_this_turn.get(seat, 0) == before_draws + int(pay if paid else loot)
            data = {'source': item.source_card_id, 'stack_id': item.id, 'cost': paid,
                    'before_money': before_money, 'after_money': after_money, 'action': action}
            (paid_receipts if paid else free_choices).append(data)
            frozen = snapshot(match)
            response = act(offline_http, match, seat, action)
            assert response.status_code == 422 and snapshot(match) == frozen
        elif pending:
            order_current_group()
        elif mechanic:
            assert mechanic['kind'] == 'copy_target' and 'keep' in mechanic['options']
            response = act(offline_http, match, mechanic['player_id'], {
                'type': 'choose_mechanic', 'card_ids': ['keep']})
            assert response.status_code == 200, response.text
        else:
            actor = current.priority_player
            response = (offline_http.post('/matches/' + state.id + '/autoplay?ticks=1')
                        if match.controllers[actor] == 'ai' else
                        act(offline_http, match, actor, {'type': 'pass_priority'}))
            assert response.status_code == 200, response.text
    else:
        pytest.fail('Bounded64 actual mixed continuation did not finish')

    match = capture('resolved mixed paid/free/copy stack')
    public = main._serialize_match_controller(match)
    assert secret.id not in json.dumps(public) and public['root_seed'] is None
    fresh_readonly_restore(match)
    casts = 1 + int(copy_spell)
    assert len(groups) == casts
    assert len(paid_receipts) == len(free_choices) == casts
    assert len({row['stack_id'] for row in paid_receipts + free_choices}) == 2 * casts
    assert match.state.draws_this_turn[seat] == casts * (int(pay) + int(loot))
    assert len(match.state.players[seat].hand) == casts * int(pay)
    assert not match.state.cards[goblin.id].tapped
    assert audit.effective_power(match.state, goblin.id) == 1 + casts
    assert match.state.players[3-seat].life == 20 - 2 * casts
    treasures = [match.state.cards[cid] for cid in match.state.players[seat].battlefield
                 if match.state.cards[cid].name == 'Treasure']
    assert len(treasures) == casts + int(copy_spell)
    assert RESOLUTION_PAYER.get() is None
    record(request, {'trace': trace, 'paid_receipts': paid_receipts, 'free_choices': free_choices,
                     'groups': groups, 'public': public, 'draws': match.state.draws_this_turn,
                     'treasure_count': len(treasures), 'resolved': serialize_match_snapshot(match.state)})


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_unknown_paid_copy_retains_unsupported_source_receipt(request, monkeypatch, seat):
    from rules_engine import events

    compile_clause = events._cast_clause_trigger
    returned = []

    def observe(*args, **kwargs):
        result = compile_clause(*args, **kwargs)
        returned.append(deepcopy(result))
        return result

    monkeypatch.setattr(events, '_cast_clause_trigger', observe)
    state, source = position(seat)
    owner = add(state, 'Mirari', seat)
    state.players[seat].mana_pool = {'R': 1, 'C': 3}
    paid, action = announce(state, seat, source)
    unsupported = [item for item in paid.stack if item.source_card_id == owner.id]
    record(request, {'canonical': PAID_RAW['Mirari'], 'actual_action': action,
                     'expected_trigger_count': 1, 'actual_trigger_count': len(unsupported),
                     'queued': serialize_match_snapshot(paid), 'compiled_rows': returned,
                     'source_hashes': 'evidence/composed-source.sha256'})
    assert paid.players[seat].mana_pool.get('C') == 3
    assert not any(item.payload.get('__stack_copy_kind') for item in paid.stack)
    assert any(row['effect_key'] == 'noop' and row['payload'].get('__unsupported_trigger_instruction')
               for row in returned)
    assert len(unsupported) == 1
    assert unsupported[0].effect_key == 'noop'
    assert unsupported[0].payload['__unsupported_trigger_instruction']
    assert not paid.pending_trigger_order
