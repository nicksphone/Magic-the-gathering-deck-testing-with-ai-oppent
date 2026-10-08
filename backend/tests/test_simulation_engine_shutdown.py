"""Pure actual-lifespan ordering; real FD/restart gate is separate."""
import __future__
import ast
import asyncio
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest


def lifecycle(shutdown_fails=False):
    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "lifespan")
    calls = []

    def shutdown():
        calls.append("join")
        if shutdown_fails:
            raise RuntimeError("live worker")

    engine = SimpleNamespace(dispose=lambda: calls.append("dispose"))

    class Owner:
        path = SimpleNamespace(name="non-SQL-fixture", exists=lambda: False,
                               with_name=lambda name: None)
        epoch = "fake"

        def acquire(self): return self
        def open_admission(self): pass
        def fence_admission(self): pass
        def drain_producers(self, *, timeout): pass
        def close(self): engine.dispose()

    state = dict(asynccontextmanager=asynccontextmanager, engine=engine,
                 DatabaseOwner=lambda engine: Owner(),
                 initialize_resource_capacity=lambda owner, backup: None,
                 SIM_JOB_SHUTDOWN_TIMEOUT=20,
                 _shutdown_simulation_workers=shutdown,
                 _prepare_simulation_admission=lambda: calls.append("prepare"),
                 init_db=lambda: calls.append("init"),
                 Session=lambda engine: nullcontext(object()), Repository=lambda session: session,
                 _ensure_builtin_decks=lambda repo: None,
                 _ensure_expansion_top_decks=lambda repo: None,
                 _restore_simulation_jobs=lambda repo: None,
                 SIM_START_LOCK=nullcontext(), SIM_SHUTTING_DOWN=True)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "actual-lifespan", "exec",
                 flags=__future__.annotations.compiler_flag), state)
    return state, calls


@pytest.mark.parametrize("body_fails", [False, True])
def test_lifespan_disposes_only_after_successful_join(body_fails):
    state, calls = lifecycle()

    async def run():
        async with state["lifespan"](None):
            assert not state["SIM_SHUTTING_DOWN"]
            if body_fails:
                raise ValueError("application body failure")

    if body_fails:
        with pytest.raises(ValueError, match="application body failure"):
            asyncio.run(run())
    else:
        asyncio.run(run())
    assert calls == ["prepare", "init", "join", "dispose"]


def test_failed_worker_join_does_not_dispose_engine():
    state, calls = lifecycle(shutdown_fails=True)

    async def run():
        async with state["lifespan"](None):
            pass

    with pytest.raises(RuntimeError, match="live worker"):
        asyncio.run(run())
    assert calls == ["prepare", "init", "join"]
