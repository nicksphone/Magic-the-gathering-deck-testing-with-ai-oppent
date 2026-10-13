# Public Inventory Advisory Schema Qualification

Base: `837bf5137a2adaa62a32942ccbde15a568c43545`.

`CardInstance.knowledge_snapshot` increased the declared field count from 49
to 50. Removing only that field reproduces the previous inventory schema pin.
The reviewed replacement pin covers those exact 50 names. Nonempty advisory
snapshots must pass the existing semantic snapshot validator and its live
card-surface binding; they never supply a rules permission. Existing typed
checks, future-field rejection, context guards and permission vetoes remain.

Qualification uses eight unchanged whole public modules, globally denying
SQL, sockets and process execution before collection, plus 24 new tests.
The original baseline was 122 failures / 489 passes; the new baseline was
16 failures / 8 passes. The focused correction passed all 24 tests and the
whole correction passed all 635 tests, with no errors or skips. The final
wrapper exited 0 and all 3,147 source files were byte-identical before/end.
Its XML duration was 177.194 seconds. Actual first-fence native probes were
denied; no database was created. Canonical row projections are not proof of
SQL persistence, source acquisition, native authority or AI quality.

The 122 original failures match the public function multiset from the older
7c5 sanitized CI artifact. The artifact's other 17 protected-trace failures
are a separate parent-owned serialization issue and were not read or run
here. Task44's new `MatchState.sideboard_facts` field requires a separately
reviewed schema epoch; it is not covered by this correction.

This note was added after the final gate. Failed harness setup and the
initial incomplete new row fixture are retained as distinct historical
ledgers, not counted as semantic baseline failures.
