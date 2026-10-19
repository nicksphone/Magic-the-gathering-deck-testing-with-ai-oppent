# Browser BO3 Readiness Contract

The workflow on `3b99b96d` passed its frontend job and logged 76 successful
browser checkpoints before stopping at `browser-game-over.mjs:78`. The earlier
modal legal-moves rejection no longer occurs. The new failure is a stale test
expectation, not demonstrated loss of the play/draw controls.

The serialized game-over fixture has a human seat with `sideboarding.applied`
false. Both actual `Controls` and the backend next-game endpoint require each
human to apply swaps or explicitly confirm no swaps before starting a new game.
The old assertion incorrectly required Play First/Draw First to be enabled
before that confirmation.

The test now asserts both buttons are disabled before sideboarding, then keeps
the enabled-button assertions after the actual Apply Sideboard Swaps request.
All winner/draw branches, no-auto-advance checks, exact submitted requests,
authoritative completion and other existing assertions remain. No UI/backend
behavior, fixture result or security policy is changed to satisfy the test.

An unchanged repository-native readiness script completed eight actual Controls
renders, loaded through Vite's real SSR middleware with WebSocket/watch disabled.
It checks both-human readiness combinations, human/AI readiness and unavailable
inventory. The renderer denied unexpected listeners/connections. JavaScript
syntax checking passed. This is static component evidence, not a browser or
HTTP/gameplay certificate; the corrected full browser workflow must run remotely.

The original job log and test preimage are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ci/3b99b96d-37918736751-20261009/`.
