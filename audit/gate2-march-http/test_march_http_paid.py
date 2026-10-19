"""UNEXECUTED proposal: real HTTP casts, payments and storage cold reloads."""
from copy import deepcopy
import json
import os

import pytest

import inventory as inv
import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.test_api_input_contracts import game, persist, rejected, snapshot
from tests.test_fixed_spell_cost_witness import setup as finite_setup
from test_march_pitch_paid import setup


@pytest.fixture(scope='module')
def http_facts():
    seed, selected, provenance = inv.load_inputs()
    with (inv.ROOT.parent / 'evidence' /
          (os.environ['ADMISSION_PHASE'] + '-http-facts.json')).open('x') as stream:
        json.dump(provenance, stream, indent=2)
    return {name: selected[row['scryfall_id']] for name, row in seed.items()}


def install(controller, state):
    state.id = controller.state.id
    controller.state = state
    persist(controller)


def public_move(client, controller, seat, source):
    before = snapshot(controller)
    response = client.get(f'/matches/{controller.state.id}/legal-moves',
                          params={'player_id': seat})
    assert response.status_code == 200, response.text
    assert snapshot(controller) == before
    return next(row for row in response.json()['moves']
                if row.get('type') == 'cast_spell' and row.get('card_id') == source)


def cold_reload(client, controller, seat, source):
    match_id = controller.state.id
    before = serialize_match_snapshot(controller.state)
    main.ACTIVE_MATCHES.pop(match_id)
    response = client.get(f'/matches/{match_id}/legal-moves', params={'player_id': seat})
    assert response.status_code == 200, response.text
    restored = main.ACTIVE_MATCHES[match_id]
    assert restored is not controller
    assert serialize_match_snapshot(restored.state) == before
    assert restored.controllers == controller.controllers
    return restored


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', ['empty', 'one', 'reverse'])
@pytest.mark.parametrize('cold', [False, True])
def test_public_deliberate_pitch_paid_http_and_cold_resume(game, http_facts, seat, variant, cold):
    client, controller = game
    x, count = {'empty': (2, 0), 'one': (4, 1), 'reverse': (4, 2)}[variant]
    state, action, whites, red, foreign = setup(http_facts, seat, x=x, n=count)
    if variant == 'reverse':
        action['cost_choice']['exile_card_ids'].reverse()
    install(controller, state)
    if cold:
        controller = cold_reload(client, controller, seat, action['card_id'])
    move = public_move(client, controller, seat, action['card_id'])
    option = next(row for row in move['cost_options'] if row['id'] == 'base')
    assert set(option['exile_card_ids']) == set(whites)
    assert foreign not in option['exile_card_ids'] and red not in option['exile_card_ids']
    assert option['hand_exile_color'] == 'W' and option['hand_exile_generic_reduction'] == 2
    assert option['mana_cost'] == '{X}{W}'
    original_state = controller.state
    original_snapshot = serialize_match_snapshot(original_state)
    response = client.post(f'/matches/{state.id}/action',
                           json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert serialize_match_snapshot(original_state) == original_snapshot
    paid = controller.state
    assert paid is not original_state
    assert paid.cards[action['card_id']].zone == Zone.STACK
    item = next(item for item in paid.stack if item.source_card_id == action['card_id'])
    assert item.controller == seat and item.payload['mana_spent'] == max(0, x-2*count)+1
    assert item.payload['__announced_targets'] == action['targets']
    assert not sum(paid.players[seat].mana_pool.values())
    selected = action['cost_choice']['exile_card_ids']
    assert all(paid.cards[cid].zone == Zone.EXILE for cid in selected)
    assert all(paid.cards[cid].zone == Zone.HAND for cid in whites if cid not in selected)
    assert paid.cards[red].zone == paid.cards[foreign].zone == Zone.HAND
    receipt = {'seat': seat, 'variant': variant, 'cold_reload': cold,
               'complete_public_move_and_cost_view': move, 'submitted_action': action,
               'actual_paid_mana': item.payload['mana_spent'],
               'selected_exile_ids': selected, 'remaining_pool': paid.players[seat].mana_pool,
               'original_root_unchanged': True, 'HTTP_status': response.status_code}
    name = os.environ['ADMISSION_PHASE'] + f'-http-paid-{seat}-{variant}-{cold}.json'
    with (inv.ROOT.parent / 'evidence' / name).open('x') as stream:
        json.dump(receipt, stream, indent=2)
    if cold:
        controller = cold_reload(client, controller, seat, action['card_id'])
    # Actual HTTP priority passes, never a direct effect-handler shortcut.
    for _ in range(12):
        if not controller.state.stack:
            break
        actor = controller.state.priority_player
        response = client.post(f'/matches/{state.id}/action',
                               json={'player_id': actor, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    assert not controller.state.stack
    assert controller.state.cards[action['targets']['target_card_id']].zone == Zone.EXILE
    assert controller.state.cards[action['card_id']].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['null', 'unknown-field', 'duplicate', 'stale', 'foreign',
                                'red', 'source', 'missing-x', 'negative-x', 'bool-x',
                                'no-white-mana', 'wrong-actor', 'ai-controller'])
def test_http_rejection_preserves_root_controller_and_sql(game, http_facts, seat, bad):
    client, controller = game
    state, action, whites, red, foreign = setup(http_facts, seat)
    action = deepcopy(action)
    choice = action['cost_choice']
    actor = seat
    if bad in {'null','duplicate','stale','foreign','red','source'}:
        choice['exile_card_ids'] = {'null': None, 'duplicate': [whites[0], whites[0]],
            'stale': ['nonexistent-pitch'], 'foreign': [foreign], 'red': [red],
            'source': [action['card_id']]}[bad]
    elif bad == 'unknown-field':
        choice['unrecognized_cost_field'] = []
    elif bad == 'missing-x':
        action['targets'].pop('x_value')
    elif bad in {'negative-x','bool-x'}:
        action['targets']['x_value'] = -1 if bad == 'negative-x' else True
    elif bad == 'no-white-mana':
        state.players[seat].mana_pool = {}
    elif bad == 'wrong-actor':
        actor = 3-seat
    elif bad == 'ai-controller':
        controller.controllers[seat] = 'ai'
    install(controller, state)
    rejected(client, controller, action, player_id=actor)


@pytest.mark.parametrize('seat', [1, 2])
def test_unrelated_finite_cost_rejects_pitch_field_then_pays_normally(game, seat):
    client, controller = game
    state, spell, _, victim, _, action = finite_setup(seat, 'familiar', True)
    install(controller, state)
    invalid = deepcopy(action)
    invalid['cost_choice']['exile_card_ids'] = []
    rejected(client, controller, invalid, player_id=seat)
    response = client.post(f'/matches/{state.id}/action',
                           json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert controller.state.cards[spell.id].zone == Zone.STACK
    assert controller.state.cards[victim.id].zone == Zone.GRAVEYARD
