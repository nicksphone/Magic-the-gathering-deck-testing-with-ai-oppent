"""Effect-authorized casts share normal targets, costs, events and departures."""
import pytest

from effects.registry import resolve_effect
from game_state.state import Zone, Step
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
from rules_engine.stack_engine import add_to_stack
from rules_engine.events import flush_staged_triggers
from tests.test_activation_modifiers import board
from tests.test_surveil_mill import add, cast, choice, resolve_to_choice, resolve
from tests.test_api_input_contracts import game, persist, rejected


@pytest.mark.parametrize('seat', [1, 2])
def test_free_counter_with_no_spell_target_does_not_move_or_cast(seat):
    state = board(seat)
    counter = add(state, 'Counterspell', seat, Zone.GRAVEYARD)
    ability = add(state, 'Mind Stone', 3-seat)
    add_to_stack(state, ability.id, 3-seat, 'Draw ability', 'draw_cards', {'amount': 1}, is_spell=False)
    before = serialize_match_snapshot(state)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': counter.id})
    after = serialize_match_snapshot(state)
    assert state.cards[counter.id].zone == Zone.GRAVEYARD
    after['log'] = before['log']
    assert after == before


@pytest.mark.parametrize('seat', [1, 2])
def test_free_counter_has_announced_target_and_exiles_when_countered_target_is_legal(seat):
    state = board(3-seat)
    counter = add(state, 'Counterspell', seat, Zone.GRAVEYARD)
    spell = add(state, 'Grizzly Bears', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool.update(C=1, G=1)
    state = cast(state, spell)
    target = state.stack[-1].id
    # The permission belongs to seat, even though they do not currently have priority.
    assert state.priority_player == 3-seat
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': counter.id, 'exile_after_cast': True})
    item = next(item for item in state.stack if item.source_card_id == counter.id)
    assert item.payload['__announced_targets']['target_stack_id'] == target
    assert state.spells_cast_this_turn[seat] == 1
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert state.cards[counter.id].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_waiver_does_not_waive_mana_taxes(seat):
    state = board(seat)
    spell = add(state, 'Consider', seat, Zone.GRAVEYARD)
    add(state, 'Thalia, Guardian of Thraben', 3-seat)
    original = serialize_match_snapshot(state)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    after = serialize_match_snapshot(state)
    after['log'] = original['log']
    assert after == original
    state.players[seat].mana_pool.update(C=1)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    assert state.cards[spell.id].zone == Zone.STACK and state.players[seat].mana_pool['C'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_free_cast_pays_mandatory_discard_and_uses_zero_for_printed_x(seat):
    state = board(seat)
    shards = add(state, 'Bone Shards', seat, Zone.GRAVEYARD)
    target = add(state, 'Grizzly Bears', 3-seat)
    fodder = add(state, 'Island', seat, Zone.HAND)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': shards.id})
    assert state.cards[shards.id].zone == Zone.STACK
    assert state.cards[fodder.id].zone == Zone.GRAVEYARD
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    wastes = add(state, 'Secure the Wastes', seat, Zone.GRAVEYARD)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': wastes.id})
    assert state.stack[-1].payload['__announced_targets']['x_value'] == 0
    state = resolve(state)
    assert not any(state.cards[cid].is_token for cid in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
def test_free_spell_emits_cast_surveil_before_spell_resolution(seat):
    state = board(seat)
    add(state, "Dragon's Rage Channeler", seat)
    spell = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    flush_staged_triggers(state)
    assert len(state.stack) == 2 and state.stack[-1].effect_key == 'surveil'
    state = resolve_to_choice(state)
    assert state.cards[spell.id].zone == Zone.STACK
    state = resolve(choice(state, seat, []))
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert state.surveils_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_free_sorcery_permission_not_ordinary_timing_or_split_second_override(seat):
    state = board(3-seat)
    state.step = Step.UPKEEP
    spell = add(state, 'Glimpse the Unthinkable', seat, Zone.GRAVEYARD)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    assert state.cards[spell.id].zone == Zone.STACK
    state = resolve(state)
    assert len(state.players[3-seat].graveyard) == 10
    grip = add(state, 'Krosan Grip', 3-seat, Zone.HAND)
    state.players[3-seat].hand.remove(grip.id)
    grip.zone = Zone.STACK
    add_to_stack(state, grip.id, 3-seat, grip.name, 'noop', {})
    bolt = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': bolt.id})
    assert state.cards[bolt.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_mana_spent_free_deluge_does_not_look_at_four_cards(seat):
    state = board(seat)
    spell = add(state, 'Memory Deluge', seat, Zone.GRAVEYARD)
    library = list(state.players[seat].library)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    assert state.stack[-1].payload['mana_spent_to_cast'] == 0
    state = resolve(state)
    assert not state.pending_mechanic_choice and state.players[seat].library == library


@pytest.mark.parametrize('seat', [1, 2])
def test_api_cannot_forge_effect_permission(game, seat):
    client, controller = game
    state = board(seat)
    state.id = controller.state.id
    spell = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    controller.state = state
    persist(controller)
    rejected(client, controller, {'type': 'cast_spell', 'card_id': spell.id,
        'from_graveyard': True, 'effect_cast': True}, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payment', ['discard', 'sacrifice'])
def test_ordinary_cast_can_choose_either_additional_cost(seat, payment):
    state = board(seat)
    spell = add(state, 'Bone Shards', seat, Zone.HAND)
    target = add(state, 'Grizzly Bears', 3-seat)
    fodder = add(state, 'Island', seat, Zone.HAND)
    creature = add(state, 'Grizzly Bears', seat)
    state.players[seat].mana_pool['B'] = 1
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': spell.id,
        'cost_choice': {'id': 'base_' + payment}, 'targets': {'target_card_id': target.id}})
    assert state.cards[fodder.id].zone == (Zone.GRAVEYARD if payment == 'discard' else Zone.HAND)
    assert state.cards[creature.id].zone == (Zone.GRAVEYARD if payment == 'sacrifice' else Zone.BATTLEFIELD)
    assert state.cards[spell.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_free_cast_falls_back_to_available_sacrifice_cost(seat):
    state = board(seat)
    spell = add(state, 'Bone Shards', seat, Zone.GRAVEYARD)
    add(state, 'Grizzly Bears', 3-seat)
    fodder = add(state, 'Grizzly Bears', seat)
    assert not state.players[seat].hand
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    assert state.cards[spell.id].zone == Zone.STACK
    assert state.cards[fodder.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_free_deluge_counts_tax_mana_actually_paid(seat):
    state = board(seat)
    add(state, 'Thalia, Guardian of Thraben', 3-seat)
    spell = add(state, 'Memory Deluge', seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool['C'] = 1
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    assert state.stack[-1].payload['mana_spent_to_cast'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_exile_replacement_does_not_replace_return_to_hand(seat):
    from rules_engine.zone_actions import move_spell_from_stack
    state = board(seat)
    spell = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id, 'exile_after_cast': True})
    item = state.stack.pop()
    assert move_spell_from_stack(state, item, Zone.HAND) == Zone.HAND
    assert state.cards[spell.id].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_gearhulk_etb_permission_preserves_exile_after_snapshot(seat):
    state = board(seat)
    bolt = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    gearhulk = add(state, 'Torrential Gearhulk', seat, Zone.HAND)
    state.players[seat].mana_pool.update(C=4, U=2)
    state = resolve(cast(state, gearhulk))
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[bolt.id].zone == Zone.EXILE
    assert state.players[3-seat].life == 17
    assert state.spells_cast_this_turn[seat] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_effect_permission_does_not_allow_pregame_casting(seat):
    state = board(seat)
    state.pregame_pending = True
    state.kept_hands = set()
    spell = add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    after = serialize_match_snapshot(state)
    after['log'] = before['log']
    assert after == before
