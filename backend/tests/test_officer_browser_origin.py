"""Officer's actual launcher origin through real middleware, without SQL/server I/O."""
from pathlib import Path
import shlex

import pytest
from starlette.middleware.cors import CORSMiddleware

from browser_origin import BrowserOriginMiddleware, trusted_origins


SCRIPT = Path(__file__).parents[2] / 'frontend/tests/run-activated-top-selection.sh'
ORIGIN = 'http://127.0.0.1:15237'


def configured_origin():
    values = {}
    # Read only the launcher's exports before any service is started.
    prefix = SCRIPT.read_text().split("backend='' frontend='' browser=''", 1)[0]
    for line in prefix.splitlines():
        if not line.startswith('export '):
            continue
        for token in shlex.split(line)[1:]:
            key, value = token.split('=', 1)
            values[key] = values.get(value[1:]) if value.startswith('$') else value
    assert values['MTG_FRONTEND_ORIGIN'] == ORIGIN
    return values.get('MTG_TRUSTED_ORIGINS')


def dispatch(method, origin):
    messages, calls = [], []

    async def endpoint(scope, receive, send):
        calls.append(scope)
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'{}'})

    async def receive():
        pytest.fail('An origin check must not read the body')

    async def send(message):
        messages.append(message)

    config = configured_origin()
    assert trusted_origins(config) == (ORIGIN,), 'Trust only the Officer frontend'
    app = BrowserOriginMiddleware(
        CORSMiddleware(endpoint, allow_origins=list(trusted_origins(config)),
                       allow_credentials=True, allow_methods=['GET', 'POST'],
                       allow_headers=['Content-Type']), origins=trusted_origins(config))
    headers = [(b'origin', origin.encode())]
    if method == 'OPTIONS':
        headers += [(b'access-control-request-method', b'POST'),
                    (b'access-control-request-headers', b'content-type')]
    coroutine = app({'type': 'http', 'method': method, 'path': '/matches/example',
                     'headers': headers}, receive, send)
    with pytest.raises(StopIteration):
        coroutine.send(None)
    return messages[0], calls


@pytest.mark.parametrize('method', ['GET', 'POST', 'OPTIONS'])
def test_officer_frontend_reaches_exact_real_origin_policy(method):
    result, calls = dispatch(method, ORIGIN)
    assert result['status'] == 200
    assert dict(result['headers'])[b'access-control-allow-origin'] == ORIGIN.encode()
    assert bool(calls) == (method != 'OPTIONS')


def test_officer_does_not_trust_the_ordinary_harness_or_foreign_origin():
    for origin in ['http://127.0.0.1:15173', 'https://foreign.example']:
        result, calls = dispatch('POST', origin)
        assert result['status'] == 403
        assert not calls
        assert b'access-control-allow-origin' not in dict(result['headers'])
