# Learned matchup profile protocol

This Task 3.2 component is based on immutable public
`7c5e933a73755b53da5efd50159c1bb248cf4906`. It changes only
`ai/matchup_profiles.py`, adds `scripts/derive_matchup_profiles.py` and one new
whole test module, and ships **no generated matchup data**. The exact signature
and complete original fallback body are retained. Existing agent scoring and
call sites are untouched.

## Admission and lineage

The builder accepts the actual Task 3.1 summary, complete deck export, explicit
source binding, and readonly measured backend directory. It reuses the existing
export, schedule, source-manifest and aggregation helpers. Admission is
all-or-nothing: all 11 builtin decks, all 55 deck pairs, every declared seed in
both seats, resolved BO3 outcomes, complete per-player quality availability,
typed player-indexed game/series wins, sanitized evidence receipts, fixed
resource policy, and equal before/after measured-source closure are required.
Timeouts, draw-cap series, resource stops, unknown classification, duplicates,
partial schedules, missing counters and mismatched pair totals reject the table.
Private game records and raw traces are never read.

The consumer's explicit expected **measurement** lineage is:

- Source commit: `7c5e933a73755b53da5efd50159c1bb248cf4906`.
- Original 1,897-file backend map SHA:
  `57b0b0e28dfa2896b14b52505e8b978da4a6cc3c65202a86b738419101c9003c`.
- Original complete binding canonical SHA:
  `7059b869b0a7693a8d4a463dffc44e39e45708280e56854c499218f2dedd59ce`.

These pins describe the immutable pre-consumer measurement source. Runtime does
not rehash the changed consumer or look up ambient Git, avoiding self-invalidation.
The generated file is read once per process from
`ai/data/matchup_profiles.json`. Absent, stale, incompatible or malformed data
preserves the entire original fallback. Unknown pairs do likewise. Returned
dicts are copies. Re-sealed altered numeric values, incomplete totals and unknown
pairs must still pass semantic sample-to-profile validation; a checksum alone
is insufficient. Synthetic tests explicitly supply a separate synthetic lineage;
that is protocol testing, not production source or execution authority.

The parent's actual all-11 setup hit a separately owned DFC printed-front versus
canonical-full-name admission mismatch before games. This component does not
change `admit_execution_rows`. Any subsequently measured helper/source epoch
requires a separate reviewed lineage update before its data can load. No ambient
repin, old-source/current-release projection, budget change, or reset is inferred.

The corrected coverage payload explicitly carries `roster_schema_version: 1`
and `roster_archetypes`, the verified export's complete builtin-name to normalized
classification map. The consumer requires exactly the shipped builtin names and
known classifications. For each unordered pair of distinct builtin decks, every
seed supplies two seat orders and contributes each participant's direction.
Expected bucket series counts are derived from this roster, not from an assumed
number of archetypes. Same-archetype pairs contribute twice to their single
bucket. Missing metadata or impossible ordered-pair coverage rejects the table.
Reciprocal buckets must have equal series/games, complementary wins, and swapped
own/opposing quality totals. Self buckets require even series/games, half wins,
and identical own/opposing quality. Changing samples and consistently re-deriving
their profiles/checksum does not bypass these invariants.

## Deterministic advisory transform

Series wins and quality counters are attributed using the real `deck_a_seat`:
Task 3.1 `wins.deck_a/deck_b` denote player 1/2, not exported deck identities.
Duplicate archetype pairs aggregate all their series; draws inside resolved
series count as games but not wins. For each ordered archetype pair, with own
and opposing counter totals `a` and `b`, a gap is `(b-a)/(1+a+b)`:

- Proactive delta: win fraction minus 0.5 plus 0.25 times unused-mana gap,
  clamped to +/-0.5.
- Holdup delta: minus 0.25 times redundant-removal gap, clamped to +/-0.25.
- Risk delta: 0.25 times combined bad-block/lethal-miss gap, clamped to +/-0.25.

These deltas are added to the unchanged fallback; final values are clamped to
[-2, 2] and rounded to six places. They are documented descriptive heuristics,
not causal estimates, tuned coefficients, or measured strength. Mirrored seeds
are dependent. All six original quality counters remain required and retained.
Summary identity canonicalizes pair/series order but preserves game chronology;
it is a canonical JSON digest, not a raw-file SHA. Before input reads or
computation, the CLI rejects output within the resolved measured backend and
output with symlink parents, then reserves the **original** output path using
exclusive `xb`. It cannot overwrite an existing input/output alias and never
opens the resolved target of a dangling output leaf. Failed input/derivation
leaves an empty reservation as evidence; it is not deleted or silently retried.

```bash
python -B -m scripts.derive_matchup_profiles \
  --summary /owned/sanitized-summary.json --deck-export /owned/export.json \
  --source-binding /owned/binding.json --measured-backend /owned/measured/backend \
  --output /owned/new-matchup_profiles.json
```

## Evidence and limits

All new fixtures are synthetic protocol rows, not native matches or canonical
deck execution. Initial 33 tests failed strictly, 10.43s. The first green attempt
had 33 setup errors from reused basetemp FD-relative cleanup, 2.41s; it exercised
no learning behavior. A fresh basetemp yielded 32 passes/one determinism failure,
11.55s. Seven re-sealed-table controls then yielded 32 passes/eight strict
failures, 13.85s. Corrected whole new module: 40 passes, 13.87s.

The initial six whole modules passed 87 ordinary tests in 47.57s, with 10 separately
reported subtests, zero failures/errors/skips, unchanged source bytes and no
unexpected I/O. SQL, socket and process constructors and foreign-FD source
mutation were physically denied. TemporaryDirectory cleanup was admitted only
for a literal child of a canonical owned-TMP directory FD. No game runtime,
provider, network or database was used. All 1,897 original backend source paths
except the owned consumer remain byte-exact; its original fallback body and
signature are exact. The Task 3.1 runner remains unchanged.

Independent static review found two P2 gaps in that held candidate: re-sealed
one-sided samples and deletion of both cross directions with totals folded into
a self bucket. Its source and 87-test evidence remain immutable. A fresh owned
correction first produced 40 passes/nine strict failures, 16.45s; corrected
focused whole module: 49 passes, 16.32s. Two additional complete-matrix controls
validate one shared archetype and eleven distinct archetypes, including valid
absence of self buckets for singleton classifications. The final six whole
modules pass **98 ordinary tests**, 52.13s, with **10 separate subtest reports**;
JUnit has 98 unique cases and zero failures/errors/skips. All original 40 test
definitions remain exact; the old file is an exact prefix. Transform, coefficients,
expected lineage and original fallback remain unchanged. Source bytes before/end
are equal, all four physical denial canaries pass, and unexpected I/O is empty.
No genuine matchup artifact was produced, and no game runtime was executed.

A further independent P2 finding concerned the CLI, not table semantics: the
98-test builder could add a new file inside its verified measured source after
derivation. That candidate and its evidence remain frozen. A fresh CLI-only
increment actually reproduced both direct and symlink-parent writes:
`source_equal=false`, `output_exists=true`, `derive_calls=1`. The whole new module
first yielded 52 passes/seven strict failures, 20.16s. Corrected focused result:
59 passes, 19.40s. Both source-write probes now reject with no computation/file
creation and equal source hashes; three existing-input aliases, dangling leaves,
valid external reservation and failed-input reservation are also checked.

The final six-module cohort passes **106 ordinary tests**, 55.94s, plus **10
separate subtest reports**, zero failures/errors/skips. Source bytes before/end
are equal, four physical denials succeed and unexpected I/O is empty. Only
`main` changed relative to the reciprocal-corrected builder; its full-body
reverse restores that builder's entire bytes. The consumer, all derivation
functions/coefficients, expected lineage and old 51 test definitions are unchanged.

Full genuine builtin-pair data, its qualification/installation, parent composition
and independent review, and seeded A/B nonregression of stalls/timeouts remain
open. This is Task 3.2 engineering progress, not completion or a release/AI-strength
certificate.
