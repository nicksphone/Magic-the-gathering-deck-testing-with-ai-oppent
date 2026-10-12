# Canary Finalization

The test audit hook retained its function but looked up module globals after
interpreter shutdown cleared them. This produced an ignored `AttributeError`
after an otherwise passing API run. Capturing the existing ContextVar and
thread-identity function in defaults fixes that lifetime mismatch. The active
flag, exact thread check, event set and exception types are unchanged.

Three regressions fail against the old hook and pass against the correction.
All seven original parametrized native SQL/socket canaries and those three
regressions pass together. The separate whole API/provenance/finalization cohort
passes all 51 tests in 175.95 seconds, without the shutdown exception. A missing
public fixture collection error is preserved separately; its exact Git fixture
was restored before the compatibility run. No product code or CI permission is
changed. These are component results, not whole-backend qualification.

Verified private evidence is in the RCHFiles
`diagnostics/ci/canary-finalization-qualified-20261012-fvcftwlc` archive;
no private payload is published.
