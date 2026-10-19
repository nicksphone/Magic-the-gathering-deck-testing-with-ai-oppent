"""Offline raw HTTP optional-observer decisions, durable retry and rejection."""
from copy import deepcopy
import json

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.test_library_reorder import FIXTURES
from tests.readiness_rules_seam_support import normalize
from tests.spell_admission_safety_support import seed_cache
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_shuffle_observer_audit import prepare, snap


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_raw_http_cosi_after_draw_optional_restart_private_and_idempotent(repo, client, seat, accept):
    import main
    seed_cache(repo)
    repo.upsert_card(normalize(json.loads((FIXTURES / 'ponder.json').read_text())))
    deck = [{'card_name': 'Island', 'quantity': 7}, {'card_name': 'Ponder', 'quantity': 1}]
    response = client.post('/matches/start', json={
        'deck_a': deck, 'deck_b': deck, 'sandbox': True,
        'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200, response.text
    identifier = response.json()['id']
    controller = main.ACTIVE_MATCHES[identifier]
    state, spell, source = prepare('Ponder', seat, "Cosi's Trickster")
    # Canonical retained board setup; all spell/payment/choice transitions below are HTTP.
    state.id = identifier
    controller.state = state
    main._persist_active_match(repo, controller)

    def current():
        return main.ACTIVE_MATCHES[identifier].state

    def post(actor, action, key=None):
        revision = main.ACTIVE_MATCHES[identifier].revision
        headers = {'Idempotency-Key': key or f'cosi-{revision}', 'X-Match-Revision': str(revision)}
        value = client.post(f'/matches/{identifier}/action', json={'player_id': actor, 'action': action}, headers=headers)
        assert value.status_code == 200, value.text
        return headers

    def reload():
        expected = snap(current())
        main.ACTIVE_MATCHES.clear()
        main._restore_active_matches(repo, identifier)
        assert snap(current()) == expected

    post(seat, {'type': 'cast_spell', 'card_id': spell})
    assert current().players[seat].mana_pool.get('U', 0) == 0
    for _ in range(2):
        post(current().priority_player, {'type': 'pass_priority'})
    reload()
    inspected = current().pending_mechanic_choice['options']
    post(seat, {'type': 'choose_mechanic', 'card_ids': list(reversed(inspected))})
    reload()
    post(seat, {'type': 'choose_mechanic', 'card_ids': ['shuffle']})
    assert current().cards[spell].zone == Zone.GRAVEYARD
    assert len(current().players[seat].hand) == 1 and not current().cards[source].counters
    assert current().stack[-1].payload['__shuffle_cause']['source_card_id'] == spell
    foreign, _ = decision_view(current(), 3-seat, RulesEngine().legal_moves(current(), 3-seat))
    assert all(is_unknown(foreign.cards[cid]) for cid in current().players[seat].hand + current().players[seat].library)
    assert current().stack[-1].payload['target_card_id'] == source
    for _ in range(2):
        post(current().priority_player, {'type': 'pass_priority'})
    reload()
    assert current().pending_trigger_order['phase'] == 'optional'
    offered = client.get(f'/matches/{identifier}/legal-moves?player_id={3-seat}')
    assert offered.status_code == 200
    action = next(move for move in RulesEngine().legal_moves(current(), 3-seat) if move['accept'] == accept)
    before = (snap(current()), deepcopy(main._controller_snapshot(main.ACTIVE_MATCHES[identifier])), sql_facts(repo))
    rejected = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert rejected.status_code == 422
    assert (snap(current()), main._controller_snapshot(main.ACTIVE_MATCHES[identifier]), sql_facts(repo)) == before
    headers = post(3-seat, action, 'cosi-final-optional')
    after = (snap(current()), deepcopy(main._controller_snapshot(main.ACTIVE_MATCHES[identifier])), sql_facts(repo))
    reload()
    replay = client.post(f'/matches/{identifier}/action', json={'player_id': 3-seat, 'action': action}, headers=headers)
    assert replay.status_code == 200, replay.text
    assert (snap(current()), main._controller_snapshot(main.ACTIVE_MATCHES[identifier]), sql_facts(repo)) == after
    assert current().cards[source].counters.get('+1/+1', 0) == int(accept)
    assert not current().stack and not current().pending_trigger_order
