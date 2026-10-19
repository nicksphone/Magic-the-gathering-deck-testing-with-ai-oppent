# Human Hand-to-Library Ordering

Checkpoint: 2026-10-08. Backend continuation is the published `ce97fe1` product;
this increment adds its existing `hand_top_order` view to the frontend's existing
topmost-first ordering control. It does not change backend choices or infer IDs.

The NEW frontend regression uses both-seat canonical paid Brainstorm positions,
actual legal views and checked backend resolution. It failed on the unsupported
mechanic warning before the UI change, then passed with deliberate reverse-option
click order, unchanged actor/ordered IDs, cardinality and reset controls. Existing
scry, surveil, bottom-order and unknown-kind warning paths remain unchanged.

The first NEW fixture attempt stopped at the public-view parser: the reused pure
board helper cleared ordinary mana but retained default zero snow-mana keys. Only
the NEW non-snow fixture was corrected before the actual UI baseline failure;
that draft is preserved and is not a product failure.

Current typecheck, lint, the entire configured `npm test` chain and production
build pass. Python fixtures used a pre-start audit hook denying SQLite, sockets
and further children, with all completion receipts installed and no denied
attempts. This does not sandbox Node/esbuild or certify browser interactions.
Dependencies were the existing qualified local installation, not a new install.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/brainstorm-ui-ordering/parent-ce97-20261008/`.
Actual browser/API ordering, HTTP/SQLite pending-choice restoration, broader
private-response qualification and the original release gates remain open.

## Browser Component Follow-Up

On the current `ff2ff42` component, NEW `browser-hand-top-order.mjs` passed both
seats in native Chromium 154. It renders the real Controls component with paid
canonical backend views and clicks actual DOM buttons in deliberate reverse
option order. Exact actor/ordered IDs, disabled duplicate/cardinality controls
and reset pass. The backend pure fixture independently verifies the selected
topmost-first order. Screenshots and the callback transcript are preserved.

This is an unstyled isolated component page on an owned loopback server, not
the built application, a live API or SQLite restoration. Chromium used its own
fresh profile and a local-test `--no-sandbox` launch; the Python fixture's native
SQL/socket/child audit denial is not claimed to sandbox Chromium or Node.
The complete release browser gate remains open.

The first NEW draft stopped before assertions because the existing browser
driver rejects the file-origin readiness condition. The second stopped at
navigation because the launcher's DNS-denial rule also blocked its own loopback
fixture. Only the NEW fixture/launcher were corrected; the product and shared
browser driver were unchanged. The final run exited 0 and all owned browser
processes closed. An idle fixture-server connection delayed natural teardown;
the successful exit and observed resource closure are recorded separately.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/brainstorm-human-browser/parent-ff2-20261008/`.
Run with an owned Chromium CDP endpoint in `MTG_BROWSER_ORIGIN`, the qualified
Python executable in `MTG_TEST_PYTHON`, and a fresh local absolute
`MTG_BROWSER_TEST_EVIDENCE` directory. The NEW script creates only that evidence
directory and its own ephemeral loopback fixture server.
