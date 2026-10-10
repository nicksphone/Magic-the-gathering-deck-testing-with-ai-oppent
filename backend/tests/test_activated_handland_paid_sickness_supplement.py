"""Bare availability and real paid HTTP casts; strict reject expectations only."""
from urllib.parse import quote

import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine.costs import activated_cost_available
from tests.test_activated_handland_instruction_audit import setup, FAMILIES
from tests.test_activated_handland_http_audit import server
from tests.test_private_choice_http_restart import stable


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_bare_source_tap_availability_rejects_sickness_without_query_mutation(seat, family):
    state, source, _, _ = setup(family, seat, sick=True)
    before = serialize_match_snapshot(state)
    available = activated_cost_available(state, seat, source.id, '{T}', ability_index=0)
    assert serialize_match_snapshot(state) == before
    assert not available, 'Bare helper admits a sick Creature source tap cost'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_actual_paid_http_cast_then_sick_tap_rejects_full_root_sql_after_restart(server, seat, family):
    status, data = server.call('/fixture/paid-activated-handland?family=' + quote(family) + f'&seat={seat}', {})
    assert status == 200
    base = '/matches/' + data['id']
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': {
        'type': 'cast_spell', 'card_id': data['source_id'], 'cost_choice': {'id': 'base'}}})
    assert status == 200
    announced = server.audit(data['id'])
    assert announced['state']['stack'][-1]['payload']['mana_spent'] == (1 if family == 'Sakura-Tribe Scout' else 2)
    for _ in range(8):
        current = server.audit(data['id'])
        if not current['state']['stack']:
            break
        status, _ = server.call(base + '/action', {'player_id': current['state']['priority_player'],
                                                  'action': {'type': 'pass_priority'}})
        assert status == 200
    before = server.audit(data['id'])
    assert not before['state']['stack']
    card = before['state']['cards'][data['source_id']]
    assert card['summoning_sick'] and not card['tapped']
    assert data['source_id'] in before['state']['players'][str(seat)]['battlefield']
    before = server.restart(data['id'], before)
    assert stable(server.audit(data['id'])) == stable(before)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': {
        'type': 'activate_ability', 'card_id': data['source_id'], 'ability_index': 0, 'targets': {}}})
    after = server.audit(data['id'])
    assert status == 422, 'Actual paid creature cast can immediately tap despite sickness'
    assert stable(after) == stable(before)
