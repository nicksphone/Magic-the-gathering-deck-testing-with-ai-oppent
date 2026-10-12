"""Real checked rules outcomes; explicit old boards/pools, no AI or D13 claim."""
import json
import pytest

from .test_full_vraska import (ROOT, RAW, STIFLE, ISLAND, add, bare, born, act, activate,
                              advance, settle, BEAR, Zone, Step, RulesEngine)
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import object_incarnation
from rules_engine.closed_loyalty import compile_body
from rules_engine.loyalty_instructions import timing
from rules_engine.targeting import stack_object_kind

FLICKER = json.loads((ROOT/'fixtures/flicker-of-fate.json').read_bytes())
ANGEL = json.loads((ROOT/'fixtures/platinum-angel.json').read_bytes())
DIVINATION = json.loads((ROOT/'fixtures/divination.json').read_bytes())
PLAINS = json.loads((ROOT/'fixtures/plains.json').read_bytes())


def damage_until_trigger(state, seat, attacker, target, key):
    state = advance(state, seat, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': [attacker],
                              'attack_targets': {attacker: target}})
    for _ in range(80):
        if state.stack and state.stack[-1].effect_key == key:
            assert stack_object_kind(state, state.stack[-1]) == 'triggered'
            return state
        assert state.winner is None
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Actual combat did not publish requested trigger')


def respond(state, seat, raw, targets, cost):
    spell = add(state, raw, seat, Zone.HAND)
    for _ in range(4):
        if state.priority_player == seat:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    # Phase changes consumed the initial pool. Declared old-board lands fund real responses.
    assert not any(state.players[seat].mana_pool.values())
    color, land_raw = ('U', ISLAND) if cost == 1 else ('W', PLAINS)
    for _ in range(cost):
        land = add(state, land_raw, seat, Zone.BATTLEFIELD, old_board=True)
        state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': land.id, 'color': color})
        assert state.cards[land.id].tapped
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    assert state.stack[-1].payload['mana_spent'] == cost
    return state


def ultimate(seat):
    state, walker, _ = born(seat)
    for expected in (6, 7):
        turn = state.turn
        state = settle(activate(state, seat, walker, 0))
        assert state.cards[walker].loyalty == expected
        state = advance(state, seat, Step.PRECOMBAT_MAIN, after_turn=turn)
    state = settle(activate(state, seat, walker, 2))
    assert state.cards[walker].zone == Zone.GRAVEYARD
    tokens = [c.id for c in state.cards.values() if c.is_token]
    assert len(tokens) == 3
    state = advance(state, seat, Step.DECLARE_ATTACKERS, after_turn=state.turn)
    return state, tokens[0]


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_stifle_counters_real_retaliation_trigger(seat):
    state, walker, creature = born(seat)
    state = settle(activate(state, seat, walker, 0))
    state = damage_until_trigger(state, 3-seat, creature, 'planeswalker:'+walker,
                                 'loyalty_combat_retaliation_destroy')
    trigger = state.stack[-1].id
    assert state.cards[walker].loyalty == 4
    state = respond(state, 3-seat, STIFLE, {'target_stack_id': trigger}, 1)
    state = settle(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[creature].zone == Zone.BATTLEFIELD
    assert state.cards[walker].loyalty == 4 and state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_flicker_invalidates_that_creature_reference_not_same_id_reentry(seat):
    state, walker, creature = born(seat)
    state = settle(activate(state, seat, walker, 0))
    state = damage_until_trigger(state, 3-seat, creature, 'planeswalker:'+walker,
                                 'loyalty_combat_retaliation_destroy')
    before = object_incarnation(state.cards[creature])
    state = respond(state, 3-seat, FLICKER, {'target_card_id': creature}, 2)
    state = settle(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[creature].zone == Zone.BATTLEFIELD
    assert object_incarnation(state.cards[creature]) != before
    assert state.cards[creature].owner == state.cards[creature].controller == 3-seat
    assert state.cards[walker].loyalty == 4 and state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keyword', ['indestructible', 'hexproof'])
def test_retaliation_is_destruction_but_not_targeting(seat, keyword):
    state, walker, creature = born(seat)
    # Controlled continuous-keyword boundary on the canonical old-board creature.
    from rules_engine.keyword_effects import add_keyword_effect
    add_keyword_effect(state, creature, [keyword])
    state = settle(activate(state, seat, walker, 0))
    state = damage_until_trigger(state, 3-seat, creature, 'planeswalker:'+walker,
                                 'loyalty_combat_retaliation_destroy')
    assert not state.stack[-1].payload.get('__trigger_target_choice')
    state = settle(state)
    assert state.cards[creature].zone == (Zone.BATTLEFIELD if keyword == 'indestructible' else Zone.GRAVEYARD)
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_loss_trigger_respects_canonical_cant_lose_then_later_combat_can_win(seat):
    state, token = ultimate(seat)
    angel = add(state, ANGEL, 3-seat, Zone.BATTLEFIELD, old_board=True)
    state = damage_until_trigger(state, seat, token, 'player:'+str(3-seat), 'player_loses_game')
    state = settle(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.winner is None and state.players[3-seat].life == 19
    # Controlled removal of the old-board prohibition; the next damage is real checked combat.
    from effects.registry import resolve_effect
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': angel.id})
    assert state.cards[angel.id].zone == Zone.GRAVEYARD
    state = advance(state, seat, Step.DECLARE_ATTACKERS, after_turn=state.turn)
    state = damage_until_trigger(state, seat, token, 'player:'+str(3-seat), 'player_loses_game')
    state = settle(state)
    assert state.winner == seat and state.players[3-seat].life == 18


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_stifle_counters_actual_token_loss_trigger(seat):
    state, token = ultimate(seat)
    state = damage_until_trigger(state, seat, token, 'player:'+str(3-seat), 'player_loses_game')
    trigger = state.stack[-1].id
    state = respond(state, 3-seat, STIFLE, {'target_stack_id': trigger}, 1)
    state = settle(state)
    assert state.winner is None and state.players[3-seat].life == 19
    assert state.cards[token].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_retaliation_does_not_grant_flash_and_old_flash_permission_still_does(seat):
    state, walker, _ = born(seat)
    sorcery = add(state, DIVINATION, seat, Zone.HAND)
    state = settle(activate(state, seat, walker, 0))
    state = advance(state, 3-seat, Step.PRECOMBAT_MAIN)
    assert timing(state, state.cards[sorcery.id], seat) == (True, False)
    assert not any(m.get('card_id') == sorcery.id for m in RulesEngine().legal_moves(state, seat))
    from effects.registry import resolve_effect
    resolve_effect(state, seat, 'loyalty_flash', {})
    assert timing(state, state.cards[sorcery.id], seat) == (True, True)


@pytest.mark.parametrize('suffix', [' Unaccounted tail.', '\nUnaccounted companion.', '; another instruction'])
@pytest.mark.parametrize('index', [0, 1, 2])
def test_full_card_unaccounted_clause_still_rejects_whole_surface(index, suffix):
    lines = RAW['oracle_text'].splitlines()
    lines[index] += suffix
    assert compile_body('\n'.join(lines), RAW['name']) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_loss_handler_preserves_terminal_winner_and_rejects_bool_player(seat):
    from effects.registry import resolve_effect
    state = bare(seat)
    before = serialize_match_snapshot(state)
    resolve_effect(state, seat, 'player_loses_game', {'target_player': True})
    assert serialize_match_snapshot(state) == before
    state.winner = 3-seat  # Explicit terminal-handler guard fixture, not a gameplay victory.
    resolve_effect(state, seat, 'player_loses_game', {'target_player': 3-seat})
    assert state.winner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keyword', ['indestructible', 'hexproof'])
def test_minus_three_keeps_real_target_legality_and_destruction_prohibition(seat, keyword):
    from rules_engine.keyword_effects import add_keyword_effect
    from rules_engine.action_validation import ActionRejected, checked_action
    state, walker, creature = born(seat)
    add_keyword_effect(state, creature, [keyword])
    if keyword == 'hexproof':
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, {'type': 'activate_loyalty',
                'card_id': walker, 'ability_index': 1, 'targets': {'target_card_id': creature}})
        assert serialize_match_snapshot(state) == before
    else:
        state = settle(activate(state, seat, walker, 1, {'target_card_id': creature}))
        assert state.cards[walker].loyalty == 2
    assert state.cards[creature].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_retaliation_old_source_permission_does_not_follow_reentered_walker(seat):
    from effects.registry import resolve_effect
    from .test_full_vraska import combat
    state, walker, creature = born(seat)
    state = settle(activate(state, seat, walker, 0))
    before = object_incarnation(state.cards[walker])
    # Explicit controlled blink effect seam, not an announced blink-spell episode.
    resolve_effect(state, seat, 'exile_return_immediate', {'target_card_id': walker,
        'return_control': 'owner', '__announced_reference': {
            'incarnation': before, 'zone_change_sequence': state.cards[walker].zone_change_sequence}})
    assert object_incarnation(state.cards[walker]) != before
    assert state.cards[walker].loyalty == 5
    state = combat(state, 3-seat, creature, 'planeswalker:'+walker)
    assert state.cards[creature].zone == Zone.BATTLEFIELD
    assert state.cards[walker].loyalty == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_simultaneous_retaliation_preserves_explicit_controller_order_selection(seat):
    state, walker, first = born(seat)
    second = add(state, BEAR, 3-seat, Zone.BATTLEFIELD, old_board=True).id
    state = settle(activate(state, seat, walker, 0))
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state = advance(state, 3-seat, Step.DECLARE_ATTACKERS)
    state = act(state, 3-seat, {'type': 'attack', 'attackers': [first, second],
        'attack_targets': {first: 'planeswalker:'+walker, second: 'planeswalker:'+walker}})
    for _ in range(80):
        if state.pending_trigger_order:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.pending_trigger_order['current_controller'] == seat
    group = state.pending_trigger_order['groups'][str(seat)]
    assert len(group) == 2 and {t['payload']['target_card_id'] for t in group} == {first, second}
    requested = [t['_choice_id'] for t in reversed(group)]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = act(state, seat, {'type': 'choose_trigger_order', 'trigger_order': requested})
    assert state.pending_trigger_order is None and len(state.stack) == 2
    state = settle(state)
    assert state.cards[first].zone == state.cards[second].zone == Zone.GRAVEYARD
    assert state.cards[walker].loyalty == 2
