# Match recovery regression

Use the isolated backend, test Vite API override and Chromium debugger setup in [human actions](human-actions-browser.md). The fixture module adds only test setup to the production FastAPI app; normal reads/writes use production route dependencies, locks and durable storage. Never run it next to the live database.

```bash
cd frontend
npm run build
npm run test:unit
node tests/browser-human-actions.mjs
node tests/browser-recovery.mjs
```

The App tests render the actual root application, not a substitute mutation harness. They restore a persisted selected ID, double-click land play and assert one accepted revision, reload and verify the land is still played, then discard a successful POST response using Chromium interception. The latter verifies visible error, paused automation and authoritative state reconciliation without replaying the write. Interception excludes OPTIONS and rejects only a successful POST response, so it exercises ambiguous accepted writes rather than failed admission.

After that test finishes, stop **only the test fixture backend**, restart it using the same isolated source/database, then run:

```bash
node tests/browser-recovery.mjs --verify-restart
```

This last check expects the preceding test's selected ID and one played Forest. It verifies actual process-start snapshot restoration into the root App, with automatic play paused. Keep the test Chromium profile and Vite process alive between these steps. It is not a destructive crash test, full-game/BO3 flow, HTTPS deployment, multiworker test or long-session soak.

Backend `test_match_recovery.py` additionally checks concurrent identical retries, stale/conflicting keys, restored receipts/revisions and storage/commit failure injection with unchanged complete snapshots/database. Run it only from a disposable backend source copy. Original live source-local databases/cache must not be reused.

On 2026-09-27 all these checks passed; full backend suite had 822 passes with 798 deprecation warnings. No dependency changes or new model calls were needed for the recovery implementation. A prior bounded Jev opinion helped prioritize the gap but did not validate this later patch.
