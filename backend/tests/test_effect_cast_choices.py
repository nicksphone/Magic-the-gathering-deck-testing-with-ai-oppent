"""Human permission choices and public-information graveyard target ranking."""
import pytest

from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from ai.effect_cast_policy import preferred_graveyard_spell
from ai.agent import AIAgent
from tests.test_activation_modifiers import board
from tests.test_surveil_mill import add, resolve
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_api_input_contracts import game, persist, rejected


def permission(seat, name='Lightning Bolt', taxed=False):
    state = board(seat)
    state.mechanic_choice_players = [seat]
    card = add(state, name, seat, Zone.GRAVEYARD)
    if taxed:
        add(state, 'Thalia, Guardian of Thraben', 3-seat)
    resolve_effect(state, seat, 'cast_from_graveyard', {
        'target_card_id': card.id, 'exile_after_cast': True})
    return state, card


@pytest.mark.parametrize('seat', [1, 2])
def test_human_can_resume_and_choose_a_different_target(seat):
    state, card = permission(seat)
    target = add(state, 'Grizzly Bears', 3-seat)
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    assert RulesEngine().legal_moves(state, 3-seat) == []
    moves = RulesEngine().legal_moves(state, seat)
    assert {move['type'] for move in moves} == {'cast_spell', 'choose_mechanic'}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
        'targets': {'target_card_id': target.id}})
    assert not state.pending_mechanic_choice
    assert state.spells_cast_this_turn[seat] == 1
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert state.cards[card.id].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('error', ['wrong_seat', 'missing_target', 'wrong_source'])
def test_rejected_announcements_preserve_permission_and_entire_state(seat, error):
    state, card = permission(seat)
    other = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    action = {'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
              'targets': {'target_player': 3-seat}}
    actor = seat
    if error == 'wrong_seat':
        actor = 3-seat
    elif error == 'missing_target':
        action['targets'] = {}
    else:
        action['card_id'] = other.id
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_declining_does_not_pay_tax_or_move_card(seat):
    state, card = permission(seat, taxed=True)
    state.players[seat].mana_pool['C'] = 1
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[card.id].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool['C'] == 1
    assert not state.spells_cast_this_turn.get(seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_printed_x_must_be_zero_during_free_cast(seat):
    state, card = permission(seat, 'Secure the Wastes')
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
            'targets': {'x_value': 1}})
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
        'targets': {'x_value': 0}})
    assert state.stack[-1].payload['__announced_targets']['x_value'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_selects_usable_spell_not_unusable_counter_or_zero_deluge(seat):
    state = board(seat)
    names = ['Memory Deluge', 'Counterspell', 'Lightning Bolt']
    cards = [add(state, name, seat, Zone.GRAVEYARD) for name in names]
    options = [{'target_card_id': card.id} for card in cards]
    before = serialize_match_snapshot(state)
    assert preferred_graveyard_spell(state, seat, options)['target_card_id'] == cards[-1].id
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('name', ['Lightning Bolt', 'Counterspell', 'Memory Deluge'])
def test_ai_explicit_permission_casts_or_declines_without_treating_option_as_card(seat, difficulty, name):
    state, card = permission(seat, name)
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty=difficulty).choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == ('cast_spell' if name == 'Lightning Bolt' else 'choose_mechanic')
    state = checked_action(state, RulesEngine(), seat, decision.action)
    assert not state.pending_mechanic_choice
    assert state.cards[card.id].zone == (Zone.STACK if name == 'Lightning Bolt' else Zone.GRAVEYARD)


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_gearhulk_trigger_announces_useful_spell_before_resolution(seat):
    state = board(seat)
    add(state, 'Memory Deluge', seat, Zone.GRAVEYARD)
    add(state, 'Counterspell', seat, Zone.GRAVEYARD)
    bolt = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    hulk = add(state, 'Torrential Gearhulk', seat, Zone.HAND)
    state.players[seat].mana_pool.update(C=4, U=2)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': hulk.id})
    resolve_top_of_stack(state)
    assert not state.pending_trigger_order
    assert state.stack[-1].payload['target_card_id'] == bolt.id
    state = resolve(state)
    assert state.cards[bolt.id].zone == Zone.EXILE
    assert state.players[3-seat].life == 17


@pytest.mark.parametrize('seat', [1, 2])
def test_tax_blocks_human_cast_but_not_decline(seat):
    state, card = permission(seat, taxed=True)
    assert [move['type'] for move in RulesEngine().legal_moves(state, seat)] == ['choose_mechanic']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
            'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_departed_graveyard_card_cannot_be_cast_with_saved_permission(seat):
    state, card = permission(seat)
    state.players[seat].graveyard.remove(card.id)
    state.players[seat].exile.append(card.id)
    card.zone = Zone.EXILE
    assert [move['type'] for move in RulesEngine().legal_moves(state, seat)] == ['choose_mechanic']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
            'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('decline', [False, True])
def test_gearhulk_target_then_cast_choice_survives_both_resolution_stages(seat, decline):
    state = board(seat)
    state.mechanic_choice_players = {seat}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    counter = add(state, 'Counterspell', seat, Zone.GRAVEYARD)
    bolt = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    hulk = add(state, 'Torrential Gearhulk', seat, Zone.HAND)
    state.players[seat].mana_pool.update(C=4, U=2)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': hulk.id})
    resolve_top_of_stack(state)
    assert state.pending_trigger_order['phase'] == 'targets'
    options = RulesEngine().legal_moves(state, seat)
    # An ability can target a Counterspell even when there is nothing to counter.
    assert {move['target_card_id'] for move in options} == {counter.id, bolt.id}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    move = next(move for move in options if move['target_card_id'] == bolt.id)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'choose_trigger_target', 'stack_id': move['stack_id'], 'target_card_id': bolt.id})
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    assert state.pending_mechanic_choice.get('resolving_item')
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    action = ({'type': 'choose_mechanic', 'card_ids': ['decline']} if decline else {
        'type': 'cast_spell', 'card_id': bolt.id, 'from_graveyard': True,
        'targets': {'target_player': 3-seat}})
    state = checked_action(state, RulesEngine(), seat, action)
    assert not state.pending_mechanic_choice and not state.pending_trigger_order
    state = resolve(state)
    assert state.cards[hulk.id].zone == Zone.BATTLEFIELD
    assert state.cards[bolt.id].zone == (Zone.GRAVEYARD if decline else Zone.EXILE)
    assert state.players[3-seat].life == (20 if decline else 17)


@pytest.mark.parametrize('seat', [1, 2])
def test_http_saved_cast_permission_and_duplicate_rejection(game, seat):
    client, controller = game
    state, card = permission(seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    rejected(client, controller, {'type': 'cast_spell', 'card_id': card.id,
                                 'from_graveyard': True, 'targets': {}}, seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': {
        'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
        'targets': {'target_player': 3-seat}}})
    assert response.status_code == 200, response.text
    assert not controller.state.pending_mechanic_choice
    rejected(client, controller, {'type': 'cast_spell', 'card_id': card.id,
        'from_graveyard': True, 'targets': {'target_player': 3-seat}}, seat)
