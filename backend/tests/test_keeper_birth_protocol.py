"""Pure fixture-function controls, not real Factory/HTTP/serializer qualification.

Only the three reviewed fixture bodies execute. Factory, cards and HTTP are
primitive spies; their labels are not Oracle data or gameplay observations.
"""
import ast
from copy import deepcopy
from enum import Enum
from pathlib import Path
import random
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
BASELINE = '--baseline' in sys.argv
if BASELINE:
    sys.argv.remove('--baseline')
SOURCE = ROOT / 'preimages/backend/tests' if BASELINE else Path(__file__).resolve().parent
CONTROL_THREAD = None


class ProtocolStep(Enum):
    PRECOMBAT_MAIN = 'main'


def deny_native(event, args):
    if CONTROL_THREAD != threading.get_ident():
        return
    if event.startswith(('sqlite3.', 'socket.', 'subprocess.', 'ctypes.')) or event in {
            'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.posix_spawnp'}:
        raise PermissionError('Pure keeper controls deny native I/O')
    if event == 'import' and args[0].split('.')[0] in {
            'ai', 'card_data', 'game_state', 'persistence', 'rules_engine', 'sqlmodel'}:
        raise PermissionError('Pure keeper controls deny project imports')


sys.addaudithook(deny_native)


def definition(filename, name, method=None):
    tree = ast.parse((SOURCE / filename).read_text())
    node = next(x for x in tree.body if getattr(x, 'name', None) == name)
    if method is not None:
        node = next(x for x in node.body if getattr(x, 'name', None) == method)
    return node


class Protocol:
    def __init__(self, target_id='http-root'):
        self.events = []
        self.births = []
        self.published = []
        self.target_original = SimpleNamespace(id=target_id)
        self.controller = SimpleNamespace(state=self.target_original)
        self.main = ModuleType('main')
        self.main.ACTIVE_MATCHES = {target_id: self.controller}
        self.main._persist_active_match = self.persist
        self.repo = SimpleNamespace(upsert_card=lambda row: self.events.append('upsert'))
        self.client = SimpleNamespace(post=lambda *args, **kwargs: self.post())
        self.ns = {
            'Step': ProtocolStep,
            'Zone': SimpleNamespace(HAND='hand', LIBRARY='library'),
            'canonical': lambda name: {'card_name': name},
            'MatchFactory': SimpleNamespace(from_decks=self.factory),
            'raw_card': self.card, 'normalize': lambda row: row,
            'ROWS': {name: {'protocol_label': name} for name in (
                'Doomed Traveler', 'Grizzly Bears', 'Rest in Peace',
                'Humility', 'Act of Treason', 'legend')},
        }
        sys.modules['main'] = self.main
        self.load()

    def load(self):
        position = definition('extra_sequence_support.py', 'position')
        episode = definition('test_combat_graveyard_caller_audit.py', 'Episode')
        episode.body = [x for x in episode.body if getattr(x, 'name', None) in {
            '__init__', 'persist'}]
        legend = definition('test_human_legend_keeper_audit.py', 'Legend')
        legend.body = [x for x in legend.body if getattr(x, 'name', None) == '__init__']
        module = ast.fix_missing_locations(ast.Module(body=[position, episode, legend], type_ignores=[]))
        exec(compile(module, str(SOURCE / 'fixture-protocol-only'), 'exec'), self.ns)

    def factory(self, a, b, seed, game_id=None):
        self.events.append(('birth_request', game_id))
        # Existing public Factory schema; no new fixture-side validator.
        if game_id is not None and (type(game_id) is not str or not game_id
                or not game_id.isprintable() or any(c.isspace() for c in game_id)):
            raise ValueError('game_id must be a nonempty clean string or None')
        identifier = game_id if game_id is not None else 'birth-' + str(len(self.births) + 1)
        state = SimpleNamespace(id=identifier, players={
            pid: SimpleNamespace(hand=[], library=[], mana_pool={}) for pid in (1, 2)},
            cards={}, starting_decks={1: deepcopy(a), 2: deepcopy(b)},
            rng=random.Random(seed), sideboard_facts={'game_id': identifier,
            'capture_version': 3, 'coverage_ok': True, 'inventory': {'original': 'stock'}})
        self.births.append(state)
        self.events.append(('captured', identifier))
        return state

    def card(self, state, row, owner, zone):
        self.events.append(('card', state.id))
        cid = 'protocol-card-' + str(len(state.cards))
        card = SimpleNamespace(id=cid, owner=owner, zone=zone)
        state.cards[cid] = card
        return card

    def post(self):
        self.events.append('http_start')
        return SimpleNamespace(status_code=200, text='protocol',
            json=lambda: {'id': self.target_original.id})

    @staticmethod
    def birth_snapshot(state):
        # The precise copy_facts:24 ID invariant, not the complete serializer.
        if state.sideboard_facts['game_id'] != state.id:
            raise ValueError('Invalid private sideboard facts: birth identity')
        return {'id': state.id, 'facts': deepcopy(state.sideboard_facts),
            'starting_decks': deepcopy(state.starting_decks), 'rng': state.rng.getstate()}

    def persist(self, repo, controller):
        self.birth_snapshot(controller.state)
        if controller.state.id != self.target_original.id:
            raise ValueError('Controller root changed after birth')
        self.events.append(('published', controller.state.id))
        self.published.append(controller.state)

    def position(self, identifier):
        # Let old code reach the actual missing-binding assertion, not TypeError.
        fn = self.ns['position']
        node = definition('extra_sequence_support.py', 'position')
        if any(arg.arg == 'game_id' for arg in node.args.kwonlyargs):
            return fn(1, game_id=identifier)
        return fn(1)

    def construct(self, name, http=False):
        kwargs = {'client': self.client, 'repo': self.repo} if http else {}
        if name == 'Legend':
            return self.ns[name](1, 'legend', **kwargs)
        return self.ns[name](1, 'ordinary', False, **kwargs)


class KeeperBirthControls(unittest.TestCase):
    def setUp(self):
        global CONTROL_THREAD
        CONTROL_THREAD = threading.get_ident()
        self.previous_main = sys.modules.get('main')
        try:
            self.p = Protocol()
        except BaseException:
            CONTROL_THREAD = None
            raise

    def tearDown(self):
        global CONTROL_THREAD
        CONTROL_THREAD = None
        if self.previous_main is None:
            sys.modules.pop('main', None)
        else:
            sys.modules['main'] = self.previous_main

    def test_position_default_capture_and_rng_preserved(self):
        state = self.p.ns['position'](1)
        snap = self.p.birth_snapshot(state)
        self.assertEqual(snap['id'], 'birth-1')
        self.assertEqual(snap['facts']['inventory'], {'original': 'stock'})
        self.assertEqual(snap['facts']['capture_version'], 3)
        self.assertTrue(snap['facts']['coverage_ok'])
        self.assertEqual(snap['rng'], random.Random(7214).getstate())
        self.assertEqual(state.players[1].mana_pool, {'W': 0, 'U': 10, 'B': 0, 'R': 10, 'G': 0, 'C': 10})

    def test_position_id_is_keyword_only_optional(self):
        node = definition('extra_sequence_support.py', 'position')
        self.assertEqual([arg.arg for arg in node.args.kwonlyargs], ['game_id'])
        self.assertEqual(ast.dump(node.args.kw_defaults[0]), ast.dump(ast.Constant(None)))

    def test_position_declared_id_captured_at_birth(self):
        state = self.p.position('declared-root')
        self.assertEqual(state.id, 'declared-root')
        self.assertEqual(self.p.birth_snapshot(state)['facts']['game_id'], 'declared-root')

    def test_position_invalid_ids_reject_before_capture(self):
        for identifier in (True, 1, [], '', 'bad id', 'bad\n'):
            with self.subTest(identifier=repr(identifier)):
                p = Protocol()
                with self.assertRaises(ValueError):
                    p.position(identifier)
                self.assertEqual(p.births, [])

    def test_episode_default_capture_stays_known(self):
        episode = self.p.construct('Episode')
        self.assertEqual(self.p.birth_snapshot(episode.state)['facts']['inventory'], {'original': 'stock'})
        self.assertEqual(self.p.published, [])

    def test_episode_http_birth_precedes_publish_without_rebind(self):
        try:
            episode = self.p.construct('Episode', http=True)
        except ValueError as exc:
            self.fail(str(exc))
        self.assertEqual(episode.state.id, 'http-root')
        self.assertEqual(self.p.births[0].sideboard_facts['game_id'], 'http-root')
        self.assertEqual(self.p.published, [episode.state])
        self.assertLess(self.p.events.index('http_start'), self.p.events.index(('captured', 'http-root')))
        self.assertLess(self.p.events.index(('captured', 'http-root')), self.p.events.index(('published', 'http-root')))

    def test_episode_invalid_target_preserved_and_no_capture(self):
        for identifier in (True, 42, 'bad id'):
            with self.subTest(identifier=repr(identifier)):
                p = Protocol(identifier)
                with self.assertRaises(ValueError):
                    p.construct('Episode', http=True)
                self.assertIs(p.controller.state, p.target_original)
                self.assertEqual(p.births, [])
                self.assertEqual(p.published, [])

    def test_legend_pure_replacement_keeps_original_match_id(self):
        legend = self.p.construct('Legend')
        self.assertEqual(legend.state.id, self.p.births[0].id)
        try:
            snap = self.p.birth_snapshot(legend.state)
        except ValueError as exc:
            self.fail(str(exc))
        self.assertEqual(snap['facts']['game_id'], self.p.births[0].id)
        self.assertEqual(snap['facts']['inventory'], {'original': 'stock'})

    def test_legend_http_both_births_use_declared_root(self):
        try:
            legend = self.p.construct('Legend', http=True)
        except ValueError as exc:
            self.fail(str(exc))
        self.assertEqual([s.sideboard_facts['game_id'] for s in self.p.births], ['http-root', 'http-root'])
        self.assertEqual([s.id for s in self.p.published], ['http-root', 'http-root'])
        self.assertIs(self.p.controller.state, legend.state)

    def test_no_state_id_or_facts_write_in_fixture_callers(self):
        for filename, name in (('test_combat_graveyard_caller_audit.py', 'Episode'),
                ('test_human_legend_keeper_audit.py', 'Legend')):
            node = definition(filename, name, '__init__')
            targets = [target for item in ast.walk(node) if isinstance(item, ast.Assign) for target in item.targets]
            self.assertFalse(any(ast.unparse(t) in ('self.state.id', 'self.state.sideboard_facts') for t in targets))


if __name__ == '__main__':
    unittest.main(verbosity=2)
