"""Inert actual-supervisor contracts; no real process, signal, procfs or lock."""
import contextlib
import io
from pathlib import Path
import signal
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).with_name('run.py')
PIDS = (700001, 700002)


class ObservationFinished(Exception):
    """End a fake HOLD observation without catching production failures."""


class NoTraversalPath(type(Path())):
    def denied(self, *args, **kwargs):
        raise AssertionError('Undeclared filesystem/proc traversal in inert fixture')

    open = read_text = read_bytes = stat = lstat = iterdir = glob = rglob = denied
    exists = is_file = is_dir = is_symlink = resolve = denied


class Kernel:
    def __init__(self, mode):
        self.mode = mode
        self.children = []
        self.groups = set(PIDS)
        self.foreign = set()
        self.handlers = {}
        self.signals = []
        self.unsafe_signals = []
        self.events = []
        self.close_snapshots = []
        self.sleeps = 0
        self.clock = 0
        self.result = None
        self.observation_finished = False

    def spawn(self, argv, **kwargs):
        assert kwargs['start_new_session'] is True
        index = len(self.children)
        assert index < 2, 'Only the two original inert service children are admitted'
        assert argv[0] == ('/inert/python' if index == 0 else '/inert/caddy')
        kernel = self

        class Child:
            pid = PIDS[index]
            code = None

            def __init__(self):
                self.waits = []

            def poll(self):
                return self.code

            def wait(self, timeout=None):
                self.waits.append(timeout)
                kernel.events.append(('wait', self.pid))
                assert self.code is not None, 'Fake live child cannot be reaped'
                return self.code

        child = Child()
        self.children.append(child)
        self.events.append(('spawn', child.pid))
        return child

    def getpgid(self, pid):
        assert type(pid) is int and pid in PIDS, 'Foreign or traversed PID operand'
        if pid in self.foreign:
            return pid
        child = next(c for c in self.children if c.pid == pid)
        if child.code is not None:
            raise ProcessLookupError
        return pid

    def killpg(self, pgid, signum):
        assert type(pgid) is int and pgid in PIDS, 'Foreign or traversed PGID operand'
        self.events.append(('group', pgid, signum))
        if self.mode == 'unknown' and pgid == PIDS[0]:
            raise PermissionError('inert observation unavailable')
        if pgid not in self.groups:
            raise ProcessLookupError
        if signum == 0:
            return
        assert signum in (signal.SIGTERM, signal.SIGKILL)
        self.signals.append((pgid, signum))
        if pgid in self.foreign:
            self.unsafe_signals.append((pgid, signum))
            return
        child = next(c for c in self.children if c.pid == pgid)
        child.code = 0
        if self.mode == 'after_wait' and pgid == PIDS[0] and signum == signal.SIGTERM:
            return  # Leader exits; its descendant deliberately remains in the group.
        self.groups.remove(pgid)

    def sleep(self, seconds):
        self.sleeps += 1
        if self.sleeps != 1:
            raise ObservationFinished
        if self.mode in ('fresh', 'after_wait'):
            self.handlers[signal.SIGINT](signal.SIGINT, None)
        else:
            self.children[0].code = 0
            if self.mode == 'absent':
                self.children[1].code = 0
                self.groups.clear()
            elif self.mode == 'reused':
                self.foreign.add(PIDS[0])

    def monotonic(self):
        self.clock += 1
        return self.clock

    def close_lock(self):
        self.close_snapshots.append(set(self.groups - self.foreign))
        self.events.append(('close',))


def drive(mode):
    # Execute the whole pinned actual module, not a rewritten cleanup algorithm.
    namespace = {'__name__': 'inert_actual_operator', '__file__': str(SOURCE)}
    exec(compile(SOURCE.read_text(), str(SOURCE), 'exec'), namespace)
    kernel = Kernel(mode)
    config = dict(runtime=Path('/inert/runtime'), python=Path('/inert/python'),
                  caddy=Path('/inert/caddy'), origin='https://inert.invalid:18443',
                  bind_address='127.0.0.1', backend_port=18444,
                  dist=Path('/inert/dist'), cert=Path('/inert/cert'),
                  key=Path('/inert/key'), user='fixture', password_hash='FIXTURE_SECRET')

    def validate(argv, **kwargs):
        assert argv == ['/inert/caddy', 'validate', '--config',
                        str(SOURCE.with_name('Caddyfile')), '--adapter', 'caddyfile']
        return SimpleNamespace(returncode=0)

    namespace.update(
        settings=lambda: config,
        prepare=lambda supplied: SimpleNamespace(close=kernel.close_lock),
        Path=NoTraversalPath,
        os=SimpleNamespace(umask=lambda mask: None, killpg=kernel.killpg, getpgid=kernel.getpgid),
        signal=SimpleNamespace(SIGINT=signal.SIGINT, SIGTERM=signal.SIGTERM,
                               SIGKILL=signal.SIGKILL,
                               signal=lambda number, handler: kernel.handlers.update({number: handler})),
        subprocess=SimpleNamespace(run=validate, Popen=kernel.spawn, DEVNULL=-3,
                                   TimeoutExpired=namespace['subprocess'].TimeoutExpired),
        sys=SimpleNamespace(argv=[str(SOURCE)], stderr=io.StringIO()),
        time=SimpleNamespace(sleep=kernel.sleep, monotonic=kernel.monotonic))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            kernel.result = namespace['main']()
        except ObservationFinished:
            kernel.observation_finished = True
    return kernel


class OwnedGroupCleanupTests(unittest.TestCase):
    def assert_no_release_with_survivor(self, result):
        self.assertFalse(any(result.close_snapshots),
                         'Actual main released operator.lock with an owned group still alive')
        self.assertNotEqual(result.result, 0, 'Unknown closure is not successful shutdown')

    def test_exited_leader_surviving_group_is_not_leader_only_closure(self):
        result = drive('exited')
        self.assertEqual(result.children[0].code, 0)
        self.assertEqual(result.children[0].waits, [30])
        self.assert_no_release_with_survivor(result)

    def test_term_and_leader_wait_do_not_certify_surviving_descendant(self):
        result = drive('after_wait')
        self.assertIn((PIDS[0], signal.SIGTERM), result.signals)
        self.assertEqual(result.children[0].waits, [30])
        self.assert_no_release_with_survivor(result)

    def test_dead_leader_reused_pgid_is_never_signalled_as_owned(self):
        result = drive('reused')
        self.assertEqual(result.foreign, {PIDS[0]})
        self.assertEqual(result.unsafe_signals, [])
        self.assertFalse(any(pgid == PIDS[0] for pgid, _ in result.signals))
        self.assertNotEqual(result.result, 0)

    def test_group_observation_permission_error_is_not_quiet(self):
        result = drive('unknown')
        self.assert_no_release_with_survivor(result)
        self.assertEqual(result.unsafe_signals, [])

    def test_fresh_owned_groups_keep_ctrl_c_and_one_wait_each(self):
        result = drive('fresh')
        self.assertEqual(result.result, 0)
        self.assertEqual(result.signals, [(pid, signal.SIGTERM) for pid in PIDS])
        self.assertEqual(result.unsafe_signals, [])
        self.assertEqual([child.waits for child in result.children], [[30], [30]])
        self.assertEqual(result.close_snapshots, [set()])
        self.assertEqual(result.events[-1], ('close',))

    def test_absent_dead_groups_reap_both_leaders_before_release(self):
        result = drive('absent')
        self.assertEqual(result.result, 1)  # Unexpected service exit remains a failure.
        self.assertEqual(result.signals, [])
        self.assertEqual([child.waits for child in result.children], [[30], [30]])
        self.assertEqual(result.close_snapshots, [set()])
        self.assertEqual(result.events[-5:], [('wait', PIDS[0]), ('wait', PIDS[1]),
                                             ('group', PIDS[0], 0), ('group', PIDS[1], 0), ('close',)])
