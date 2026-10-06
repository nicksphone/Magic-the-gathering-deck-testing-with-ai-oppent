"""Actual HTTP actions and fresh-process resume of admitted queues/choices."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


def run(phase, seat, mode, root):
    import persistence.db as db
    from sqlmodel import create_engine, Session
    db.DATABASE_PATH = root / 'owned.sqlite'
    db.DATABASE_URL = 'sqlite:///' + str(db.DATABASE_PATH)
    db.engine = create_engine(db.DATABASE_URL, connect_args={'check_same_thread': False})

    def audit(event, args):
        if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
            address = str(args[0])
            if address.startswith('file:'):
                address = unquote(urlsplit(address).path)
            assert Path(address).resolve().is_relative_to(root.resolve()), address
        if event in {'socket.connect', 'socket.bind'}:
            raise AssertionError('No network/listeners')
    sys.addaudithook(audit)
    from card_data.sync import ScryfallSyncService
    def forbidden(*a, **k):
        raise AssertionError('No remote sync')
    ScryfallSyncService.sync_card_by_name = forbidden
    from fastapi.testclient import TestClient
    from game_state.serializers import serialize_match_snapshot
    from game_state.state import Step, Zone
    from persistence.repository import Repository
    from tests.queued_sequence_support import add, facts, position, seed_cache
    import main

    def wire(value):
        return json.loads(json.dumps(value))
    def sql_facts():
        with db.engine.connect() as connection:
            return list(connection.connection.driver_connection.iterdump())

    evidence = {'phase': phase, 'seat': seat, 'mode': mode, 'pid': os.getpid(),
                'transport': 'actual FastAPI TestClient startup/actions/restore',
                'extra_sequence_execution_certified': False,
                'qualified_schema_execution': True}
    with TestClient(main.app) as client:
        serial = 0
        first_request = None
        def post(action, player=None):
            nonlocal serial, first_request
            serial += 1
            body = {
                'player_id': controller.state.priority_player if player is None else player,
                'action': action}
            headers = {'Idempotency-Key': phase + '-action-' + str(serial),
                       'X-Match-Revision': str(controller.revision)}
            response = client.post('/matches/' + controller.state.id + '/action', json=body, headers=headers)
            assert response.status_code == 200, response.text
            if first_request is None:
                first_request = {'body': body, 'headers': headers, 'response': response.json()}
            return response
        def passes():
            post({'type': 'pass_priority'})
            post({'type': 'pass_priority'})
        if phase == 'seed':
            with Session(db.engine) as session:
                seed_cache(Repository(session))
            deck = [{'card_name': 'Island', 'quantity': 7}, {'card_name': 'Time Warp', 'quantity': 1}]
            response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7214},
                headers={'Idempotency-Key': 'queue-start'})
            assert response.status_code == 200, response.text
            controller = main.ACTIVE_MATCHES[response.json()['id']]
            state = position(seat)
            state.id = controller.state.id
            state.priority_stops = {1: set(Step), 2: set(Step)}
            state.mechanic_choice_players = {1, 2}
            source = add(state, 'Time Warp' if mode in ('turn', 'pending') else 'Aggravated Assault', seat,
                         Zone.HAND if mode in ('turn', 'pending') else Zone.BATTLEFIELD)
            creature = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
            creature.tapped = True
            if mode == 'pending':
                add(state, 'Opt', seat)
            controller.state = state
            with Session(db.engine) as session:
                main._persist_active_match(Repository(session), controller)
            root_before = facts(state)
            post({'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_player': seat}}
                 if mode in ('turn', 'pending') else
                 {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}, seat)
            assert sum(controller.state.players[seat].mana_pool.values()) == sum(root_before['players'][seat]['mana_pool'].values()) - 5
            assert controller.state.stack
            passes()
            state = controller.state
            if mode in ('turn', 'pending'):
                assert len(state.extra_turns) == 1
            else:
                assert len([r for r in state.phase_plan if r['group']]) == 2
                assert not state.cards[creature.id].tapped and state.cards[creature.id].summoning_sick
            if mode == 'midphase':
                passes()
                assert controller.state.step == Step.BEGIN_COMBAT
            if mode == 'pending':
                opt = next(state.cards[c] for c in state.players[seat].hand if state.cards[c].name == 'Opt')
                post({'type': 'cast_spell', 'card_id': opt.id}, seat)
                passes()
                assert controller.state.pending_mechanic_choice['kind'] == 'scry'
            saved = {'mid': state.id, 'creature': creature.id,
                     'accepted_request': first_request,
                     'snapshot': wire(serialize_match_snapshot(controller.state)),
                     'config': wire(main._controller_snapshot(controller)),
                     'rng': wire(controller.state.rng.getstate())}
            (root / 'expected.json').write_text(json.dumps(saved, sort_keys=True))
        else:
            saved = json.loads((root / 'expected.json').read_text())
            listed = client.get('/matches')
            assert listed.status_code == 200, listed.text
            assert saved['mid'] in {item['id'] for item in listed.json()}
            restored = client.get('/matches/' + saved['mid'])
            assert restored.status_code == 200, restored.text
            controller = main.ACTIVE_MATCHES[saved['mid']]
            assert wire(serialize_match_snapshot(controller.state)) == saved['snapshot']
            assert wire(main._controller_snapshot(controller)) == saved['config']
            assert wire(controller.state.rng.getstate()) == saved['rng']
            evidence['restored_snapshot_config_rng_receipts_exact'] = True
            before = facts(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts()
            diagnostic = client.get('/matches/' + saved['mid'] + '/rules-diagnostics')
            assert diagnostic.status_code == 200, diagnostic.text
            view = client.get('/matches/' + saved['mid'])
            assert view.status_code == 200, view.text
            assert (facts(controller.state), main._controller_snapshot(controller), sql_facts()) == before
            evidence['diagnostic_and_reads_root_sql_config_rng_exact'] = True
            receipt = saved['accepted_request']
            retry = client.post('/matches/' + saved['mid'] + '/action',
                                json=receipt['body'], headers=receipt['headers'])
            assert retry.status_code == 200 and retry.json() == view.json(), retry.text
            assert (facts(controller.state), main._controller_snapshot(controller), sql_facts()) == before
            evidence['idempotent_restore_does_not_duplicate_queue'] = True
            rejected = client.post('/matches/' + saved['mid'] + '/action', json={
                'player_id': seat, 'action': {'type': 'cast_spell', 'card_id': 'missing-source'}})
            assert rejected.status_code == 422, rejected.text
            assert (facts(controller.state), main._controller_snapshot(controller), sql_facts()) == before
            evidence['invalid_action_existing_queue_root_sql_rng_config_exact'] = True
            if mode == 'pending':
                pending = controller.state.pending_mechanic_choice
                assert pending['player_id'] == seat and pending['kind'] == 'scry'
                # Shared human HTTP surface is not an authenticated per-seat view.
                # Check the actual actor-private policy view, without changing it.
                from ai.information import decision_view, is_unknown
                from rules_engine.engine import RulesEngine
                before_private = facts(controller.state)
                owner, _ = decision_view(controller.state, seat, RulesEngine().legal_moves(controller.state, seat))
                opponent, _ = decision_view(controller.state, 3 - seat, [])
                for cid in pending['options']:
                    assert not is_unknown(owner.cards[cid]) and is_unknown(opponent.cards[cid])
                assert facts(controller.state) == before_private
                evidence['actor_private_inspection_identity_boundary'] = True
                post({'type': 'choose_mechanic', 'card_ids': []}, seat)
                assert not controller.state.pending_mechanic_choice
                assert len(controller.state.extra_turns) == 1
            visits = []
            for _ in range(64):
                state = controller.state
                visits.append([state.turn, state.active_player, state.step.value,
                    state.phase_plan[state.phase_cursor]['visit'] if state.phase_plan else None])
                if state.turn > 5 and state.step == Step.UPKEEP:
                    break
                passes()
            else:
                raise AssertionError('Bounded real action progression did not reach next upkeep')
            state = controller.state
            assert state.active_player == (seat if mode in ('turn', 'pending') else 3 - seat)
            assert state.turn == 6
            if mode in ('turn', 'pending'):
                assert not state.cards[saved['creature']].tapped and not state.cards[saved['creature']].summoning_sick
                assert not state.extra_turns
            else:
                combat_visits = {v[3] for v in visits if v[2] == 'begin_combat'}
                assert len(combat_visits) == 2  # Inserted visit plus preserved ordinary combat.
            evidence['actual_http_progression'] = visits
            evidence['resume_did_not_repeat_resolution_or_entry'] = True
        evidence['snapshot'] = wire(serialize_match_snapshot(controller.state))
    db.engine.dispose()
    (root / (phase + '-evidence.json')).write_text(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == '__main__':
    run(sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
