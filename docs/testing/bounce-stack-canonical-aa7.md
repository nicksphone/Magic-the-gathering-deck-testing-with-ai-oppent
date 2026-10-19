# Canonical Bounce And Uncounterable Stack Fixtures

This test-only component is based on immutable
`aa7fdc6250a0770f225ec8c704740b709f03527d`. It changes only the three named
Petty Theft positive constructors in `test_bounce_rules.py` and the Supreme
Verdict constructor in `test_priority_stack.py`, plus local imports. All nine
original functions, 28 assertion ASTs, engine actions, resources, actor IDs and
target-negative operands remain unchanged. Borrowed Bolt and Borrowed Draw
remain exact synthetic protocol fixtures, not official cards or waived scope.

The complete official `Brazen Borrower // Petty Theft` parent and Supreme
Verdict objects are reused unchanged from the existing pinned seed155 JSONL
and its Scryfall provenance. The finite local SOURCES file pins the source,
provenance, exact lines, raw line hashes, Scryfall IDs and Oracle IDs. No intake,
network, user data or database is involved.

The helper follows the existing counter-family Factory-template pattern:
normalize full RAW, supply complete rules/faces before real Factory birth,
then apply only runtime ID/owner/controller/zone with `dataclasses.replace`.
Petty Theft uses native `select_cast_face(card, 1)`. Its parent, both full
faces, retained physical characteristics and native selected Adventure surface
are retained. No captured stock is cleared, retagged or resealed, and there is
no production or shared-helper modification.

The new fidelity module captures the actual original first consumers. It
checks full source facts and the actual Factory input/result, selected-surface
snapshot roundtrips, and rejection of real body/face corruption. These observer
tests stop before the original rules consumer; the separate unchanged original
tests execute the real consumer and original assertions normally.

Actual pure ledger: initial new fidelity 19 FAIL / 2 PASS; first whole run
27 PASS / 3 FAIL. The three latter failures were a NEW test's raw-to-normalized
face comparison, not a product result. A diagnostic attempt with the same
27/3 result is retained. The final comparator requires every field of the
complete normalized Factory entry, including normalized face image fields.
Exact final test bytes against old fixtures again give 19 FAIL / 2 PASS.
The final three whole modules give 30 PASS, zero failures/errors/skips, in
3.57 seconds, retaining all nine original and 21 new identities with 90 passed
setup/call/teardown reports.

The 150-case unit ceiling, 900-second deadline and 15-second TERM/KILL grace
remain bounded. Preimport controls deny SQLite aliases/direct constructors,
sockets, process creation, provider imports, App/TestClient startup and foreign
writes; all nine deliberate canaries reject. Actual source and FRESH dependency
bytes/links/directories remain equal, with no unexpected denial, database,
child, new thread or FD drift. This is cooperative trusted-source enforcement,
not hostile-code OS isolation. This document was written after the final gate
and is not part of its source-before/after claim.

This qualifies only the stated local pure fixture component. It does not
establish whole-backend, HTTP/SQL, browser/native, original protected replay,
Task1.3 literal zero or Phase1 completion. The inherited graph is navigation
only; parent integration owns the eventual derived graph update.

## Independent P2 Oracle Correction

The original six-path `4d5f4271` packet and all 30-pass/earlier ledgers remain
immutable. Independent review found a gap in the NEW fidelity oracle: selected
card and retained values could agree on wrong typed fields. No actual native
helper leak was established.

A separate test-only epoch adds independently source-derived expected types,
keywords, numeric/printed stats and loyalty for the physical parent and actual
selected Adventure. The finite oracle uses complete pinned source/schema, not
the materializer, Factory output or native selected-face projection as its
expected typed view. Borrower's complete Creature/Flash/Flying/3/1 properties
cannot satisfy Petty Theft's Instant-Adventure expectations. Missing printed
power/toughness remain absent rather than invented printed zero; schema-defined
runtime numeric conversion is separate from those printed strings.

The 59 new rejection controls cover every typed field with coherent current/
retained-value corruption, physical-only corruption, and composite real-parent
trait leakage. Four positive controls preserve genuinely missing noncreature
printed stats. Before oracle correction the same three whole modules give
59 FAIL / 34 PASS in 8.92s, including all original 30 passing cases. With only
the NEW oracle strengthened, they give 93 PASS in 8.40s and all 279 phases
pass once. All old 30 identities remain first, all existing test-function
ASTs are retained, and no original module, helper, source index or production
code changes. No old assertion/action is adapted.

The unchanged original guard retains 150-unit/900-second/+15 bounds, nine
preimport denials, source/FRESH equality and resource closure with no unexpected
I/O. This addendum is post-gate. It closes the stated test-oracle P2 only, not
any broader gameplay, native/browser, SQL, Task1.3 or Phase1 acceptance.
