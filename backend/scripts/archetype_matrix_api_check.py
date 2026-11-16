"""Selected imported engine boundaries through real handlers and owned SQLite.

This is not HTTP/browser transport or a continuous API-played game. The checked
transition is observed before application bookkeeping; none of its fields are
normalized. Application bookkeeping is then verified by its own exact saved
state/controller roundtrip and original-key retry.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path

from scripts.archetype_matrix_game import TraceDivergence, plain, snapshot
from scripts.archetype_matrix_plan import digest


class HandlerChecks:
    def __init__(self, database):
        self.path = Path(database)
        self.stack = ExitStack()

    def __enter__(self):
        from sqlmodel import SQLModel, create_engine
        import main
        import persistence.db as db
        from persistence.capacity import DatabaseOwner, initialize_capacity
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError('Handler parity database must be new')
        try:
            self.main = main
            self.engine = create_engine('sqlite:///' + str(self.path))
            self.stack.callback(self.engine.dispose)
            for module, name, value in ((main, 'engine', self.engine),
                                        (db, 'engine', self.engine),
                                        (main, 'ACTIVE_MATCHES', {})):
                original = getattr(module, name)
                setattr(module, name, value)
                self.stack.callback(setattr, module, name, original)
            owner = DatabaseOwner(self.engine).acquire()
            def close_owner():
                owner.fence_admission()
                owner.drain_producers(timeout=5)
                owner.close()
            self.stack.callback(close_owner)
            SQLModel.metadata.create_all(self.engine, tables=[table
                for table in SQLModel.metadata.sorted_tables
                if table.name not in {'resourcecapacity', 'resourcereservation'}])
            initialize_capacity(owner, self.path.with_suffix('.before-capacity.db'))
            owner.open_admission()
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def __call__(self, initial, row):
        from ai.agent import AIAgent
        from ai.deck_analysis import guess_archetype
        from game_state.serializers import deserialize_match_snapshot
        from persistence.repository import Repository
        from rules_engine.engine import RulesEngine
        from sqlmodel import Session
        from starlette.requests import Request
        app, step = self.main, row['step']
        state = deserialize_match_snapshot(deepcopy(row['before']))
        if digest(snapshot(state)) != digest(row['before']):
            raise TraceDivergence(step, ['handler_initial_roundtrip'])
        boards = {1: initial['deck_a'], 2: initial['deck_b']}
        controller = app.MatchController(state=state, rules=RulesEngine(),
            controllers={1: 'human', 2: 'human'},
            ai={pid: AIAgent(difficulty='master', archetype=guess_archetype(boards[pid]),
                            opponent_archetype=guess_archetype(boards[3-pid])) for pid in (1, 2)},
            mode='human_vs_human', deck_ids=(None, None), mainboards=deepcopy(boards),
            sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
            match_complete=False, best_of=1, root_seed=initial['seed'], revision=step)
        app.ACTIVE_MATCHES[state.id] = controller
        payload = app.ActionRequest.model_validate({'player_id': row['actor'], 'action': row['action']})
        request = Request({'type': 'http', 'headers': [
            (b'idempotency-key', f'pilot-boundary-{step}'.encode()),
            (b'x-match-revision', str(step).encode())]})
        observed, original = [], app.checked_action
        def checked(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(snapshot(result))
            return result
        with Session(self.engine) as session:
            repo = Repository(session)
            # Import a trusted engine boundary exactly, without invoking the
            # app's _remember_public_types before observing the transition.
            repo.save_active_match(state.id, json.dumps(row['before']),
                                   json.dumps(app._controller_snapshot(controller)))
            app.checked_action = checked
            try:
                response = app.take_action(state.id, payload, repo, request)
            finally:
                app.checked_action = original
            if len(observed) != 1 or digest(observed[0]) != digest(row['after']):
                raise TraceDivergence(step, ['handler_checked_transition'])
            expected_state = snapshot(controller.state)
            expected_controller = plain(app._controller_snapshot(controller))
            session.expire_all()
            stored = repo.get_active_match(state.id)
            raw = (stored.state_json, stored.controller_json)
            if (digest(json.loads(raw[0])) != digest(expected_state)
                    or digest(json.loads(raw[1])) != digest(expected_controller)):
                raise TraceDivergence(step, ['handler_persistence'])
            app.ACTIVE_MATCHES.pop(state.id)
            app._restore_active_matches(repo, state.id)
            restored = app.ACTIVE_MATCHES[state.id]
            if (digest(snapshot(restored.state)) != digest(expected_state)
                    or digest(app._controller_snapshot(restored)) != digest(expected_controller)):
                raise TraceDivergence(step, ['handler_sqlite_roundtrip'])
            retry = app.take_action(state.id, payload, repo, request)
            session.expire_all()
            saved = repo.get_active_match(state.id)
            if (digest(retry) != digest(response) or
                    (saved.state_json, saved.controller_json) != raw):
                raise TraceDivergence(step, ['handler_original_key_retry'])
        return {'step': step, 'transition_equal': True, 'sqlite_roundtrip': True,
                'original_key_retry': True, 'transport': 'direct_handler',
                'continuous_api_game': False,
                'application_snapshot_sha256': digest(expected_state),
                'controller_sha256': digest(expected_controller)}
