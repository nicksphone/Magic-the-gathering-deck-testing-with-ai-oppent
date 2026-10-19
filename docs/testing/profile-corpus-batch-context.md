# Batch-local tactical profile context

`profile_corpus` prepares the built-in estimator's supplied corpus normalization,
deck analysis, weighted curve and corpus fingerprint once per invocation. This
context is local to that invocation, never a global/persistent result cache. Each
profile receives its own deep-copied context, including nested caller-declared
archetype data. Card normalization, input hash, face compilation, full printed
body and known-gap derivation still run separately for every card.

`derive_profile(card, corpus=(), *, archetype=None)` retains its signature and
single-card evaluation order. The shared private helpers reuse the original
formulas; numeric coefficients, tags, schemas, source identities, quantities and
legal-action policy are unchanged. The script's existing injected estimator seam
retains its original call contract; arbitrary replacements are not silently
batched. Context preparation remains inside the per-row error boundary and after
card validation. No valid rows means no eager context validation or analysis.

## Qualification

Base: immutable `8ad9724fb69641a731f39ed7a2074962f5dce57c` source. Three unchanged
whole modules (`test_knowledge_profiles`, `test_knowledge_profile_review_regressions`,
`test_knowledge_profile_sync`) contribute55 ordinary cases, plus NEW11 batch
controls:66 ordinary PASS and10 subtest PASS54.24s/exit0. XML has66 unique cases.
Pre-import public/native SQL and socket aliases and process canaries denied;
no unexpected IO/default database creation. Source before/end matched. Initial
NEW11 included two small-fixture index failures (Bears absent from155 snapshot);
those remain recorded separately from corrected three strict assertion REDs
(3FAIL1.48s) and three GREENs(3PASS1.42s). No old tests/assertions were modified.

The PUBLIC shipped155 snapshot pin is
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.
Measured plain in-memory synthetic storage uses the real canonical-row validator,
not a SQL Repository/native CLI. Before/after report and complete write payloads
are byte-identical(1,179,939 bytes), SHA256
`e95ac7cca3fc26a58869a5956518cdc655a3709e01d5e83d5a62d47b20fcc26c`.
Measured `_raw` calls24,196->326; analysis155->1; corpus fingerprint155->1.
Observed profile function elapsed10.721s->0.860s on this single instrumented
synthetic155 run. These are observations, not a native speed guarantee or
statistical performance claim. Repeated idempotence, weighted/declarative context,
full face outputs, payload/input/context hashes, limitations/known gaps and
nested ownership controls are covered without changing canonical input bytes.

## Independent Parent Acceptance

A fresh parent checkout of the same production increment passes those same four
whole modules: **66 ordinary cases and ten separate subtests, 54.17 seconds,
exit 0**, with source before/end equality, five genuine native pre-import
denials and no unexpected IO. The first parent attempt ends exit 4 before any
test executes: pytest selects the caller's home directory and encounters an
unrelated unavailable backup mount. That collection failure is retained. Only
the caller's working directory and explicit owned `--rootdir` change for the
complete passing run; source, guards, test bodies and module list are unchanged.

The separate real repository/CLI run uses an immutable `8ad9724f` archive with
only the two approved production postimages. It exits zero in **25.649 seconds**:
the actual default CLI checks 149 names and the same report independently checks
all 155 seed names, with no missing cards or pending rulings. All 155 canonical
objects, 443 rulings and 35 verified empty lists persist; profiling updates 155
rows once and zero on repetition. Real hydration/readiness checks all 155.
The probe, engine and owned local SQLite handles close, direct existing-file
`fuser` returns one with empty output, and source/harness before/end match.

After that release, a separate exact-two-file read-only comparison checks every
semantic column of all **155 CardKnowledge and 155 CardCache rows** against the
previous current-source run. Canonical bodies, profiles, faces, input hashes,
context, rulings and cache payloads match. Only row IDs, update timestamps and
the two explicit fetch timestamps are excluded and recorded separately. Both
database file hashes remain unchanged; ATTACH and writes are denied and both
connections close. No SQLite database is executed on NFS.

The earlier 47.698-second CLI run and this 25.649-second run are separate observed
executions, not a controlled statistical speed comparison. Local image and
placeholder coverage remains zero in the fresh image folder. This acceptance
does not prove natural/native game performance, measured AI improvement,
arbitrary decks, all rules or release completion. No numeric weights, body rules,
sideboarding/planner or SDK/capture allocations change.
