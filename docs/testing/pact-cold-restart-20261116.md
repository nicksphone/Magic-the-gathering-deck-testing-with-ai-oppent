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

Use a disposable checkout with the backend dependencies installed. The test
**does not require `backend/mtg_lab.db` to be absent**: it creates its own empty
temporary SQLite file before starting the first worker. The explicit configured
path therefore already exists, so a default DB left by an earlier test cannot
trigger the new-path/legacy-data guard. This makes startup independent of that
test-order condition. The test neither opens nor deletes the default database
or its locks. Its owned-file initialization is not an export or migration of
operator saved games; the production guard is unchanged.

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


## CI order-dependence correction — 2026-11-16

PR #87 [CI run 43914513053](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/43914513053)
subsequently failed `backend-workers (2)` at
`test_pact_cold_restart.py:29`: the child process returned nonzero. Claude
reproduced the cause with a stray source-tree `backend/mtg_lab.db`: the original
test supplied a missing configured path, so the production guard refused to
silently abandon the legacy database. The earlier clean-checkout four-pass
result did not cover this shard-order condition; requiring a clean default DB
was not a sufficient test-isolation fix.

Commit `ea759dbf59493929b983960bc7da33af392f78cd` pre-creates only the owned
temporary file with `sqlite3.connect(...).close()`, before any child app import.
Claude reports the original fails with a stray default DB and the fixed module
passes **4/4 with it present and 4/4 without it**. Those are separate host runs,
not eight distinct cases or a new full CI result. The fixed [CI run 43925771281](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/43925771281) must still
finish independently; no shard success or full-suite total is implied here.
The earlier local TestClient timeout remains separate and has not been
reclassified as a pass.
