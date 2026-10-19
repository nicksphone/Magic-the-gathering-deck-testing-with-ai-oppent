# Hydration And Foretell Fixture Contracts

Current hydration deliberately rejects malformed cached face JSON rather than
hiding it behind valid seed data. The existing four parameter identities remain:
empty/absent containers still exercise canonical recovery; `{}` and invalid JSON
now explicitly exercise fail-closed behavior. Their old positive recovery
assertions are intentionally not executed for those two cases. This is a test
expectation correction, not restoration of malformed-data admission.

The foretell BO3 fixture now has both human seats explicitly confirm no swaps
before requesting the next game. All its original reveal/history/public-memory
assertions remain. No automatic confirmation or gameplay policy change.

Original159:154 passed,4 failed and1 harness temp-path error35.94s. Corrected
owned basetemp with source unchanged:155 passed,4 failed34.88s. Final three whole
modules165 passed38.27s, reusing that owned database. New6 malformed-cache
controls separately pass0.87s with SQL/socket/process denied before collection.
The independent fresh combined12-module395-case cohort passes84.26s.

All89 original assertion ASTs remain in order, subject to the explicit two-case
expectation change above;32 unrelated functions are byte-exact. Production,
cache validation and human sideboarding requirements are untouched. Historical
failure ledgers and closed owned SQL are retained privately on NFS under
`current-c6-composed395`, dated2026-10-12. No whole backend or release claim.

