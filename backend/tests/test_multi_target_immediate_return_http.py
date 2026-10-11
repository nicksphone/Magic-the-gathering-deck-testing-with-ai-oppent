"""Real typed HTTP, private actor views, and owned SQLite batch continuations."""
from copy import deepcopy

import pytest

from ai.information import decision_view, is_unknown
from rules_engine.engine import RulesEngine

from game_state.state import Zone
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.test_paid_counter_family_audit import http_position
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_multi_target_immediate_return import case, canonical, raw_card
from game_state.serializers import serialize_match_snapshot


def install(repo, client, seat):
    import main
    controller, _, _, path = http_position(repo, client, seat, 'Fertilid')
    state, targets, spell = case(seat, foreign=True)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return state, targets, spell, path


def send(client, path, seat, action):
    import main
    response = client.post(path + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    return main.ACTIVE_MATCHES[path.rsplit('/', 1)[-1]].state


def restore(repo, state):
    import main
    controller = main.ACTIVE_MATCHES[state.id]
    before = (serialize_match_snapshot(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo))
    main.ACTIVE_MATCHES.pop(state.id)
    main._restore_active_matches(repo, state.id)
    controller = main.ACTIVE_MATCHES[state.id]
    assert (serialize_match_snapshot(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    return controller.state


def resolve(client, path, state):
    for _ in range(2):
        state = send(client, path, state.priority_player, {'type': 'pass_priority'})
    return state


def request(spell, targets):
    return {'type': 'cast_spell', 'card_id': spell, 'cost_choice': {'id': 'base'},
            'targets': {'target_card_ids': targets}}


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_foreign_owner_batch_http_restore_and_private_views(repo, client, seat):
    state, targets, spell, path = install(repo, client, seat)
    state = send(client, path, seat, request(spell, targets))
    assert state.stack[-1].payload['mana_spent'] == 3
    state = resolve(client, path, restore(repo, state))
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].controller == seat
               and state.cards[cid].owner == 3-seat and state.cards[cid].zone_change_sequence == 3
               for cid in targets)
    assert state.cards[targets[0]].counters['+1/+1'] == 2
    assert state.cards[targets[1]].counters.get('+1/+1', 0) == 0
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert_private(restore(repo, state))


@pytest.mark.parametrize('seat', [1, 2])
def test_batch_entry_choice_http_restores_both_exiled_and_commits_once(repo, client, seat):
    import main
    state, targets, spell, path = install(repo, client, seat)
    shock = raw_card(state, canonical('targeted_search_resolver/breeding-pool.json'), seat, Zone.BATTLEFIELD)
    shock.owner = 3-seat
    targets[1] = shock.id
    main._persist_active_match(repo, main.ACTIVE_MATCHES[state.id])
    life = state.players[seat].life
    state = resolve(client, path, send(client, path, seat, request(spell, targets)))
    assert all(state.cards[cid].zone == Zone.EXILE for cid in targets)
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    assert state.pending_mechanic_choice['player_id'] == seat
    state = restore(repo, state)
    state = send(client, path, seat, {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'})
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in targets)
    assert state.players[seat].life == life - 2
    assert not state.cards[shock.id].tapped
    assert state.cards[spell].zone == Zone.GRAVEYARD and not state.pending_mechanic_choice
    assert_private(restore(repo, state))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['duplicate', 'wrong_seat'])
def test_invalid_batch_http_keeps_complete_root_controller_and_sql(repo, client, seat, invalid):
    import main
    state, targets, spell, path = install(repo, client, seat)
    controller = main.ACTIVE_MATCHES[state.id]
    before = (serialize_match_snapshot(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo))
    response = client.post(path + '/action', json={
        'player_id': 3-seat if invalid == 'wrong_seat' else seat,
        'action': request(spell, targets if invalid == 'wrong_seat' else targets[:1] * 2)})
    assert response.status_code == 422, response.text
    controller = main.ACTIVE_MATCHES[state.id]
    assert (serialize_match_snapshot(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    assert_private(restore(repo, controller.state))


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_bounce_http_filters_one_target_after_sql_restore(repo, client, seat):
    import main
    state, targets, spell, path = install(repo, client, seat)
    bounce = raw_card(state, canonical('immediate_return_product/unsummon.json'), seat, Zone.HAND).id
    state.players[seat].mana_pool = {'U': 2, 'C': 2}
    main._persist_active_match(repo, main.ACTIVE_MATCHES[state.id])
    state = send(client, path, seat, request(spell, targets))
    state = send(client, path, seat, {'type': 'cast_spell', 'card_id': bounce,
                                     'targets': {'target_card_id': targets[0]}})
    state = resolve(client, path, state)
    assert state.cards[targets[0]].zone == Zone.HAND
    state = resolve(client, path, restore(repo, state))
    assert state.cards[targets[0]].zone == Zone.HAND and state.cards[targets[0]].zone_change_sequence == 2
    assert state.cards[targets[1]].zone == Zone.BATTLEFIELD and state.cards[targets[1]].zone_change_sequence == 3
    assert state.cards[spell].zone == Zone.GRAVEYARD
    state = restore(repo, state)
    for actor in (1, 2):
        view, _ = decision_view(state, actor, RulesEngine().legal_moves(state, actor))
        # A public battlefield card bounced to hand remains remembered, not unknown.
        assert not is_unknown(view.cards[targets[0]])
        assert view.cards[targets[0]].name == 'Fertilid'
        hidden = state.players[3-actor].hand + state.players[3-actor].library
        assert all(is_unknown(view.cards[cid]) for cid in hidden if cid != targets[0])
