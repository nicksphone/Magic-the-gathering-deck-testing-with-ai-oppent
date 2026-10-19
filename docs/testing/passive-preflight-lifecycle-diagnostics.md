# Passive Preflight And Lifecycle Facts

This diagnostic-only addendum is based on immutable `db4e0758a5a1d755abc964e7f40b0286783506e5`.
It does not fix or identify the cause of the historical legacy-start abort.

The opt-in `browserMetadata` buffer now projects `Network.responseReceived.response.headers`
for correlated OPTIONS requests and legal-moves responses. Existing response rows retain
their actual method/status; a legal-moves GET is not relabeled as a preflight.

- `allowOrigin`: expected frontend origin, wildcard, absent, multiple, other, or unavailable.
- `getAllowed` / `postAllowed`: explicit case-sensitive method-token membership only.
- `contentTypeAllowed` / `idempotencyKeyAllowed`: explicit header-token membership only.
- `methodsWildcard` / `headersWildcard`: separate wildcard presence, not inferred permission.
- `privateNetwork`: literal true/false, absent, multiple, other, or unavailable.

These are header facts, not a CORS-policy verdict. Unknown header shapes, invalid token
lists, and over-bound inputs produce unavailable/null facts, not successful allowance.
Header names/values, origins, URLs, IDs, bodies, and arbitrary error/reason/status text
are never emitted. The adapter reuses the existing Fetch-header categorizer; original
Fetch pause rows and their command/error/result handling are unchanged.

Page frame detach/subtree-detach notifications use existing local frame ordinals;
unknown IDs remain unjoined and do not allocate identities. Inspector detach/crash
notifications describe the direct owned page session. Target destroy/crash/detach
notifications require exact equality with the actual CDP page ID supplied by the
driver's existing observer hook. Missing, foreign, deprecated-absent, or Firefox/BiDi
target identity remains unjoined. Child-session and BiDi-branded lifecycle messages
cannot impersonate direct-page CDP notifications. Only a safe integer crash error code
is retained. Loss retires diagnostic signal-context attribution, not requests or replies.

All observations share the existing 64-event / 16-identity bounds. Header input and
newline-expanded selected header entries remain capped at 128, keys at 256 characters,
and values at 4096 characters. No protocol command, enable/discovery, listener, reload,
timer, request wrapper/header, retry, deadline, application/client, or scenario assertion
is added or changed. Without metadata opt-in, the observer remains absent and the old
report schema is unchanged. Failure publication remains once-only and cannot consume
the original command result, protocol rejection, or Fetch-handler error.

No ExtraInfo event is required or newly enabled. Its availability/order is not assumed.
Likewise, absence of an Inspector/Target/Page event does not prove that no lifecycle
loss occurred: the current session may not expose that notification, identities may be
unjoined, or the existing finite buffer may omit it. No new transport-close inference is
made. No browser, server, SQL, native vendor, Firefox whole-launcher, or root-cause
qualification follows from the pure supplied-protocol tests.

## Primary Protocol Fields

Field definitions were checked against the official ChromeDevTools protocol JSON
snapshot (SHA-256 `a3f0c370dc5761daaa570afa34a6c536fa029f6294f1cf415a871d43b4eb30c2`):
[official browser protocol JSON](https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/browser_protocol.json).
Relevant definitions are Network `responseReceived`, `Response.headers`, `Headers`,
and the newline duplicate-header representation documented on `responseReceivedExtraInfo`;
Page `frameDetached` (remove/swap) / `frameSubtreeWillBeDetached`; Inspector `detached` /
`targetCrashed`; Target `targetDestroyed` / `targetCrashed` / `detachedFromTarget`.
The raw Target status and Inspector reason are open strings, not public diagnostic enums.
