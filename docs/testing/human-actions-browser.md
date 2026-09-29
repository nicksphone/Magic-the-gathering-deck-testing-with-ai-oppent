# Human action browser regression

The harness renders the production Battlefield and Controls components and invokes the production API action handlers. It tests action paths including seat-2 land play, targeted permanent activation, explicit Vehicle crew selection, permitted exile casting, permitted top-library casting, deliberate seat-2 London mulligan bottom selection, an affordable modal spell face, a deliberate face switch with distinct cost, a tapped modal land play, an Adventure spell followed by its normal-face cast from exile, a human ETB target choice, a separate optional-trigger decline at resolution, a cast-trigger choice above its creature spell, an ordered resolution-time Expressive Iteration-style hand/exile/bottom choice, a two-step Collected Company selection and ordered library-bottom choice, a resolution-time library-search choice, a draw replacement followed by two nested dredge choices, and both previous-loser BO3 play/draw choices. It also tests Tamiyo, Compleated Sage with life or mana payment and checks the displayed loyalty. It verifies the opposing hand is not rendered as playable cards, Keep is disabled until the required number of bottoms is selected, and active-match seeds stay hidden.

This is not a complete App onboarding/game/recovery test or a rules certification. Fixtures use named real cards with only relevant clauses, never add cards to the gameplay corpus, and cannot be launched from the live Git checkout. The crew path asserts that tapping pays its cost before the Vehicle gains creature type on stack resolution; see [crew timing checks](crew-stack-timing.md).

CI runs `bash frontend/tests/run-browser-ci.sh` in a separate Ubuntu browser job. The script copies the backend to a temporary directory, starts loopback API/Vite/Chrome, runs all action paths and the App recovery scenarios, restarts only the copied backend, then verifies restored state. It drops one or two successful match-start responses and checks that automatic retry, reload, and a second Start click produce only one match per request. A separate between-games fixture checks that a human sideboard swap survives reload and changes game two's deck. The hosted runner prefers Chrome because its Chromium binary did not expose CDP. It uses `MTG_BROWSER_NO_SANDBOX=1` only for this isolated test process; leave the flag unset for a local browser when sandboxing works. The local full harness verifies action, recovery, sideboard and natural BO3 paths; hosted CI for this revision is not claimed.

Requirements: installed backend dependencies in `backend/.venv`, installed frontend dependencies, Node 22 with built-in WebSocket, and Chromium with remote debugging. The one-command CI script uses `backend/.venv/bin/python` by default; set `MTG_TEST_PYTHON` to another installed backend interpreter if needed. For manual setup, use three separate terminals; all services bind loopback. The copied backend owns its database/cache; changing only cwd is not isolation.

```bash
cd /home/nick/mtg-deck-testing-lab
scratch=$(mktemp -d /tmp/mtg-human-actions-XXXXXX)
# After this milestone is committed, all harness files are tracked.
git ls-files backend | tar -cf - -T - | tar -xf - -C "$scratch"
cd "$scratch/backend"
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m uvicorn \
  tests.browser_fixture_server:app --host 127.0.0.1 --port 10199
```

```bash
cd /home/nick/mtg-deck-testing-lab/frontend
VITE_API_BASE_URL=http://127.0.0.1:10199 npm run dev -- --host 127.0.0.1 --port 15173 --strictPort
```

```bash
profile=$(mktemp -d /tmp/mtg-chromium-XXXXXX)
chromium --headless --disable-dev-shm-usage --no-first-run \
  --user-data-dir="$profile" --remote-debugging-port=19222 about:blank
```

Run in another terminal:

```bash
cd /home/nick/mtg-deck-testing-lab/frontend
node tests/browser-human-actions.mjs
```

Exit status must be zero with all PASS lines. Stop these test-only services afterward. Do not expose Chromium debugging or fixture routes on the network. Root/container Chromium may require `--no-sandbox`; prefer an ordinary-user sandboxed browser where available.

Validation on 2026-09-29: all action paths, including compleated life and mana choices with displayed loyalty, pass against production routes in the isolated fixture backend, and the configured TypeScript/Vite production build passes. `npm run test:unit` runs seven HTTP error-message assertions plus mutation-gate/key checks with Node 22 TypeScript stripping. Backend regression evidence is recorded in the root plan/changelog. The BO3 fixture starts between games; it does not play a complete series or sideboard. No dependency installs or paid model calls are required for this harness. See [App recovery checks](match-recovery.md) for additional refresh/lost-response/process-restart scenarios, [modal spell boundaries](modal-spell-faces.md), [land/Adventure boundaries](land-adventure-boundary.md) and [targeted triggers](targeted-trigger-choices.md) for canonical fixture scope.
