"""Actual lifespan AST with fake services/owner; no Main import, SQL or HTTP."""
import asyncio
from types import SimpleNamespace

import pytest

from tests.test_simulation_engine_shutdown import lifecycle


def tracked_lifecycle(*, join_fails=False, native_fails=False, owner_failure=None):
    namespace, calls = lifecycle(shutdown_fails=join_fails)
    owner = namespace['DatabaseOwner'](namespace['engine'])

    def owner_step(name):
        def step(**kwargs):
            calls.append(name)
            if name == owner_failure:
                raise RuntimeError('owner ' + name + ' failed')
        return step

    owner.fence_admission = owner_step('fence')
    owner.drain_producers = owner_step('drain')
    namespace['DatabaseOwner'] = lambda engine: owner

    def close_native():
        calls.append('native')
        if native_fails:
            raise RuntimeError('native cleanup failed')

    app = SimpleNamespace(state=SimpleNamespace(forge_manager=SimpleNamespace(close_all=close_native)))

    async def run():
        async with namespace['lifespan'](app):
            calls.append('yield')

    return calls, app, run


@pytest.mark.parametrize('join_fails', [False, True])
@pytest.mark.parametrize('native_fails', [False, True])
def test_native_cleanup_is_independent_but_owner_requires_successful_shutdown(join_fails, native_fails):
    calls, app, run = tracked_lifecycle(join_fails=join_fails, native_fails=native_fails)
    if native_fails or join_fails:
        message = 'native cleanup failed' if native_fails else 'live worker'
        with pytest.raises(RuntimeError, match=message) as failure:
            asyncio.run(run())
        if native_fails and join_fails:
            assert str(failure.value.__context__) == 'live worker'
    else:
        asyncio.run(run())
    expected = ['prepare', 'init', 'yield', 'join', 'native', 'fence']
    if not join_fails and not native_fails:
        expected += ['drain', 'dispose']
    assert calls == expected
    assert app.state.new_match_policy_frozen is True


@pytest.mark.parametrize('owner_failure', ['fence', 'drain'])
def test_owner_is_not_disposed_when_fencing_or_drain_fails(owner_failure):
    calls, app, run = tracked_lifecycle(owner_failure=owner_failure)
    with pytest.raises(RuntimeError, match='owner ' + owner_failure + ' failed'):
        asyncio.run(run())
    expected = ['prepare', 'init', 'yield', 'join', 'native', 'fence']
    if owner_failure == 'drain':
        expected.append('drain')
    assert calls == expected
    assert app.state.new_match_policy_frozen is True
