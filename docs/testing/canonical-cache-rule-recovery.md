# Canonical Cache Rule Recovery

This bounded component was qualified on an isolated
`01bbd252ee12f34f1289d54f2aba2bb4105972a3` source archive plus the three-file
correction below. It does not certify all Phase 1 requirements or arbitrary-card
gameplay. The subsequent owned-copy qualification below repairs only a disposable
copy; no live deployment database is selected, repaired or promoted.

## Behavior And Preservation

Verified local knowledge can repair an incomplete **selected existing** cache row
offline. The owned fields are `oracle_text`, `mana_cost`, `type_line`, `layout`,
`colors`, `power`, `toughness`, `loyalty`, and `card_faces_json`; `updated_at` changes
only when those rules actually change. The selected primary identity, name,
printing ID, artwork, unrelated fields, and face artwork/unknown extensions remain
intact. Other cache rows and the canonical, rulings, and learned knowledge records
are protected by the regression comparisons. Existing missing-cache recovery still
creates the canonical printing as before.

Hydration uses a read-only coherent physical front and complete ordered face
bundle. Legitimate display-face aliases, different printing IDs, verified empty
rulings, genuinely empty Oracle text, optional legacy hash absence, and existing
pending-rulings hydration remain supported. Split display aliases do not change
physical split-card routing. Malformed facts remain unavailable rather than being
hidden by canonical fallback. Decoded legacy `null` face containers retain their
accepted empty-container meaning; absent face colors are not explicit colorless.

The new fixtures use pinned complete official rows. Their incomplete cache rows,
duplicate candidates, and certain verification flags are explicitly synthetic
protocol inputs, not claims about upstream rulings or the contents of a user
database. In particular, they do not establish that a previously inspected
canonical-printing counterpart was stale or that two exact-name rows existed.

## Actual Qualification

- Final ordinary run: **19 whole modules, 603 unique cases, 603 passed**, zero
  failures/errors/skips, 2,899 warnings, 59.99 seconds, exit 0. This includes all
  original ten-module/235 cases, seven whole hydration/malformed-data neighbors,
  and the two new whole modules (35 cases). Counts are not summed across runs.
- The frozen original new 16-case module first established nine behavior failures
  and seven passes. Earlier fixture-expectation errors remain separately recorded.
  The initial eight boundary cases established five failures; independent review
  then exposed malformed-face exception, null-container/color, and split-alias
  regressions, each retained as a separate RED before correction.
- All 17 original test modules and all original canonical fixtures are byte
  unchanged. Only three existing backend files changed: three existing functions,
  two new pure helpers, and one `datetime` import. Whole-module AST inversion and
  all 1,993 original backend-file comparisons are recorded privately.
- All 6,311 pre-existing source files and the pinned runtime files/links matched
  before/end. The 180 new media/default-database/ownership artifacts are separately
  inventoried; the full source **file set** was not unchanged.
- The inherited fixture runner disposed 243 tracked engines and explicitly closed
  89 remaining fixture connections. All 149 original CLI children returned zero
  and were absent at closure; jobs/live threads were zero. Existing SQLite/lock
  files and owned directories had an empty physical closure scan. The fixed local
  execution lock was released at `2026-10-15T20:34:01.395517Z`.

The inherited parent audit allows owned fixture SQLite and loopback-only network
operations; its hooks are not claimed to be inherited by CLI children. This is
not an all-native-alias, pool-inventory, live-data, browser, or AI-strength
certificate. Private raw test output, fixture databases, source/runtime maps,
historical failures, and receipts are retained in the private evidence archive
`cache-rule-recovery603-01bb-qualified-20261015-QZY8dWAd`.

## Original CLI On The Physical Legacy Copy

The unchanged `scripts.sync_corpus_cards --database <same-owned-copy> --profile`
command then runs twice on the existing local copy with backend bytes matching
published `8083a80e`. This is an actual execution, not another synthetic fixture
or a rerun on a newly manufactured database. The preceding read-only comparison
binds the exact expected cache projection before either write is allowed.

Both passes exit zero: 158 cached names, zero fetched names, 150 profiled rows,
zero updated profiles and zero errors. The first pass repairs exactly 78 of 176
cache rows, changing only the nine rule fields above and their `updated_at`.
All other 98 cache rows, all primary identities and request-to-row mappings,
all 38,690 complete knowledge rows including existing profiles and timestamps,
all eleven non-cache tables and the schema remain equal. Face artwork and
unknown face extensions are preserved. The second pass makes **zero changes**:
all tables, cache timestamps and physical database bytes equal the first pass.
The report's cumulative `repair_rows: 78` is not 78 additional second-pass writes.

The supervised operator takes 20.325 seconds; the two passes including their
checks take 8.365 and 6.998 seconds. These are not game or AI speed measurements.
All eleven connections close without forced cleanup; immediate source/runtime
comparisons match, no network request occurs, and physical handle checks are
empty before the copy returns to mode `0400`. The fixed execution lock releases
at `2026-10-15T21:01:58.705672Z`.

Private evidence is `diagnostics/ci/cache-repair-cli8083-two-pass-qualified-20261015-JIVWcjcn/`.
Its report SHA256 is
`1d8cf2d9b3304d7a76ca6f87e26fb313961b33504fddee0d4a5be7a2748bebc2`;
the verified closed executor/database archive SHA256 is
`fea4a10d479d836205797b4d2d8a206070fcc2fb18fa404e061b46dd9cafc346`.
The final copy SHA256 is
`169a42ce3fc8352e61487dc62a6fdfb9be7daa4b8b80d5b460242f2c5c6074f4`.
No raw database, card-name list or private trace is published. This closes the
observed copied-data cache discrepancy, not live migration, playing strength,
the remaining Phase 1 specification differences or later whole hosted CI.
