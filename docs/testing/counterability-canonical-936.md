# Canonical Counterability Fixtures

On isolated immutable `93630f38847b7266809a1acf3ebd440ddce94399`, the
counter-replacement family was already backed by nine complete official rows.
Its fixture SHA still matches the existing counter-replacements receipt. This
batch does not redo that family or claim every counter fixture is canonical.

This separate migration covers all seven named positives in
`test_counterability_scope.py`: Allosaurus Shepherd, Destiny Spinner, Stifle,
Counterspell, Llanowar Elves, Cultivate and Lightning Bolt, plus its Island deck.
The old nine-field records are replaced by complete pinned official objects.
Four named parents and Island reuse committed full rows; Stifle uses the committed
native-counter fixture. Allosaurus Shepherd and Destiny Spinner use unchanged
rows from the already archived Scryfall Oracle bulk, with source-line, object,
file and bulk hashes. No new network requests or handwritten Oracle are used.

The local materializers follow the existing canonical Factory/template pattern.
Original IDs, owners/controllers, zones, deck size, seed, StackItems, action
sequence and resource assignments remain unchanged. All eight original test
bodies and eighteen assertion ASTs are identical. The existing explicit stack
frames are counterability protocol fixtures, not proof that an actual activated
ability produced them. Anonymous runtime and invalid-target controls remain
explicit controls; this is not a waiver of the original Task1.3 scope.

## Actual Pure Evidence

Twelve new tests include eight observations at the original real first consumers,
full provenance checks, mutation independence, direct-constructor runtime-default
parity and rejection of printed-field overrides. They do not merely check a new
loader independently of the original tests.

- Whole original module plus fidelity: 37 tests, initially 29 PASS / 8 FAIL,
  0 errors/skips, 2.682s JUnit. All 25 original cases passed; the eight new
  first-consumer comparisons exposed incomplete printed metadata.
- The unchanged same cohort after fixture migration: 37 PASS, 4.273s JUnit.
- Four whole modules: 45 PASS, 0 failures/errors/skips, 5.838s JUnit:
  `test_counterability_scope`, `test_counterability_fixture_fidelity_936`,
  `test_conditional_counter_rules`, and `test_stack_target_kinds`.

All stages used direct FRESH Python `-I -B` and outer bytecode disable, with a
pre-import native audit fence: seven SQL/socket/child denials plus provider-import
denial. All SQL aliases, sockets, processes and providers remained denied. There
was no unexpected I/O, database, remaining child/thread or FD difference.
Source file sets/bytes and runtime 3674 files / 4 links / 429 directories matched
before/end. Generated media stayed in owned runtime scratch. Documentation and
AST-only graph metadata were added separately after terminal; they were not tests.

## Caller Limits

The local `add_card` / `state_with_card` signatures are unchanged, but other test
modules and `browser_fixture_server.py` import them. Their exact static references
are retained in the private packet. In particular `test_hand_activations` has
real HTTP/SQLite cases: neither it nor browser HTTP flows were run under this
pure profile. Other unexecuted callers are not covered by the 45-case result.
No shared helper module, production code, API/schema, parent checkout or live
database was changed. This is bounded fixture evidence, not full Phase1, all
caller, browser, native, AI-strength or release acceptance.
