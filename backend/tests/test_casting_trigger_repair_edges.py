"""Canonical fixtures plus explicitly labeled core event/zone boundary packets."""
import pytest

from effects.handlers import destroy_permanent, change_control, temporary_ability_loss
from game_state.state import Zone
from rules_engine.flashback_grants import granted_cost
from tests.regression_agent_wave2.support import position, add, cast, settle, resume, moves, RULES
from rules_engine.action_validation import checked_action, ActionRejected


@pytest.mark.parametrize('seat', [1, 2])
def test_fling_uses_effective_paid_power_after_anthem_departure(seat):
    from tests.regression_agent.test_interactions import add as first_wave_add
    state = position(seat)
    bear = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    anthem = first_wave_add(state, 'Glorious Anthem', seat, Zone.BATTLEFIELD)
    spell = add(state, 'Fling', seat)
    state.players[seat].mana_pool.update(R=1, U=1)
    state = cast(state, spell, {'target_player': 3-seat},
                 cost_choice={'id': 'base', 'sacrifice_card_ids': [bear.id]})
    destroy_permanent(state, seat, {'target_card_id': anthem})  # Core destruction packet.
    state = settle(resume(state))
    assert state.players[3-seat].life == 17


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stale,suppressed', [(False, False), (True, False), (False, True)])
def test_self_return_uses_old_controller_owner_and_graveyard_reference(seat, stale, suppressed):
    state = position(seat)
    bear = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    aura = add(state, 'Rancor', 3-seat, Zone.BATTLEFIELD)
    aura.attached_to = bear.id
    change_control(state, seat, {'target_card_id': aura.id})  # Core control-change packet.
    if suppressed:
        temporary_ability_loss(state, seat, {'target_card_id': aura.id})  # Core loss packet.
    destroy_permanent(state, seat, {'target_card_id': aura.id})
    if suppressed:
        assert not state.stack
        assert aura.id in state.players[3-seat].graveyard
        return
    assert state.stack[-1].controller == seat
    if stale:
        # A real intervening zone-history boundary; never restore the old object.
        state.cards[aura.id].move_to_zone(Zone.HAND)
        state.cards[aura.id].move_to_zone(Zone.GRAVEYARD)
    state = settle(resume(state))
    assert state.cards[aura.id].zone == (Zone.GRAVEYARD if stale else Zone.HAND)
    if not stale:
        assert aura.id in state.players[3-seat].hand
        assert state.cards[aura.id].controller == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lost', ['first', 'all', 'returned'])
def test_ordered_counters_keep_allocation_and_revalidate_objects(seat, lost):
    state = position(seat)
    spell = add(state, 'Incremental Growth', seat)
    bears = [add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD) for _ in range(3)]
    state.players[seat].mana_pool.update(G=2, U=3)
    state = cast(state, spell, {'target_card_ids': [card.id for card in bears]})
    for card in bears if lost == 'all' else bears[:1]:
        state.players[seat].battlefield.remove(card.id)
        state.cards[card.id].move_to_zone(Zone.HAND)
        state.players[seat].hand.append(card.id)
    if lost == 'returned':
        card = state.cards[bears[0].id]
        state.players[seat].hand.remove(card.id)
        card.move_to_zone(Zone.BATTLEFIELD)
        state.players[seat].battlefield.append(card.id)
    state = settle(resume(state))
    expected = [0, 0, 0] if lost == 'all' else [0, 2, 3]
    assert [state.cards[card.id].counters.get('+1/+1', 0) for card in bears] == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalidated', ['cleanup', 'new-turn', 'new-object'])
def test_granted_flashback_expires_and_never_attaches_to_new_object(seat, invalidated):
    state = position(seat)
    spell = add(state, 'Burst Lightning', seat, Zone.GRAVEYARD)
    snap = add(state, 'Snapcaster Mage', seat)
    state.players[seat].mana_pool.update(U=1, C=1, R=1)
    state = settle(resume(cast(state, snap)))
    assert granted_cost(state, state.cards[spell.id], seat) == '{R}'
    assert moves(state, state.cards[spell.id])
    assert granted_cost(state, state.cards[spell.id], 3-seat) is None
    if invalidated == 'cleanup':
        RULES._clear_marked_damage(state)  # Shared cleanup-expiration operation.
    elif invalidated == 'new-turn':
        state.turn += 1
    else:
        state.cards[spell.id].move_to_zone(Zone.EXILE)
        state.cards[spell.id].move_to_zone(Zone.GRAVEYARD)
    state = resume(state)
    assert granted_cost(state, state.cards[spell.id], seat) is None
    assert not moves(state, state.cards[spell.id])


@pytest.mark.parametrize('seat', [1, 2])
def test_human_flashback_target_choice_is_owned_durable_and_object_bound(seat):
    state = position(seat)
    first = add(state, 'Burst Lightning', seat, Zone.GRAVEYARD)
    second = add(state, 'Shock', seat, Zone.GRAVEYARD)
    snap = add(state, 'Snapcaster Mage', seat)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state.players[seat].mana_pool.update(U=1, C=1, R=1)
    state = cast(state, snap)
    for _ in range(2):
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    state = resume(state)
    pending = state.pending_trigger_order
    assert pending and pending['phase'] == 'targets' and pending['current_controller'] == seat
    action = {'type': 'choose_trigger_target', 'stack_id': pending['current_stack_id'], 'target_card_id': second.id}
    with pytest.raises(ActionRejected):
        checked_action(state, RULES, 3-seat, action)
    state = checked_action(state, RULES, seat, action)
    # Target leaves and returns before resolution: the same ID is a new object.
    state.cards[second.id].move_to_zone(Zone.EXILE)
    state.cards[second.id].move_to_zone(Zone.GRAVEYARD)
    state = settle(resume(state))
    assert granted_cost(state, state.cards[first.id], seat) is None
    assert granted_cost(state, state.cards[second.id], seat) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_native_and_granted_flashback_keep_distinct_costs_and_x(seat):
    state = position(seat)
    spell = add(state, "Devil's Play", seat, Zone.GRAVEYARD)
    snap = add(state, 'Snapcaster Mage', seat)
    state.players[seat].mana_pool.update(U=1, C=4, R=3)
    state = settle(resume(cast(state, snap)))
    offered = moves(state, state.cards[spell.id])
    options = {option['id']: option['mana_cost'] for move in offered for option in move['cost_options']}
    assert options['flashback'] == '{X}{R}{R}{R}'
    assert options['flashback_granted'] == '{X}{R}'
    state = cast(state, state.cards[spell.id], {'x_value': 3, 'target_player': 3-seat},
                 from_graveyard=True, cost_choice={'id': 'flashback_granted'})
    state = settle(resume(state))
    assert state.players[3-seat].life == 17
    assert state.cards[spell.id].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_required_distinct_targets_are_not_offered_with_too_few_creatures(seat):
    state = position(seat)
    spell = add(state, 'Incremental Growth', seat)
    for _ in range(2):
        add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool.update(G=2, U=3)
    assert not moves(state, spell)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('style', ['Aggro', 'Control'])
def test_ai_chooses_distinct_ordered_allocations_and_pays(seat, difficulty, style):
    from ai.agent import AIAgent
    from game_state.serializers import serialize_match_snapshot
    state = position(seat)
    spell = add(state, 'Incremental Growth', seat)
    bears = [add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD) for _ in range(3)]
    add(state, 'Birds of Paradise', 3-seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool.update(G=2, U=3)
    agent = AIAgent(difficulty=difficulty, archetype=style)
    before = serialize_match_snapshot(state)
    action = agent.choose_action(state, RULES.legal_moves(state, seat), seat).action
    assert action['type'] == 'cast_spell' and action['card_id'] == spell.id
    assert serialize_match_snapshot(state) == before
    assert set(action['targets']['target_card_ids']) == {card.id for card in bears}
    state = checked_action(state, RULES, seat, action)
    state = settle(resume(state))
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert sorted(state.cards[card.id].counters.get('+1/+1', 0) for card in bears) == [1, 2, 3]
