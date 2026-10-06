"""Desired canonical graveyard-entry semantics; no injected event or stack item."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import position, act, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS


KOZILEK = 'Kozilek, Butcher of Truth'
FIXTURES = Path(__file__).parent / 'fixtures/kozilek_trigger_audit'
HASHES = {'stifle': 'da05b112322f3583368fcb40f9e634b8dc973f9867607d0d33f1d04dbd186627',
          'cremate': '1c3e8c658013778a3930a61fda2ca9a4a3d8fe4b9f547f23079f73d80e61b481'}
FRESH = {}
for name, digest in HASHES.items():
    path = FIXTURES / (name + '.json')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    row = json.loads(path.read_text())
    assert row['object'] == 'card' and row['oracle_id']
    FRESH[row['name']] = row


@pytest.fixture(autouse=True)
def actual_event_trace(monkeypatch, tmp_path):
    from rules_engine import events
    original = events._collect_triggers
    trace = []

    def observe(state, event, payload):
        collected = original(state, event, payload)
        card = state.cards.get(payload.get('card_id'))
        trace.append({'event': event, 'payload': deepcopy(payload),
                      'source_zone_at_collection': card.zone.value if card else None,
                      'collected': deepcopy(collected)})
        return collected

    monkeypatch.setattr(events, '_collect_triggers', observe)
    yield
    # act() executes root and independent repeated snapshots; both traces are retained.
    (tmp_path / 'actual-events.json').write_text(json.dumps(trace, sort_keys=True, default=str))


def start(seat, stimulus, *, foreign=False, humility=False):
    state, target, source, artist, action = position(KOZILEK, seat, stimulus, foreign)
    # Explicit retained canonical position: remove unrelated Artist trigger noise.
    state.players[artist.controller].battlefield.remove(artist.id)
    artist.move_to_zone(Zone.EXILE)
    state.players[artist.owner].exile.append(artist.id)
    old_grave = state.players[target.owner].library.pop(0)
    state.cards[old_grave].move_to_zone(Zone.GRAVEYARD)
    state.players[target.owner].graveyard.append(old_grave)
    if humility:
        raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    state.mechanic_choice_players = {1, 2}
    return state, target.id, source.id, old_grave, action


def passes(state):
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return state


def enter(state, seat, stimulus, action):
    state = act(state, seat, action)
    if stimulus == 'mill':
        state = passes(state)  # Real paid activation, both response opportunities.
    return state


def save(tmp_path, label, state):
    (tmp_path / (label + '.json')).write_text(json.dumps(snap(state), sort_keys=True))
    return restart(state, tmp_path, label + '-restart')


def trigger(state, cid):
    items = [item for item in state.stack if item.source_card_id == cid]
    assert len(items) == 1, 'Actual graveyard entry needs one respondable source trigger'
    item = items[0]
    assert stack_object_kind(state, item) == 'triggered'
    assert item.controller == state.cards[cid].owner
    return item


def opposing_priority(state, actor):
    if state.priority_player != actor:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == actor
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stimulus', ['discard', 'mill', 'sacrifice'])
def test_real_entry_preserves_graveyard_and_respondable_owner_trigger(seat, stimulus, tmp_path):
    state, cid, source, old, action = start(seat, stimulus)
    library = list(state.players[seat].library)
    state = enter(state, seat, stimulus, action)
    state = save(tmp_path, 'actual-entry-before-trigger-assertion', state)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert {cid, old}.issubset(state.players[seat].graveyard)
    if stimulus != 'mill':
        assert state.players[seat].library == library, 'Do not execute immediate replacement shuffle'
        assert state.cards[source].zone == Zone.STACK
    item = trigger(state, cid)
    assert state.stack[-1].id == item.id, 'Cost trigger must be above the paid spell'
    assert sum(state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_stifle_response_counters_trigger_not_its_graveyard_source(seat, tmp_path):
    state, cid, _, old, action = start(seat, 'discard')
    counter = raw_card(state, FRESH['Stifle'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = save(tmp_path, 'actual-discard-before-stifle', enter(state, seat, 'discard', action))
    item = trigger(state, cid)
    library = list(state.players[seat].library)
    grave = list(state.players[seat].graveyard)
    state = opposing_priority(state, 3-seat)
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                              'targets': {'target_stack_id': item.id}})
    state = passes(state)
    assert not any(other.id == item.id for other in state.stack)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert state.players[seat].library == library and state.players[seat].graveyard == grave
    assert old in grave
    save(tmp_path, 'countered-no-shuffle', state)


@pytest.mark.parametrize('seat', [1, 2])
def test_resolving_trigger_shuffles_whole_current_graveyard_and_actual_observers(seat, tmp_path):
    state, cid, _, old, action = start(seat, 'discard')
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD)
    state = save(tmp_path, 'actual-discard-before-resolution', enter(state, seat, 'discard', action))
    item = trigger(state, cid)
    library = list(state.players[seat].library)
    grave = list(state.players[seat].graveyard)
    assert cid in grave and old in grave
    state = passes(state)
    assert not state.players[seat].graveyard
    assert set(state.players[seat].library) == set(library + grave)
    assert all(state.cards[target].zone == Zone.LIBRARY for target in grave)
    assert len([other for other in state.stack if other.source_card_id == probe.id]) == 1
    assert len([other for other in state.stack if other.source_card_id == cosi.id]) == 1
    for other in state.stack:
        if other.source_card_id in {probe.id, cosi.id}:
            cause = other.payload['__shuffle_cause']
            assert cause['kind'] == 'triggered' and cause['stack_id'] == item.id
            assert cause['source_card_id'] == cid and cause['controller'] == seat
    assert not state.cards[cosi.id].counters, 'Observer is queued, not free immediate reward'
    save(tmp_path, 'whole-graveyard-actual-shuffle', state)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_cremate_source_departure_does_not_remove_retained_trigger(seat, tmp_path):
    state, cid, _, old, action = start(seat, 'discard')
    exile = raw_card(state, FRESH['Cremate'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'B': 1}
    state = save(tmp_path, 'actual-discard-before-source-departure', enter(state, seat, 'discard', action))
    item = trigger(state, cid)
    state = opposing_priority(state, 3-seat)
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': exile.id,
                              'targets': {'target_card_id': cid}})
    state = passes(state)
    assert state.cards[cid].zone == Zone.EXILE
    assert any(other.id == item.id for other in state.stack)
    state = save(tmp_path, 'exiled-source-retained-trigger', state)
    state = passes(state)
    assert state.cards[cid].zone == Zone.EXILE
    assert old in state.players[seat].library and not state.players[seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
def test_humility_before_death_does_not_suppress_new_graveyard_anywhere_trigger(seat, tmp_path):
    state, cid, _, _, action = start(seat, 'sacrifice', humility=True)
    state = save(tmp_path, 'humility-actual-death', enter(state, seat, 'sacrifice', action))
    assert state.cards[cid].zone == Zone.GRAVEYARD
    trigger(state, cid)


@pytest.mark.parametrize('seat', [1, 2])
def test_foreign_owned_actual_death_trigger_belongs_to_graveyard_owner(seat, tmp_path):
    state, cid, _, _, action = start(seat, 'sacrifice', foreign=True)
    state = save(tmp_path, 'foreign-owned-actual-death', enter(state, seat, 'sacrifice', action))
    assert state.cards[cid].owner == 3-seat and state.cards[cid].zone == Zone.GRAVEYARD
    assert cid in state.players[3-seat].graveyard
    assert trigger(state, cid).controller == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_control_real_stifle_is_payable_against_actual_millstone_ability(seat):
    state, cid, source, _, action = start(seat, 'mill')
    counter = raw_card(state, FRESH['Stifle'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = act(state, seat, action)
    target = state.stack[-1]
    assert target.source_card_id == source and stack_object_kind(state, target) == 'activated'
    library = list(state.players[seat].library)
    state = opposing_priority(state, 3-seat)
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                              'targets': {'target_stack_id': target.id}})
    state = passes(state)
    assert not state.stack and state.players[seat].library == library
    assert state.cards[cid].zone == Zone.LIBRARY and state.cards[source].tapped
    assert state.cards[counter.id].zone == Zone.GRAVEYARD
    assert not state.players[3-seat].mana_pool.get('U', 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_control_real_cremate_payable_exile_and_draw_after_actual_discard(seat):
    state, cid, _, _, action = start(seat, 'discard')
    exile = raw_card(state, FRESH['Cremate'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'B': 1}
    state = enter(state, seat, 'discard', action)
    state = opposing_priority(state, 3-seat)
    hand = len(state.players[3-seat].hand)
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': exile.id,
                              'targets': {'target_card_id': cid}})
    state = passes(state)
    assert state.cards[cid].zone == Zone.EXILE
    assert len(state.players[3-seat].hand) == hand  # Paid card out, one actual draw in.
    assert not state.players[3-seat].mana_pool.get('B', 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_control_private_hand_public_graveyard_and_invalid_response_atomic(seat):
    state, cid, _, _, action = start(seat, 'discard')
    own, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    other, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert not is_unknown(own.cards[cid]) and is_unknown(other.cards[cid])
    state = enter(state, seat, 'discard', action)
    other, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert not is_unknown(other.cards[cid])
    counter = raw_card(state, FRESH['Stifle'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = opposing_priority(state, 3-seat)
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {
            'type': 'cast_spell', 'card_id': counter.id, 'targets': {'target_stack_id': 'unknown'},
        })
    assert snap(state) == before
