# Optional CI interruption observation

This change adds diagnostic observation only to the backend pytest evidence and
sanitized metadata reporters. It does not change pytest execution, mandatory
session/phase ledgers, audit, exit status, coverage completeness or CI eligibility.
No backend rules, API, AI policy, dependency or workflow limits change.

The optional `interruption.jsonl` record has schema version 1, hook
`pytest_keyboard_interrupt`, and only four identity-based categories:
`KeyboardInterrupt`, `PytestInterrupted`, `PytestExit`, `Other`. The native
traceback walk stops at 256 hops; at most two innermost eligible public Python
frames carry relative source path, positive line number and source SHA-256.
A truncated walk exports no frames. The metadata consumer requires verified
committed public-source frames using its existing validator.

Messages, exception args, locals, dynamic class names, private paths, node
parameters, credentials and environment payloads are not exported. No record
leaves the legacy metadata projection unchanged. A malformed, ambiguous,
duplicate, symlink or unverifiable record yields only a fixed degraded marker,
not a selected first record. Optional writer failure cannot disable the mandatory
ledger. The signature is attribution, not proof of why a CI run was interrupted;
historical missing-phase and exit-2 causes remain unknown.

## Qualification scopes

The immutable source base was `136917284d963c076855d2452f86f8de74fbe9ff`
plus the three observer/reporter/test postimages. No current moving checkout was
used. The original optional privacy class passed 14 pure tests; its historical
full reporter run passed 185 ordinary tests in 34.348 seconds across all 14 whole
files, using the original unfiltered unittest discovery command. That run mounted
an extra legacy reporter preimage for one new test and is NOT a portable public
checkout certificate.

A clean source-only copy without that external preimage reproduced one error in
the new absent-record test (13 passes). The test-only correction compares the
complete absent-record export against the same current build with the optional
`interruption_fields` composition patched to `{}`. The exact equality assertion
is retained; it no longer loads an outside-checkout helper. All 66 pre-existing
function/method bodies in the test file, including helpers, remain unchanged;
this body count is not a test count. The file retains its original 46 ordinary
tests and adds 14 new ordinary tests. Immutable historical reporter-body
and single-line inverse witnesses remain separate evidence, not this mocked
composition test.

The corrected privacy class passed all 14 tests in 5.378 seconds with source bytes
unchanged and zero SQL, socket or child activity. Its canonical-source fixtures
are explicitly synthetic protocol fixtures, not real Git-verification proof.
The corrected full reporter suite subsequently passed **185 ordinary tests in
34.582 seconds across all 14 whole files**, with exit 0 and qualification true.
The exact unfiltered `python -m unittest discover -s .github/scripts/tests -v`
command was retained. Source3222 and HF3678 entry pins stayed equal; parent
external verification confirmed observed known PIDs absent, existing owned
paths quiet (fuser exit 1), and journals absent. Lease release was recorded
on 2026-10-14 at 04:16:45.127084 UTC. The new pure14 and both full185 ledgers
are distinct stages, not an additive test total.

The full-suite operational boundary uses private network/IPC namespaces, read-only
source/dependencies/host paths, and owned writable scratch with private `/tmp`
fallback. Original child argv, bodies, `-I` and clean-environment assertions stay
unchanged. The two original snapshot SQL scenario bodies retain their original
pre-import SQL/socket audits. This is not a blanket certificate of native SQL or
socket-alias denial for every child, an exhaustive short-lived child count, a
full backend gameplay run, or a retrospective diagnosis of hosted CI.

No outside-checkout legacy fixture, private game trace, harness bootstrap, grant,
runtime database or private evidence payload is part of the public patch. The
portable full-suite continuation uses fresh owned scratch and removes the obsolete
legacy-file read-only mount only; the original discovery command, child code,
physical boundary and 600+15 bounds are unchanged. The corrected terminal and external closure receipts qualify that reporter
scope only. No whole hosted backend, gameplay, release-readiness or global
native-alias assurance follows from it.
