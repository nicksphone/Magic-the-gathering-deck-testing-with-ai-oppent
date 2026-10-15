# Firefox Screenshot And Bodyless Response Component

This component extends the existing owned-page Firefox transport in two
bounded places. It does not certify native Firefox, the whole application
browser suite or release acceptance.

## Behavior

PNG screenshot requests admit an optional boolean `captureBeyondViewport`.
An omitted or false flag requests the native viewport; true requests the
document. Other options, formats and nonboolean flag values remain rejected.

A response with status 204 and a genuinely absent `body` field can be
fulfilled without adding a native response body. Explicit string bodies,
including an empty string, are preserved. Null or otherwise invalid bodies
remain rejected, as do missing bodies for other response statuses. Existing
request ownership, native acknowledgements, failure propagation and pending
request drainage remain in place.

## Verification

The original 51 transport cases and 20 driver cases are preserved. Appending
23 transport cases produces a two-module Firefox declaration of 94 cases,
including rejection, native-error, acknowledgement and ownership controls.
The first regression run preserved 85 passes and nine failures before the
implementation. The larger pure protocol declaration passes 219 cases. An
independent reviewer also passes the complete two-module, 94-case declaration
and verifies the frozen source hashes before and after.

The parent's complete frontend test command, production build and lint each
exit zero on the final component. This is frontend/code-level evidence, not
an actual native-browser execution.

Frozen source SHA-256 values:

- `frontend/tests/firefox-transport.mjs`:
  `6104fb691b217027ac9c5f12e5a6b3d38da3c528b36ffed0160f5afcae2a0218`.
- `frontend/tests/firefox-transport.test.mjs`:
  `9345ba75b160bf138d8059f42b86496503e48de4c7fe83d5e158281303ec2cb7`.

The immutable private component evidence is stored under the project's NFS
archive at `firefox-screenshot-204-pure-20261015-e4lixg/`. It contains no
native-browser, SQL or network qualification for this change.

## Remaining Firefox Work

Keyboard and pointer actions, mobile and reduced-motion semantics, profile
identity, future-child registration and other explicit capability holds are
not implemented by this component. The older native application result also
retains its external ancestry hold. Existing version, origin and ownership
restrictions are not widened. Full Firefox acceptance requires actual native
evidence at the original application-suite scope, not additional mock passes.
