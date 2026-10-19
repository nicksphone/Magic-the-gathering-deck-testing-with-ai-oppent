# Tactical Profile CLI: Physical Legacy-Copy Qualification

The original Task2.1 command runs twice on one disposable local database copy,
using immutable source `049d6d188447534d5c3640e1a2a456fa9e581702`.
All 1,993 backend files independently match published `ad87f4fd`; the later
commit changes documentation only. This is executed CLI evidence, not a new
unit-test count or a live deployment migration.

```bash
python -m scripts.sync_corpus_cards --database /owned/local/working.sqlite --profile --out /owned/private/pass1.json
python -m scripts.sync_corpus_cards --database /owned/local/working.sqlite --profile --out /owned/private/pass2.json
```

The actual commands use the same owned absolute database path and different
private report paths. No force refresh, search, additional name, deck-specific
context, network request, game or external AI call occurs.

## Observed Results

| Result | First Run | Identical Repeat |
| --- | --- | --- |
| Exit | 0 | 0 |
| Requested names | 158 | 158 |
| Cached names | 158 | 158 |
| Synced names | 0 | 0 |
| Unique profiled knowledge rows | 150 | 150 |
| Updated profiles | 150 | 0 |
| Errors | 0 | 0 |

Aliases account for the difference between names and rows. The complete
supervised worker takes 19.487 seconds, including checks; per-pass measurements
including preservation checks are 8.399 and 7.045 seconds, not a throughput or
AI-performance benchmark.
The second run leaves all table contents and timestamps unchanged.

## Preservation

Only the five declared estimate columns, a new 18-key `tactical_profile`
namespace and `updated_at` change on the 150 selected rows. Their initial
tactical namespaces are absent and their flat estimates are unset/default.
Every pre-existing profile value remains equal after removing only the new
namespace, using type-preserving deterministic JSON encoding. The enclosing
JSON text is reserialized by the original repository; raw string identity is
not claimed for those intentionally updated rows.

All 38,540 untargeted knowledge rows, all eleven other tables, cache contents,
decks, canonical card objects, rulings, provenance and schema remain unchanged.
The original CLI's `create_all` is a no-op. All 3,333 source files match before
and after. The CLI wrapper does not take its own immediate before/after runtime
inventory; an earlier read-only run's inventory is not relabeled as that proof.
Independent parent checks reconcile the protected projections and full repeat
snapshots, not just the command's summary counters.

All 150 selected rows have matching Oracle IDs and valid stored ruling pages.
Eighty-two lack newer optional per-row hashes/provenance objects, rather than
having mismatching hashes or false verification flags. Those legacy absences
are preserved; no refresh is manufactured to satisfy a new audit predicate.

## Boundaries And Closure

The context is the supplied unique corpus, not a quantity-weighted stored deck
or verified archetype. The output contains heuristic estimates, not learned
matchup evidence, measured playing strength or rules-support certification.
This copy does not authorize promotion into the operator's live database.

One pre-existing cache/knowledge surface discrepancy remains unchanged in this
historical qualification and is not profiler input. A later, separately qualified
[canonical cache-rule recovery](canonical-cache-rule-recovery.md#original-cli-on-the-physical-legacy-copy)
repairs the same owned copy on corrected source while preserving every knowledge
row and profile, then repeats with zero changes. That does not retroactively
change this earlier source, result or final hash.
Known generated tactical structures are replaced as units; this initial
namespace-absent run does not certify preservation of extensions inside an
already populated known structure.

Nine tracked database connections close, engines are disposed, no extra thread
or owned file descriptor remains, no default app database or journal appears,
and actual existing-path handle checks are empty. The fixed lease releases at
2026-10-15 19:38:11.087946 UTC. The closed copy is restored to mode `0400`.
Its final SHA256 is
`79f96dd9f2d8231c83457391c28062bcc255c10c003d1f4b8efa8d19d3438668`.

The earlier read-only annotation failure and conservative provenance check
remain separate historical ledgers. This result does not complete the remaining
Phase2 scoring migration, matched quality comparison, whole current CI or release.

Private immutable evidence is archived under the project's RCHFiles storage at
`diagnostics/ci/phase2-task21-profile158-cli049d-qualified-20261015-y5zstd6k/`.
Its report SHA256 is
`951d76d8dbb1ade255ffd4dac0504a690ad662f575cf139ce4bdb45f9bf726ba`;
the closed source/database/evidence archive SHA256 is
`b5802cab92ffd9adfbca7d8ff96465c0051a114a9b45247f6862ad0e93500435`.
All outer checksums and member bytes are verified; no SQLite execution occurs
on the archive share. Raw names, profiles and database contents remain private.
