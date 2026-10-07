"""Exact browser-origin policy; this is not authentication or multi-user access."""
from __future__ import annotations

from ipaddress import IPv6Address
import re
from urllib.parse import urlsplit


DEFAULT_TRUSTED_ORIGINS = tuple(
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1", "[::1]")
    for port in (5173, 4173, 9999)
)
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\Z")
_REJECTION = b'{"detail":{"code":"untrusted_browser_origin","message":"Browser origin is not trusted."}}'


def trusted_origins(config: str | None) -> tuple[str, ...]:
    """Missing config uses fixed loopback ports; empty config trusts no origins."""
    if config is None:
        return DEFAULT_TRUSTED_ORIGINS
    if not config.strip():
        return ()
    origins = []
    for origin in config.split(","):
        origin = origin.strip()
        try:
            if not origin.isascii() or any(c.isspace() for c in origin):
                raise ValueError
            if any(c in origin for c in "*\\%?#"):
                raise ValueError
            url = urlsplit(origin)
            host, port = url.hostname, url.port
            if url.scheme not in {"http", "https"} or not host or url.path:
                raise ValueError
            if url.username is not None or url.password is not None:
                raise ValueError
            if ":" in host:
                host = f"[{IPv6Address(host)}]"
            elif not _HOST.fullmatch(host):
                raise ValueError
            if port == 0:
                raise ValueError
            canonical = f"{url.scheme}://{host}"
            if port is not None and port != {"http": 80, "https": 443}[url.scheme]:
                canonical += f":{port}"
            if origin != canonical:
                raise ValueError
        except ValueError:
            # Never echo configuration: malformed URLs can contain credentials.
            raise ValueError("MTG_TRUSTED_ORIGINS requires exact canonical HTTP(S) origins") from None
        if origin not in origins:
            origins.append(origin)
    return tuple(origins)


class BrowserOriginMiddleware:
    """Reject unsafe browser requests before routing/dependencies/body reads."""

    def __init__(self, app, *, origins):
        self.app = app
        self.origins = frozenset(origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            origins = [value for key, value in scope.get("headers", ()) if key.lower() == b"origin"]
            if origins and (len(origins) != 1 or origins[0].decode("latin-1") not in self.origins):
                await send({"type": "http.response.start", "status": 403, "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_REJECTION)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"vary", b"Origin"),
                ]})
                await send({"type": "http.response.body", "body": _REJECTION})
                return
        await self.app(scope, receive, send)
