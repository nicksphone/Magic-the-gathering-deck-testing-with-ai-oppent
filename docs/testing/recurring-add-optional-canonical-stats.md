# Recurring Fixture: Optional Canonical Creature Stats

On immutable `76b0befd7b3aed9365c7a5c5b9d20faafa77ef02`, the shared
`tests.test_ai_recurring_engines.add` fixture indexed `power` and `toughness`
unconditionally. Complete official noncreature objects legitimately omit those
creature-only fields. The Phasing of Zhalfir reached this error through the real
linked-entry and entry-route tests.

The fixture-only correction changes two conditions to optional lookups. Present
values still undergo the original integer conversion; explicit null stays null,
and malformed present values still raise. No canonical row, Oracle text, production
code, AI, stock-copy helper, capture, runtime pose or original assertion changes.

## Actual Whole-Module Evidence

All runs declared the same four whole modules, without selection or exclusions:

- `test_linked_entry_counters.py`: 9 cases.
- `test_entry_routes.py`: 18 cases.
- `test_ai_recurring_engines.py`: 24 cases.
- New `test_recurring_add_optional_stats.py`: 9 cases.

The first RED run was 52 PASS/8 FAIL in 11.17s. Six failures reached the helper's
missing `power` lookup; two were a new-test source mistake assuming the existing
reduced Hallowed Fountain caller row was complete RAW. That ledger and new-test
preimage are preserved. Only the new controls were corrected to use the existing
byte-pinned official seed155 Hallowed Fountain loader, with no facts fabricated.

Corrected RED: 52 PASS/8 FAIL in 11.47s, all eight actual `KeyError: 'power'`
failures: four original caller cases plus four new controls. Then the two-condition
helper correction produced 60 PASS in 11.66s, no failures/errors/skips. The new
regression module was byte-identical between corrected RED and GREEN. The original
three modules retain all 30 test definitions and 101 assertion ASTs, and both caller
modules are byte-identical to the immutable baseline.

The unchanged parent pure runner installed its native audit fence before project
collection. Eight expected SQLite/socket/child/provider canaries denied, with no
unexpected I/O. Every run retained equal source and FRESH runtime bytes, 3,674 files,
4 links and 429 directories; FD maps matched, with no database, child or non-main
thread. Credential-free direct Python `-I -B` plus outer bytecode disable,
`--noconftest`, whole-module arguments, and 900s TERM/15s KILL bounds were retained.
Generated media remained in owned runtime scratch, not source.

This document was added after terminal and was not in the gated source inventory.
This is fixture-helper and pure caller acceptance, not SQL/HTTP/browser/native-game,
whole-backend, Phase1, or release qualification.
