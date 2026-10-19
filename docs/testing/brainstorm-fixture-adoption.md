# Brainstorm Fixture Identity Adoption

Source baseline: `c6dee1fb2ee9fc9d2609a2342492d46b0042c789`.
This is a test-only installer correction, not an AI, rules or capture-policy change.

The original HTTP installer replaced a genuine Factory-created state ID after
private stock capture. Both ordinary Brainstorm and retained channel producers
therefore failed snapshot validation at `sideboard_facts.py:28` before persistence.
The installer now uses the existing explicit `adopt_fixture_state` helper:
validate first, retain the genuine state identity and capture, persist the fixture
under that identity, and replace only the old explicit fixture registration/row.
Foreign registrations and malformed captures still reject. No facts are cleared,
rewritten or recaptured; canonical card data, RNG, physical IDs, gameplay actions
and all inherited assertions remain unchanged.

## Pure Boundary Qualification

The whole new `test_brainstorm_fixture_adoption.py` module used genuine current
Factory/serde and both original position producers. HTTP/controller/repository
callbacks were explicitly inert, as in the existing fixture-binding protocol tests.
The original installer produced **10 failures in 12.81 seconds**, including both
producer families on both seats. After the installer-only correction, the same
whole module produced **10 passes in 9.94 seconds**.

Both gates preserved the complete 3,233-file source map. Precollection native
SQLite constructor/connector and socket denials, plus explicit process-audit and
provider-import canaries, were observed; unexpected I/O was empty. A profile
fence prohibited rule actions, legal-move queries and AI choosing. This is not
an all-native-alias security certificate, actual HTTP/restart qualification,
paid-action acceptance, or a whole-backend/playing-strength result.

The first RED ledger is separately sealed; it is not replaced by GREEN. New
controls retain full captured facts and real canonical cards, verify serde,
unrelated registration preservation, foreign-registration denial and rejection
before controller/persistence changes when the original capture is forged.

## Pending Whole HTTP Qualification

Prepare exactly the original whole `test_brainstorm_http_ordering_goldens.py`
and the whole new boundary module, without selectors, skips or exclusions.
The historical original module has 20 parameterized cases; the new module has
10 observed pure cases. Expected 30 is not an actual mixed collection count.
Real API, paid actions, restart, SQLite owner/backup and physical closure require
an independently issued parent gate. No such positive runtime is qualified here.

## Actual Whole HTTP Qualification

The preceding pending section records the pre-runtime stage. A separately issued
parent one-shot on the same candidate subsequently qualified **both whole modules:
30 ordinary passes, 30 unique JUnit cases, zero failures/errors/skips**, native and
outer exit 0. Outer elapsed time was **38.9516575 seconds**. No selectors, exclusions,
case caps, original gameplay actions or inherited assertions were changed.

This actual mixed gate covers the original API/paid action/choice/restart assertions
and the new boundary module. It is distinct from the earlier pure ten-case gate;
the two results are not added into a fictitious 40-case execution.

All existing **6,116 source files** and **3,678 cached dependency entries**, plus
fixed inputs, were byte-equal before/end. **172 new generated runtime/source output
files** were classified separately, not represented as full-filesystem equality.
All **358 recorded native connections** were closed; no unexpected I/O, jobs,
workers, owned FDs or new live threads remained. The three known owner/child process
identities were absent. All **22 actual existing default/backup/lock files** had
`fuser` exit 1 with empty output, with no residual journals. SQL lease was released
only after external physical closure. This physical boundary is not an all-native-
alias denial or child-SQL-readonly certificate.

Closed private evidence was byte/readback verified under
`diagnostics/ci/brainstorm30-physical-qualified-parent-20261014T062043Z`.
Private snapshots, SQLite files and diagnostic operands stay private; no SQLite
was executed from archived NFS evidence. These component results do not certify
all historical CI rows, the current whole backend, or AI playing strength.

A preceding administrative activation attempt stopped on the frozen launcher's
write permission **before any test, once marker or project SQL/runtime**. Its
zero-execution ledger is retained separately and is not a game/test failure.
The approved activation procedure temporarily grants owner write (`0400` to
`0600`) on the exact launcher solely for the two issued activation literals,
checks the normalized launcher SHA and restores its frozen mode. No runner body,
policy or test source was changed to resolve that administrative stop.
