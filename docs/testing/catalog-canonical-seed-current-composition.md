# Current Catalog And Canonical Seed Composition

Base: `55ebc8c6cba982300f85289bdbe3d114fa29b2e5`.
Date: 2026-10-06 UTC. Unreleased branch acceptance, not live deployment.

## Scope

Compose the verified catalog product, seed append and fixture transitions once
over the current counter/search milestone. Preserve original catalog IDs/order
and template identity. Distinguish 51 templates from two historical event lists;
historical OTJ/MH3 imports retain published 60+15 inventories and provenance.
Current-format admission fails closed rather than asserting current legality.

The offline seed grows from 119 to 155 records by appending 36 verified full raw
canonical records. Original nested properties, face facts and derived provenance
remain intact. A historical exporter fixture intentionally retains its explicit
119-record inventory; separate strict tests check the full 155-record admission.
This does not certify a future full-corpus regeneration or new card mechanics.

## Executed Gates

- Nineteen whole modules: 501 passed, 1,418 warnings, 104.20s, exit 0.
- Six whole neighboring modules: 437 passed, 4,717 warnings, 167.86s, exit 0.
- Two separate HTTP processes: catalog 53, both event imports 60+15, stable
  IDs/catalog/inventory/SQLite across cold restart; current imports reject
  atomically. External network blocked; no card-cache/knowledge writes.
- Configured frontend tests, lint and production build: exit 0 each.

Initial unchanged affected gate: 500 passed and one setup error, 205.20s.
SQLite reported database/disk full during fixture setup. Preserve that terminal
ledger; do not classify it as a gameplay defect or a green run. After verified
owned-backup cleanup and a successful write probe, rerun the same declared
modules with explicit isolated basetemp/local database. No source changes.
The transient storage cause was not established, and SSD headroom remains tight.

All databases and running code stayed local; completed evidence and source are
archived under `parent-integration/catalog-canonical-seed-current-20261006/`
on the verified RCHFiles share. Main checkout, live servers and user data were
not changed. Graphify is refreshed after completed test scratch leaves source.

## Remaining Risks

Historical success is neither current-format legality nor a guarantee of strong
play. Metadata coverage is not complete effect interpretation. Full current
backend suite, browser human-flow acceptance, deployment, arbitrary-card rules,
full seed exporter non-lossiness and broad AI-quality measurement remain open.
These gates overlap other milestone gates; their counts are not one full-suite
run. Review historical source context and newly imported card support before
using match statistics as competitive evidence.
