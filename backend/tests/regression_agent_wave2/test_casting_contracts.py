"""Wave two: expected rules, not compatibility assertions for current bugs."""
import pytest
from ai.agent import AIAgent
from game_state.state import Zone, Step
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.combat import effective_power
from tests.regression_agent_wave2.support import (
    RULES, position, add, moves, cast, reject, resume, settle, record,
)


@pytest.mark.parametrize('seat,x', [(1, 0), (2, 3)])
def test_blaze_announced_x_payment_and_damage(seat, x):
    s = position(seat)
    c = add(s, 'Blaze', seat)
    s.players[seat].mana_pool.update(R=1, U=x)
    assert moves(s, c)
    s = cast(s, c, {'x_value': x, 'target_player': 3-seat})
    assert sum(s.players[seat].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.players[3-seat].life == 20-x
    assert s.cards[c.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('x', [-1, 4, None], ids=['negative', 'unaffordable', 'missing'])
def test_blaze_invalid_x_is_fully_atomic(x):
    s = position()
    c = add(s, 'Blaze')
    s.players[1].mana_pool.update(R=1, U=3)
    targets = {'target_player': 2}
    if x is not None:
        targets['x_value'] = x
    reject(s, 1, {'type': 'cast_spell', 'card_id': c.id, 'targets': targets})


@pytest.mark.parametrize('pool,legal', [({'G': 2}, False), ({'G': 1, 'C': 1}, True)], ids=['colored-is-not-colorless', 'true-colorless'])
def test_spatial_contortion_colorless_requirement(pool, legal):
    s = position(2)
    c = add(s, 'Spatial Contortion', 2)
    target = add(s, 'Grizzly Bears', 1, Zone.BATTLEFIELD)
    s.players[2].mana_pool.update(pool)
    offered = bool(moves(s, c))
    action = {'type': 'cast_spell', 'card_id': c.id, 'targets': {'target_card_id': target.id}}
    if not legal:
        reject(s, 2, action)
        assert not offered
    else:
        assert offered
        s = cast(s, c, action['targets'])
        assert sum(s.players[2].mana_pool.values()) == 0
        s = settle(resume(s))
        assert s.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('pool', [{'R': 2}, {'G': 2}, {'R': 1, 'G': 1}], ids=['red', 'green', 'mixed'])
def test_hybrid_payment_then_real_entry_trigger(pool):
    s = position()
    c = add(s, 'Burning-Tree Emissary')
    s.players[1].mana_pool.update(pool)
    assert moves(s, c)
    s = cast(s, c)
    assert sum(s.players[1].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.cards[c.id].zone == Zone.BATTLEFIELD
    assert s.players[1].mana_pool['R'] == s.players[1].mana_pool['G'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_firebolt_flashback_cannot_use_front_price_and_exiles(seat):
    s = position(seat)
    c = add(s, 'Firebolt', seat, Zone.GRAVEYARD)
    s.players[seat].mana_pool.update(R=1, U=4)
    assert moves(s, c)
    reject(s, seat, {'type': 'cast_spell', 'card_id': c.id, 'from_graveyard': True,
                    'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}})
    s = cast(s, c, {'target_player': 3-seat}, from_graveyard=True, cost_choice={'id': 'flashback'})
    assert sum(s.players[seat].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.players[3-seat].life == 18
    assert s.cards[c.id].zone == Zone.EXILE


@pytest.mark.parametrize('seat,target_self', [(1, False), (2, False), (1, True)], ids=['p1-lki', 'p2-lki', 'sacrificed-target'])
def test_fling_sacrifice_target_and_lki(seat, target_self):
    s = position(seat)
    c = add(s, 'Fling', seat)
    bear = add(s, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    # Real prior +1/+1 counters, not altered printed stats.
    bear.counters['+1/+1'] = 2
    assert effective_power(s, bear.id) == 4
    s.players[seat].mana_pool.update(R=1, U=1)
    assert moves(s, c)
    target = {'target_card_id': bear.id} if target_self else {'target_player': 3-seat}
    s = cast(s, c, target, cost_choice={'id': 'base', 'sacrifice_card_ids': [bear.id]})
    assert s.cards[bear.id].zone == Zone.GRAVEYARD
    assert sum(s.players[seat].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.players[3-seat].life == (20 if target_self else 16)
    assert s.cards[c.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('kicked', [False, True], ids=['base', 'kicker'])
def test_burst_lightning_exact_branch_payment(kicked):
    s = position()
    c = add(s, 'Burst Lightning')
    s.players[1].mana_pool.update(R=1, U=4)
    assert moves(s, c)
    s = cast(s, c, {'target_player': 2}, cost_choice={'id': 'kicker' if kicked else 'base'})
    assert sum(s.players[1].mana_pool.values()) == (0 if kicked else 4)
    s = settle(resume(s))
    assert s.players[2].life == (16 if kicked else 18)


def test_snapcaster_flashback_can_add_kicker_after_restart():
    s = position()
    burst = add(s, 'Burst Lightning', 1, Zone.GRAVEYARD)
    snap = add(s, 'Snapcaster Mage')
    s.players[1].mana_pool.update(U=1, R=1, C=5)
    s = cast(s, snap)
    s = settle(resume(s))
    record('granted-flashback', s, legal_moves=moves(s, s.cards[burst.id]))
    offered = moves(s, s.cards[burst.id])
    assert offered
    s = cast(s, s.cards[burst.id], {'target_player': 2}, from_graveyard=True,
             cost_choice={'id': 'flashback_kicker'})
    assert sum(s.players[1].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.players[2].life == 16 and s.cards[burst.id].zone == Zone.EXILE


RECOVERY = 'Bala Ged Recovery // Bala Ged Sanctuary'
GIANT = 'Bonecrusher Giant // Stomp'


def test_mdfc_land_face_cannot_bypass_land_limit_or_timing():
    s = position(2)
    c = add(s, RECOVERY, 2)
    s.players[2].lands_played_this_turn = 1
    s.players[2].last_land_play_turn = s.turn
    s.players[2].land_plays_recorded_on_turn = 1
    reject(s, 2, {'type': 'play_land', 'card_id': c.id, 'selected_face_index': 1})
    s.players[2].lands_played_this_turn = 0
    s.players[2].land_plays_recorded_on_turn = 0
    s.active_player = 1
    reject(s, 2, {'type': 'play_land', 'card_id': c.id, 'selected_face_index': 1})
    assert not moves(s, c)


def test_mdfc_front_recovers_only_own_graveyard_then_restores_identity():
    s = position()
    c = add(s, RECOVERY)
    library_copy = add(s, RECOVERY, 1, Zone.LIBRARY)
    from rules_engine.card_types import is_land_card
    assert library_copy.types == ['Sorcery'] and library_copy.mana_cost == '{2}{G}'
    assert not is_land_card(library_copy)
    own = add(s, 'Shock', 1, Zone.GRAVEYARD)
    enemy = add(s, 'Lightning Bolt', 2, Zone.GRAVEYARD)
    s.players[1].mana_pool.update(G=1, U=2)
    reject(s, 1, {'type': 'cast_spell', 'card_id': c.id, 'selected_face_index': 0,
                  'targets': {'target_card_id': enemy.id}})
    assert any(m['type'] == 'cast_spell' for m in moves(s, c))
    s = cast(s, c, {'target_card_id': own.id}, selected_face_index=0)
    assert sum(s.players[1].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.cards[own.id].zone == Zone.HAND and s.cards[enemy.id].zone == Zone.GRAVEYARD
    assert s.cards[c.id].types == ['Sorcery'] and s.cards[c.id].zone == Zone.GRAVEYARD


def test_adventure_opponent_turn_then_creature_permission_waits_for_main():
    s = position(2)
    c = add(s, GIANT, 2)
    s.active_player = 1
    s.step = Step.UPKEEP
    s.players[2].mana_pool.update(R=2, U=3)
    assert {m.get('selected_face_index', 0) for m in moves(s, c)} == {1}
    s = cast(s, c, {'target_player': 1}, selected_face_index=1)
    s = settle(resume(s))
    assert s.cards[c.id].zone == Zone.EXILE and s.players[1].life == 18
    s.priority_player = 2
    reject(s, 2, {'type': 'cast_spell', 'card_id': c.id, 'from_exile': True})
    s.active_player = 2
    s.step = Step.PRECOMBAT_MAIN
    s = cast(s, s.cards[c.id], from_exile=True)
    s = settle(resume(s))
    assert s.cards[c.id].zone == Zone.BATTLEFIELD
    assert c.id not in s.adventure_permissions


RETURN = 'Return target creature card from your graveyard to your hand'
DAMAGE = "Kolaghan's Command deals 2 damage to any target"
DISCARD = 'Target player discards a card'


def command_position():
    s = position()
    c = add(s, "Kolaghan's Command")
    grave = add(s, 'Grizzly Bears', 1, Zone.GRAVEYARD)
    target = add(s, 'Birds of Paradise', 2, Zone.BATTLEFIELD)
    s.players[1].mana_pool.update(B=1, R=1, U=1)
    targets = {'mode_texts': [RETURN, DAMAGE], 'mode_targets': {
        RETURN: {'target_card_id': grave.id}, DAMAGE: {'target_card_id': target.id}}}
    return s, c, grave, target, targets


@pytest.mark.parametrize('lost', ['none', 'battlefield', 'both'])
def test_modal_mixed_zones_recheck_independently_after_restart(lost):
    s, c, grave, target, targets = command_position()
    assert moves(s, c)
    s = cast(s, c, targets)
    assert sum(s.players[1].mana_pool.values()) == 0
    # A position boundary, not a mocked resolution: targeted objects changed zones.
    if lost != 'none':
        s.players[2].battlefield.remove(target.id)
        s.players[2].hand.append(target.id)
        s.cards[target.id].move_to_zone(Zone.HAND)
    if lost == 'both':
        s.players[1].graveyard.remove(grave.id)
        s.players[1].library.append(grave.id)
        s.cards[grave.id].move_to_zone(Zone.LIBRARY)
    s = settle(resume(s))
    assert s.cards[grave.id].zone == (Zone.LIBRARY if lost == 'both' else Zone.HAND)
    assert s.cards[target.id].zone == (Zone.GRAVEYARD if lost == 'none' else Zone.HAND)
    assert s.cards[c.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('bad', ['one-mode', 'three-modes', 'duplicate-mode'])
def test_modal_min_max_and_duplicate_modes_are_atomic(bad):
    s, c, grave, target, targets = command_position()
    if bad == 'one-mode':
        targets = {'mode_texts': [DAMAGE], 'target_player': 2}
    elif bad == 'three-modes':
        targets['mode_texts'].append(DISCARD)
        targets['mode_targets'][DISCARD] = {'target_player': 2}
    else:
        targets = {'mode_texts': [DAMAGE, DAMAGE], 'target_player': 2}
    reject(s, 1, {'type': 'cast_spell', 'card_id': c.id, 'targets': targets})


def test_common_bond_two_occurrences_can_target_same_creature():
    s = position()
    c = add(s, 'Common Bond')
    bear = add(s, 'Grizzly Bears', 1, Zone.BATTLEFIELD)
    s.players[1].mana_pool.update(G=1, W=1, U=1)
    assert moves(s, c)
    s = cast(s, c, {'target_card_id': bear.id})
    s = settle(resume(s))
    assert s.cards[bear.id].counters.get('+1/+1') == 2


def test_incremental_growth_rejects_duplicate_target_before_payment():
    s = position()
    c = add(s, 'Incremental Growth')
    bears = [add(s, 'Grizzly Bears', 1, Zone.BATTLEFIELD) for _ in range(3)]
    s.players[1].mana_pool.update(G=2, U=3)
    assert moves(s, c)
    reject(s, 1, {'type': 'cast_spell', 'card_id': c.id,
                  'targets': {'target_card_ids': [bears[0].id, bears[0].id, bears[1].id]}})


def test_incremental_growth_distinct_targets_keep_announced_counter_amounts():
    s = position(2)
    c = add(s, 'Incremental Growth', 2)
    bears = [add(s, 'Grizzly Bears', 2, Zone.BATTLEFIELD) for _ in range(3)]
    s.players[2].mana_pool.update(G=2, U=3)
    assert moves(s, c)
    s = cast(s, c, {'target_card_ids': [bear.id for bear in bears]})
    assert sum(s.players[2].mana_pool.values()) == 0
    s = settle(resume(s))
    assert [s.cards[bear.id].counters.get('+1/+1', 0) for bear in bears] == [1, 2, 3]


@pytest.mark.parametrize('style,seat', [('Aggro', 1), ('Aggro', 2), ('Control', 1), ('Control', 2)])
def test_actual_ai_chooses_payable_action_with_hidden_information_invariance(style, seat):
    s = position(seat)
    # Red pressure and blue-red control positions share a public lethal decision,
    # with different real alternatives and an impossible generic-vs-C candidate.
    for name in (['Blaze', 'Shock', 'Burning-Tree Emissary'] if style == 'Aggro'
                 else ['Blaze', 'Firebolt', 'Spatial Contortion']):
        add(s, name, seat)
    add(s, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
    hidden = add(s, 'Lightning Bolt', 3-seat)
    s.players[seat].mana_pool.update(R=1, U=2)
    s.players[3-seat].life = 2
    before = serialize_match_snapshot(s)
    legal = RULES.legal_moves(s, seat)
    assert len([m for m in legal if m['type'] == 'cast_spell']) >= 2
    ai = AIAgent(difficulty='master', archetype=style)
    action = ai.choose_action(s, legal, seat).action
    assert serialize_match_snapshot(s) == before
    changed = resume(s)
    # Replace an unobserved opponent hand card with another canonical card.
    changed.players[3-seat].hand.remove(hidden.id)
    del changed.cards[hidden.id]
    add(changed, 'Forest', 3-seat)
    alternate = AIAgent(difficulty='master', archetype=style).choose_action(
        changed, RULES.legal_moves(changed, seat), seat).action
    record('actual-ai', s, legal_moves=legal, action=action, hidden_variant_action=alternate, style=style)
    assert alternate == action
    assert action['type'] == 'cast_spell', 'Public immediate lethal alternative must not idle'
    result = checked_action(s, RULES, seat, action)
    assert serialize_match_snapshot(s) == before
    assert result.stack and result.stack[-1].source_card_id == action['card_id']
    assert sum(result.players[seat].mana_pool.values()) < sum(s.players[seat].mana_pool.values())
    result = settle(resume(result))
    assert result.cards[action['card_id']].zone in {Zone.GRAVEYARD, Zone.BATTLEFIELD}
    # This is a legality/progress contract, not an optimal-target policy test.
    following = ai.choose_action(result, RULES.legal_moves(result, seat), seat).action
    record('actual-ai-following', result, action=following, style=style)
    assert following.get('card_id') != action['card_id']
    checked_action(result, RULES, seat, following)
