from __future__ import annotations

import httpx

from card_data.http_utils import get_with_backoff


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def get(self, url: str, params=None, timeout=None):  # noqa: ANN001
        del url, params, timeout
        response = self.responses[self.calls]
        self.calls += 1
        return response


def test_get_with_backoff_retries_on_rate_limit(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("card_data.http_utils.time.sleep", lambda value: sleeps.append(value))

    request = httpx.Request("GET", "https://api.scryfall.com/cards/named")
    responses = [
        httpx.Response(429, request=request, headers={"Retry-After": "0"}),
        httpx.Response(200, request=request, json={"ok": True}),
    ]
    client = _FakeClient(responses)

    response = get_with_backoff(client, "https://api.scryfall.com/cards/named", timeout=1.0)

    assert response.status_code == 200
    assert client.calls == 2
    assert sleeps == [0.0]
