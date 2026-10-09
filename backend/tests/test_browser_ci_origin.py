"""Exercise the CI origin through the real ASGI policy without a server/DB."""
from pathlib import Path
import re
import shlex

import pytest
from starlette.middleware.cors import CORSMiddleware

from browser_origin import BrowserOriginMiddleware, trusted_origins


ORIGIN = 'http://127.0.0.1:15173'


def response(method, config):
    messages = []

    async def endpoint(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'{}'})

    async def receive():
        pytest.fail('This origin check must not read a request body')

    async def send(message):
        messages.append(message)

    origins = trusted_origins(config)
    app = BrowserOriginMiddleware(
        CORSMiddleware(endpoint, allow_origins=list(origins), allow_credentials=True),
        origins=origins,
    )
    coroutine = app({'type': 'http', 'method': method, 'path': '/health',
                     'headers': [(b'origin', ORIGIN.encode())]}, receive, send)
    with pytest.raises(StopIteration):
        coroutine.send(None)
    return messages[0]


def test_default_policy_rejects_nondefault_ci_origin():
    assert response('POST', None)['status'] == 403
    assert b'access-control-allow-origin' not in dict(response('GET', None)['headers'])


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_browser_ci_explicit_origin_reaches_real_policy(method):
    script = Path(__file__).parents[2] / 'frontend/tests/run-browser-ci.sh'
    values = re.findall(r'MTG_TRUSTED_ORIGINS=(\S+)', script.read_text())
    assert len(values) == 1, 'The backend child must trust only its CI frontend origin'
    configured = shlex.split(values[0])[0]
    assert trusted_origins(configured) == (ORIGIN,)
    result = response(method, configured)
    assert result['status'] == 200
    assert dict(result['headers'])[b'access-control-allow-origin'] == ORIGIN.encode()
