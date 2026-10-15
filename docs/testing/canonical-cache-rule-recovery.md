# Canonical Cache Rule Recovery

This bounded component was qualified on an isolated
`01bbd252ee12f34f1289d54f2aba2bb4105972a3` source archive plus the three-file
correction below. It does not certify all Phase 1 requirements or arbitrary-card
gameplay, and does not repair or promote any existing user database.

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
