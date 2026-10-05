# Persisted Simulator Job Quota

New background simulation starts share a single-process admission lock and a
10,000-row persisted-job quota. The count is a scalar SQL storage query; no
gameplay rules execute in the database.

An existing idempotency key is replayed before the quota check. Conflicting
reuse still returns 409. At the limit, a new keyed or unkeyed start returns
429 with `simulation_job_quota_exceeded`, before hydration, work-slot
acquisition, persistence or worker creation. All statuses count. Existing job
results, polling and cancellation remain available; no rows are deleted.

The quota bounds rows, not database bytes, result size, total request work or
other tables. It is not a distributed/multiworker admission guarantee. Reaching
the limit requires deliberate operator maintenance. Existing offline retention
tools remove durable retry history when they delete jobs; do not run them as an
automatic admission side effect.

`test_simulation_job_quota.py` exercises boundaries, replay/conflict after cache
loss, all statuses, unchanged rejected state, count failures, concurrent
single-process admission and HTTP status/cancellation availability. Acceptance
uses isolated SQLite and dormant workers, not a production load certificate.
