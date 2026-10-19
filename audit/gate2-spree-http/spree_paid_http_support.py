"""NEW declared canonical initial position, followed only by real paid HTTP actions."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from contextlib import closing

from fastapi.testclient import TestClient
from sqlmodel import Session
import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import DATABASE_PATH, engine
from persistence.capacity import _OWNERS, owner_for_engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from rules_engine.spree import parse
import domain_paid_support as g

HERE = Path(__file__).parent / 'fixtures/spree_http'
CASES = {(actor, mode, copy) for actor in (1, 2) for mode in (0, 1, 2)
         for copy in (('keep', 'new') if mode in (0, 2) else ('none',))}
PHASES = {'initial', 'paid', 'pending', 'restored', 'copy-choice', 'change-choice', 'removed-alt', 'terminal'}


def canonical_facts():
    facts = json.loads((HERE / 'canonical.json').read_bytes())
    provenance = json.loads((HERE / 'provenance.json').read_bytes())
    for name, raw in facts.items():
        blob = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(blob).hexdigest() == provenance['cards'][name]['canonical_fullrowSHA']
    return facts


def prepared_position(facts, actor, reserve_bolt=False):
    """Initial paid Storm trigger is real checked_action setup, not an HTTP claim."""
    source_actor = 3 - actor
    state = g.position(facts, source_actor)
    old_target = g.add(state, facts, 'Raging Goblin', actor)
    alternate = g.add(state, facts, 'Raging Goblin', actor)
    g.add(state, facts, 'Raging Goblin', source_actor)
    source = g.add(state, facts, 'Volatile Stormdrake', source_actor, Zone.HAND)
    state.players[source_actor].mana_pool = {'C': 1, 'U': 1}
    state = g.cast(state, source_actor, source)
    assert state.stack[-1].payload['mana_spent'] == 2
    for _ in range(16):
        if state.cards[source].zone == Zone.BATTLEFIELD:
            break
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        state = g.act(state, state.priority_player, 'pass_priority')
    else:
        raise AssertionError('Actual paid Storm entry did not finish in16 actions')
    move = next(m for m in RulesEngine().legal_moves(state, source_actor)
                if m['type'] == 'choose_trigger_target' and m.get('target_card_id') == old_target)
    state = g.act(state, source_actor, 'choose_trigger_target', stack_id=move['stack_id'], target_card_id=old_target)
    target_stack = next(i.id for i in state.stack if i.source_card_id == source)
    state = g.respond(state, actor)
    favor = g.add(state, facts, 'Return the Favor', actor, Zone.HAND)
    hidden = g.add(state, facts, 'Forest', source_actor, Zone.HAND)
    bolt = g.add(state, facts, 'Lightning Bolt', actor, Zone.HAND) if reserve_bolt else None
    state.players[source_actor].mana_pool.clear()
    return state, favor, target_stack, old_target, alternate, hidden, bolt


class SpreeCase:
    def __init__(self, actor, mode, copy='none', no_alternative=False):
        assert (actor, mode, copy) in CASES
        assert not no_alternative or (mode == 1 and copy == 'none')
        self.actor, self.mode, self.copy = actor, mode, copy
        self.no_alternative = no_alternative
        self.case_id = f'actor{actor}-mode{mode}-copy-{copy}' + ('-no-alternative' if no_alternative else '')
        self.client = None
        self.epochs = []
        self.actions = 0
        self.http_requests = []
        self.emitted_phases = set()
        self.restored = False
        self.old_matches = dict(main.ACTIVE_MATCHES)

    @property
    def controller(self):
        return main.ACTIVE_MATCHES[self.mid]

    @property
    def state(self):
        return self.controller.state

    def open(self):
        assert self.client is None
        client = TestClient(main.app)
        client.__enter__()
        self.client = client
        owner = owner_for_engine(engine)
        assert owner.fd is not None and _OWNERS.get(engine) is owner
        self.epochs.append(owner.epoch)

    def close(self):
        assert self.client is not None
        owner = owner_for_engine(engine)
        self.client.__exit__(None, None, None)
        self.client = None
        assert owner.fd is None and engine not in _OWNERS
        assert not main.SIM_JOB_WORKERS and engine.pool.checkedout() == 0

    def __enter__(self):
        try:
            return self.start()
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def start(self):
        self.open()
        deck = [{'quantity': 60, 'card_name': 'Island'}]
        payload = {'deck_a': deck, 'deck_b': deck, 'mode': 'player_vs_ai', 'seed': 4,
                   'controller_a': 'human' if self.actor == 1 else 'ai',
                   'controller_b': 'human' if self.actor == 2 else 'ai', 'ai_difficulty': 'casual'}
        response = self.request('POST', '/matches/start', json=payload)
        assert response.status_code == 200, response.text
        self.mid = response.json()['id']
        assert self.controller.controllers == {self.actor: 'human', 3-self.actor: 'ai'}
        facts = canonical_facts()
        state, self.favor, self.original, self.old_target, self.alternate, self.hidden, self.bolt = prepared_position(
            facts, self.actor, reserve_bolt=self.no_alternative)
        state.id = self.mid
        total = 4 if self.mode == 2 else 3
        state.players[self.actor].mana_pool = {'C': total-2, 'R': 2 + int(self.no_alternative)}
        self.controller.state = state
        with Session(engine) as session:
            main._persist_active_match(Repository(session), self.controller)
        self.emit('initial')
        return self

    def __exit__(self, kind, error, trace):
        try:
            if kind is not None and 'terminal' not in self.emitted_phases:
                self.emit('terminal', failure=kind.__name__)
        finally:
            try:
                if self.client is not None:
                    self.close()
            finally:
                main.ACTIVE_MATCHES.clear()
                main.ACTIVE_MATCHES.update(self.old_matches)

    def request(self, method, path, **kwargs):
        assert len(self.http_requests) < 256
        route, separator, query = path.partition('?')
        row = {'sequence': len(self.http_requests) + 1, 'method': method,
               'path': route, 'query': query if separator else '',
               'request_JSON': deepcopy(kwargs.get('json')), 'status': None,
               'response_JSON': None, 'response_raw_SHA256': None,
               'request_outcome': 'invoked; response not yet available'}
        self.http_requests.append(row)
        try:
            response = self.client.request(method, path, **kwargs)
        except BaseException as error:
            row['request_exception_class'] = type(error).__name__
            raise
        row.update(method=response.request.method, path=response.request.url.path,
                   query=response.request.url.query.decode('ascii'), status=response.status_code,
                   request_outcome='actual response returned',
                   request_raw_SHA256=hashlib.sha256(response.request.content).hexdigest(),
                   response_raw_SHA256=hashlib.sha256(response.content).hexdigest())
        try:
            row['request_wire_JSON'] = json.loads(response.request.content) if response.request.content else None
        except ValueError:
            row['request_wire_JSON_unavailable'] = True
        try:
            row['response_JSON'] = response.json()
        except ValueError:
            row['response_JSON_unavailable'] = True
        return response

    def emit(self, phase, failure=None):
        assert phase in PHASES
        out = Path(os.environ['MTG_SPREE_HTTP_EVIDENCE'])
        controller = main.ACTIVE_MATCHES.get(getattr(self, 'mid', None))
        state = controller.state if controller is not None else None
        packet = {'case': self.case_id, 'phase': phase, 'actor': self.actor, 'epochs': self.epochs,
                  'match_state_available': state is not None, 'failure_class': failure,
                  'snapshot': None, 'controller': None, 'public_HTTP': None,
                  'HTTP_actions': self.actions}
        if failure is None:
            packet.update(snapshot=serialize_match_snapshot(self.state),
                          controller=main._controller_snapshot(self.controller),
                          public_HTTP=self.public())
        elif state is not None:
            try:
                packet.update(snapshot=serialize_match_snapshot(state),
                              controller=main._controller_snapshot(controller))
            except BaseException as error:
                packet['failure_snapshot_exception_class'] = type(error).__name__
        packet['HTTP_requests'] = deepcopy(self.http_requests)
        with (out / f'{self.case_id}-{phase}.json').open('x') as stream:
            json.dump(packet, stream, indent=2)
        self.emitted_phases.add(phase)

    def public(self):
        response = self.request('GET', f'/matches/{self.mid}')
        assert response.status_code == 200, response.text
        return response.json()

    def privacy(self):
        packet = self.public()
        assert packet['controllers'] == {str(self.actor): 'human', str(3-self.actor): 'ai'}
        assert packet['players'][str(3-self.actor)]['hand'] == []
        hidden = {cid for p in self.state.players.values() for cid in p.library}
        hidden.add(self.hidden)
        encoded = json.dumps(packet, sort_keys=True)
        assert all(cid not in encoded for cid in hidden)
        assert self.request('GET', f'/matches/{self.mid}/legal-moves?player_id={3-self.actor}').status_code == 403
        assert self.request('GET', f'/matches/{self.mid}/debug/ai-hands').status_code == 403
        assert packet['root_seed'] is None and packet['game_seed'] is None
        response = self.request('GET', f'/matches/{self.mid}/legal-moves?player_id={self.actor}')
        assert response.status_code == 200, response.text
        return packet, response.json()['moves']

    def root(self):
        with closing(sqlite3.connect(DATABASE_PATH)) as connection:
            sql = list(connection.iterdump())
        return (serialize_match_snapshot(self.state), deepcopy(main._controller_snapshot(self.controller)), sql)

    def submit(self, action, expected=200):
        self.actions += 1
        assert self.actions <= 128
        response = self.request('POST', f'/matches/{self.mid}/action', json={'player_id': self.actor, 'action': action})
        assert response.status_code == expected, response.text
        return response.json()

    def advance(self, predicate):
        for _ in range(128):
            if predicate(self.state):
                return
            assert not self.state.pending_mechanic_choice and not self.state.pending_trigger_order
            if self.state.priority_player == self.actor:
                self.submit({'type': 'pass_priority'})
            else:
                self.actions += 1
                assert self.actions <= 128
                response = self.request('POST', f'/matches/{self.mid}/autoplay?ticks=1')
                assert response.status_code == 200, response.text
        raise AssertionError('128 actual HTTP actions exceeded bound')

    def cast(self):
        modes = parse(self.state.cards[self.favor].oracle_text)
        _, moves = self.privacy()
        offered = next(m for m in moves if m.get('card_id') == self.favor and m['type'] == 'cast_spell')
        hints = offered['target_hints']
        assert len(hints['available_modes']) == 2
        assert hints['mode_base_mana_costs'] == {'base': '{R}{R}'}
        assert all(hints['mode_additional_mana_costs'][m.text] == '{1}' for m in modes)
        chosen = [modes[self.mode]] if self.mode < 2 else list(modes)
        targets = {'mode_texts': [m.text for m in chosen],
                   'mode_targets': {m.text: {'target_stack_id': self.original} for m in chosen}}
        before = sum(self.state.players[self.actor].mana_pool.values())
        self.submit({'type': 'cast_spell', 'card_id': self.favor, 'from_graveyard': False,
                     'cost_choice': {'id': 'base'}, 'targets': targets})
        favor = next(i for i in self.state.stack if i.source_card_id == self.favor)
        total = 4 if self.mode == 2 else 3
        assert favor.payload['mana_spent'] == total
        assert before - sum(self.state.players[self.actor].mana_pool.values()) == total
        assert self.state.cards[self.favor].zone == Zone.STACK
        self.emit('paid')

    def cold(self):
        assert not self.restored
        self.restored = True
        snapshot = serialize_match_snapshot(self.state)
        controller = deepcopy(main._controller_snapshot(self.controller))
        public = self.privacy()
        self.close()
        main.ACTIVE_MATCHES.pop(self.mid)
        self.open()
        assert len(self.epochs) == 2 and len(set(self.epochs)) == 2
        # Real coordinated GET loads the exact saved controller via the real repository.
        self.public()
        assert serialize_match_snapshot(self.state) == snapshot
        assert main._controller_snapshot(self.controller) == controller
        assert self.privacy() == public
        self.emit('restored')

    def choice(self, kind, keep=False):
        pending = self.state.pending_mechanic_choice
        assert pending['kind'] == kind and pending['player_id'] == self.actor
        _, moves = self.privacy()
        options = pending['options']
        assert ('keep' in options) is (kind == 'copy_target')
        before = self.root()
        self.submit({'type': 'choose_mechanic', 'card_ids': ['keep' if kind != 'copy_target' else 'forged-option']}, 422)
        assert self.root() == before
        token = 'keep' if keep else next(x for x in options if x != 'keep')
        offered = [m for m in moves if m['type'] == 'choose_mechanic' and m.get('kind') == kind]
        assert len(offered) == 1
        assert offered[0]['player_id'] == self.actor and offered[0]['count'] == pending['count'] == 1
        assert offered[0]['options'] == options and token in offered[0]['options']
        self.submit({'type': 'choose_mechanic', 'card_ids': [token]})
        return token
