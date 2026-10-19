# Native Suspend HTTP Acceptance

The original whole `backend/tests/test_suspend_composition_http.py` module
completes on 2026-10-10: ten passes, zero failures/errors/skips, 52.25 seconds.
The executed scoped source contains 1,778 files: 1,777 byte-equal published
`58ab28814dd083200ac960777c3d32491e762809` inputs and the two-line fixture reload
correction below. This is not execution of the full backend suite or proof of
the entire working tree.

## Fixture Correction

After a real process restart, `ACTIVE_MATCHES` is initially empty. The fixture's
`owned()` helper now calls the existing `_load_saved_match()` on a cache miss,
then preserves its original claim, card-presence and supported-source checks.
Cached matches are not reloaded and an unowned match remains rejected. No
production engine, public API, native ownership or storage code changes.

Seven new pure regressions exercise the actual extracted helper. The same
final tests fail four cases before the correction and pass all seven afterward.
An earlier test-harness exception is preserved separately. These are helper
tests, not seven additional HTTP or gameplay episodes.

## Actual Execution

The unchanged ten ordered cases cover both seats' burn, creature, draw, decline
and unpayable choices. They use real production AI selection, checked actions,
autoplay, stack resolution, persistence and private-input invariance checks.
The burn cases perform two real cold restarts. Three actual server processes
start in total; ten cases do not mean ten servers or independent games.

The original actions, assertions and clocks remain unchanged: requests 20s,
startup 60s, readiness polling 0.1s and TERM/KILL waits of 10s each. The reviewed
native runner retains its 900s outer bound and 3 GiB capacity floor. The source,
2,587 cached dependency files, four dependency links and interpreter remain
pinned before and after execution. No dependency installation occurs.

Before the original fixture deletes its runtime, each actual child records
production-first disposal and owner closure. Registered owners, connections,
workers and jobs are empty; tracked children and the listener are absent.
Actual owned SQL paths have empty `fuser`/`lsof` results. An independent external
check releases the lease at 22:20:00 UTC. No observer manufactures disposal.
These checks are scoped to owned resources, not exhaustive host visibility.

Private evidence preserves the original logs, JUnit, source/dependency pins,
closed runtime archive and closure records on verified NFS. No database,
credential, raw synthetic trace or private game episode is published.

## Guard Repairs And Preserved History

Earlier native attempts stop at implicit pytest logging, child-registration
ordering and startup timeout. Their setup failures remain separate; they are
not counted as completed gameplay. A separately authorized startup diagnostic
observes repeated ancestor scans during genuine placeholder hydration.

The final guard registers the actual returned child PID before its restricted
epoch read. An immutable, content-keyed ancestor index replaces repeated scans
without changing protected paths, denial policy or clocks. Internal controls
and registration/index regressions pass, followed by the actual original ten
HTTP cases. Diagnostic signal handlers are absent from that final run.

## Remaining Acceptance

Owner-upkeep transitions are explicit fixture operations, not naturally played
intervening turns. This cohort does not certify arbitrary decks, all supported
actions, expert AI, full-horizon strategy, production HTTPS or full backend CI.
All unproved original requirements in `plan.md` remain open.

The module remains opt-in: execute it only through the reviewed isolated native
runner with owned local SQLite and verified NFS archival. The pure reload
regressions can run independently from `backend`:

```bash
python -m unittest tests.test_suspend_composition_owned_reload
```
