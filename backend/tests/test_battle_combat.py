"""Battle combat with full printings and explicit native policy positions.

Factory births use the original complete printing readers. Initial zones,
counter totals, mixed types, direct effect packets and token blueprints are
declared core-policy inputs, not invented printings or paid histories. Paid
Lightning Bolt and priority-driven attack/block/damage cases exercise the
ordinary engine. Tests inspect only their own game and snapshot bodies.
"""
from collections import Counter
from copy import deepcopy

import pytest

from effects.handlers import deal_damage, deal_damage_batch, grant_keyword, prevent_damage
from effects.registry import resolve_effect
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.battles import ensure_protectors
from rules_engine.combat import declare_attackers, _deal_unblocked_damage
from rules_engine.control_effects import transfer_controller
from rules_engine.copiable_values import apply, values
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.type_effects import add_type_effect, effective_types
from tests.test_battle_entry import BATTLE, place
from tests.test_battle_transformed_cast import row as original_row
from tests.test_battle_characteristics import mark


def row(name, count):
    if name == 'Soul-Scar Mage':
        from tests.pending_source_privacy_support import ROWS
        raw = deepcopy(ROWS[name])
    else:
        raw = original_row(name, count)
    full = (raw.get('object') == 'card' and len(raw) >= 50
            and all(raw.get(k) for k in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'layout')))
    if not full: mark('Task5-original-reader-not-a-full-printing')
    assert full
    return {**raw, 'card_name': name, 'quantity': count}


def position(seat, extra=()):
    counts = Counter((BATTLE, BATTLE, 'Grizzly Bears', 'Grizzly Bears', 'Grizzly Bears', *extra))
    counts['Forest'] += 60-sum(counts.values())
    deck = [row(name, count) for name, count in counts.items()]
    state = MatchFactory.from_decks(deck, deck, seed=71203)
    state.pregame_pending = False; state.kept_hands = {1, 2}; state.turn = 5
    state.active_player = state.priority_player = seat; state.step = Step.DECLARE_ATTACKERS
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY); player.library.append(cid)
        player.hand.clear(); player.mana_pool = {}
        player.lands_played_this_turn = player.land_plays_recorded_on_turn = 1
        player.last_land_play_turn = state.turn
    for _ in range(6): place(state, seat, 'Forest', Zone.BATTLEFIELD)
    battle = place(state, seat, BATTLE, Zone.BATTLEFIELD)
    state.cards[battle].counters['defense'] = 3; state.cards[battle].battle_protector = 3-seat
    attacker = place(state, seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    return state, battle, attacker


def cold(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def act(state, player, action):
    return checked_action(state, RulesEngine(), player, action)


def offer(state, seat):
    return next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'attack')


def attack(state, seat, attacker, target):
    return act(state, seat, {'type': 'attack', 'attackers': [attacker],
                            'attack_targets': {attacker: target}})


def reach(state, step):
    for _ in range(8):
        if state.step == step: return state
        assert not state.stack and not state.pending_mechanic_choice and not state.pending_replacement_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Combat did not reach the declared step')


def blocks(state, seat, assignments=None):
    state = reach(state, Step.DECLARE_BLOCKERS)
    if not state.attackers:
        assert not assignments
        return state
    if state.priority_player == seat:
        state = act(state, seat, {'type': 'pass_priority'})
    return act(state, 3-seat, {'type': 'block', 'blocks': assignments or {}})


def damage(state, seat, assignments=None):
    return reach(blocks(state, seat, assignments), Step.COMBAT_DAMAGE)


def keyword(state, seat, cid, *names):
    grant_keyword(state, seat, {'target_card_id': cid, 'keywords': list(names)})


def counters(state, cid, kind, amount):
    from rules_engine.counter_placement import put_counters
    put_counters(state, kind, amount, target_card_id=cid)


def mixed(state, seat, *, planeswalker=False):
    cid = place(state, seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    add_type_effect(state, cid, ['Battle', *(['Planeswalker'] if planeswalker else [])])
    state.cards[cid].counters['defense'] = 3
    state.cards[cid].battle_protector = seat
    if planeswalker: state.cards[cid].loyalty = 7
    return cid


def reject(state, seat, action):
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): act(state, seat, action)
    assert serialize_match_snapshot(state) == before


def assert_life(state):
    assert state.players[1].life == state.players[2].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_own_siege_is_a_legal_native_attack_destination(seat):
    state, battle, attacker = position(seat)
    mark('Task5-own-Siege-legal-destination-assertion-reached')
    target = 'battle:' + battle
    assert target in {d['id'] for d in offer(state, seat)['defenders']}
    state = attack(state, seat, attacker, target)
    assert state.attack_targets[attacker] == target and state.cards[attacker].tapped
    assert state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_opposing_non_siege_is_attackable_using_its_protector(seat):
    state, _, attacker = position(seat)
    battle = mixed(state, 3-seat)
    counters(state, battle, '+1/+1', 1)
    assert state.cards[battle].controller == state.cards[battle].battle_protector == 3-seat
    assert 'battle:' + battle in {d['id'] for d in offer(state, seat)['defenders']}
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat)
    assert state.cards[battle].counters['defense'] == 1
    assert state.cards[battle].counters['__damage_marked'] == 2
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_protector_cannot_attack_the_battle(seat):
    state, battle, attacker = position(seat)
    transfer_controller(state, state.cards[battle], 3-seat)
    state.cards[battle].battle_protector = seat
    assert 'battle:' + battle not in {d['id'] for d in offer(state, seat)['defenders']}
    reject(state, seat, {'type': 'attack', 'attackers': [attacker],
                        'attack_targets': {attacker: 'battle:' + battle}})


@pytest.mark.parametrize('seat', [1, 2])
def test_invalid_destination_rejects_before_native_taps_and_payments(seat):
    state, battle, attacker = position(seat)
    before = serialize_match_snapshot(state)
    for target in ('battle:absent', 'battle:' + attacker, 'unknown:' + battle, 'player:' + str(seat)):
        with pytest.raises(ValueError): declare_attackers(state, [attacker], {attacker: target})
        assert serialize_match_snapshot(state) == before
        reject(state, seat, {'type': 'attack', 'attackers': [attacker], 'attack_targets': {attacker: target}})
    assert not state.cards[attacker].tapped and all(not state.cards[c].tapped for c in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
def test_only_protector_creatures_can_block_for_own_siege(seat):
    state, battle, attacker = position(seat)
    own = place(state, seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    protector = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    state = reach(attack(state, seat, attacker, 'battle:' + battle), Step.DECLARE_BLOCKERS)
    if state.priority_player == seat: state = act(state, seat, {'type': 'pass_priority'})
    block = next(m for m in RulesEngine().legal_moves(state, 3-seat) if m['type'] == 'block')
    assert protector in {b['id'] for b in block['blockers']} and own not in {b['id'] for b in block['blockers']}
    reject(state, 3-seat, {'type': 'block', 'blocks': {attacker: [own]}})
    state = act(state, 3-seat, {'type': 'block', 'blocks': {attacker: [protector]}})
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters['defense'] == 3
    assert state.cards[attacker].zone == state.cards[protector].zone == Zone.GRAVEYARD
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_unblocked_damage_removes_defense_without_player_damage(seat):
    state, battle, attacker = position(seat)
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat)
    assert state.cards[battle].counters['defense'] == 1
    assert not state.stack and state.cards[battle].zone == Zone.BATTLEFIELD
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_trample_remainder_hits_battle_after_blocker_lethal(seat):
    state, battle, attacker = position(seat)
    counters(state, attacker, '+1/+1', 2)
    keyword(state, seat, attacker, 'trample')
    blocker = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat, {attacker: [blocker]})
    assert state.cards[blocker].zone == Zone.GRAVEYARD
    assert state.cards[battle].counters['defense'] == 1
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_double_strike_defeats_once_across_snapshot_priority_window(seat):
    state, battle, attacker = position(seat)
    keyword(state, seat, attacker, 'double strike')
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat)
    assert state.combat_damage_stage == 'first' and state.cards[battle].counters['defense'] == 1
    state = cold(state)
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.combat_damage_stage == 'regular' and state.cards[battle].counters.get('defense', 0) == 0
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_trample_over_planeswalkers_does_not_overflow_battle_to_player(seat):
    state, battle, attacker = position(seat)
    keyword(state, seat, attacker, 'trample', 'trample over planeswalkers', 'lifelink')
    counters(state, attacker, '+1/+1', 3)
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat)
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.players[seat].life == 25 and state.players[3-seat].life == 20
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_combat_prevention_applies_before_defense_and_lifelink(seat):
    state, battle, attacker = position(seat)
    keyword(state, seat, attacker, 'lifelink')
    prevent_damage(state, seat, {'target_card_id': battle, 'amount': 1})
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat)
    assert state.cards[battle].counters['defense'] == 2
    assert state.players[seat].life == 21 and state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_fully_prevented_battle_combat_has_no_damage_consequences(seat):
    state, battle, attacker = position(seat)
    keyword(state, seat, attacker, 'lifelink')
    prevent_damage(state, seat, {'target_card_id': battle, 'amount': 2})
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat)
    assert state.cards[battle].counters['defense'] == 3 and not state.stack
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_lightning_bolt_targets_battle_and_causes_native_defeat(seat):
    state, battle, _ = position(seat, ('Lightning Bolt', 'Mountain'))
    state.step = Step.PRECOMBAT_MAIN
    mountain = place(state, seat, 'Mountain', Zone.BATTLEFIELD)
    bolt = place(state, seat, 'Lightning Bolt', Zone.HAND)
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id') == bolt and m['type'] == 'cast_spell')
    assert battle in {r['id'] for key, rows in move['target_hints'].items()
                      if key.endswith('_targets') and isinstance(rows, list)
                      for r in rows if isinstance(r, dict)}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': bolt, 'targets': {'target_card_id': battle}})
    assert state.cards[bolt].zone == Zone.STACK and state.cards[mountain].tapped
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert resolve_top_of_stack(state)
    assert state.cards[battle].counters.get('defense', 0) == 0 and state.cards[bolt].zone == Zone.GRAVEYARD
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_prevented_bolt_applies_all_three_permanent_consequences_once(seat):
    state, _, _ = position(seat, ('Lightning Bolt', 'Mountain'))
    target = mixed(state, 3-seat, planeswalker=True)
    state.step = Step.PRECOMBAT_MAIN
    mountain = place(state, seat, 'Mountain', Zone.BATTLEFIELD)
    bolt = place(state, seat, 'Lightning Bolt', Zone.HAND)
    prevent_damage(state, 3-seat, {'target_card_id': target, 'amount': 2})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': bolt, 'targets': {'target_card_id': target}})
    assert state.cards[mountain].tapped and state.cards[bolt].zone == Zone.STACK
    assert resolve_top_of_stack(state)
    card = state.cards[target]
    assert card.zone == Zone.BATTLEFIELD and card.counters['__damage_marked'] == 1
    assert card.counters['defense'] == 2 and card.loyalty == 6
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_infect_creature_battle_planeswalker_gets_every_actual_damage_result(seat):
    state, _, source = position(seat)
    target = mixed(state, 3-seat, planeswalker=True)
    keyword(state, seat, source, 'infect', 'lifelink')
    assert deal_damage(state, seat, {'target_card_id': target, 'amount': 1, '__source_card_id': source}) == 1
    card = state.cards[target]
    assert card.counters['-1/-1'] == 1 and not card.counters.get('__damage_marked', 0)
    assert card.counters['defense'] == 2 and card.loyalty == 6
    assert state.players[seat].life == 21 and state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_wither_creature_battle_planeswalker_gets_every_actual_damage_result(seat):
    state, _, source = position(seat)
    target = mixed(state, 3-seat, planeswalker=True)
    keyword(state, seat, source, 'wither')
    assert deal_damage(state, seat, {'target_card_id': target, 'amount': 1, '__source_card_id': source}) == 1
    card = state.cards[target]
    assert card.counters['-1/-1'] == 1 and not card.counters.get('__damage_marked', 0)
    assert card.counters['defense'] == 2 and card.loyalty == 6
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_infect_to_pure_battle_still_removes_defense(seat):
    state, battle, source = position(seat)
    keyword(state, seat, source, 'infect')
    assert deal_damage(state, seat, {'target_card_id': battle, 'amount': 1, '__source_card_id': source}) == 1
    assert state.cards[battle].counters['defense'] == 2
    assert not state.cards[battle].counters.get('-1/-1', 0)
    assert state.players[1].poison == state.players[2].poison == 0
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_soul_scar_replacement_has_no_defense_loyalty_or_lifelink_result(seat):
    state, _, source = position(seat, ('Soul-Scar Mage',))
    place(state, seat, 'Soul-Scar Mage', Zone.BATTLEFIELD)
    target = mixed(state, 3-seat, planeswalker=True)
    keyword(state, seat, source, 'lifelink')
    assert deal_damage(state, seat, {'target_card_id': target, 'amount': 1, '__source_card_id': source}) == 0
    card = state.cards[target]
    assert card.counters['-1/-1'] == 1 and not card.counters.get('__damage_marked', 0)
    assert card.counters['defense'] == 3 and card.loyalty == 7
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_soul_scar_does_not_replace_damage_to_pure_battle(seat):
    state, battle, source = position(seat, ('Soul-Scar Mage',))
    place(state, seat, 'Soul-Scar Mage', Zone.BATTLEFIELD)
    assert deal_damage(state, seat, {'target_card_id': battle, 'amount': 1, '__source_card_id': source}) == 1
    assert state.cards[battle].counters['defense'] == 2
    assert not state.cards[battle].counters.get('-1/-1', 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_damage_above_defense_is_not_capped_for_lifelink(seat):
    state, battle, source = position(seat)
    keyword(state, seat, source, 'lifelink')
    assert deal_damage(state, seat, {'target_card_id': battle, 'amount': 5, '__source_card_id': source}) == 5
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.players[seat].life == 25 and state.players[3-seat].life == 20
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_batch_applies_both_battle_results_before_state_based_departure(seat):
    state, battle, source = position(seat)
    other = mixed(state, 3-seat)
    keyword(state, seat, source, 'lifelink')
    deal_damage_batch(state, seat, {'__source_card_id': source, 'recipients': [
        {'target_card_id': battle, 'amount': 3}, {'target_card_id': other, 'amount': 3}]})
    assert state.cards[battle].counters.get('defense', 0) == state.cards[other].counters.get('defense', 0) == 0
    assert state.cards[other].zone == Zone.BATTLEFIELD and state.cards[other].counters['__damage_marked'] == 3
    assert state.players[seat].life == 26 and state.players[3-seat].life == 20
    apply_state_based_actions(state)
    assert state.cards[other].zone == Zone.GRAVEYARD
    assert state.cards[battle].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_controller_change_invalidates_battle_target_without_player_fallback(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    transfer_controller(state, state.cards[battle], 3-seat)
    state = damage(cold(state), seat)
    assert attacker in state.attackers and state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_controller_away_and_back_does_not_rejoin_combat(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    transfer_controller(state, state.cards[battle], 3-seat); transfer_controller(state, state.cards[battle], seat)
    state = damage(cold(state), seat)
    assert state.cards[battle].counters['defense'] == 3 and attacker in state.attackers
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_protector_change_invalidates_target_across_snapshot(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    # Declared core-policy protector transition, with the normal SBA boundary.
    state.cards[battle].battle_protector = seat
    apply_state_based_actions(state)
    state = damage(cold(state), seat)
    assert state.cards[battle].counters['defense'] == 3 and attacker in state.attackers
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_native_exile_invalidates_target_without_player_redirection(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    resolve_effect(state, seat, 'exile', {'target_card_id': battle})
    state = damage(cold(state), seat)
    assert state.cards[battle].zone == Zone.EXILE and attacker in state.attackers
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_native_blink_does_not_rebind_attack_to_new_incarnation(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    card = state.cards[battle]
    previous = object_incarnation(card)
    resolve_effect(state, seat, 'exile_return_immediate', {'target_card_id': battle,
        '__announced_reference': {'incarnation': previous, 'zone_change_sequence': card.zone_change_sequence},
        'return_control': 'owner'})
    assert state.cards[battle].zone == Zone.BATTLEFIELD and object_incarnation(state.cards[battle]) != previous
    # The genuine ETB may search; resolve its real native trigger before combat.
    while state.stack: assert resolve_top_of_stack(state)
    state = damage(cold(state), seat)
    assert state.cards[battle].counters['defense'] == 3 and attacker in state.attackers
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_losing_battle_type_removes_target_without_default_player(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    forest = next(state.cards[c] for c in state.players[seat].battlefield if state.cards[c].name == 'Forest')
    apply(state.cards[battle], values(forest))
    apply_state_based_actions(state)
    state = damage(cold(state), seat)
    assert attacker in state.attackers and state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_type_loss_and_restoration_does_not_reenter_combat(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    saved = values(state.cards[battle])
    forest = next(state.cards[c] for c in state.players[seat].battlefield if state.cards[c].name == 'Forest')
    apply(state.cards[battle], values(forest)); apply_state_based_actions(state)
    apply(state.cards[battle], saved); apply_state_based_actions(state)
    state = damage(cold(state), seat)
    assert state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_mixed_battle_losing_battle_remains_attacked_as_pw_if_controller_is_protector(seat):
    state, _, attacker = position(seat)
    target = place(state, 3-seat, BATTLE, Zone.BATTLEFIELD)
    state.cards[target].type_line = 'Battle'
    state.cards[target].counters['defense'] = 3
    state.cards[target].battle_protector = 3-seat
    add_type_effect(state, target, ['Planeswalker']); state.cards[target].loyalty = 7
    state = attack(state, seat, attacker, 'battle:' + target)
    forest = next(state.cards[c] for c in state.players[seat].battlefield if state.cards[c].name == 'Forest')
    # Copy changes layer one; the later native PW addition remains.
    card = state.cards[target]
    apply(card, values(forest))
    assert card.controller == card.battle_protector == 3-seat
    apply_state_based_actions(state)
    state = damage(cold(state), seat)
    assert state.cards[target].loyalty == 5 and state.cards[target].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_mixed_battle_losing_battle_is_removed_when_controller_is_not_protector(seat):
    state, target, attacker = position(seat)
    add_type_effect(state, target, ['Planeswalker']); state.cards[target].loyalty = 7
    state = attack(state, seat, attacker, 'battle:' + target)
    forest = next(state.cards[c] for c in state.players[seat].battlefield if state.cards[c].name == 'Forest')
    apply(state.cards[target], values(forest))
    apply_state_based_actions(state)
    state = damage(cold(state), seat)
    assert state.cards[target].loyalty == 7 and state.cards[target].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_mixed_pw_losing_pw_stays_attacked_as_battle(seat):
    state, target, attacker = position(seat)
    add_type_effect(state, target, ['Planeswalker']); state.cards[target].loyalty = 7
    transfer_controller(state, state.cards[target], 3-seat)
    # Opponent controller/protector coincide in a declared non-Siege position.
    state.cards[target].type_line = 'Battle'
    state.cards[target].battle_protector = 3-seat
    state = attack(state, seat, attacker, 'planeswalker:' + target)
    from rules_engine.type_effects import clear_type_effects
    clear_type_effects(state.cards[target]); apply_state_based_actions(state)
    state = damage(cold(state), seat)
    assert state.cards[target].counters['defense'] == 1 and state.cards[target].loyalty == 7
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_siege_subtype_loss_defers_illegal_protector_repair_while_attacked(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    state.cards[battle].type_line = 'Battle'
    ensure_protectors(state)
    assert state.cards[battle].battle_protector == 3-seat
    state = damage(cold(state), seat)
    assert state.cards[battle].counters['defense'] == 1
    state = reach(state, Step.END_COMBAT)
    state = reach(state, Step.POSTCOMBAT_MAIN)
    ensure_protectors(state)
    assert state.cards[battle].battle_protector == seat
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_protector_is_repaired_after_attack_is_removed(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    state.cards[battle].battle_protector = None
    apply_state_based_actions(state)
    assert state.cards[battle].battle_protector == 3-seat
    state = damage(cold(state), seat)
    assert state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_battle_creature_cannot_be_declared_attacking(seat):
    state, battle, attacker = position(seat)
    add_type_effect(state, attacker, ['Battle'])
    state.cards[attacker].counters['defense'] = 3; state.cards[attacker].battle_protector = seat
    moves = RulesEngine().legal_moves(state, seat)
    assert all(attacker not in m.get('options', []) for m in moves if m['type'] == 'attack')
    reject(state, seat, {'type': 'attack', 'attackers': [attacker],
                        'attack_targets': {attacker: 'player:' + str(3-seat)}})


@pytest.mark.parametrize('seat', [1, 2])
def test_battle_creature_cannot_be_declared_blocking(seat):
    state, battle, attacker = position(seat)
    blocker = mixed(state, 3-seat)
    state = reach(attack(state, seat, attacker, 'battle:' + battle), Step.DECLARE_BLOCKERS)
    if state.priority_player == seat: state = act(state, seat, {'type': 'pass_priority'})
    move = next(m for m in RulesEngine().legal_moves(state, 3-seat) if m['type'] == 'block')
    assert blocker not in {b['id'] for b in move['blockers']}
    reject(state, 3-seat, {'type': 'block', 'blocks': {attacker: [blocker]}})


@pytest.mark.parametrize('seat', [1, 2])
def test_attacker_becoming_battle_is_removed_and_cannot_rejoin(seat):
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    add_type_effect(state, attacker, ['Battle'])
    state.cards[attacker].counters['defense'] = 3; state.cards[attacker].battle_protector = seat
    apply_state_based_actions(state)
    from rules_engine.type_effects import clear_type_effects
    clear_type_effects(state.cards[attacker]); apply_state_based_actions(state)
    state = damage(cold(state), seat)
    assert attacker not in state.attackers and state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_blocker_becoming_battle_is_removed_but_attacker_stays_blocked(seat):
    state, battle, attacker = position(seat)
    blocker = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    state = blocks(attack(state, seat, attacker, 'battle:' + battle), seat, {attacker: [blocker]})
    add_type_effect(state, blocker, ['Battle'])
    state.cards[blocker].counters['defense'] = 3; state.cards[blocker].battle_protector = 3-seat
    apply_state_based_actions(state)
    state = reach(cold(state), Step.COMBAT_DAMAGE)
    assert state.blocks[attacker] == [] and state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_native_battle_creature_token_does_not_enter_attacking(seat):
    state, _, _ = position(seat)
    before = set(state.cards)
    resolve_effect(state, seat, 'create_token', {'name': 'Declared policy Battle creature',
        'types': ['Battle', 'Creature'], 'type_line': 'Battle Creature',
        'printed_defense': '3', 'power': 2, 'toughness': 2,
        'tapped_and_attacking': True, 'attack_target': 'player:' + str(3-seat)})
    token = next(cid for cid in state.cards if cid not in before)
    assert state.cards[token].zone == Zone.BATTLEFIELD and state.cards[token].counters['defense'] == 3
    assert token not in state.attackers and token not in state.attack_targets


@pytest.mark.parametrize('seat', [1, 2])
def test_native_ordinary_creature_token_can_enter_attacking_battle(seat):
    state, battle, _ = position(seat)
    before = set(state.cards)
    resolve_effect(state, seat, 'create_token', {'name': 'Declared policy creature',
        'types': ['Creature'], 'power': 1, 'toughness': 1,
        'tapped_and_attacking': True, 'attack_target': 'battle:' + battle})
    token = next(cid for cid in state.cards if cid not in before)
    assert token in state.attackers and state.attack_targets[token] == 'battle:' + battle
    state.attackers_declared = True
    state = damage(cold(state), seat)
    assert state.cards[battle].counters['defense'] == 2
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_damage_destination_never_falls_back_to_player_two(seat):
    state, battle, source = position(seat)
    for target in ('unknown:' + battle, 'battle:absent', 'player:absent', ''):
        assert _deal_unblocked_damage(state, target, 2, source) == 0
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_invalidated_target_does_not_damage_again_in_second_strike(seat):
    state, battle, attacker = position(seat)
    keyword(state, seat, attacker, 'double strike')
    state = damage(attack(state, seat, attacker, 'battle:' + battle), seat)
    assert state.cards[battle].counters['defense'] == 1
    transfer_controller(state, state.cards[battle], 3-seat); transfer_controller(state, state.cards[battle], seat)
    state = cold(state)
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.cards[battle].counters['defense'] == 1 and not state.stack
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_combat_applies_creature_battle_and_pw_consequences_to_one_recipient(seat):
    state, _, attacker = position(seat)
    target = mixed(state, 3-seat, planeswalker=True)
    prevent_damage(state, 3-seat, {'target_card_id': target, 'amount': 1})
    state = damage(attack(state, seat, attacker, 'battle:' + target), seat)
    card = state.cards[target]
    assert card.zone == Zone.BATTLEFIELD and card.counters['__damage_marked'] == 1
    assert card.counters['defense'] == 2 and card.loyalty == 6
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_targetless_trample_assigns_all_damage_to_remaining_blocker(seat):
    state, battle, attacker = position(seat)
    blocker = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    counters(state, attacker, '+1/+1', 2)
    keyword(state, seat, attacker, 'trample')
    prevent_damage(state, 3-seat, {'target_card_id': blocker, 'amount': 2})
    state = blocks(attack(state, seat, attacker, 'battle:' + battle), seat, {attacker: [blocker]})
    transfer_controller(state, state.cards[battle], 3-seat)
    state = reach(cold(state), Step.COMBAT_DAMAGE)
    mark('Task5-targetless-trample-remaining-blocker-assertion-reached')
    assert state.cards[blocker].zone == Zone.GRAVEYARD
    assert state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_targetless_trample_choice_has_only_live_blocking_recipients(seat):
    state, battle, attacker = position(seat)
    blockers = [place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD) for _ in range(2)]
    counters(state, attacker, '+1/+1', 2)
    keyword(state, seat, attacker, 'trample')
    state.mechanic_choice_players = {seat}
    state = blocks(attack(state, seat, attacker, 'battle:' + battle), seat, {attacker: blockers})
    transfer_controller(state, state.cards[battle], 3-seat)
    state = reach(cold(state), Step.COMBAT_DAMAGE)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'combat_damage' and set(pending['options']) == set(blockers)
    state = act(cold(state), seat, {'type': 'choose_mechanic',
        'damage_assignment': {blockers[0]: 4, blockers[1]: 0}})
    assert state.cards[blockers[0]].zone == Zone.GRAVEYARD
    assert state.cards[blockers[1]].zone == Zone.BATTLEFIELD
    assert state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_battle_combat_identity_is_internal_and_unbound_resume_cannot_retarget(seat):
    from game_state.serializers import serialize_match
    state, battle, attacker = position(seat)
    state = attack(state, seat, attacker, 'battle:' + battle)
    public = serialize_match(state)
    assert public['attack_targets'][attacker] == 'battle:' + battle
    assert 'combat_target_context' not in public
    snapshot = serialize_match_snapshot(state)
    malformed = deepcopy(snapshot)
    malformed['combat_target_context'][attacker]['incarnation'] = True
    with pytest.raises(ValueError): deserialize_match_snapshot(malformed)
    snapshot.pop('combat_target_context')
    state = damage(deserialize_match_snapshot(snapshot), seat)
    assert state.cards[battle].counters['defense'] == 3 and attacker in state.attackers
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_combat_context_preserves_ordinary_bounded_inventory(seat):
    from ai.information import decision_view
    from tests.test_numeric_inventory_adapter import positive, pure_inventory
    state = positive(seat)
    before = serialize_match_snapshot(state)
    assert 'combat_target_context' not in before
    expected = pure_inventory(state, seat)
    mark('Task5-ordinary-inventory-schema-assertion-reached')
    assert expected['status'] == 'inert'
    view, _ = decision_view(deserialize_match_snapshot(before), seat, [])
    assert pure_inventory(view, seat) == expected
    # Declared unsupported metadata must remain outside the bounded proof.
    view.combat_target_context = {'unreviewed': {}}
    assert pure_inventory(view, seat)['status'] == 'unknown'
    view.combat_target_context = []
    assert pure_inventory(view, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_battle_combat_damage_event_identifies_actual_permanent_recipient(seat):
    from rules_engine.combat import _combat_damage_results
    state, battle, attacker = position(seat)
    state = blocks(attack(state, seat, attacker, 'battle:' + battle), seat)
    prevent_damage(state, seat, {'target_card_id': battle, 'amount': 1})
    events, _ = _combat_damage_results(cold(state), 3-seat, set(), False)
    assert len(events) == 1
    event = events[0]
    assert event['source_card_id'] == attacker and event['target_card_id'] == battle
    assert event['target_key'] == 'battle:' + battle and event.get('target_player') is None
    assert event['amount'] == 1
