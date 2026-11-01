"""Real copied contexts/tasks must not outlive the trusted automatic waiver."""
import ast
import asyncio
from contextlib import contextmanager
from contextvars import Context, ContextVar, copy_context
from pathlib import Path
from types import SimpleNamespace

import pytest


def implementation():
    path = Path(__file__).resolve().parents[1] / 'ai/casting_resources.py'
    tree = ast.parse(path.read_bytes())
    nodes = [node for node in tree.body
             if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
                 and t.id == '_automatic_effect_cost_context' for t in node.targets))
             or (isinstance(node, ast.FunctionDef) and node.name in {
                 '_automatic_effect_cost_scope', '_materialization_without_mana'})]
    assert len(nodes) == 3
    namespace = {'ContextVar': ContextVar, 'contextmanager': contextmanager}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['_automatic_effect_cost_scope'], namespace['_materialization_without_mana']


@pytest.mark.parametrize('exceptional', [False, True])
def test_real_copied_context_is_revoked_after_normal_or_exception_exit(exceptional):
    scope, allowed = implementation()
    state = SimpleNamespace(pending_mechanic_choice=None)
    captured = None
    try:
        with scope(state, 1, 'canonical-source'):
            captured = copy_context()
            assert captured.run(allowed, state, 1, 'canonical-source')
            assert not Context().run(allowed, state, 1, 'canonical-source')
            if exceptional:
                raise RuntimeError('synthetic exceptional unwind')
    except RuntimeError:
        assert exceptional
    assert not allowed(state, 1, 'canonical-source')
    assert not captured.run(allowed, state, 1, 'canonical-source')


def test_nested_copied_contexts_revoke_only_the_entry_that_exited():
    scope, allowed = implementation()
    state = SimpleNamespace(pending_mechanic_choice=None)
    with scope(state, 1, 'outer'):
        outer = copy_context()
        with scope(state, 1, 'inner'):
            inner = copy_context()
            assert inner.run(allowed, state, 1, 'inner')
            assert not inner.run(allowed, state, 2, 'inner')
            assert not inner.run(allowed, SimpleNamespace(pending_mechanic_choice=None), 1, 'inner')
        assert not inner.run(allowed, state, 1, 'inner')
        assert outer.run(allowed, state, 1, 'outer')
        assert allowed(state, 1, 'outer')
    assert not outer.run(allowed, state, 1, 'outer')


def drain(loop, task):
    # Real asyncio Task/Handle contexts, without allocating an OS selector/self-pipe.
    for _ in range(8):
        if task.done():
            return task.result()
        assert loop._ready
        loop._ready.popleft()._run()
    raise AssertionError('Synthetic async ready-queue bound')


@pytest.mark.parametrize('exceptional', [False, True])
def test_real_async_task_captured_inside_scope_cannot_use_it_after_exit(exceptional):
    scope, allowed = implementation()
    state = SimpleNamespace(pending_mechanic_choice=None)
    loop = asyncio.BaseEventLoop()
    async def query():
        await asyncio.sleep(0)
        return allowed(state, 1, 'canonical-source')
    try:
        try:
            with scope(state, 1, 'canonical-source'):
                task = loop.create_task(query())
                if exceptional:
                    raise RuntimeError('synthetic exceptional unwind')
        except RuntimeError:
            assert exceptional
        assert drain(loop, task) is False
    finally:
        loop.close()


def test_real_async_task_within_active_scope_keeps_identity_and_native_pending_control():
    scope, allowed = implementation()
    state = SimpleNamespace(pending_mechanic_choice=None)
    loop = asyncio.BaseEventLoop()
    async def query():
        await asyncio.sleep(0)
        return allowed(state, 1, 'canonical-source')
    try:
        with scope(state, 1, 'canonical-source'):
            task = loop.create_task(query())
            assert drain(loop, task) is True
        assert not allowed(state, 1, 'canonical-source')
        for kind in ('effect_cast', 'suspend_cast'):
            pending = SimpleNamespace(pending_mechanic_choice={'kind': kind})
            assert allowed(pending, 1, 'canonical-source')
    finally:
        loop.close()
