"""Canonical -X exiles the announced card before copying printed facts."""
import pytest

from game_state.state import Zone
from effects.registry import resolve_effect
from tests.test_compleated_loyalty_full import (
    cast_walker, activate, settle, reject, raw_card, RAW, SEED, next_main, act)


def await_attachment(state):
    for _ in range(32):
        if state.pending_mechanic_choice:
            assert state.pending_mechanic_choice['kind'] == 'loyalty_attachment'
            return state
        assert state.stack, 'Aura copy must offer its legal attachment before entry'
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Aura attachment did not materialize')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,x', [('Ornithopter', 0), ('Llanowar Elves', 1), ('Tamiyo, Compleated Sage', 5)])
def test_canonical_exile_then_copy_zero_and_paid_to_zero(seat, name, x):
    state, cid = cast_walker(seat)
    raw = RAW if name == RAW['name'] else SEED[name]
    target = raw_card(state, raw, seat, Zone.GRAVEYARD)
    state = activate(state, seat, cid, 1, {'target_card_id': target.id, 'x_value': x})
    assert state.cards[cid].loyalty == 5-x if x < 5 else state.cards[cid].zone == Zone.GRAVEYARD
    state = settle(state)
    assert state.cards[target.id].zone == Zone.EXILE
    tokens = [state.cards[t] for t in state.players[seat].battlefield if state.cards[t].is_token]
    assert len(tokens) == 1
    token = tokens[0]
    assert token.name == raw['name'] and token.oracle_text == raw['oracle_text']
    assert token.owner == token.controller == seat
    assert token.mana_cost == raw['mana_cost']
    assert token.summoning_sick
    if x == 5: assert token.loyalty == 5


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['enemy', 'hand', 'land', 'instant', 'wrong_mv', 'too_high', 'negative', 'bool'])
def test_exile_copy_target_and_x_rejections_are_root_pure(seat, bad):
    state, cid = cast_walker(seat)
    raw = SEED[{'land': 'Forest', 'instant': 'Lightning Bolt'}.get(bad, 'Llanowar Elves')]
    target = raw_card(state, raw, 3-seat if bad == 'enemy' else seat, Zone.HAND if bad == 'hand' else Zone.GRAVEYARD)
    x = {'wrong_mv': 0, 'too_high': 6, 'negative': -1, 'bool': True}.get(bad, 1)
    reject(state, seat, {'type': 'activate_loyalty', 'card_id': cid, 'ability_index': 1,
        'targets': {'target_card_id': target.id, 'x_value': x}})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['exile', 'reentry'])
def test_graveyard_target_reference_does_not_follow_zone_changes(seat, change):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], seat, Zone.GRAVEYARD)
    state = activate(state, seat, cid, 1, {'target_card_id': target.id, 'x_value': 1})
    resolve_effect(state, seat, 'exile_from_graveyard', {'target_card_id': target.id})
    if change == 'reentry':
        state.players[seat].exile.remove(target.id)
        state.players[seat].graveyard.append(target.id)
        state.cards[target.id].move_to_zone(Zone.GRAVEYARD)
    state = settle(state)
    assert state.cards[target.id].zone == (Zone.GRAVEYARD if change == 'reentry' else Zone.EXILE)
    assert not any(state.cards[t].is_token for t in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
def test_life_paid_source_real_positive_costs_then_uncast_graveyard_copy(seat):
    state, cid = cast_walker(seat, 'P')
    target = raw_card(state, RAW, seat, Zone.GRAVEYARD)
    for loyalty in (4, 5):
        state = settle(activate(state, seat, cid, 0, {'target_card_ids': []}))
        assert state.cards[cid].loyalty == loyalty
        state = next_main(state, seat)
    state = settle(activate(state, seat, cid, 1, {'target_card_id': target.id, 'x_value': 5}))
    token, = [state.cards[t] for t in state.players[seat].battlefield if state.cards[t].is_token]
    assert token.loyalty == 5
    assert state.cards[cid].zone == Zone.GRAVEYARD and state.cards[target.id].zone == Zone.EXILE
    assert state.players[seat].life == 18


@pytest.mark.parametrize('seat', [1, 2])
def test_generic_graveyard_copy_of_canonical_aura_enters_attached_without_targeting(seat):
    import json
    from tests.test_compleated_loyalty_full import FIX
    state, cid = cast_walker(seat)
    state.mechanic_choice_players = {seat}
    creature = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    from rules_engine.keyword_effects import add_keyword_effect
    add_keyword_effect(state, creature.id, ['hexproof'])
    aura = next(row for row in json.loads((FIX.parent / 'aura_costs.json').read_bytes()) if row['name'] == 'Pacifism')
    target = raw_card(state, aura, seat, Zone.GRAVEYARD)
    state = await_attachment(activate(state, seat, cid, 1, {'target_card_id': target.id, 'x_value': 2}))
    assert creature.id in state.pending_mechanic_choice['options']
    state = settle(act(state, seat, {'type': 'choose_mechanic', 'choice_id': creature.id}))
    token, = [state.cards[t] for t in state.players[seat].battlefield if state.cards[t].is_token]
    assert token.oracle_text == aura['oracle_text'] and token.attached_to == creature.id
    assert state.cards[target.id].zone == Zone.EXILE
    assert not state.stack, 'uncast Aura attachment does not target and does not pay ward'
