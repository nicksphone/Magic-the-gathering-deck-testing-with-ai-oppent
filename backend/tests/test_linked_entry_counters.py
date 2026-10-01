"""Canonical card fixtures; linked-return records are explicit engine packets."""
import pytest
import json
from pathlib import Path

from effects.registry import resolve_effect
from effects.handlers import exile_permanent
from game_state.state import Zone, object_incarnation, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.linked_exile import record_linked_exile, flush_linked_exile_returns
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_counter_prohibitions import source as permanent
from tests.test_counter_replacements import source as modifier, choose
from tests.test_linked_exile import _state
from tests.test_ai_recurring_engines import add as add_card
from tests.test_spell_entry_counters import ROWS as SPELLS

LANDS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/attached_scaling.json').read_text())}


def hold(state, source, cards, destination=Zone.BATTLEFIELD):
    for card in cards:
        exile_permanent(state, source.controller, {'target_card_id': card.id})
    record_linked_exile(state, source.id, object_incarnation(source), [c.id for c in cards], destination)


def release(state, source):
    resolve_effect(state, source.controller, 'return_permanent_to_hand', {'target_card_id': source.id})


@pytest.mark.parametrize('active', [1, 2])
def test_mixed_owner_return_choices_are_apnap_atomic_and_durable(active):
    state, source = _state()
    state.active_player = active
    cards = [permanent(state, "Elspeth, Sun's Champion", seat) for seat in (1, 2)]
    for seat in (1, 2):
        modifier(state, 'Doubling Season', seat)
        modifier(state, "Lae'zel, Vlaakith's Champion", seat)
    hold(state, source, cards)
    release(state, source)
    assert state.pending_replacement_choice['player_id'] == active
    assert all(c.zone == Zone.EXILE for c in cards)
    assert state.linked_exiles == []
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'add', active)
    assert state.pending_replacement_choice['player_id'] == 3-active
    assert all(state.cards[c.id].zone == Zone.EXILE for c in cards)
    state = choose(state, 'double', 3-active)
    for card in cards:
        returned = state.cards[card.id]
        assert returned.zone == Zone.BATTLEFIELD and returned.controller == card.owner
        assert returned.loyalty == (10 if card.owner == active else 9)
        assert state.players[card.owner].battlefield.count(card.id) == 1
    flush_linked_exile_returns(state)
    assert not state.pending_replacement_choice


def test_linked_read_ahead_pauses_sbas_and_returns_with_chapter_choice():
    state, source = _state()
    card = add_card(state, 'The Phasing of Zhalfir', 2, cards=SPELLS)
    hold(state, source, [card])
    release(state, source)
    assert state.pending_mechanic_choice['player_id'] == 2
    apply_state_based_actions(state)
    assert card.zone == Zone.EXILE and not state.stack
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 2, {'type': 'choose_mechanic', 'choice_id': '2'})
    assert state.cards[card.id].counters['__lore'] == 2
    assert [item.payload['__chapter_number'] for item in state.stack] == [2]


def test_linked_hand_return_does_not_add_loyalty_or_request_replacements():
    state, source = _state()
    card = permanent(state, "Elspeth, Sun's Champion", 2)
    modifier(state, 'Doubling Season', 2)
    modifier(state, "Lae'zel, Vlaakith's Champion", 2)
    hold(state, source, [card], Zone.HAND)
    release(state, source)
    assert card.zone == Zone.HAND and card.id in state.players[2].hand
    assert not state.pending_replacement_choice


def test_mixed_owner_land_payments_reserve_life_per_player():
    state, source = _state()
    cards = [add_card(state, 'Hallowed Fountain', seat, cards=LANDS) for seat in (1, 2)]
    for seat in state.players.values():
        seat.life = 2
    hold(state, source, cards)
    release(state, source)
    assert state.pending_mechanic_choice['player_id'] == 1
    state = checked_action(state, RulesEngine(), 1, {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'})
    assert state.pending_mechanic_choice['player_id'] == 2
    assert 'pay_two_life' in state.pending_mechanic_choice['options']
    assert all(state.cards[c.id].zone == Zone.EXILE for c in cards)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 2, {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'})
    assert all(state.players[seat].life == 0 for seat in (1, 2))
    assert all(state.cards[c.id].zone == Zone.BATTLEFIELD and not state.cards[c.id].tapped for c in cards)


def test_stolen_planeswalker_returns_to_owner_with_owners_modifiers():
    state, source = _state()
    card = permanent(state, "Elspeth, Sun's Champion", 1)
    state.players[1].battlefield.remove(card.id)
    state.players[2].battlefield.append(card.id)
    card.controller = 2
    modifier(state, 'Doubling Season', 1)
    hold(state, source, [card])
    release(state, source)
    assert card.controller == card.owner == 1 and card.loyalty == 8


def test_returning_counter_ban_does_not_retroactively_apply_to_batch():
    state, source = _state()
    saga = add_card(state, 'The Phasing of Zhalfir', 2, cards=SPELLS)
    ban = permanent(state, 'Solemnity')
    hold(state, source, [ban, saga])
    release(state, source)
    state = checked_action(state, RulesEngine(), 2, {'type': 'choose_mechanic', 'choice_id': '1'})
    assert state.cards[saga.id].counters['__lore'] == 1


def test_departed_exile_incarnation_is_not_returned():
    state, source = _state()
    card = permanent(state, "Elspeth, Sun's Champion", 2)
    hold(state, source, [card])
    state.players[2].exile.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[2].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    exile_permanent(state, 1, {'target_card_id': card.id})
    release(state, source)
    assert card.zone == Zone.EXILE and card.id in state.players[2].exile


def test_state_based_death_pauses_before_publishing_return_chapter_triggers():
    state, _ = _state()
    source = modifier(state, "Lae'zel, Vlaakith's Champion")
    card = add_card(state, 'The Phasing of Zhalfir', 2, cards=SPELLS)
    hold(state, source, [card])
    source.counters['__damage_marked'] = 100
    apply_state_based_actions(state)
    assert source.zone == Zone.GRAVEYARD
    assert card.zone == Zone.EXILE and state.pending_mechanic_choice['player_id'] == 2
    assert state.trigger_staging and not state.stack
    state = checked_action(state, RulesEngine(), 2, {'type': 'choose_mechanic', 'choice_id': '2'})
    assert state.cards[card.id].counters['__lore'] == 2
    assert [item.payload['__chapter_number'] for item in state.stack] == [2]
    assert not state.trigger_staging
