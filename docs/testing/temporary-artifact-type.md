# Temporary Artifact Type Addition

This component is based on published
`a2fbcc99ca4b093224e93c5c2fde98db7e8804e3`. It connects one complete printed
instruction to the existing object-bound type-effect engine. It does not add a
new type layer, change public schemas, or special-case a card name.

At its input boundary, the compiler admits the complete instruction "Target permanent becomes an
artifact in addition to its other types until end of turn." before reminder
stripping. Unknown suffixes, including parenthesized instructions, remain
unsupported rather than granting a partial reward. The handler reuses
`add_type_effect`; ordinary target validation, retained target references,
snapshot serialization, copiable values, and cleanup remain shared paths.

A subsequent shared-path review found that activated-ability extraction could
remove parenthetical text before this compiler was called. The five malformed
body cases below invoke inference directly; they did not certify that earlier
extraction boundary. The later [RAW occurrence correction](activated-raw-occurrence.md)
retains the actual printed body through legal offering and activation, and tests
unknown parenthesized bodies through both checked and direct engine actions.
The original 35/219 results below remain historical component evidence, not
retroactive proof of that later correction.

## Actual Qualification

The same 35 new cases first produced **25 failures and 10 passes**, then
**35 passes in 4.14 seconds** after the three-file correction. No test changed
between those runs. A subsequent declaration of eight whole modules produced
**219 passes in 84.95 seconds**, including every earlier 128 activation-copy
case. No failures, errors, skips or filtered test cases are counted as passes.

The eight modules are:

- `test_temporary_artifact_type.py`
- `test_devotion_compiler_precedence.py`
- `test_temporary_characteristics_layer_readers.py`
- `test_self_entry_devotion_priority.py`
- `test_rings_activation_copy_native.py`
- `test_chandra_native_copy_targets.py`
- `test_loyalty_copy_boundaries.py`
- `test_loyalty_counter_costs.py`

Full retained official inputs are materialized at factory birth. Real checked
Coating activations pay the tap cost, affect own or opposing permanents, survive
snapshots, exclude the later type addition from copiable values, and expire at
cleanup. Actual paid Cloudshift and Disenchant responses test target reentry
and source departure respectively. Hexproof/protection tests use explicitly
labeled resolved-keyword primitives; malformed bodies are noncanonical grammar
protocols, not altered positive card fixtures. Opposing-target coverage does
not certify a separate owner/controller mismatch scenario.

The inherited pre-import runner denies eight native SQL/socket/process/provider
canaries. All gates have zero unexpected I/O, unchanged source and release
runtime bytes, equal FD sets, no children or non-main threads, and no database.
These are trusted-cohort local rules tests, not hostile-kernel isolation,
HTTP/cold-database, physical browser, Steel copy-on-entry, whole Phase 1, or
release acceptance.

Static preparation initially listed three mixed modules. Source inspection
found their HTTP or subprocess tests before any execution; the actual pure
declaration above excludes those whole modules, not selected failing cases.
Their unexecuted preparation list remains in the evidence packet. The final
documentation and AST graph are generated after gates; tested code hashes
remain pinned separately.
