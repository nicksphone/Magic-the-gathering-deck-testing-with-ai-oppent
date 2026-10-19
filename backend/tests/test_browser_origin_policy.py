"""Pure policy/direct-ASGI checks: no main import, database or event-loop sockets."""
import json
import ast
from pathlib import Path

import pytest

from browser_origin import BrowserOriginMiddleware, DEFAULT_TRUSTED_ORIGINS, trusted_origins


def test_fixed_loopback_defaults_and_explicit_replacement():
    assert len(DEFAULT_TRUSTED_ORIGINS) == 9
    assert trusted_origins(None) == DEFAULT_TRUSTED_ORIGINS
    assert trusted_origins("") == ()
    assert trusted_origins("  ") == ()
    assert trusted_origins("https://lab.example,http://127.0.0.1:12345,https://lab.example") == (
        "https://lab.example", "http://127.0.0.1:12345",
    )
    assert "http://127.0.0.1:5173" not in trusted_origins("https://lab.example")


@pytest.mark.parametrize("value", [
    "*", "https://*.example", "null", "file://localhost", "ftp://example.com",
    "https://user:secret@example.com", "https://example.com/", "https://example.com/path",
    "https://example.com?", "https://example.com#", "https://example.com:0",
    "https://example.com:65536", "https://example.com:", "https://EXAMPLE.com",
    "https://example.com:443", "https://example.com,,https://other.example",
    "https://example.com\\evil", "https://exam ple.com", "https://example.com\n/",
    "https://example.com%2fevil", "https://[::1%25zone]", "https://-example.com",
    "https://example..com", "https://\u00e9xample.com",
    "http://[0:0:0:0:0:0:0:1]:5173",
])
def test_bad_configuration_fails_closed_without_echoing(value):
    with pytest.raises(ValueError) as failure:
        trusted_origins(value)
    assert str(failure.value) == "MTG_TRUSTED_ORIGINS requires exact canonical HTTP(S) origins"
    assert "secret" not in str(failure.value)


def dispatch(method="POST", headers=(), origins=None, kind="http"):
    calls = []
    messages = []

    async def handler(scope, receive, send):
        calls.append(scope)

    async def receive():
        pytest.fail("Origin rejection must not read the body")

    async def send(message):
        messages.append(message)

    scope = {"type": kind, "method": method, "headers": headers,
             "server": ("lab.example", 443), "scheme": "https", "path": "/matches/start"}
    middleware = BrowserOriginMiddleware(handler, origins=trusted_origins(origins))
    # These coroutines have no blocking awaits; drive directly without asyncio's
    # socketpair/event-loop setup, so the whole module supports socket-deny gates.
    coroutine = middleware(scope, receive, send)
    with pytest.raises(StopIteration):
        coroutine.send(None)
    return calls, messages


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "TRACE", "CUSTOM"])
@pytest.mark.parametrize("origin", [
    b"https://evil.example", b"null", b"", b"https://lab.example.evil",
    b"http://localhost.evil:5173", b"http://127.0.0.1:54321", b"http://0.0.0.0:5173",
    b"http://localhost:5173/", b"http://localhost:5173,https://evil.example",
])
def test_unsafe_untrusted_origin_never_enters_handler(method, origin):
    calls, messages = dispatch(method, [(b"origin", origin)])
    assert not calls
    assert messages[0]["status"] == 403
    assert json.loads(messages[1]["body"])["detail"]["code"] == "untrusted_browser_origin"
    assert b"evil" not in messages[1]["body"]


@pytest.mark.parametrize("origins, origin", [
    (None, origin.encode("ascii")) for origin in DEFAULT_TRUSTED_ORIGINS
] + [("https://lab.example", b"https://lab.example"),
     ("http://127.0.0.1:12345", b"http://127.0.0.1:12345")])
def test_allowed_dev_and_configured_same_origin_reach_handler(origins, origin):
    calls, messages = dispatch(headers=[(b"origin", origin)], origins=origins)
    assert len(calls) == 1 and not messages


def test_duplicate_origin_and_host_spoofing_do_not_grant_trust():
    for headers in (
        [(b"origin", b"http://localhost:5173"), (b"Origin", b"http://localhost:5173")],
        [(b"origin", b"https://evil.example"), (b"host", b"evil.example"),
         (b"x-forwarded-host", b"evil.example"), (b"x-forwarded-proto", b"https")],
    ):
        calls, messages = dispatch(headers=headers)
        assert not calls and messages[0]["status"] == 403


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_no_origin_nonbrowser_calls_remain_compatible(method):
    calls, messages = dispatch(method, origins="")
    assert len(calls) == 1 and not messages


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_safe_methods_pass_to_inner_cors_policy(method):
    calls, messages = dispatch(method, [(b"origin", b"https://evil.example")])
    assert len(calls) == 1 and not messages


def test_non_http_scope_passes_unchanged():
    calls, messages = dispatch(headers=[(b"origin", b"null")], kind="lifespan")
    assert len(calls) == 1 and not messages


def test_main_wiring_uses_one_config_and_outer_guard_without_importing_main():
    tree = ast.parse((Path(__file__).parents[1] / "main.py").read_text())
    calls = [node.value for node in tree.body if isinstance(node, ast.Expr)
             and isinstance(node.value, ast.Call)
             and isinstance(node.value.func, ast.Attribute)
             and isinstance(node.value.func.value, ast.Name)
             and node.value.func.value.id == "app"
             and node.value.func.attr == "add_middleware"]
    assert [call.args[0].id for call in calls] == ["CORSMiddleware", "BrowserOriginMiddleware"]
    cors = {kw.arg: kw.value for kw in calls[0].keywords}
    assert ast.unparse(cors["allow_origins"]) == "list(TRUSTED_BROWSER_ORIGINS)"
    assert ast.literal_eval(cors["allow_credentials"]) is True
    assert "*" not in ast.literal_eval(cors["allow_methods"])
    assert "*" not in ast.literal_eval(cors["allow_headers"])
    assert ast.unparse(calls[1].keywords[0].value) == "TRUSTED_BROWSER_ORIGINS"
    configured = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "TRUSTED_BROWSER_ORIGINS"
                              for t in node.targets))
    assert ast.unparse(configured) == "trusted_origins(os.environ.get('MTG_TRUSTED_ORIGINS'))"
