"""Real paid activation frames, plus explicitly malformed internal-reader controls."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.shuffle_actions import shuffle_library
from tests.test_activation_payment_choices import position as payment_position
from tests.test_hand_activations import board as hand_board, hand_card
from tests.test_activation_modifiers import add
from tests.test_paid_counter_family_audit import board, action
from tests.test_self_graveyard_replacement_audit import snap


def reference(card):
    return {'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence}


def paid_fertilid(seat):
    state, source, target = board(seat, 'Fertilid')
    return checked_action(state, RulesEngine(), seat,
                          action('Fertilid', source, target, 3-seat)), source


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Fertilid', 'Lux Cannon', 'self-sacrifice', 'hand-discard'])
def test_real_generic_announcement_captures_before_all_cost_departures(seat, family):
    if family in ('Fertilid', 'Lux Cannon'):
        state, cid, target = board(seat, family)
        request = action(family, cid, target, 3-seat)
    elif family == 'self-sacrifice':
        state, source, _, key = payment_position(seat, 'sacrifice')
        cid = source.id
        request = {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0,
                   'payment_choices': {key: [cid]}}
    else:
        state = hand_board(seat)
        source = hand_card(state, 'Colossal Skyturtle', seat)
        cid = source.id
        target = add(state, 'Azure Mage', 3-seat)
        state.players[seat].mana_pool.update(C=1, U=1)
        request = {'type': 'activate_ability', 'card_id': cid, 'ability_index': 1,
                   'targets': {'target_card_id': target.id}}
    before = snap(state)
    retained = reference(state.cards[cid])
    result = checked_action(state, RulesEngine(), seat, request)
    assert snap(state) == before
    item = result.stack[-1]
    assert item.source_card_id == cid and item.controller == seat
    assert item.payload['__activation_source_reference'] == retained
    if family in ('self-sacrifice', 'hand-discard'):
        assert result.cards[cid].zone == Zone.GRAVEYARD
        assert result.cards[cid].zone_change_sequence == retained['zone_change_sequence'] + 1
    restored = deserialize_match_snapshot(snap(result))
    assert snap(restored) == snap(result)
    assert restored.stack[-1].payload['__activation_source_reference'] == retained


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [None, {}, {'incarnation': 0},
    {'incarnation': 0, 'zone_change_sequence': True},
    {'incarnation': -1, 'zone_change_sequence': 1},
    {'incarnation': 0, 'zone_change_sequence': '1'},
    {'incarnation': 0, 'zone_change_sequence': 1, 'extra': 0}])
def test_malformed_actual_frame_rejected_before_rng_log_or_event(seat, bad, monkeypatch):
    state, _ = paid_fertilid(seat)
    # Negative internal-receipt corruption, never an invented executable positive frame.
    frame = asdict(state.stack[-1])
    frame['payload']['__activation_source_reference'] = deepcopy(bad)
    before = snap(state)
    from rules_engine import events
    calls = []
    monkeypatch.setattr(events, 'emit_event', lambda *args: calls.append(args))
    with pytest.raises(ValueError, match='retained activation reference'):
        shuffle_library(state, 3-seat, resolving_item=frame)
    assert snap(state) == before and calls == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('conflict', ['trigger', 'trigger-reference', 'spell-copy', 'missing-body'])
def test_reference_cannot_relabel_other_frame_families(seat, conflict):
    state, _ = paid_fertilid(seat)
    frame = asdict(state.stack[-1])
    changes = {'trigger': {'__trigger_event': 'enters_graveyard'},
               'trigger-reference': {'__trigger_source_reference': reference(state.cards[frame['source_card_id']])},
               'spell-copy': {'__stack_copy_kind': 'spell'},
               'missing-body': {'__ability_target_text': ''}}
    frame['payload'].update(changes[conflict])
    before = snap(state)
    with pytest.raises(ValueError, match='retained activation reference'):
        shuffle_library(state, 3-seat, resolving_item=frame)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_frame_without_reference_keeps_documented_live_fallback(seat, monkeypatch):
    state, source = paid_fertilid(seat)
    frame = asdict(state.stack[-1])
    frame['payload'].pop('__activation_source_reference')
    from rules_engine import events
    original = events.emit_event
    receipts = []

    def observe(current, event, payload):
        if event == 'shuffle':
            receipts.append(deepcopy(payload))
        return original(current, event, payload)

    monkeypatch.setattr(events, 'emit_event', observe)
    shuffle_library(state, 3-seat, resolving_item=frame)
    assert len(receipts) == 1
    assert receipts[0]['cause']['source_reference'] == reference(state.cards[source])
    assert receipts[0]['cause']['stack_id'] == frame['id']
