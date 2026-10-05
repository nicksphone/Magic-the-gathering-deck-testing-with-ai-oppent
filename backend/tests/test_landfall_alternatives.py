"""Canonical landfall instructions choose one branch at resolution."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.continuous import effective_combat_stats
from rules_engine.events import emit_event
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_recurring_engines import add


FILES = ['groundswell', 'rest-for-the-weary', 'mysteries-of-the-deep']


def position(name, seat):
    raw = json.loads((Path(__file__).parent / 'fixtures/landfall' / (name+'.json')).read_text())
    state = bare_state(seat)
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 8}], [], seed=829)
    spell = deepcopy(next(iter(sample.cards.values())))
    spell.id = state.allocate_object_id()
    spell.owner = spell.controller = seat
    spell.move_to_zone(Zone.HAND)
    state.cards[spell.id] = spell
    state.players[seat].hand.append(spell.id)
    recipient = add(state, 'Torrential Gearhulk', seat)
    targets = {'target_card_id': recipient.id} if name == 'groundswell' else {'target_player': 3-seat} if name == 'rest-for-the-weary' else {}
    state.players[seat].mana_pool = {'G': 1, 'W': 1, 'U': 1, 'C': 4}
    return state, spell, recipient, targets


@pytest.mark.parametrize('name', FILES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('entry', ['none', 'before', 'after', 'opponent'])
def test_alternative_is_selected_at_resolution_after_reload(name, seat, entry):
    state, spell, recipient, targets = position(name, seat)
    def enter(actor):
        cid = state.players[actor].library.pop()
        card = state.cards[cid]
        assert 'Land' in card.types
        card.move_to_zone(Zone.BATTLEFIELD)
        state.players[actor].battlefield.append(cid)
        emit_event(state, 'enters_battlefield', {'card_id': cid, 'controller': actor})
        # Departure must not undo this turn's entry history.
        state.players[actor].battlefield.remove(cid)
        card.move_to_zone(Zone.GRAVEYARD)
        state.players[actor].graveyard.append(cid)
    if entry in ['before', 'opponent']:
        enter(seat if entry == 'before' else 3-seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    assert state.cards[spell.id].zone == Zone.STACK
    if entry == 'after':
        enter(seat)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    power, toughness = effective_combat_stats(state, recipient.id)
    life = state.players[3-seat].life
    hand = len(state.players[seat].hand)
    assert resolve_top_of_stack(state)
    enhanced = entry in ['before', 'after']
    if name == 'groundswell':
        amount = 4 if enhanced else 2
        assert effective_combat_stats(state, recipient.id) == (power+amount, toughness+amount)
    elif name == 'rest-for-the-weary':
        assert state.players[3-seat].life == life+(8 if enhanced else 4)
    else:
        assert len(state.players[seat].hand) == hand+(3 if enhanced else 2)
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert not state.stack


@pytest.mark.parametrize('name', FILES)
def test_unknown_legacy_history_rejects_without_consuming_stack(name):
    state, spell, _, targets = position(name, 1)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    state.land_entry_history_known = False
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='land-entry history'):
        resolve_top_of_stack(state)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enhanced', [False, True])
def test_selected_draw_branch_uses_existing_draw_replacement(seat, enhanced):
    state, spell, _, targets = position('mysteries-of-the-deep', seat)
    cards = {card['name']: card for card in json.loads(
        (Path(__file__).parent / 'fixtures/draw_forecast.json').read_text())}
    add(state, 'Thought Reflection', seat, cards=cards)
    state.land_entries_this_turn[seat] = int(enhanced)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    before = len(state.players[seat].hand)
    assert resolve_top_of_stack(state)
    assert len(state.players[seat].hand) == before+(6 if enhanced else 4)


@pytest.mark.parametrize('seat', [1, 2])
def test_draw_branch_suspends_and_resumes_dredge_without_reselecting_branch(seat):
    state, spell, _, targets = position('mysteries-of-the-deep', seat)
    cards = {card['name']: card for card in json.loads(
        (Path(__file__).parent / 'fixtures/linked_discard.json').read_text())}
    dredger = add(state, 'Stinkweed Imp', seat, Zone.GRAVEYARD, cards=cards)
    state.land_entries_this_turn[seat] = 1
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    before = len(state.players[seat].hand)
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'draw'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'choice_id': dredger.id})
    assert state.pending_mechanic_choice is None
    assert len(state.players[seat].hand) == before+3
    assert dredger.id in state.players[seat].hand
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert not state.stack


@pytest.mark.parametrize('name', FILES)
@pytest.mark.parametrize('seat', [1, 2])
def test_copy_checks_its_controller_history_not_original_controller(name, seat):
    from effects.handlers import copy_spell
    state, spell, recipient, targets = position(name, seat)
    state.land_entries_this_turn[seat] = 1
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    original = state.stack[-1].id
    copy_spell(state, 3-seat, {'target_stack_id': original})
    assert len(state.stack) == 2
    power, toughness = effective_combat_stats(state, recipient.id)
    life = state.players[3-seat].life
    hand = len(state.players[3-seat].hand)
    assert resolve_top_of_stack(state)
    if name == 'groundswell':
        assert effective_combat_stats(state, recipient.id) == (power+2, toughness+2)
    elif name == 'rest-for-the-weary':
        assert state.players[3-seat].life == life+4
    else:
        assert len(state.players[3-seat].hand) == hand+2
    assert len(state.stack) == 1
    assert state.stack[0].id == original


@pytest.mark.parametrize('seat', [1, 2])
def test_illegal_only_target_fizzles_even_when_legacy_history_is_unknown(seat):
    from effects.registry import resolve_effect
    state, spell, recipient, targets = position('groundswell', seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    resolve_effect(state, seat, 'exile', {'target_card_id': recipient.id})
    state.land_entry_history_known = False
    assert resolve_top_of_stack(state)
    assert not state.stack
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
