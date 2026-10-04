"""Canonical interaction positions, not tournament decks or full-card certification.

Aggro: burn / green counters; control: prevention / layers / recursion / counters.
All spell announcements and priority passes use the production checked action path.
"""
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_power, effective_toughness

CARDS = {r['card']['name']: r['card'] for r in json.loads(
    (Path(__file__).parents[1] / 'fixtures/regression_agent/cards.json').read_text())}


def position(seat):
    raw = CARDS['Island']
    deck = [dict(raw, quantity=60, card_name=raw['name'])]
    state = MatchFactory.from_decks(deck, deck, seed=20261004)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for p in state.players.values():
        p.mana_pool = dict(W=20, U=20, B=20, R=20, G=20, C=20)
    return state


def add(state, name, seat, zone=Zone.HAND, owner=None):
    raw = CARDS[name]
    card = CardInstance(
        id=state.allocate_object_id(), name=name, owner=seat if owner is None else owner,
        controller=seat, zone=zone,
        types=[t for t in ['Land', 'Creature', 'Artifact', 'Enchantment', 'Instant', 'Sorcery']
               if t in raw['type_line'].split(' — ')[0].split()],
        type_line=raw['type_line'], mana_cost=raw['mana_cost'], oracle_text=raw['oracle_text'],
        colors=raw['colors'], keywords=raw['keywords'],
        power=int(raw['power']) if raw.get('power') else None,
        toughness=int(raw['toughness']) if raw.get('toughness') else None,
    )
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False
    return card.id


def action(state, seat, **move):
    return checked_action(state, RulesEngine(), seat, move)


def cast(state, card_id, **targets):
    return action(state, state.cards[card_id].controller, type='cast_spell', card_id=card_id, targets=targets)


def pass_once(state):
    return action(state, state.priority_player, type='pass_priority')


def restore(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def settle(state):
    for _ in range(40):
        if not state.stack:
            return state
        assert not state.pending_mechanic_choice, state.pending_mechanic_choice
        assert not state.pending_replacement_choice, state.pending_replacement_choice
        state = pass_once(state)
    raise AssertionError('stack failed to settle in 40 legal priority passes')


@pytest.mark.parametrize('seat', [1, 2])
def test_skullcrack_disables_prevention_before_its_own_damage(seat):
    state = position(seat)
    # A pre-existing rules-level shield isolates instruction ordering, not Salve parsing.
    state.players[3-seat].prevent_damage_shield = 3
    spell = add(state, 'Skullcrack', seat)
    before = sum(state.players[seat].mana_pool.values())
    state = cast(state, spell, target_player=3-seat)
    assert sum(state.players[seat].mana_pool.values()) == before - 2
    state = settle(restore(state))
    assert state.players[3-seat].life == 17
    assert state.players[3-seat].prevent_damage_shield == 3
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_two_furnaces_replace_bolt_each_once(seat):
    state = position(seat)
    add(state, 'Furnace of Rath', seat, Zone.BATTLEFIELD)
    add(state, 'Furnace of Rath', 3-seat, Zone.BATTLEFIELD)
    spell = add(state, 'Lightning Bolt', seat)
    state = settle(restore(cast(state, spell, target_player=3-seat)))
    assert state.players[3-seat].life == 8
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_humility_anthem_counter_pump_and_source_departure(seat):
    state = position(seat)
    bear = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    state.cards[bear].counters['+1/+1'] = 1
    anthem = add(state, 'Glorious Anthem', seat, Zone.BATTLEFIELD)
    add(state, 'Humility', 3-seat, Zone.BATTLEFIELD)
    pump = add(state, 'Giant Growth', seat)
    remove = add(state, 'Disenchant', seat)
    state = settle(cast(state, pump, target_card_id=bear))
    assert (effective_power(state, bear), effective_toughness(state, bear)) == (6, 6)
    state = settle(restore(cast(state, remove, target_card_id=anthem)))
    assert (effective_power(state, bear), effective_toughness(state, bear)) == (5, 5)
    assert state.cards[anthem].zone == Zone.GRAVEYARD
    assert (state.cards[bear].power, state.cards[bear].toughness) == (2, 2)
    # Continue from an explicitly declared, unblocked combat position.
    state.step = Step.DECLARE_BLOCKERS
    state.blockers_declared = True
    state.attackers = [bear]
    state.attack_targets = {bear: f'player:{3-seat}'}
    state = pass_once(pass_once(restore(state)))
    assert state.step == Step.COMBAT_DAMAGE
    assert state.players[3-seat].life == 15


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('rip', [False, True], ids=['dies', 'exile-replacement'])
def test_stolen_undying_returns_only_after_actual_death(seat, rip):
    state = position(seat)
    wolf = add(state, 'Young Wolf', 3-seat, Zone.BATTLEFIELD, owner=seat)
    if rip:
        add(state, 'Rest in Peace', seat, Zone.BATTLEFIELD)
    kill = add(state, 'Doom Blade', seat)
    state = settle(restore(cast(state, kill, target_card_id=wolf)))
    card = state.cards[wolf]
    if rip:
        assert card.zone == Zone.EXILE
        assert wolf in state.players[seat].exile
        assert not state.stack
    else:
        assert card.zone == Zone.BATTLEFIELD
        assert card.controller == seat
        assert wolf in state.players[seat].battlefield
        assert card.counters.get('+1/+1') == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_reanimate_enemy_graveyard_preserves_owner_and_loses_life(seat):
    state = position(seat)
    bear = add(state, 'Grizzly Bears', 3-seat, Zone.GRAVEYARD)
    spell = add(state, 'Reanimate', seat)
    state = settle(restore(cast(state, spell, target_card_id=bear)))
    assert state.cards[bear].zone == Zone.BATTLEFIELD
    assert state.cards[bear].controller == seat
    assert state.cards[bear].owner == 3-seat
    assert state.players[seat].life == 18
    assert bear not in state.players[3-seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Grizzly Bears', 'Allosaurus Shepherd'], ids=['counterable', 'uncounterable'])
@pytest.mark.parametrize('check', ['draw', 'destination'])
def test_remand_response_preserves_conditional_destination_and_draw(seat, name, check):
    state = position(seat)
    threat = add(state, name, seat)
    remand = add(state, 'Remand', 3-seat)
    state = cast(state, threat)
    target = state.stack[-1].id
    state = pass_once(state)
    assert state.priority_player == 3-seat
    hand_before = len(state.players[3-seat].hand)
    mana_before = sum(state.players[3-seat].mana_pool.values())
    state = cast(state, remand, target_stack_id=target)
    assert sum(state.players[3-seat].mana_pool.values()) == mana_before - 2
    state = restore(state)
    state = pass_once(pass_once(state))
    assert state.cards[remand].zone == Zone.GRAVEYARD
    if check == 'draw':
        assert len(state.players[3-seat].hand) == hand_before  # Remand spent, one drawn.
        return
    if name == 'Grizzly Bears':
        assert state.cards[threat].zone == Zone.HAND
        assert threat in state.players[seat].hand
        assert not state.stack
    else:
        assert state.cards[threat].zone == Zone.STACK
        assert len(state.stack) == 1
        state = settle(state)
        assert state.cards[threat].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_bounce_and_recast_do_not_reuse_pump_or_counters(seat):
    state = position(seat)
    bear = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    state.cards[bear].counters['+1/+1'] = 1
    pump = add(state, 'Giant Growth', seat)
    bounce = add(state, 'Unsummon', seat)
    state = settle(cast(state, pump, target_card_id=bear))
    assert effective_power(state, bear) == 6
    state = settle(cast(state, bounce, target_card_id=bear))
    assert state.cards[bear].zone == Zone.HAND
    state = settle(cast(restore(state), bear))
    assert state.cards[bear].zone == Zone.BATTLEFIELD
    assert state.cards[bear].counters == {}
    assert (effective_power(state, bear), effective_toughness(state, bear)) == (2, 2)
    assert state.cards[bear].summoning_sick


@pytest.mark.parametrize('seat', [1, 2])
def test_response_without_priority_is_atomic(seat):
    state = position(seat)
    threat = add(state, 'Grizzly Bears', seat)
    remand = add(state, 'Remand', 3-seat)
    state = cast(state, threat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, remand, target_stack_id=state.stack[-1].id)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_flashback_countered_after_restore_exiles_without_draw_or_refund(seat):
    state = position(seat)
    spell = add(state, 'Think Twice', seat, Zone.GRAVEYARD)
    counter = add(state, 'Counterspell', 3-seat)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m.get('card_id') == spell and m['type'] == 'cast_spell')
    mana_before = sum(state.players[seat].mana_pool.values())
    hand_before = len(state.players[seat].hand)
    state = checked_action(state, RulesEngine(), seat, move)
    assert sum(state.players[seat].mana_pool.values()) == mana_before - 3
    target = state.stack[-1].id
    state = pass_once(state)
    state = settle(restore(cast(state, counter, target_stack_id=target)))
    assert state.cards[spell].zone == Zone.EXILE
    assert spell in state.players[seat].exile
    assert len(state.players[seat].hand) == hand_before
    assert sum(state.players[seat].mana_pool.values()) == mana_before - 3


@pytest.mark.parametrize('seat', [1, 2])
def test_no_graveyard_cast_permission_is_atomic_after_restore(seat):
    state = position(seat)
    spell = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    state = restore(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, spell, target_player=3-seat)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_reanimate_removed_target_does_not_return_or_lose_life(seat):
    state = position(seat)
    bear = add(state, 'Grizzly Bears', 3-seat, Zone.GRAVEYARD)
    spell = add(state, 'Reanimate', seat)
    response = add(state, 'Cremate', 3-seat)
    state = cast(state, spell, target_card_id=bear)
    state = pass_once(state)
    state = settle(restore(cast(state, response, target_card_id=bear)))
    assert state.cards[bear].zone == Zone.EXILE
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.players[seat].life == 20
