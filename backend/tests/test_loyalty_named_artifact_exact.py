"""Canonical -7 produces real legendary spell-discount/tap-draw artifact."""
import pytest

from game_state.state import Zone
from rules_engine.continuous import printed_abilities_suppressed
from tests.test_compleated_loyalty_full import (
    cast_walker, activate, settle, reject, raw_card, act, SEED)


def notebook(seat):
    state, cid = cast_walker(seat, doubling=True)
    assert state.cards[cid].loyalty == 10
    state = settle(activate(state, seat, cid, 2))
    tokens = [state.cards[t] for t in state.players[seat].battlefield if state.cards[t].is_token]
    assert len(tokens) == 1, 'native legendary SBA leaves one of doubled Notebook tokens'
    token = tokens[0]
    assert token.name == "Tamiyo's Notebook"
    assert 'Legendary' in token.types and 'Artifact' in token.types
    assert 'Book' in token.type_line and token.colors == []
    assert token.oracle_text == 'Spells you cast cost {2} less to cast.\n{T}: Draw a card.'
    assert state.cards[cid].loyalty == 3
    return state, token.id


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_notebook_real_tap_draw_and_repeat_rejection(seat):
    state, cid = notebook(seat)
    assert state.cards[cid].summoning_sick, 'artifact may tap despite this creature-only restriction'
    before = len(state.players[seat].hand)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})
    assert state.cards[cid].tapped
    state = settle(state)
    assert len(state.players[seat].hand) == before+1
    reject(state, seat, {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('owner', ['self', 'opponent'])
def test_notebook_discount_is_spell_only_and_controller_relative(seat, owner):
    state, cid = notebook(seat)
    caster = seat if owner == 'self' else 3-seat
    state.active_player = state.priority_player = caster
    spell = raw_card(state, SEED['Divination'], caster, Zone.HAND)
    state.players[caster].mana_pool = {'U': 1}
    action = {'type': 'cast_spell', 'card_id': spell.id, 'cost_choice': {'id': 'base'}}
    if owner == 'opponent':
        reject(state, caster, action)
    else:
        state = settle(act(state, caster, action))
        assert not any(state.players[caster].mana_pool.values())
        assert state.cards[spell.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_notebook_cannot_activate_ultimate_without_seven_loyalty(seat):
    state, cid = cast_walker(seat)
    reject(state, seat, {'type': 'activate_loyalty', 'card_id': cid, 'ability_index': 2})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['ability_loss', 'exile', 'control'])
def test_notebook_discount_disappears_on_suppression_departure_or_control_change(seat, change):
    state, cid = notebook(seat)
    from rules_engine.keyword_effects import add_keyword_effect
    from effects.registry import resolve_effect
    if change == 'ability_loss':
        add_keyword_effect(state, cid, ['all abilities'], operation='remove', until_end_of_turn=True)
        assert printed_abilities_suppressed(state, cid)
        reject(state, seat, {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})
    elif change == 'exile': resolve_effect(state, seat, 'exile', {'target_card_id': cid})
    else: resolve_effect(state, 3-seat, 'change_control', {'target_card_id': cid})
    spell = raw_card(state, SEED['Divination'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    reject(state, seat, {'type': 'cast_spell', 'card_id': spell.id, 'cost_choice': {'id': 'base'}})


@pytest.mark.parametrize('seat', [1, 2])
def test_notebook_spell_discount_does_not_pay_lithoform_activation_cost(seat):
    state, cid = notebook(seat)
    import json
    from tests.test_compleated_loyalty_full import FIX
    engine = raw_card(state, json.loads((FIX.parent / 'archangel_pair/lithoform-engine.json').read_bytes()), seat, Zone.BATTLEFIELD)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})
    state.players[seat].mana_pool = {}
    reject(state, seat, {'type': 'activate_ability', 'card_id': engine.id, 'ability_index': 0,
        'targets': {'target_stack_id': state.stack[-1].id}})


@pytest.mark.parametrize('seat', [1, 2])
def test_notebook_draw_tap_cost_is_creature_sickness_sensitive_after_animation(seat):
    state, cid = notebook(seat)
    from rules_engine.type_effects import add_type_effect
    add_type_effect(state, cid, ['Creature'])
    # Native creature-only tap-cost restriction applies; this is a layer seam witness.
    reject(state, seat, {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})


@pytest.mark.parametrize('seat', [1, 2])
def test_notebook_targetless_ultimate_rejects_injected_target_root_pure(seat):
    state, cid = cast_walker(seat, doubling=True)
    target = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    reject(state, seat, {'type': 'activate_loyalty', 'card_id': cid, 'ability_index': 2,
        'targets': {'target_card_id': target.id}})
