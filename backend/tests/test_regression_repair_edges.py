"""Canonical cards; explicit core packets are labeled rather than fake spells."""
import pytest

from effects.handlers import destroy_permanent, return_creature_from_graveyard_to_battlefield
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.regression_agent.test_interactions import add, cast, pass_once, position, restore, settle
from tests.test_counter_replacements import source as modifier, choose
from tests.test_api_input_contracts import game, persist, rejected


@pytest.mark.parametrize('seat', [1, 2])
def test_remand_draws_but_flashback_destination_is_still_exile(seat):
    state = position(seat)
    spell = add(state, 'Think Twice', seat, Zone.GRAVEYARD)
    remand = add(state, 'Remand', 3-seat)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m.get('card_id') == spell and m['type'] == 'cast_spell')
    state = checked_action(state, RulesEngine(), seat, move)
    target = state.stack[-1].id
    state = pass_once(state)
    before = len(state.players[3-seat].hand)
    state = settle(restore(cast(state, remand, target_stack_id=target)))
    assert state.cards[spell].zone == Zone.EXILE
    assert spell in state.players[seat].exile
    assert len(state.players[3-seat].hand) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_cremate_draws_and_cannot_target_a_battlefield_card(seat):
    state = position(seat)
    spell = add(state, 'Cremate', seat)
    bear = add(state, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, spell, target_card_id=bear)
    assert serialize_match_snapshot(state) == before
    destroy_permanent(state, seat, {'target_card_id': bear})  # Core destruction packet.
    hand_before = len(state.players[seat].hand)
    state = settle(restore(cast(state, spell, target_card_id=bear)))
    assert state.cards[bear].zone == Zone.EXILE
    assert bear in state.players[3-seat].exile
    assert len(state.players[seat].hand) == hand_before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('counter,suppressed', [(True, False), (False, True)])
def test_undying_requires_predeath_ability_and_no_plus_counter(seat, counter, suppressed):
    state = position(seat)
    wolf = add(state, 'Young Wolf', seat, Zone.BATTLEFIELD)
    if counter:
        state.cards[wolf].counters['+1/+1'] = 1
    if suppressed:
        add(state, 'Humility', 3-seat, Zone.BATTLEFIELD)
    kill = add(state, 'Doom Blade', seat)
    state = settle(restore(cast(state, kill, target_card_id=wolf)))
    assert state.cards[wolf].zone == Zone.GRAVEYARD
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_stolen_undying_trigger_uses_old_controller_but_owner_entry(seat):
    state = position(seat)
    wolf = add(state, 'Young Wolf', 3-seat, Zone.BATTLEFIELD, owner=seat)
    kill = add(state, 'Doom Blade', seat)
    state = cast(state, kill, target_card_id=wolf)
    state = pass_once(pass_once(state))
    assert state.cards[wolf].zone == Zone.GRAVEYARD
    assert len(state.stack) == 1
    assert state.stack[0].controller == 3-seat
    assert state.stack[0].effect_key == 'undying_return'
    state = settle(restore(state))
    assert state.cards[wolf].controller == seat
    assert state.cards[wolf].counters['+1/+1'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_old_undying_does_not_return_a_new_graveyard_incarnation(seat):
    state = position(seat)
    wolf = add(state, 'Young Wolf', seat, Zone.BATTLEFIELD)
    # Core operations isolate an old trigger from a new death, not fabricated Oracle.
    destroy_permanent(state, seat, {'target_card_id': wolf})
    old_trigger = state.stack[0].id
    return_creature_from_graveyard_to_battlefield(state, seat, {'target_card_id': wolf})
    state.cards[wolf].counters['+1/+1'] = 1
    destroy_permanent(state, seat, {'target_card_id': wolf})
    assert [item.id for item in state.stack] == [old_trigger]
    state = settle(restore(state))
    assert state.cards[wolf].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_undying_counter_entry_choice_survives_restart(seat):
    state = position(seat)
    wolf = add(state, 'Young Wolf', seat, Zone.BATTLEFIELD)
    modifier(state, 'Doubling Season', seat)
    modifier(state, "Lae'zel, Vlaakith's Champion", seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    kill = add(state, 'Doom Blade', seat)
    state = cast(state, kill, target_card_id=wolf)
    for _ in range(4):
        state = pass_once(state)
    assert state.pending_replacement_choice['player_id'] == seat
    assert state.cards[wolf].zone == Zone.GRAVEYARD
    state = choose(restore(state), 'add', seat)
    assert state.cards[wolf].zone == Zone.BATTLEFIELD
    assert state.cards[wolf].counters['+1/+1'] == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_global_damage_doubling_is_not_prevention(seat):
    state = position(seat)
    add(state, 'Furnace of Rath', 3-seat, Zone.BATTLEFIELD)
    state.players[3-seat].prevent_damage_shield = 5
    spell = add(state, 'Skullcrack', seat)
    state = settle(restore(cast(state, spell, target_player=3-seat)))
    assert state.players[3-seat].life == 14
    assert state.players[3-seat].prevent_damage_shield == 5


@pytest.mark.parametrize('seat', [1, 2])
def test_two_doublers_human_chain_consumes_each_source_once(seat):
    state = position(seat)
    first = add(state, 'Furnace of Rath', seat, Zone.BATTLEFIELD)
    second = add(state, 'Furnace of Rath', 3-seat, Zone.BATTLEFIELD)
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    spell = add(state, 'Lightning Bolt', seat)
    state = cast(state, spell, target_player=3-seat)
    state = pass_once(pass_once(state))
    assert state.pending_replacement_choice['player_id'] == 3-seat
    state = restore(state)
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_replacement', 'replacement_source_id': first})
    assert [option['source_id'] for option in state.pending_replacement_choice['options']] == [second]
    assert state.players[3-seat].life == 20
    state = restore(state)
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_replacement', 'replacement_source_id': second})
    assert not state.pending_replacement_choice
    assert state.players[3-seat].life == 8
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_two_doublers_apply_to_actual_unblocked_combat(seat):
    state = position(seat)
    add(state, 'Furnace of Rath', seat, Zone.BATTLEFIELD)
    add(state, 'Furnace of Rath', 3-seat, Zone.BATTLEFIELD)
    bear = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    state.step = Step.DECLARE_BLOCKERS
    state.blockers_declared = True
    state.attackers = [bear]
    state.attack_targets = {bear: f'player:{3-seat}'}
    state = pass_once(pass_once(restore(state)))
    assert state.step == Step.COMBAT_DAMAGE
    assert state.players[3-seat].life == 12


@pytest.mark.parametrize('seat', [1, 2])
def test_reanimate_life_loss_is_locked_across_core_entry_counter_choice(seat):
    state = position(seat)
    wolf = add(state, 'Young Wolf', 3-seat, Zone.GRAVEYARD)
    modifier(state, 'Doubling Season', seat)
    modifier(state, "Lae'zel, Vlaakith's Champion", seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    # Explicit shared return-operation packet supplies counters to force the
    # continuation seam; it is not claimed to be Young Wolf's intrinsic entry.
    return_creature_from_graveyard_to_battlefield(state, seat, {
        'target_card_id': wolf, 'lose_life_equal_to_mana_value': True,
        'counters': {'+1/+1': 1},
    })
    assert state.pending_replacement_choice['player_id'] == seat
    assert state.cards[wolf].zone == Zone.GRAVEYARD
    assert state.players[seat].life == 20
    state = choose(restore(state), 'add', seat)
    assert state.cards[wolf].zone == Zone.BATTLEFIELD
    assert state.cards[wolf].counters['+1/+1'] == 4
    assert state.players[seat].life == 19


@pytest.mark.parametrize('seat', [1, 2])
def test_http_damage_choice_restores_exactly_and_rejects_wrong_actor(game, seat):
    import main
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session

    client, controller = game
    state = position(seat)
    state.id = controller.state.id
    first = add(state, 'Furnace of Rath', seat, Zone.BATTLEFIELD)
    second = add(state, 'Furnace of Rath', 3-seat, Zone.BATTLEFIELD)
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    spell = add(state, 'Lightning Bolt', seat)
    controller.state = pass_once(pass_once(cast(state, spell, target_player=3-seat)))
    for source_id in (first, second):
        persist(controller)
        before = serialize_match_snapshot(controller.state)
        main.ACTIVE_MATCHES.pop(state.id)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session), state.id)
        controller = main.ACTIVE_MATCHES[state.id]
        assert serialize_match_snapshot(controller.state) == before
        action = {'type': 'choose_replacement', 'replacement_source_id': source_id}
        rejected(client, controller, action, seat)
        response = client.post(f'/matches/{state.id}/action',
                               json={'player_id': 3-seat, 'action': action})
        assert response.status_code == 200, response.text
        controller = main.ACTIVE_MATCHES[state.id]
    assert controller.state.players[3-seat].life == 8
    assert controller.state.cards[spell].zone == Zone.GRAVEYARD
    assert not controller.state.pending_replacement_choice
