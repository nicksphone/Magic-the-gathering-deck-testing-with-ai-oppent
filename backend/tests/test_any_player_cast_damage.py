"""Native canonical cast/trigger lifecycles; no fabricated stack objects."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.counterability_canonical_936 import raw_card
from tests.test_ai_recurring_engines import add, fixture


FIXTURES = Path(__file__).parent / 'fixtures'
RAW = {name: raw_card(name) for name in ('Lightning Bolt', 'Stifle')}
RAW['Eidolon of the Great Revel'] = json.loads(
    (FIXTURES / 'any_player_cast_damage/eidolon.json').read_bytes())
RAW['Twincast'] = json.loads(
    (FIXTURES / 'nth_spell_triggers/canonical.json').read_bytes())['Twincast']
RAW['Humility'] = next(row for row in json.loads(
    (FIXTURES / 'ability_suppression.json').read_bytes()) if row['name'] == 'Humility')
RULES = RulesEngine()


def checked(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RULES, seat, action)
    assert serialize_match_snapshot(state) == before
    return result


def settle(state):
    for _ in range(64):
        if not state.stack or state.winner is not None:
            return state
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                    or state.pending_trigger_order)
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Unresolved canonical test stack')


def cast(state, seat, name, targets=None):
    spell = add(state, name, seat, Zone.HAND, cards=RAW)
    if state.priority_player != seat:
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat
    return checked(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                                 'targets': targets or {}})


def setup(owner):
    state = fixture()
    state.active_player = state.priority_player = owner
    for player in state.players.values():
        player.mana_pool = {color: 20 for color in ('W', 'U', 'B', 'R', 'G', 'C')}
        player.snow_mana_pool.clear()
    state = cast(state, owner, 'Eidolon of the Great Revel')
    assert len(state.stack) == 1
    source_id = state.stack[0].source_card_id
    state = settle(state)
    assert state.cards[source_id].zone == Zone.BATTLEFIELD
    assert {pid: player.life for pid, player in state.players.items()} == {1: 20, 2: 20}
    return state, source_id


def triggers(state, source_id):
    return [item for item in state.stack if item.source_card_id == source_id]


def test_full_canonical_fixture_provenance():
    proof = json.loads((FIXTURES / 'any_player_cast_damage/SOURCES.json').read_bytes())
    for name, record in proof.items():
        data = (FIXTURES / record['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record['sha256']
        raw = json.loads(data)
        assert raw['object'] == 'card' and raw['name'] == name
        assert (raw['id'], raw['oracle_id']) == (record['id'], record['oracle_id'])
        assert raw == RAW[name]


@pytest.mark.parametrize('seat', [1, 2])
def test_native_birth_does_not_trigger_on_itself(seat):
    state, source_id = setup(seat)
    assert not state.stack and state.cards[source_id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('owner', [1, 2])
@pytest.mark.parametrize('own_cast', [True, False])
def test_actual_caster_takes_damage_once(owner, own_cast):
    caster = owner if own_cast else 3-owner
    state, source_id = setup(owner)
    state = cast(state, caster, 'Lightning Bolt', {'target_player': 3-caster})
    observed = triggers(state, source_id)
    assert len(state.stack) == 2 and len(observed) == 1
    assert observed[0].controller == owner
    assert observed[0].payload['target_player'] == caster
    state = settle(state)
    assert state.players[caster].life == 18
    assert state.players[3-caster].life == 17


@pytest.mark.parametrize('seat', [1, 2])
def test_native_twincast_copy_does_not_trigger(seat):
    state, source_id = setup(seat)
    state = cast(state, seat, 'Lightning Bolt', {'target_player': 3-seat})
    bolt_id = state.stack[0].id
    state = cast(state, seat, 'Twincast', {'target_stack_id': bolt_id})
    assert len(triggers(state, source_id)) == 2
    for _ in range(8):
        if state.pending_mechanic_choice:
            break
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    assert len(triggers(state, source_id)) == 1
    assert 'keep' in state.pending_mechanic_choice['options']
    state = checked(state, seat, {'type': 'choose_mechanic',
                                 'card_ids': ['keep']})
    state = settle(state)
    assert state.spells_cast_this_turn[seat] == 3
    assert state.players[seat].life == 16
    assert state.players[3-seat].life == 14


@pytest.mark.parametrize('seat', [1, 2])
def test_native_stifle_counters_trigger_but_is_itself_a_cast(seat):
    state, source_id = setup(seat)
    state = cast(state, seat, 'Lightning Bolt', {'target_player': 3-seat})
    original_trigger = triggers(state, source_id)[0].id
    state = cast(state, 3-seat, 'Stifle', {'target_stack_id': original_trigger})
    assert len(triggers(state, source_id)) == 2
    state = settle(state)
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == 15


@pytest.mark.parametrize('seat', [1, 2])
def test_native_source_departure_does_not_cancel_retained_trigger(seat):
    state, source_id = setup(seat)
    state = cast(state, seat, 'Lightning Bolt', {'target_player': 3-seat})
    state = cast(state, seat, 'Lightning Bolt', {'target_card_id': source_id})
    assert len(triggers(state, source_id)) == 2
    state = settle(state)
    assert state.cards[source_id].zone == Zone.GRAVEYARD
    assert state.players[seat].life == 16
    assert state.players[3-seat].life == 17


@pytest.mark.parametrize('seat', [1, 2])
def test_native_humility_suppresses_printed_trigger(seat):
    state, source_id = setup(seat)
    state = settle(cast(state, seat, 'Humility'))
    state = cast(state, seat, 'Lightning Bolt', {'target_player': 3-seat})
    assert not triggers(state, source_id)
    state = settle(state)
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == 17


@pytest.mark.parametrize('seat', [1, 2])
def test_synthetic_unsupported_suffix_is_not_partially_executed(seat):
    state, source_id = setup(seat)
    # Deliberate negative parser protocol, not a canonical positive Oracle row.
    state.cards[source_id].oracle_text += ' Draw a card.'
    state = cast(state, seat, 'Lightning Bolt', {'target_player': 3-seat})
    assert not triggers(state, source_id)
    state = settle(state)
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == 17
