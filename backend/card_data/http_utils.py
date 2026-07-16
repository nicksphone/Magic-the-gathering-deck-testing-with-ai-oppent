from __future__ import annotations

import time
from typing import Any

import httpx


def get_with_backoff(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
    retries: int = 2,
    base_delay: float = 1.0,
) -> httpx.Response:
    last_response: httpx.Response | None = None
    attempts = max(0, int(retries))
    for attempt in range(attempts + 1):
        if timeout is None:
            response = client.get(url, params=params)
        else:
            response = client.get(url, params=params, timeout=timeout)
        last_response = response
        if response.status_code != 429:
            return response
        if attempt >= attempts:
            break
        retry_after = response.headers.get("Retry-After")
        try:
            delay = float(retry_after) if retry_after is not None else base_delay * (2**attempt)
        except Exception:
            delay = base_delay * (2**attempt)
        time.sleep(max(0.0, delay))
    if last_response is None:
        raise httpx.HTTPError("request did not return a response")
    return last_response
