"""Paid canonical damage episodes; explicit mana/old-land setup, not D13 or AI."""
import json
import pytest

from .test_full_vraska import (ROOT, RAW, BEAR, add, bare, act, advance, paid_cast,
                              activate, settle, Zone, Step)
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.targeting import stack_object_kind

DREADMAW = json.loads((ROOT/'fixtures/colossal-dreadmaw.json').read_bytes())
WURM = json.loads((ROOT/'fixtures/craw-wurm.json').read_bytes())
FOREST = json.loads((ROOT/'fixtures/forest.json').read_bytes())
SWAMP = json.loads((ROOT/'fixtures/swamp.json').read_bytes())
MOUNTAIN = json.loads((ROOT/'fixtures/mountain.json').read_bytes())
BOLT = json.loads((ROOT/'fixtures/lightning-bolt.json').read_bytes())


def fund(state, seat, land_raw, color, amount):
    for _ in range(amount):
        land = add(state, land_raw, seat, Zone.BATTLEFIELD, old_board=True)
        state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': land.id, 'color': color})
        assert state.cards[land.id].tapped
    return state


def paid_board(seat, *, blocker=False, small_attacker=False):
    state = bare(3-seat)
    creature = add(state, BEAR if small_attacker else DREADMAW, 3-seat, Zone.HAND)
    state = paid_cast(state, 3-seat, creature, 2 if small_attacker else 6)
    state = advance(state, seat, Step.PRECOMBAT_MAIN)
    walker = add(state, RAW, seat, Zone.HAND)
    state = fund(state, seat, FOREST, 'G', 4)
    state = fund(state, seat, SWAMP, 'B', 1)
    state = paid_cast(state, seat, walker, 5)
    blocking_id = None
    if blocker:
        blocking = add(state, WURM, seat, Zone.HAND)
        state = fund(state, seat, FOREST, 'G', 6)
        state = paid_cast(state, seat, blocking, 6)
        blocking_id = blocking.id
    state = settle(activate(state, seat, walker.id, 0))
    assert state.cards[walker.id].loyalty == 6
    return state, walker.id, creature.id, blocking_id


def actual_damage_trigger(state, seat, walker, creature, blocker=None):
    state = advance(state, 3-seat, Step.DECLARE_ATTACKERS)
    state = act(state, 3-seat, {'type': 'attack', 'attackers': [creature],
        'attack_targets': {creature: 'planeswalker:'+walker}})
    blocked = False
    for _ in range(80):
        if any(item.effect_key == 'loyalty_combat_retaliation_destroy' for item in state.stack):
            return state
        if state.step == Step.END_COMBAT:
            break
        if blocker and state.step == Step.DECLARE_BLOCKERS and not blocked and state.priority_player == seat:
            state = act(state, seat, {'type': 'block', 'blocks': {creature: [blocker]}})
            blocked = True
        else:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Genuine positive combat damage did not publish retaliation trigger')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_six_damage_lethal_walker_still_publishes_counterable_retaliation(seat):
    state, walker, creature, _ = paid_board(seat)
    state = actual_damage_trigger(state, seat, walker, creature)
    assert state.cards[walker].zone == Zone.GRAVEYARD
    assert state.cards[creature].zone == Zone.BATTLEFIELD
    trigger = next(item for item in state.stack if item.effect_key == 'loyalty_combat_retaliation_destroy')
    assert trigger.source_card_id == walker and trigger.controller == seat
    assert stack_object_kind(state, trigger) == 'triggered'
    assert not trigger.payload.get('__trigger_target_choice')
    state = settle(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[creature].zone == Zone.GRAVEYARD and state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_simultaneous_lethal_attacker_and_blocker_retain_real_damage_trigger(seat):
    state, walker, creature, blocker = paid_board(seat, blocker=True)
    state = actual_damage_trigger(state, seat, walker, creature, blocker)
    assert state.cards[walker].loyalty == 4
    assert state.cards[creature].zone == state.cards[blocker].zone == Zone.GRAVEYARD
    assert len([item for item in state.stack if item.effect_key == 'loyalty_combat_retaliation_destroy']) == 1
    state = settle(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[walker].zone == Zone.BATTLEFIELD and state.cards[walker].loyalty == 4
    assert state.cards[creature].zone == Zone.GRAVEYARD and state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_attacker_protection_from_black_does_not_prevent_nontargeted_destruction(seat):
    from rules_engine.keyword_effects import add_keyword_effect
    state, walker, creature, _ = paid_board(seat, small_attacker=True)
    # Explicit continuous-effect protection boundary, not a paid protection-spell episode.
    add_keyword_effect(state, creature, ['protection from black'])
    state = actual_damage_trigger(state, seat, walker, creature)
    state = settle(state)
    assert state.cards[creature].zone == Zone.GRAVEYARD
    assert state.cards[walker].loyalty == 4 and state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_noncombat_bolt_to_same_walker_never_publishes_retaliation(seat):
    state, walker, creature, _ = paid_board(seat)
    bolt = add(state, BOLT, 3-seat, Zone.HAND)
    state = act(state, seat, {'type': 'pass_priority'})
    state = fund(state, 3-seat, MOUNTAIN, 'R', 1)
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': bolt.id,
                              'targets': {'target_card_id': walker}})
    assert state.stack[-1].payload['mana_spent'] == 1
    for _ in range(80):
        assert all(item.effect_key != 'loyalty_combat_retaliation_destroy' for item in state.stack)
        if not state.stack:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[walker].loyalty == 3
    assert state.cards[creature].zone == Zone.BATTLEFIELD and state.winner is None
