# Lazy Saved Matches Over 0a50

Scope: `main.py` and the repository discovery helper only. Single local worker;
no multiworker consistency claim, schema migration, engine/AI change, pagination,
retention cap, or match deletion.

Startup no longer restores saved matches. `/matches` streams persisted JSON into
six-field summaries without constructing gameplay cards, RulesEngine, or agents.
Loaded controllers override disk metadata under their mutation locks. Completed
matches stay stored and directly addressable but are omitted from discovery,
as before. Existing loaded controllers are never replaced by explicit restoration.

Every match-ID endpoint enters `coordinated_match`. A process-local reentrant
load lock publishes one controller on a cache miss, then releases before acquiring
its mutation lock. The original revision, receipt, fingerprint, rollback and
privacy logic remains unchanged. Start receipt reconciliation uses the same loader.
Explicit `_restore_active_matches(repo, match_id=None)` remains an eager API.

## Independent Benchmark

Two uninstrumented runs, same owned local database with 520 synthetic canonical
Island snapshots, seed 1729. Saved-only lifespan excludes builtin/expansion/job
startup. This is not the parent's captured corpus or their profiler experiment.

Before: startup 4.7821/4.5130 s, 520 resident controllers.
After: startup 0.0172/0.0034 s, zero resident controllers.
Cold listing: 1.1178/1.1050 s, zero resident controllers (eager hot list ~5 ms).
First cold read: 0.0416/0.0114 s, exactly one resident controller.
Input, summary and full restored state/config digests match before and after.
Full eager digest restoration occurs outside all timed intervals. Reported
process-lifetime peak RSS includes that eager parity phase and is not evidence
of startup-specific memory reduction. List remains O(total persisted JSON size).

## Boundaries And Acceptance

Malformed envelopes are skipped by discovery. Full by-ID deserialization remains
authoritative: structurally plausible but deeply corrupt snapshots can appear as
metadata and subsequently return 404. No universal corrupt-JSON equivalence claim.
No gameplay hydration or duplicated full serializer validation in the summary path.

The original recovery/API gate is 128 passed / 5 failed. Four existing fresh-process
workers inspect the cache before their first HTTP request. One existing receipt
fixture equates all saved rows with all cached controllers. Neither invariant is
valid for lazy startup. Original files/assertions remain unchanged. New controls
make an actual cold HTTP request before executing every original restart assertion,
and explicitly eager-load the legacy receipt fixture. They are separate acceptance,
not a claim that the original gate is green. Migrating those existing test interfaces
requires separate ownership approval.

## Authorized Test-Interface Followup

The parent authorized both adapters after the immutable failing handoff: explicit
eager restore before the receipt test's inventory capture, and a public cold GET
before the restart worker's direct cache inspection. Every existing assertion is
retained. Their original failures remain evidence, not removed or reclassified.

A separate strict corruption control persists an otherwise valid snapshot with
one card's `counters: null`. Metadata discovery still returns its six-field summary;
full cold GET returns 404 and publishes no controller. Neither request changes or
deletes the saved bytes. Discovery is not a certificate of full restorability.
This explicit supported boundary is distinct from malformed-envelope rejection.
