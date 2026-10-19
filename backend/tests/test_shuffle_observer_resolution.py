"""Canonical observer execution and bounded controlled incarnation seams."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_keywords
from tests.test_shuffle_observer_audit import prepare, order_prompt, finish, act, restore, snap, ROWS
from tests.test_linked_damage_targets import raw_card

FIXTURE = Path(__file__).parent / 'fixtures/shuffle_observer_fix/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
EXTRA = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}


def passes(state):
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return restore(state)


def optional(state, controller, accept):
    state = passes(state)
    assert state.pending_trigger_order['phase'] == 'optional'
    moves = RulesEngine().legal_moves(state, controller)
    assert {move['accept'] for move in moves} == {True, False}
    action = next(move for move in moves if move['accept'] == accept)
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-controller, action)
    assert snap(state) == before and not RulesEngine().legal_moves(state, 3-controller)
    return act(restore(state), controller, action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_actual_cosi_optional_accept_decline_restart_and_atomic_wrong_actor(seat, accept):
    state, spell, source = prepare('Ponder', seat, "Cosi's Trickster")
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    assert not state.cards[source].counters and len(state.players[seat].hand) == 1
    state = optional(state, 3-seat, accept)
    assert state.cards[source].counters.get('+1/+1', 0) == int(accept)
    assert not state.stack and not state.pending_trigger_order


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('size', [0, 1, 8])
@pytest.mark.parametrize('observer', ['Psychogenic Probe', "Cosi's Trickster"])
def test_actual_shuffle_cause_and_staging_before_draw_including_empty_library(seat, size, observer, monkeypatch):
    import rules_engine.events as events
    state, spell, source = prepare('Ponder', seat, observer, size)
    state = order_prompt(state, seat, spell)
    receipt = deepcopy(state.pending_mechanic_choice['resolving_item'])
    observed = []
    emit = events.emit_event

    def spy(current, event, payload):
        emit(current, event, payload)
        if event == 'shuffle':
            observed.append((deepcopy(payload), snap(current)))

    monkeypatch.setattr(events, 'emit_event', spy)
    state = finish(state, seat, 'shuffle')
    # act() deliberately executes a second restored copy to prove full-state parity.
    assert len(observed) == 2 and observed[0] == observed[1]
    event, during = observed[0]
    assert event['player_id'] == seat
    assert event['cause']['stack_id'] == receipt['id']
    assert event['cause']['source_card_id'] == spell
    assert event['cause']['controller'] == receipt['controller'] == seat
    assert event['cause']['kind'] == 'spell'
    assert set(event['cause']) == {'stack_id', 'source_card_id', 'controller', 'kind', 'source_reference'}
    assert during['trigger_staging'] and not during['players'][str(seat)]['hand']
    trigger = next(t for t in during['staged_triggers'] if t['source_card_id'] == source)
    assert trigger['payload']['__shuffle_cause'] == event['cause']
    if observer == 'Psychogenic Probe':
        assert 'target_card_id' not in trigger['payload'] and trigger['payload']['target_player'] == seat
    else:
        assert trigger['payload']['target_card_id'] == source and trigger['payload']['__may']
    assert trigger['payload']['__shuffle_source_reference']['incarnation'] == object_incarnation(state.cards[source])
    if size:
        assert len(state.players[seat].hand) == 1 and state.stack
    else:
        # Actual Ponder loses to its mandatory draw; it cannot grant a free damage reward.
        assert state.winner == 3-seat and state.players[seat].life == 20
        assert not state.cards[source].counters
    restore(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_apnap_and_same_controller_order_are_after_draw(seat):
    state, spell, own = prepare('Ponder', seat, 'Psychogenic Probe', observer_seat=seat)
    foreign = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD).id
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD).id
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    assert len(state.players[seat].hand) == 1 and state.cards[spell].zone == Zone.GRAVEYARD
    assert state.pending_trigger_order['current_controller'] == 3-seat
    before = snap(state)
    offered = RulesEngine().legal_moves(state, 3-seat)
    assert all(move['type'] == 'choose_trigger_order' for move in offered)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, offered[0])
    assert snap(state) == before
    state = act(restore(state), 3-seat, offered[0])
    assert [item.controller for item in state.stack] == [seat, 3-seat, 3-seat]
    assert {item.source_card_id for item in state.stack} == {own, foreign, cosi}
    assert all(item.payload['__trigger_event'] == 'shuffle' for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_probe_receipt_survives_paid_source_destruction_with_lki(seat):
    state, spell, source = prepare('Ponder', seat, 'Psychogenic Probe')
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    incarnation = object_incarnation(state.cards[source])
    destroy = raw_card(state, EXTRA['Disenchant'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 1, 'C': 1}
    assert state.priority_player == seat
    state = act(state, seat, {'type': 'cast_spell', 'card_id': destroy.id,
                            'targets': {'target_card_id': source}})
    state = passes(state)
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool.get('W', 0) == 0
    item = state.stack[-1]
    assert item.source_card_id == source and item.payload['__source_lki']['types'] == ['Artifact']
    assert item.payload['__source_lki']['battlefield_incarnation'] == incarnation
    assert item.payload['__source_lki']['controller'] == 3-seat
    state = passes(restore(state))
    assert state.players[seat].life == 18 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('return_seam', [False, True])
def test_actual_unsummon_then_old_cosi_receipt_does_not_follow_new_incarnation(seat, return_seam):
    state, spell, source = prepare('Ponder', seat, "Cosi's Trickster")
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    timestamp = state.stack[-1].payload['effect_timestamp']
    bounce = raw_card(state, EXTRA['Unsummon'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': bounce.id,
                            'targets': {'target_card_id': source}})
    state = passes(state)
    assert state.cards[source].zone == Zone.HAND
    if return_seam:
        # Explicit controlled incarnation seam, NOT a legal creature cast with an ability on stack.
        state.players[3-seat].hand.remove(source)
        state.cards[source].move_to_zone(Zone.BATTLEFIELD)
        state.players[3-seat].battlefield.append(source)
        from game_state.state import assign_static_order_on_battlefield_entry
        assign_static_order_on_battlefield_entry(state, source)
        assert object_incarnation(state.cards[source]) != timestamp
    state = optional(restore(state), 3-seat, True)
    assert not state.cards[source].counters


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_hexproof_does_not_target_or_prevent_probe_and_counterspell_cannot_counter_ability(seat):
    state, spell, source = prepare('Ponder', seat, 'Psychogenic Probe')
    raw_card(state, EXTRA['Leyline of Sanctity'], seat, Zone.BATTLEFIELD)
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    counter = raw_card(state, EXTRA['Counterspell'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 2}
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': counter.id,
                       'targets': {'target_stack_id': state.stack[-1].id}})
    assert snap(state) == before
    state = passes(state)
    assert state.players[seat].life == 18 and state.cards[source].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_protection_from_red_does_not_block_untargeted_cosi_self_counter(seat):
    state, spell, source = prepare('Ponder', seat, "Cosi's Trickster")
    raw = json.loads(FIXTURE.with_name('mask-of-law-and-grace.json').read_text())
    aura = raw_card(state, raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 1, 'R': 1, 'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': aura.id,
                            'targets': {'target_card_id': source}})
    state = passes(state)
    assert state.cards[aura.id].zone == Zone.BATTLEFIELD and state.cards[aura.id].attached_to == source
    assert 'protection from red' in effective_keywords(state, source)
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    bolt = raw_card(state, EXTRA['Lightning Bolt'], seat, Zone.HAND)
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': bolt.id,
                       'targets': {'target_card_id': source}})
    assert snap(state) == before
    state = optional(state, 3-seat, True)
    assert state.cards[source].counters.get('+1/+1') == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_unsupported_compound_observers_do_not_receive_partial_rewards(seat):
    state, spell, source = prepare('Ponder', seat, 'Psychogenic Probe')
    cards = [raw_card(state, EXTRA[name], 3-seat, Zone.BATTLEFIELD).id
             for name in ('Psychic Surgery', 'Widespread Panic')]
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    assert [item.source_card_id for item in state.stack] == [source]
    assert all(not state.cards[cid].counters for cid in cards)
    assert len(state.players[seat].hand) == 1 and not state.players[seat].exile


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_explicit_shuffle_vs_randomization_and_invalid_cause_atomicity(seat):
    from rules_engine.shuffle_actions import shuffle_library
    state, spell, source = prepare('Ponder', seat, 'Psychogenic Probe')
    # Controlled helper seam: ordinary RNG is NOT the shuffle keyword action.
    state.rng.shuffle(state.players[seat].library)
    assert not state.stack
    shuffle_library(state, seat)
    assert not state.stack  # Probe requires a spell or ability cause.
    before = snap(state)
    for bad_actor in (True, '1', 3):
        with pytest.raises(ValueError):
            shuffle_library(state, bad_actor)
        assert snap(state) == before
    with pytest.raises((TypeError, ValueError)):
        shuffle_library(state, seat, resolving_item={'controller': seat})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_counterspell_on_ponder_does_not_manufacture_shuffle(seat):
    state, spell, source = prepare('Ponder', seat, 'Psychogenic Probe')
    library = list(state.players[seat].library)
    counter = raw_card(state, EXTRA['Counterspell'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell})
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                              'targets': {'target_stack_id': state.stack[-1].id}})
    state = passes(state)
    assert state.players[3-seat].mana_pool.get('U', 0) == 0
    assert state.cards[spell].zone == state.cards[counter.id].zone == Zone.GRAVEYARD
    assert not state.stack and not state.pending_mechanic_choice
    assert state.players[seat].library == library and not state.players[seat].hand
    assert state.cards[source].zone == Zone.BATTLEFIELD and state.players[seat].life == 20
    assert not any('shuffles their library' in entry for entry in state.log)
