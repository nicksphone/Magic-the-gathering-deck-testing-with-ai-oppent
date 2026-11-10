"""Native target mana value differs from the amount chosen or paid for a cost."""
import json

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_ability_spec
from rules_engine.cast_choice import build_cast_hints
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_value
from tests.test_ai_hybrid_cast_choices import canonical, spectral_position
from tests.test_copy_stack160_fixture_fidelity import _raw as counter_row
from tests.test_linked_damage_targets import raw_card
from tests.test_low_mana_value_cast_trigger_boundaries import RAW as VARIABLE
from tests.test_source_linked_payment_matrix import EXTRA


PAYMENTS = {
    'white': ({'W': 3}, ['W', 'W', 'W'], 3),
    'mixed': ({'W': 1, 'C': 4}, ['W', '2', '2'], 5),
    'generic': ({'C': 6}, ['2', '2', '2'], 6),
}


def act(state, seat, action):
    before = serialize_match_snapshot(state)
    rng = state.rng.getstate()
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before and state.rng.getstate() == rng
    return result


def restore(state, enabled):
    before = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(json.loads(json.dumps(before))) if enabled else state
    assert serialize_match_snapshot(result) == before
    return result


def finish_top(state):
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return state


def add_counter(state, name, seat):
    row = canonical(name) if name == 'Drown in the Loch' else counter_row(name)
    return raw_card(state, row, seat, Zone.HAND)


def counter_selection(state, counter, seat, target=None):
    result = {}
    if state.cards[counter].name == 'Drown in the Loch':
        mode = build_ability_spec(state, state.cards[counter], seat).modes[0]
        assert mode.startswith('Counter target spell with mana value')
        result['mode_text'] = mode
    if target is not None:
        result['target_stack_id'] = target
    return result


def paid_spectral(seat, payment, counter=None, graveyard=0):
    pool, choices, spent = PAYMENTS[payment]
    env, _, move = spectral_position(seat, pool)
    state, source = env._state, move['card_id']
    response = add_counter(state, counter, 3-seat) if counter else None
    # Declared public old-board graveyard population, not a paid-history claim.
    player = state.players[seat]
    for cid in list(player.library[:graveyard]):
        player.library.remove(cid)
        state.cards[cid].move_to_zone(Zone.GRAVEYARD)
        player.graveyard.append(cid)
    assert len(player.graveyard) == graveyard
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
        'cost_choice': {'id': 'base'}, 'hybrid_choices': choices, 'targets': {}})
    item, = state.stack
    assert item.source_card_id == source and item.payload['mana_spent'] == spent
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.cards[source].mana_cost == '{2/W}{2/W}{2/W}'
    assert mana_value(state.cards[source].mana_cost) == 6
    return state, source, item.id, response.id if response else None


def counter_window(state, seat, restored):
    state = act(state, seat, {'type': 'pass_priority'})
    assert state.priority_player == 3-seat
    state.players[3-seat].mana_pool = {'U': 1, 'B': 1, 'C': 1}
    return restore(state, restored)


def offered_stack_targets(state, counter, seat):
    before = serialize_match_snapshot(state)
    rng = state.rng.getstate()
    hints = build_cast_hints(state, state.cards[counter], seat, counter_selection(state, counter, seat))
    moves = RulesEngine().legal_moves(state, seat)
    assert serialize_match_snapshot(state) == before and state.rng.getstate() == rng
    return {x['id'] for x in hints.get('stack_targets', [])}, moves


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payment', ['white', 'mixed', 'generic'])
def test_native_two_brid_payment_keeps_six_mana_value_and_resolves(seat, payment):
    state, source, _, _ = paid_spectral(seat, payment)
    state = finish_top(restore(state, True))
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    tokens = [state.cards[cid] for cid in state.players[seat].battlefield
              if state.cards[cid].is_token]
    assert len(tokens) == 3
    assert all(card.power == card.toughness == 1 and 'Creature' in card.types for card in tokens)
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payment', ['white', 'mixed', 'generic'])
@pytest.mark.parametrize('restored', [False, True])
def test_two_brid_spell_is_a_legal_minimum_mana_value_counter_target(seat, payment, restored):
    state, source, target, counter = paid_spectral(seat, payment, 'Disdainful Stroke')
    state = counter_window(state, seat, restored)
    targets, moves = offered_stack_targets(state, counter, 3-seat)
    assert target in targets
    assert any(move.get('card_id') == counter and move['type'] == 'cast_spell' for move in moves)
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter,
        'cost_choice': {'id': 'base'}, 'targets': {'target_stack_id': target}})
    assert state.stack[-1].payload['mana_spent'] == 2
    state = finish_top(restore(state, restored))
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[counter].zone == Zone.GRAVEYARD
    assert not any(state.cards[cid].is_token for cid in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payment', ['white', 'mixed', 'generic'])
@pytest.mark.parametrize('restored', [False, True])
def test_two_brid_spell_above_graveyard_bound_rejects_without_payment(seat, payment, restored):
    state, source, target, counter = paid_spectral(seat, payment, 'Drown in the Loch', 3)
    state = counter_window(state, seat, restored)
    targets, moves = offered_stack_targets(state, counter, 3-seat)
    assert target not in targets
    assert not any(move.get('card_id') == counter and move['type'] == 'cast_spell' for move in moves)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'cast_spell', 'card_id': counter,
            'cost_choice': {'id': 'base'}, 'targets': counter_selection(state, counter, 3-seat, target)})
    assert serialize_match_snapshot(state) == before
    assert state.cards[source].zone == Zone.STACK and state.cards[counter].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_two_brid_spell_at_graveyard_bound_is_countered_natively(seat, restored):
    state, source, target, counter = paid_spectral(seat, 'white', 'Drown in the Loch', 6)
    state = counter_window(state, seat, restored)
    targets, moves = offered_stack_targets(state, counter, 3-seat)
    assert target in targets
    move = next(move for move in moves if move.get('card_id') == counter and move['type'] == 'cast_spell')
    assert move
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter,
        'cost_choice': {'id': 'base'}, 'targets': counter_selection(state, counter, 3-seat, target)})
    assert state.stack[-1].payload['mana_spent'] == 2
    state = finish_top(restore(state, restored))
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[counter].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
@pytest.mark.parametrize('x', [1, 2])
def test_exact_counter_bound_uses_the_target_spell_chosen_x(seat, restored, x):
    env, _, _ = spectral_position(seat, {'W': 3})
    state = env._state
    state.players[seat].mana_pool = {'C': 2*x}
    source = raw_card(state, VARIABLE['Walking Ballista'], seat, Zone.HAND).id
    counter = add_counter(state, 'Spell Snare', 3-seat).id
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
        'cost_choice': {'id': 'base'}, 'targets': {'x_value': x}})
    target = state.stack[-1].id
    assert state.stack[-1].payload['x_value'] == x and state.stack[-1].payload['mana_spent'] == 2*x
    state = counter_window(state, seat, restored)
    targets, moves = offered_stack_targets(state, counter, 3-seat)
    assert (target in targets) == (x == 1)
    assert any(move.get('card_id') == counter and move['type'] == 'cast_spell' for move in moves) == (x == 1)
    action = {'type': 'cast_spell', 'card_id': counter,
        'cost_choice': {'id': 'base'}, 'targets': {'target_stack_id': target}}
    if x == 1:
        state = finish_top(restore(act(state, 3-seat, action), restored))
        assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    else:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 3-seat, action)
        assert serialize_match_snapshot(state) == before
        state = finish_top(state)
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert state.cards[source].counters.get('+1/+1') == x


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
@pytest.mark.parametrize('x', [0, 1])
def test_snow_permanent_has_one_mana_value_for_paid_x_exile(seat, restored, x):
    env, _, _ = spectral_position(seat, {'W': 3})
    state = env._state
    state.players[seat].mana_pool = {'W': 1, 'C': x}
    spell = raw_card(state, canonical('March of Otherworldly Light'), seat, Zone.HAND).id
    target = raw_card(state, EXTRA['Icehide Golem'], 3-seat, Zone.BATTLEFIELD).id
    assert state.cards[target].mana_cost == '{S}' and mana_value(state.cards[target].mana_cost) == 1
    state = restore(state, restored)
    action = {'type': 'cast_spell', 'card_id': spell,
        'cost_choice': {'id': 'base'}, 'targets': {'x_value': x, 'target_card_id': target}}
    if x == 0:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, action)
        assert serialize_match_snapshot(state) == before
        assert state.cards[spell].zone == Zone.HAND and state.cards[target].zone == Zone.BATTLEFIELD
    else:
        state = act(state, seat, action)
        assert state.stack[-1].payload['mana_spent'] == 2
        state = finish_top(restore(state, restored))
        assert not state.stack and state.cards[target].zone == Zone.EXILE
        assert state.cards[spell].zone == Zone.GRAVEYARD
