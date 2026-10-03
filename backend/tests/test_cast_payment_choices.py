"""Canonical explicit discard/sacrifice spell costs and shared event fidelity."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_activation_modifiers import board
from tests.test_surveil_mill import add, resolve
from tests.test_ai_recurring_engines import add as engine_add
from tests.test_api_input_contracts import game, persist, rejected


def setup(seat, free=False):
    state = board(seat)
    spell = add(state, 'Bone Shards', seat, Zone.GRAVEYARD if free else Zone.HAND)
    target = add(state, 'Grizzly Bears', 3-seat)
    first = add(state, 'Lightning Bolt', seat, Zone.HAND)
    selected = add(state, 'Island', seat, Zone.HAND)
    large = add(state, 'Griselbrand', seat)
    small = add(state, 'Grizzly Bears', seat)
    state.players[seat].mana_pool['B'] = 1
    if free:
        state.mechanic_choice_players = {seat}
        resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    return state, spell, target, first, selected, large, small


def announce(spell, target, payment, ids, free=False):
    return {'type': 'cast_spell', 'card_id': spell.id, 'from_graveyard': free,
            'targets': {'target_card_id': target.id},
            'cost_choice': {'id': f'base_{payment}', f'{payment}_card_ids': ids}}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('free', [False, True])
@pytest.mark.parametrize('payment', ['discard', 'sacrifice'])
def test_selected_payment_not_first_card_and_once_only(seat, free, payment):
    state, spell, target, first, selected, large, small = setup(seat, free)
    paid = selected if payment == 'discard' else small
    state = checked_action(state, RulesEngine(), seat, announce(spell, target, payment, [paid.id], free))
    assert state.cards[paid.id].zone == Zone.GRAVEYARD
    assert state.cards[first.id].zone == Zone.HAND
    assert state.cards[large.id].zone == Zone.BATTLEFIELD
    assert state.players[seat].mana_pool['B'] == (1 if free else 0)
    assert state.spells_cast_this_turn[seat] == 1
    if payment == 'sacrifice':
        assert any('sacrifices Grizzly Bears for additional cost' in line for line in state.log)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, announce(spell, target, payment, [paid.id], free))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payment', ['discard', 'sacrifice'])
@pytest.mark.parametrize('error', ['empty', 'duplicate', 'enemy', 'source', 'other_cost'])
def test_invalid_selection_rejects_before_payment_and_keeps_entire_state(seat, payment, error):
    state, spell, target, _, selected, _, small = setup(seat)
    paid = selected if payment == 'discard' else small
    ids = {'empty': [], 'duplicate': [paid.id, paid.id], 'enemy': [target.id],
           'source': [spell.id], 'other_cost': [paid.id]}[error]
    action = announce(spell, target, payment, ids)
    if error == 'other_cost':
        action['cost_choice'][f"{'sacrifice' if payment == 'discard' else 'discard'}_card_ids"] = [paid.id]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('exile', [False, True])
def test_cost_sacrifice_publishes_death_trigger_above_spell_unless_exiled(seat, exile):
    state, spell, target, _, _, _, small = setup(seat)
    artist = engine_add(state, 'Blood Artist', seat)
    if exile:
        add(state, 'Leyline of the Void', 3-seat)
    state = checked_action(state, RulesEngine(), seat, announce(spell, target, 'sacrifice', [small.id]))
    triggers = [item for item in state.stack if item.source_card_id == artist.id]
    assert len(triggers) == (0 if exile else 1)
    assert state.cards[small.id].zone == (Zone.EXILE if exile else Zone.GRAVEYARD)
    if not exile:
        assert state.stack[-1].source_card_id == artist.id
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('payment', ['discard', 'sacrifice'])
def test_ai_uses_known_retention_and_sacrifice_loss_not_zone_order(seat, difficulty, payment):
    state, spell, target, _, selected, _, small = setup(seat)
    # Surplus lands are expendable; the first nonland is retained.
    for _ in range(5):
        add(state, 'Island', seat)
    add(state, 'Island', seat, Zone.HAND)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    move = {**move, 'cost_choice': {'id': f'base_{payment}'}, 'targets': {'target_card_id': target.id}}
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty=difficulty)._materialize_action(state, move, seat)
    assert action['cost_choice'][f'{payment}_card_ids'] == [(selected if payment == 'discard' else small).id]
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, action)
    assert state.cards[spell.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('archetype', ['Aggro', 'Control', 'Tempo', 'Ramp', 'Drain', 'Tokens', 'Tribal', 'Midrange'])
def test_ai_compares_either_cost_branches_and_retains_needed_land(seat, difficulty, archetype):
    state, spell, target, _, selected, _, _ = setup(seat)
    rows = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/equip_costs.json').read_text())}
    fodder = engine_add(state, 'Ornithopter', seat, cards=rows)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    action = AIAgent(difficulty=difficulty, archetype=archetype)._materialize_action(state,
        {**move, 'targets': {'target_card_id': target.id}}, seat)
    assert action['cost_choice']['id'] == 'base_sacrifice'
    assert action['cost_choice']['sacrifice_card_ids'] == [fodder.id]
    state = checked_action(state, RulesEngine(), seat, action)
    assert state.cards[selected.id].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_http_selection_is_strict_and_rejections_preserve_database(game, seat):
    client, controller = game
    state, spell, target, _, selected, _, _ = setup(seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    rejected(client, controller, announce(spell, target, 'discard', [selected.id, selected.id]), seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat,
        'action': announce(spell, target, 'discard', [selected.id])})
    assert response.status_code == 200, response.text
    assert controller.state.cards[selected.id].zone == Zone.GRAVEYARD
