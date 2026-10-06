# Bounded Provenance-Backed Seed Face Colors

Qualified source target: c16ea8dde513c32477f8463e2a008f518d6fa4b7.
Product scope: exporter and generated builtin_oracle_seed.json only.

## Canonical Versus Derived Facts

Scryfall's live schema at https://scryfall.com/docs/api/cards#card-face-objects
allows absent face colors. Its official pinned api-types commit
c16cdfba9e09a0d3aef9ef0db6c36153a7529615 does not require side-level colors
on Adventure faces. Original bulk bytes, Oracle, art and IDs are not modified.

The admitted corpus is eight exact printings/sixteen faces: ten explicit canonical
color arrays and six derived_rule_fact arrays. Derived rows use only their own
complete face mana costs and exact source-hash semantic admission. Train Troops
is white even though the root Imodane card is red. No root colors/color_identity
copying, card-name dispatch or universal Oracle absence recognizer exists.

Official CR effective 2026-09-25, SHA256
8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca,
provides the derivation basis. The six reviewed faces have no color-defining ability.
Unknown symbols, indicators, Devoid/CDA/unsupported admission, stale hashes,
conflicting facts or missing exact printing fail closed. The admitted cost grammar
is primary W/U/B/R/G plus numeric generic symbols only. Hybrid, Phyrexian, X, C,
S and empty/missing costs are deliberately unadmitted for derivation. Existing
explicit canonical face colors do not require deriving from their costs; all five
transform back colors are explicit, including their canonical indicators.

The external fact ledger has fact_schema_version=1, fact_kind, fact_path, genuine
printing/Oracle IDs, raw/input/Oracle hashes, CR version/hash, derivation version,
basis and runtime_effect_certificate=false. Six rule-derived facts retain explicit
raw_colors_present=false; ten canonical facts have no derivation proof. The original
schema/source string is preserved, so consult this ledger for fact provenance.

## All-119 Preservation And Loyalty

The exporter reads SQLite in mode=ro, never syncs, and verifies local JSONL bulk
and semantic-admission bytes against explicitly supplied SHA256 pins. Exact-printing
bulk is available for all eight face cards and all five loyalty cards. The current
Oracle bulk contains 102 of the seed's 119 exact printing IDs; the other 17 unchanged
cache facts are preserved, not newly claimed bulk-verified or silently reprinted.

Generic exact-printing enrichment fills missing root loyalty and rejects conflicts.
Nissa, Ascended Animist has canonical printed loyalty "7"; the cached schema's lack
of loyalty must not drop it. This is not a named allowlist extension or a claim about
counters after Compleated payment. Every existing root, Oracle, cost, stat, art,
ID, face order, source string and inventory property of all 119 rows is compared
against the preservation seed, excluding only authorized missing face colors/root
loyalty. Output and caller ledger are published only after complete validation.

CLI stages/fsyncs both outputs before replacing either. Each JSON file replacement
is atomic; this is not a crash-atomic multi-file filesystem transaction. Validation
or staging failure leaves existing files unchanged. A machine crash between the
two final renames remains an operational limitation; verify the archived manifest.

Required CLI inputs are --database, --canonical-bulk, --bulk-sha256,
--semantic-admission, --admission-sha256, --preservation-seed, --output and
--fact-ledger. Admission fixture hashes are declared in
backend/tests/fixtures/builtin_face_colors/provenance.json; release archive integrity
uses archive-manifest.json (relative path -> SHA256), NOT an assumed SHA256SUMS file.

## Qualification Boundaries

The unchanged original four desired assertions were RED before and are retained as
ordinary desired tests afterward; their historical module comment is preserved.
Prior missing-field characterization assertions remain immutable archival evidence,
not intentionally RED default collection. The old test-only parity helper is an
explicit dependency; no original bug-characterization module is promoted.

NEW tests cover all sixteen selected faces on actual MatchFactory states for both
seats, existing selection/apply/view helpers, snapshot restore and complete root/RNG
pickle purity. They are printed-color tests, not Commander color-identity tests or
full Oracle execution certificates. NEW actual in-process HTTP tests use fresh
memory/file SQLite, all eight seed-only imports/starts and lazy GET restoration.
They bind both dependency sessions and the lazy restore engine to the OWN database.
No live server, network sync, opponent hidden data or borrowed DB is involved.
