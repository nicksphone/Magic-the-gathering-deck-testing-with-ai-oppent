"""Canonical permanent kicker entry, triggered payoffs and zone identity."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.kicker import permanent_kicker
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import resolve
from tests.test_kicker import setup as spell_setup

ROWS = {r['name']: r for r in json.loads((Path(__file__).parent/'fixtures/permanent_kicker.json').read_text())}


def setup(name, seat=1, free=False):
    state = board(seat)
    card = raw_add(state, name, seat, Zone.GRAVEYARD if free else Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool.update(G=10, R=10, C=20)
    target_state, _, target = spell_setup('Shivan Fire', 3-seat)
    target.counters.clear()
    state.cards[target.id] = target
    target.controller = target.owner = 3-seat
    state.players[3-seat].battlefield.append(target.id)
    if name == 'Mold Shambler':
        state.players[3-seat].battlefield.remove(target.id)
        from tests.test_legendary_channels import add
        target = add(state, 'Boseiju, Who Endures', 3-seat)
    return state, card, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('kicked', [False, True])
@pytest.mark.parametrize('free', [False, True])
def test_permanent_entry_and_conditional_payoff(seat, name, kicked, free):
    state, card, target = setup(name, seat, free)
    before = len(state.players[seat].hand)
    mana_before = sum(state.players[seat].mana_pool.values())
    text = card.oracle_text
    announcement = {
        'type':'cast_spell', 'card_id':card.id, 'from_graveyard':free,
        'cost_choice':{'id':'kicker' if kicked else 'base'}}
    if free:
        # Exercise the shared effect-authorized admission, not a fabricated
        # permission on a canonical spell whose scope is instant/sorcery only.
        from rules_engine.effect_casts import admit_cast
        admit_cast(state, seat, announcement, {'target_card_id': card.id})
    else:
        state = checked_action(state, RulesEngine(), seat, announcement)
    from rules_engine.mana import mana_value
    assert mana_before - sum(state.players[seat].mana_pool.values()) == (
        (0 if free else mana_value(card.mana_cost)) +
        (mana_value(permanent_kicker(text)['price']) if kicked else 0))
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[card.id].was_kicked is kicked
    state = resolve(state)
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].oracle_text == text
    assert state.cards[card.id].was_kicked is kicked
    if name == 'Baloth Gorger':
        assert state.cards[card.id].counters.get('+1/+1', 0) == (3 if kicked else 0)
    elif name == 'Citanul Woodreaders':
        assert len(state.players[seat].hand) == before - int(not free) + (2 if kicked else 0)
    else:
        assert state.cards[target.id].zone == (Zone.GRAVEYARD if kicked else Zone.BATTLEFIELD)


@pytest.mark.parametrize('name', list(ROWS))
def test_uncast_entry_does_not_borrow_old_kicker(name):
    state, card, _ = setup(name)
    card.was_kicked = True
    card.move_to_zone(Zone.EXILE)
    assert not card.was_kicked
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[1].hand.remove(card.id)
    state.players[1].battlefield.append(card.id)
    emit_event(state, 'enters_battlefield', {'card_id':card.id,'controller':1})
    assert not state.stack


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('name', list(ROWS))
def test_actual_ai_selects_useful_permanent_kicker(difficulty, name):
    state, card, _ = setup(name)
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == card.id)
    action = AIAgent(difficulty)._materialize_action(state, move, 1)
    assert action['cost_choice']['id'] == 'kicker'
    state = checked_action(state, RulesEngine(), 1, action)
    assert state.cards[card.id].was_kicked


def test_unrecognized_permanent_kicker_remains_unmodeled():
    assert permanent_kicker('Kicker {4}\nWhen this creature enters, if it was kicked, create a token.') is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
def test_permanent_spell_copy_keeps_paid_choice_without_second_payment(seat, name):
    state, card, target = setup(name, seat)
    if name == 'Torch Slinger':
        from tests.test_surveil_mill import add
        add(state, 'Grizzly Bears', 3-seat)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': card.id, 'cost_choice': {'id': 'kicker'}})
    mana = dict(state.players[seat].mana_pool)
    hand = len(state.players[seat].hand)
    resolve_effect(state, seat, 'copy_spell', {'target_stack_id': state.stack[-1].id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    copies = [state.cards[cid] for cid in state.players[seat].battlefield
              if state.cards[cid].name == card.name]
    assert len(copies) == 2
    assert all(c.was_kicked and c.oracle_text == card.oracle_text for c in copies)
    assert state.players[seat].mana_pool == mana
    if name == 'Baloth Gorger':
        assert all(c.counters.get('+1/+1') == 3 for c in copies)
    elif name == 'Citanul Woodreaders':
        assert len(state.players[seat].hand) == hand + 4
    else:
        assert state.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('modifier,expected', [('Doubling Season', 6), ('Solemnity', 0)])
def test_paid_entry_counters_use_shared_replacements(modifier, expected):
    from tests.test_counter_replacements import source
    from tests.test_counter_prohibitions import source as prohibition
    state, card, _ = setup('Baloth Gorger')
    (prohibition if modifier == 'Solemnity' else source)(state, modifier, 1)
    state = checked_action(state, RulesEngine(), 1, {
        'type':'cast_spell', 'card_id':card.id, 'cost_choice':{'id':'kicker'}})
    state = resolve(state)
    assert state.cards[card.id].counters.get('+1/+1', 0) == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_targeted_etb_is_chosen_after_entry_and_retains_old_object_history(seat):
    state, card, target = setup('Torch Slinger', seat)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state = checked_action(state, RulesEngine(), seat, {
        'type':'cast_spell', 'card_id':card.id, 'cost_choice':{'id':'kicker'}})
    resolve_top_of_stack(state)
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'choose_trigger_target')
    state = checked_action(state, RulesEngine(), seat, {
        'type':'choose_trigger_target','stack_id':move['stack_id'], 'target_card_id':target.id})
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id':card.id})
    assert not state.cards[card.id].was_kicked
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD


def test_noncreature_removal_hints_exclude_creature_artifacts():
    from copy import copy
    from rules_engine.oracle_effects import inspect_target_hints
    state, card, target = setup('Mold Shambler')
    other = raw_add(state, 'Torch Slinger', 2, cards=ROWS)
    other.types.append('Artifact')
    proxy = copy(card)
    proxy.oracle_text, proxy.types = permanent_kicker(card.oracle_text)['instruction'], []
    hints = inspect_target_hints(state, proxy, 1)
    ids = {t['id'] for t in hints['permanent_targets']}
    assert target.id in ids and other.id not in ids
