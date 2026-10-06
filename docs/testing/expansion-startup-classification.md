# Expansion Startup Classification

## Scope

Only `decks/bootstrap.py` production behavior changes. Expansion existing-row refresh reuses the exact `_admitted_builtin_archetype` contract already used for cold/latest builtin classification: read-only canonical hydration, nonempty complete source-backed ready cards, full type metadata, positive actual analyzer confidence, and no missing/partial/fallback signals. No remote sync, card invention, template-name guesses, mechanics execution certification, table/schema or AI policy change.

An admitted current deck may intentionally refresh a stale label to its actual canonical analysis. An unadmitted existing row retains its historical label unchanged; retained text is NOT a fresh admission certificate. New unadmitted rows still come from the existing generic importer as explicit `unknown`. No extra persisted provenance is invented: classification provenance is available on the existing import result (method, admission version, per-card sources/readiness and canonical board SHA256), and startup qualification records the actual read-only canonical facts.

## Root Cause

Previously the expansion existing-row branch assigned `item['archetype']` regardless of local evidence, although first imports used the canonical generic analyzer. On the frozen human-ready 3eL65X + generic-import candidate this changed 18 expansion labels on restart. Example: LEA's template label Aggro replaced actual Burn. The patched branch no longer uses that catalog label to classify an existing deck.

Latest normalized expansion source identity selection and pre-existing template/reference inventory synchronization are unchanged. Classification updates neither create/delete/rekey rows nor change user or historical duplicate rows. These are simulator expansion archetype templates, not claimed historical tournament decks. Existing inventory-refresh tests retain all assertions.

## Tests and Evidence

`tests/test_expansion_startup_classification.py` adds 48 ordinary contracts across fresh memory/file SQLite and genuine LEA/Burn, DRK/Control, USG/Ramp, ONS/Tribal canonical records. Both offline seed and complete canonical cache are admitted with full import provenance/hash checks. Positive refresh changes only the latest label, retaining all other fields, IDs, same-name user records and historical rows. Missing facts, incomplete Oracle, zero confidence and fallback signals reject admission; existing historical labels remain unchanged. Newly unadmitted imports are explicit unknown and remain unknown across repeat startup. Cache inventory is unchanged. Metadata facts do not certify engine mechanics or strategic strength.

`tests/test_expansion_refresh.py` adds only an empty canonical-cache read method to its test double; all nine existing test assertions remain unchanged. Real repositories already supply that method. All four archived operational contracts and their subprocess driver remain byte-identical, including the formerly red complete catalog-label preservation assertion. The same 80 adjacent recovery/persistence/input/quota/job-cache tests run with an owned local startup engine bound before main import.

Canonical cache can normalize a front-face alias such as Kumano to the actual two-face printed name. Tests compare facts/provenance against the actual parsed import board, not a pre-cache alias. Existing catalog upsert keys are case-sensitive; tests use the exact stored source for same-identity generic reimport. The pre-existing upper/lowercase direct import behavior is not fixed or silently conflated by this classification patch.

SQLite stays local. Evidence consists of synthetic private snapshots, completed subprocess logs, backup files and actual canonical analysis/source receipts archived to verified NFS only after processes exit. This is not a deployment, multiworker, authentication, graceful shutdown, broad settings or production-load certificate. Exact gate outcomes and frozen input/source hashes are in the accompanying report.
