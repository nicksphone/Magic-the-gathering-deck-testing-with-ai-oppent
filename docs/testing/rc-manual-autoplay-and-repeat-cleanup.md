# Manual/Autoplay And Repeat-Cleanup Acceptance

Two whole modules execute six actual ASGI TestClient/file-SQLite regressions:
four concurrent manual/autoplay cases and two repeat-cleanup cases, covering
both seats. All six cases and eighteen setup/call/teardown phases pass, without
errors, skips, expected failures or deselection. The guarded actor and durable
manager exit zero; source/runtime, file-descriptor/thread, database-owner,
process/group/cgroup and shared-lease closure checks pass independently.

## Concurrent Writes

`test_manual_autoplay_collision_http.py` starts both genuine requests before
the unchanged match lock. The fixture uses an end-step position with no human
priority pause. Observation delegates to the real `checked_action` and requires
an actual state-changing autoplay pass, not merely a heartbeat response or
revision increment.

Unversioned requests accept their genuinely legal serialized outcomes.
Versioned requests exercise stale-revision rejection and idempotent retries.
If autoplay loses the version race, its separately reconciled request is
identified separately rather than counted as a collision commit. Final state,
controller, revisions, persisted SQL, rejected writes and restoration are
checked; the test does not force a scheduling winner.

## Triggered Repeat Cleanup

`test_cleanup_repeat_http.py` uses full canonical Sangromancer data and a finite
initial zone/step fixture. It does not inject a StackItem or pending trigger.
Real HTTP priority passes enter cleanup, an explicit discard generates the
actual trigger, priority and the optional life-gain choice resolve, and cleanup
repeats before the next turn. Both seats retain state/controller/SQL equality
across restoration and atomic rejection of wrong-seat or duplicate selections.
This is not a naturally paid Sangromancer cast or a complete browser game.

## Isolation And Historical Result

The ordinary tests use pytest-owned temporary file databases, the existing
capacity owner, real per-request repository sessions and TestClient without a
lifespan or listener. Startup, the source-default database and remote sync are
forbidden. There is no private input, opt-in marker or skip prerequisite.

The separate local execution additionally checks native SQL aliases and I/O
boundaries. It admits only owned test databases, real generated media and the
event loop's AF_UNIX socketpairs; external networking, processes and source or
runtime writes remain prohibited. Its SQLite files execute locally, never on
the archive share. Six minimized per-case receipts and closed evidence are
archived privately; no raw game state or SQL dump is published here.

The first invocation passed four concurrency cases but its two new cleanup
fixtures passed a CardInstance to a helper expecting a card ID. The corrected
invocation changes only that fixture argument and executes the entire cohort
again. The first result is preserved, not reclassified as an application bug or
silently replaced. These results certify the declared ASGI paths, not TCP,
browser, arbitrary-card or AI-quality behavior.
