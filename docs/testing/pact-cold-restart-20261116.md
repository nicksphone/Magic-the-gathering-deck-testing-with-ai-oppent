# Pending Pact across cold backend processes

This test-only cohort has four cases: both seats, each paying or declining a real
Summoner's Pact obligation. It starts from the existing **declared canonical
midgame** fixture. The first worker casts Pact, searches, and advances through
real ASGI requests to next-own upkeep; it does not inject a debt or prompt.

Each case uses one temporary SQLite file outside the source tree and three
successive Python processes, with capacity ownership released before each exit:

1. Reach and persist the pending choice. Record hashes of the entire public
   response and stored state/controller data, plus the pending revision.
2. Cold-load the app, require those hashes and revision unchanged, read the legal
   choice, and pay or decline. Require one revision increment, four tapped Forests
   and one payment log for pay, or the opponent winning without tapping for
   decline. Repeating the same request/key must return the accepted response;
   a new intent at the old revision must be rejected without changing storage.
3. Cold-load again and retry the accepted key using the original pending
   revision. Require the same public state, revision and stored hashes, then
   reject a different stale intent again.

The capacity-owned engine is never disposed between an action and its checks.
Only after the owner closes does a worker dispose its pool. No production files,
source pins, existing fixture or browser runner change.

## Command and evidence

Use a clean disposable checkout with the backend dependencies installed and
**no legacy `backend/mtg_lab.db` in the source tree**. The app intentionally
refuses that legacy path even when `MTG_DATABASE_PATH` names a separate test DB.
Use a fresh checkout if a source-tree DB is present; do not delete an operator's
saved-game database or remove its locks to make this test start.

```bash
cd backend
python -B -m pytest -q tests/test_pact_cold_restart.py
```

Expected collection is four tests. Local collection
and source syntax checks pass, but the attempted `pay-1` case timed out after
45 seconds in the first worker's ASGI request; this is **one failed local test**,
not a pass or a skip. A separate eight-second bounded diagnostic showed the first POST blocked in
Starlette TestClient / anyio `start_task_soon`, with no application stack visible
in the captured thread dump. It
terminated with the diagnostic timeout; no production workaround was added.

These are ASGI/SQLite process-restoration tests. They do not establish TCP fault
handling, an uninterrupted browser session across server restart, or full RC
acceptance. Browser refresh while the payment prompt is pending has separate
coverage; those results must not be combined into a browser-restart claim.


## Host result — 2026-11-16

Claude ran commit `3b1518f2` on the host: **4 passed, 0 failed**. An initial
scratch-checkout attempt encountered the legacy source-tree database guard;
after correcting that disposable checkout, the four-case run passed. The guard
was retained. This host result covers the ASGI/SQLite process-restoration cases
above, not an uninterrupted browser connection or the later composed browser
program. The local timeout remains a separate result, not a passing local run.
