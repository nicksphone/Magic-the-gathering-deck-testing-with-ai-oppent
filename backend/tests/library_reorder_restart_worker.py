"""Use the existing owned-DB/network-guarded process harness for real choices."""
from copy import deepcopy
import json


def reorder_flow(client, phase, seat, name, root, evidence):
    import main
    import persistence.db as db
    from sqlmodel import Session
    from persistence.repository import Repository
    from game_state.serializers import serialize_match_snapshot
    from game_state.state import Zone
    from tests.test_library_reorder import setup, FIXTURES
    from tests.readiness_rules_seam_support import normalize
    from tests.spell_admission_safety_support import seed_cache

    def wire(value):
        return json.loads(json.dumps(value))

    def post(identifier, actor, action):
        revision = main.ACTIVE_MATCHES[identifier].revision
        response = client.post(f'/matches/{identifier}/action', json={'player_id': actor, 'action': action},
                               headers={'Idempotency-Key': f'reorder-{revision}', 'X-Match-Revision': str(revision)})
        assert response.status_code == 200, response.text

    if phase == 'seed':
        with Session(db.engine) as session:
            repo = Repository(session)
            seed_cache(repo)
            repo.upsert_card(normalize(json.loads((FIXTURES / (name.lower() + '.json')).read_text())))
        deck = [{'card_name': 'Island', 'quantity': 7}, {'card_name': name, 'quantity': 1}]
        response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'sandbox': True,
                               'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
        assert response.status_code == 200, response.text
        identifier = response.json()['id']
        controller = main.ACTIVE_MATCHES[identifier]
        state, source = setup(name, seat)
        state.id = identifier
        controller.state = state
        with Session(db.engine) as session:
            main._persist_active_match(Repository(session), controller)
        post(identifier, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
        for _ in range(2):
            post(identifier, main.ACTIVE_MATCHES[identifier].state.priority_player, {'type': 'pass_priority'})
        controller = main.ACTIVE_MATCHES[identifier]
        order = list(reversed(controller.state.pending_mechanic_choice['options']))
        if name == 'Ponder':
            post(identifier, seat, {'type': 'choose_mechanic', 'card_ids': order})
            assert controller.state.pending_mechanic_choice['kind'] == 'library_shuffle'
        saved = {'id': identifier, 'source': source.id, 'order': order,
                 'snapshot': wire(serialize_match_snapshot(controller.state)),
                 'config': wire(main._controller_snapshot(controller)),
                 'rng': wire(controller.state.rng.getstate())}
        (root / 'reorder-expected.json').write_text(json.dumps(saved, sort_keys=True))
    else:
        saved = json.loads((root / 'reorder-expected.json').read_text())
        identifier = saved['id']
        response = client.get(f'/matches/{identifier}')
        assert response.status_code == 200, response.text
        controller = main.ACTIVE_MATCHES[identifier]
        assert wire(serialize_match_snapshot(controller.state)) == saved['snapshot']
        assert wire(main._controller_snapshot(controller)) == saved['config']
        assert wire(controller.state.rng.getstate()) == saved['rng']
        evidence['restored_snapshot_config_rng_exact'] = True
        action = {'type': 'choose_mechanic', 'card_ids': ['keep'] if name == 'Ponder' else saved['order']}
        post(identifier, seat, action)
        state = controller.state
        assert state.pending_mechanic_choice is None
        assert state.cards[saved['source']].zone == Zone.GRAVEYARD
        if name == 'Ponder':
            assert state.players[seat].hand == [saved['order'][0]]
        else:
            assert state.players[seat].library[-len(saved['order']):] == list(reversed(saved['order']))
        evidence['actual_order_draw_and_source_departure'] = True
    evidence['library_resolution_certified'] = True
