"""Paid canonical Flicker domain/choice HTTP with exclusively owned SQL."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.test_cloudshift_compound_audit import cold_sql
from tests.test_paid_counter_family_audit import http_position
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_flicker_nontoken_domain import position, KINDS, EXTRA, raw_card, search_raw, snap


def install(repo, client, seat, kind='Creature'):
    import main
    controller, _, _, path = http_position(repo, client, seat, 'Fertilid')
    state, target, spell = position(seat, kind, foreign=True)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return state, target, spell, path


def restore(repo, state):
    import main
    controller = main.ACTIVE_MATCHES[state.id]
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    cold_sql(repo, state.id, before[:2])
    main.ACTIVE_MATCHES.pop(state.id)
    main._restore_active_matches(repo, state.id)
    controller = main.ACTIVE_MATCHES[state.id]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    return controller.state


def send(client, path, actor, action):
    import main
    response = client.post(path + '/action', json={'player_id': actor, 'action': action})
    assert response.status_code == 200, response.text
    return main.ACTIVE_MATCHES[path.rsplit('/', 1)[-1]].state


def cast_request(spell, target):
    return {'type': 'cast_spell', 'card_id': spell, 'cost_choice': {'id': 'base'},
            'targets': {'target_card_id': target}}


def resolve(client, path, state):
    for _ in range(2):
        state = send(client, path, state.priority_player, {'type': 'pass_priority'})
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', KINDS)
def test_full_domain_paid_http_foreign_owner_exact_new_object_cold_restart(repo, client, seat, kind):
    state, target, spell, path = install(repo, client, seat, kind)
    sequence = state.cards[target].zone_change_sequence
    state = send(client, path, seat, cast_request(spell, target))
    assert state.stack[-1].controller == seat
    assert state.stack[-1].payload['mana_spent'] == 2
    assert state.stack[-1].payload['requires_nontoken'] is True
    state = resolve(client, path, restore(repo, state))
    card = state.cards[target]
    assert card.zone == Zone.BATTLEFIELD and card.owner == card.controller == 3-seat
    assert card.zone_change_sequence == sequence + 2
    assert card.summoning_sick and not card.is_token
    assert sum(target in player.battlefield for player in state.players.values()) == 1
    assert target not in state.players[3-seat].exile
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert_private(restore(repo, state))


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_actual_token_http_rejects_entire_root_controller_sql(repo, client, seat):
    import main
    state, _, spell, path = install(repo, client, seat)
    producer = raw_card(state, EXTRA['raise-the-alarm'], seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 2, 'C': 2}
    main._persist_active_match(repo, main.ACTIVE_MATCHES[state.id])
    state = send(client, path, seat, {'type': 'cast_spell', 'card_id': producer,
                                     'cost_choice': {'id': 'base'}})
    state = resolve(client, path, state)
    token = next(cid for cid in state.players[seat].battlefield if state.cards[cid].is_token)
    controller = main.ACTIVE_MATCHES[state.id]
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post(path + '/action', json={'player_id': seat,
                                                  'action': cast_request(spell, token)})
    assert response.status_code == 422, response.text
    controller = main.ACTIVE_MATCHES[state.id]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    assert_private(restore(repo, controller.state))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pay', [False, True])
def test_actual_foreign_owner_entry_choice_http_paused_sql_resume_once(repo, client, seat, pay):
    import main
    state, _, spell, path = install(repo, client, seat)
    land = raw_card(state, search_raw('breeding-pool'), seat, Zone.BATTLEFIELD)
    land.owner = 3-seat
    sequence = land.zone_change_sequence
    life = {pid: player.life for pid, player in state.players.items()}
    main._persist_active_match(repo, main.ACTIVE_MATCHES[state.id])
    state = send(client, path, seat, cast_request(spell, land.id))
    state = resolve(client, path, restore(repo, state))
    assert state.cards[land.id].zone == Zone.EXILE
    assert state.cards[land.id].zone_change_sequence == sequence + 1
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    state = restore(repo, state)
    controller = main.ACTIVE_MATCHES[state.id]
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post(path + '/action', json={'player_id': seat, 'action': {
        'type': 'choose_mechanic', 'choice_id': 'pay_two_life'}})
    assert response.status_code == 422, response.text
    controller = main.ACTIVE_MATCHES[state.id]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    state = send(client, path, 3-seat, {'type': 'choose_mechanic',
                                       'choice_id': 'pay_two_life' if pay else 'tapped'})
    assert state.pending_mechanic_choice is None
    assert state.cards[land.id].zone == Zone.BATTLEFIELD
    assert state.cards[land.id].owner == state.cards[land.id].controller == 3-seat
    assert state.cards[land.id].zone_change_sequence == sequence + 2
    assert state.cards[land.id].tapped == (not pay)
    assert state.players[3-seat].life == life[3-seat] - 2 * pay
    assert state.players[seat].life == life[seat]
    assert sum(land.id in player.battlefield for player in state.players.values()) == 1
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert_private(restore(repo, state))
