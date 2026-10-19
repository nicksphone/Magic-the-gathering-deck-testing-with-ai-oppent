# Canonical Positive Fixture Batch

Immutable base: `0953ac312c0fd9ce24acb43fecb0efac359e1e43`. This test-only
Task1.3 batch replaces incomplete named positive card facts in
`test_deck_analysis.py` and `test_card_image_sync.py`. No production, AI,
classifier, API, schema, dependency, frontend or parent-source change is made.

## Genuine Sources

Six authorized exact-name public Scryfall requests return HTTP200: Flame Rift,
Mystic Sanctuary, Island Sanctuary, Fire // Ice, Old Fogey and Willbender.
`fixtures/canonical_positive_batch/PROVENANCE.json` retains the requested and
response URLs, UTC times, complete response headers/cache metadata, unmodified
body SHA256/size and actual identity fields. Request starts are at least0.5001s
apart. There are no redirects, retries, art, rulings or external-AI requests.

The shared helper reuses the pinned official155 loader and existing complete
Valki, Bala Ged Recovery, Benalish Hero and Grizzly Bears RAW. Wedding
Announcement uses its actual official parent, Wedding Announcement // Wedding
Festivity; the back face is not discarded. Every call returns fresh parsed
objects. Deck metadata is the complete RAW. Cache rows use the existing
`_normalize_payload` mapper, with only the existing local display-image URI
supplied explicitly; no Oracle, face, cost or characteristic is shortened.

All15 original functions remain.42 original assertion ASTs/operands are exact;
one explicitly reviewed counter operand changes from4 to8 for the actual complete
input, as described below. The synthetic Modal Utility case, including its4
counter, is byte-exact. Generic Cached Card/Complete Card, blank-cache,
offline429/error and reporting protocol vectors are unchanged. These deliberately
noncanonical vectors are not claimed as official card facts.

## Actual RED And Post-Migration HOLD

Three whole modules collect27 ordinary cases: original15 plus NEW12. The NEW
module captures the actual old deck/cache builders before analysis/reporting;
ten meaningful fidelity comparisons fail, while all original15 and the two
provenance/freshness controls pass:10 failed/17 passed in2.63s. This is not an
absent-helper import failure. Both original modules are still byte-exact at RED.

After fixture-only substitution, all12 new cases and14 original cases pass.
One unchanged original assertion fails:26 passed/1 failed in2.70s, exit1,
zero errors/skips. The failing split-deck case expects
`face_card_count_estimate == 4`; its actual result is8. The deck contains four
Fire // Ice cards and four genuine two-faced Wedding Announcement cards. The
old handwritten Wedding metadata omitted its back face. The unchanged
classifier counts both populations by their actual ordered face metadata.

This is a genuine changed-input cardinality, not a demonstrated classifier bug.
The original assertion was NOT edited at that stage; its following three checks
(split-card count, average cost and archetype) were not reached. That entire
43-assertion-exact HOLD stage remains immutable in separate private evidence:
RCHFiles `diagnostics/ci/20261015-task13-positive27-HOLD-2UvGncYP`, archive SHA256
`737d4268f577462f6dfd1e6752ff1574db454eb5bd4b2d364ad238a53c2c4c6a`.

## Explicit Counter Correction And Whole Qualification

After source review, the parent explicitly authorized ONLY that expected4-to8
operand change. A fresh isolated0953 derivative uses the unchanged RAW/helper
and adds one independent golden. It captures the actual split-deck quantities,
checks four Fire // Ice plus four Wedding Announcement copies and two genuine
faces on each, and derives eight face-card copies versus four split-card copies
directly from pinned RAW/layouts. It does not call the production analyzer to
manufacture its expectation. No other numeric, archetype or Old Fogey operand is
changed. The four previous fidelity test-function bodies (12 parametrized cases)
remain byte-exact; the golden adds the thirteenth case.

The three whole modules then pass28 ordinary cases in2.76s, exit0. The original
split test's previously unreached three checks now actually pass. The subsequent
ONE final declaration contains eight whole modules: the published original and
fidelity fallback-hydration modules, original and fidelity card-hydration modules,
knowledge-ingest fixture fidelity, both batch originals and the NEW batch fidelity
module. It passes52 unique ordinary cases in5.21s, exit0, zero failures/errors/
skips. The28-case component is included in52, not an additional28 unique cases.
All original Old Fogey checks pass with its complete RAW; nothing is truncated.

## Pure Execution Boundary

Each whole execution has a300-second TERM/15-second KILL bound, explicit owned
backend root/cwd, `--noconftest`, disabled plugin autoload/cache and fresh phase
outputs. Seven precollection physical denial canaries cover three SQLite
aliases, two socket constructors, Popen and provider import. Neither execution
records unexpected SQL, socket, child or provider I/O. One unused imported
SQLAlchemy engine is disposed without connecting; no database is copied/created.
FD sets match, children/extra threads are empty, and2946 runtime regular files
and existing source files remain byte-equal across each execution. Historical
RED creates seven media SVGs; its post-migration HOLD reuses those assets and
adds one SVG for Willbender's genuine creature type rather than the inherited
Instant. The fresh corrective component creates seven SVGs; the final eight-
module gate reuses those warm assets and adds six separately recorded SVGs.

The historical HOLD is not erased or retroqualified. The final result is a
bounded pure fixture qualification, not integration authority, full backend,
HTTP/TestClient, browser, gameplay, Task1.3 literal closure or Phase1 signoff.
Historical/protocol/generated-text scope remains unresolved. No user waiver
is inferred. Parent integration and independent peer review are separate steps.
