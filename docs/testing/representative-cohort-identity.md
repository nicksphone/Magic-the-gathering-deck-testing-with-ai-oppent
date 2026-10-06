# Representative Cohort Identity

Repository replay and overnight simulation now consume an existing local catalog
read-only. They do not initialize database schemas or bootstrap decks. Populate a
disposable local catalog separately; use a resolved manifest to avoid repository
access entirely. No SQLite should be executed on NFS.

`prepare_cohort` chooses the newest normalized `(name, source=builtin)` record
by recorded creation time then ID. Historical database records remain untouched.
Every custom/user/file record remains a candidate by stable ID; same-name records
are not merged. Exact repeated IDs deduplicate; conflicting facts for the same
catalog ID fail explicitly. Catalog IDs are scoped to one repository, not a
cross-database universal identity.

Identity is serialized JSON: `['record', normalized_source, positive_int_id]`, or
`['source-name', normalized_source, original_name]` for source-only inputs. Empty
source on an ID-only input means missing source provenance, not an invented source.
Names are preserved verbatim. No report-name suffixes or artificial deck labels
are generated. Legacy inputs with neither source nor ID retain raw-name behavior.
Conflicting source/name-only or legacy-name-only inventories fail explicitly;
identical repeated inputs deduplicate instead of silently discarding different boards.

Classification uses the existing local canonical hydrator and actual analyzer.
Complete sourced card readiness, full type coverage, positive confidence, and no
missing/partial/fallback signals admit a resolved classification. Otherwise the
effective archetype is `unknown`, with stored label, actual analysis, source/hash
provenance, and status retained separately. This is heuristic data analysis, not
learned quality, calibrated confidence, or Oracle execution certification.
Selected unknown/incomplete cohorts cannot execute simulation or be exported as
resolved identified inputs. Repository rows are never relabeled by this adapter.
First-time cold import fallback remains unfixed; local offline seed availability
can nevertheless allow a read-only cohort classification without updating it.

Legacy v1 manifests retain unique names, verbatim resolved inputs, existing corpus
hashes, and original name-based pair seeds, including extra legacy metadata fields.
Identified cohorts use v2: every key must match its ID/source facts, keys must be
unique, all entries are validated before truncation, and card data must be ready.
Duplicate display names are permitted only with distinct canonical identities.
Writing either version validates before file creation; malformed or ambiguous
exports cannot produce an un-restorable manifest. Mixed legacy/identified inputs
without identity keys for every entry are rejected rather than silently aliased.

V2 pair seeds hash JSON identities/index; v1 seeds preserve the original
`sha256(left_name::right_name::index)` prefix. Seed values remain 32-bit hashes,
not a mathematical collision-free guarantee. Explicit identity keys disambiguate
pair/seat/winner diagnostics even when display names match. Overnight preserves
legacy unannotated artifact shapes and uses deterministic seeds for identified
cohorts; it does not adopt new AI policy or opponent-information access.

Focused desired contracts and manifest compatibility tests are separate from the
frozen 20-case characterization artifact. Baseline characterization evidence is
historical, not a desired assertion to retain after an intentional selection fix.
