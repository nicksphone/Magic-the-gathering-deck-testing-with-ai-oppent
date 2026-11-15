"""Paid canonical animation and native combat decisions, not style-strength proof."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.block_search import block_intents
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.query_context import query_cache
from rules_engine.type_effects import copiable_types, effective_types
from tests.ai_decisions_canonical_cdba import canonical_deck_entry
from tests.test_canonical_land_animation_audit import FAMILIES, action, position, resolve
from tests.test_linked_damage_targets import raw_card


def combat_root(seat, name, *, animated=True, tapped=False):
    state, land = position(seat, name)
    # Declared old-board position and funded pool precede every checked action.
    state.active_player = state.priority_player = 3-seat
    state.players[seat].life = 2
    attacker = raw_card(state, canonical_deck_entry('Grizzly Bears', 1),
                        3-seat, Zone.BATTLEFIELD)
    attacker.summoning_sick = False
    assign_static_order_on_battlefield_entry(state, attacker.id)
    if animated:
        state = checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
        assert state.priority_player == seat
        before = serialize_match_snapshot(state)
        paid = checked_action(state, RulesEngine(), seat, action(state.cards[land.id]))
        assert sum(paid.players[seat].mana_pool.values()) == 0
        assert paid.stack[-1].source_card_id == land.id
        assert paid.stack[-1].effect_key == 'animate_self_land'
        assert not paid.cards[land.id].tapped
        assert serialize_match_snapshot(state) == before
        state = resolve(paid)
        assert 'Creature' in effective_types(state, land.id)
    if tapped:
        assert animated
        for _ in range(4):
            if state.priority_player == seat:
                break
            state = checked_action(state, RulesEngine(), state.priority_player,
                                   {'type': 'pass_priority'})
        state = checked_action(state, RulesEngine(), seat, {'type': 'tap_land_for_mana',
            'card_id': land.id, 'color': 'C' if name == 'Mutavault' else 'U'})
        assert state.cards[land.id].tapped
    for _ in range(24):
        if state.step == Step.DECLARE_ATTACKERS and state.priority_player == 3-seat:
            break
        state = checked_action(state, RulesEngine(), state.priority_player,
                               {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_ATTACKERS and state.priority_player == 3-seat
    state = checked_action(state, RulesEngine(), 3-seat, {'type': 'attack',
        'attackers': [attacker.id], 'attack_targets': {attacker.id: f'player:{seat}'}})
    for _ in range(24):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat and not state.stack:
            break
        state = checked_action(state, RulesEngine(), state.priority_player,
                               {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat
    assert not state.stack and state.winner is None
    assert set(copiable_types(state.cards[land.id])) == {'Land'}
    assert ('Creature' in effective_types(state, land.id)) is animated
    assert all(not player.mana_pool or sum(player.mana_pool.values()) == 0
               for player in state.players.values())
    return state, land.id, attacker.id


def finish(root, seat, chosen):
    state = checked_action(root, RulesEngine(), seat, chosen)
    for _ in range(80):
        if state.winner is not None or state.step == Step.END_COMBAT:
            return state
        if state.pending_mechanic_choice:
            owner = state.pending_mechanic_choice['player_id']
            move = AIAgent().choose_action(state, RulesEngine().legal_moves(state, owner), owner).action
            assert move['type'] == 'choose_mechanic'
        else:
            owner = state.priority_player
            move = {'type': 'pass_priority'}
        state = checked_action(state, RulesEngine(), owner, move)
    raise AssertionError('Native blocking continuation did not finish')


def assert_survived(outcome, seat, land, attacker, name):
    assert outcome.winner is None
    assert outcome.players[seat].life == 2
    assert outcome.cards[attacker].zone == Zone.GRAVEYARD
    assert outcome.cards[land].zone == (Zone.GRAVEYARD if name == 'Mutavault' else Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_paid_animation_supplies_a_real_native_surviving_block(seat, name):
    root, land, attacker = combat_root(seat, name)
    before = serialize_match_snapshot(root)
    offered = RulesEngine().legal_moves(root, seat)
    assert land in {b['id'] for move in offered if move['type'] == 'block'
                    for b in move.get('blockers', [])}
    outcome = finish(root, seat, {'type': 'block', 'blocks': {attacker: [land]}})
    assert_survived(outcome, seat, land, attacker, name)
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('difficulty', ['master', 'master_plus'])
def test_restored_actual_ai_uses_animated_blocker_to_prevent_native_loss(seat, name, difficulty):
    root, land, attacker = combat_root(seat, name)
    before = serialize_match_snapshot(root)
    state = deserialize_match_snapshot(deepcopy(before))
    moves = RulesEngine().legal_moves(state, seat)
    offered, rng = deepcopy(moves), state.rng.getstate()
    decision = AIAgent(difficulty, archetype='Ramp').choose_action(state, moves, seat).action
    assert decision['type'] in {'block', 'pass_priority'}
    outcome = finish(state, seat, decision)
    assert_survived(outcome, seat, land, attacker, name)
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(root) == before
    assert moves == offered and state.rng.getstate() == rng
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_ordered_intents_keep_current_creature_types_without_mutating_printing(seat, name):
    root, land, attacker = combat_root(seat, name)
    before = serialize_match_snapshot(root)
    assert block_intents(root, [attacker], [land]) == [{}, {attacker: [land]}]
    restored = deserialize_match_snapshot(deepcopy(before))
    assert block_intents(restored, [attacker], [land]) == [{}, {attacker: [land]}]
    assert set(copiable_types(restored.cards[land])) == {'Land'}
    assert serialize_match_snapshot(root) == serialize_match_snapshot(restored) == before
    assert query_cache(root) is query_cache(restored) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_unanimated_land_stays_excluded_and_native_rejection_is_atomic(seat, name):
    root, land, attacker = combat_root(seat, name, animated=False)
    before = serialize_match_snapshot(root)
    assert block_intents(root, [attacker], [land]) == [{}]
    assert land not in {b['id'] for move in RulesEngine().legal_moves(root, seat)
                        if move['type'] == 'block' for b in move.get('blockers', [])}
    with pytest.raises(ActionRejected):
        checked_action(root, RulesEngine(), seat, {'type': 'block', 'blocks': {attacker: [land]}})
    assert serialize_match_snapshot(root) == before
    assert query_cache(root) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_genuinely_tapped_animated_land_stays_excluded(seat, name):
    root, land, attacker = combat_root(seat, name, tapped=True)
    before = serialize_match_snapshot(root)
    assert 'Creature' in effective_types(root, land)
    assert block_intents(root, [attacker], [land]) == [{}]
    with pytest.raises(ActionRejected):
        checked_action(root, RulesEngine(), seat, {'type': 'block', 'blocks': {attacker: [land]}})
    assert serialize_match_snapshot(root) == before
    assert query_cache(root) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_opponent_identity_does_not_change_animated_block(seat):
    root, land, attacker = combat_root(seat, 'Mutavault')
    choices = []
    for name in ('Lightning Bolt', 'Counterspell'):
        state = deepcopy(root)
        raw_card(state, canonical_deck_entry(name, 1), 3-seat, Zone.HAND)
        before = serialize_match_snapshot(state)
        moves = RulesEngine().legal_moves(state, seat)
        choice = AIAgent('master', archetype='Ramp').choose_action(state, moves, seat).action
        assert_survived(finish(state, seat, choice), seat, land, attacker, 'Mutavault')
        assert serialize_match_snapshot(state) == before
        choices.append(choice)
    assert choices[0] == choices[1]
