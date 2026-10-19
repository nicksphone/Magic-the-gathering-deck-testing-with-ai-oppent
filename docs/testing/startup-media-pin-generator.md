# Public startup-media pin bundle

The generator reads an immutable, reviewed public source archive. It creates a
new exclusive directory containing `startup-media-pins.json` and separate
readable SVG files under `fixtures/`. It does not populate the application's
media cache or install an operator artifact.

```bash
python3 -B backend/scripts/generate_startup_media_pins.py \
  --source-root /absolute/path/to/reviewed-source \
  --output-dir /absolute/path/to/new-bundle
```

The output parent must already exist. Source and output paths must be absolute
and have no symlink components. The output must be outside the source tree and
must not exist, including as a symlink. Existing operator files are never merged
or overwritten. Inputs must remain immutable during generation. On an I/O error,
an incomplete new bundle may remain; the manifest is written last. Do not stage
an incomplete bundle or reuse its destination.

This revision accepts twelve finite public file digests, explicitly listed in
the script. The eight `source_module_pins` match the frozen c259 source plus the
reviewed Task1.3 seed API migration: `main`, `decks.bootstrap`,
`card_data.hydration`, `card_data.display`, `card_data.placeholders`,
`card_data.seed_cards`, `decks.expansion_top_decks`, and `persistence.capacity`.
The other inputs are the built-in deck definitions, the historical catalog
helper, and the two committed canonical JSON files. A source change requires a
new finite pin review. Syntax compilation executes no project module.

The existing seed alias functions, historical-entry functions, expansion `_entry`,
and placeholder `_family`, `_slug`, `_svg_for` are selected from their pinned ASTs.
Only these existing pure bodies and the pinned expansion expression execute in
a standard-library namespace. No module imports `main`, creates an application,
runs a lifespan, opens SQL, starts a child process, or contacts Scryfall. The
public historical catalog is read solely to reconstruct the expansion global;
its card data are not emitted as an additional placeholder authority.

The manifest uses the guard's existing schema exactly:

- Eight source byte hashes in `source_module_pins`.
- `seed_cards_structural_sha256`, `builtin_decks_structural_sha256`, and
  `expansion_decks_structural_sha256`, calculated with the guard's exact sorted,
  compact, UTF-8 JSON formula.
- `startup_media`, keyed by the existing placeholder filename. Each row has
  `name`, `type_line`, `seed_row_sha256`, `content`, and the SVG UTF-8 `sha256`.

The public inventory has 11 built-in decks, 53 expansion entries, and 149 distinct
printed startup names. Every name joins an actual seed row. The bundle includes
all 155 seed entries and their exact canonical-name aliases, a finite superset
of those startup inputs; it does not claim that every fixture is written at
startup. Unknown names, fabricated back faces, missing fields, modified rows,
and modified helper bytes cannot expand this set. The old convenience lookup of
`Delver of Secrets // Bogus Face` does not emit an artifact row for that name.
Committed Oracle, provenance, RAW, and face fields remain unchanged.

This bundle establishes reproducibility and consistency, not runtime authority.
The existing guard remains unchanged: actual frames, repository/owner identity,
closed admissions, exact source/global/row/content hashes, absent-once writes,
and the operator lease still apply. Existing user databases, caches, or metadata
may yield different runtime characteristics and fail that guard; the generator
does not inspect or certify them. Independent readiness review and parent
approval are required before staging the manifest or running SQL/browser control.
