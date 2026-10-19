# Color consumer current-main requalification

## Source and patch boundary

Qualified committed main `3ccbdf203a4ee1aeb848e219769c9dfac0f20e8c` in a fresh
source-only checkout `/home/nick/mtg-color-rebase-006PiX`. No parent staging,
main, live database, frontend, CI, mana, costs, engine, or events writes.

The frozen integration patch SHA256 is
`be1d294288c688cc278097e06a67a445ae31e2ecae7907cdc50751b636c6d4b6`.
`git apply --check` passed and it applied unchanged. Production changes remain
the same five files: handlers, static_conditions, protection, targeting, and
stack_engine (27 insertions, 16 deletions). No production adjustment was needed.

Committed main lacks `backend/tests/test_color_consumer_goldens.py` and its
`backend/tests/fixtures/color_consumer_goldens/provenance.json`. Both were
restored byte-for-byte from the immutable frozen qualified source archive.
These new-file qualification prerequisites are a separate patch, not a fixture
rewrite or modification of HTTP test dependencies. All twelve canonical source
receipts match their existing hashes. The original 45 tests plus four supplemental
retained-source projection tests are unchanged.

Current main's parent-owned basic_land_layer/type_effects optional-metadata
increment remains intact. The old helper hash therefore differs intentionally;
it was not reverted. Current baseline helper, type_effects, and events bytes
remain unchanged by this candidate.

## Executed qualification

Reused `/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`, Python 3.12.3.
All eight exact backend requirement pins matched installed versions.
No dependency installation, external services, or model downloads.

- Focused: 49 ordinary passes in 9.60 seconds.
- Full affected scope: 380 ordinary passes in 32.65 seconds, 15 modules.
- All nine existing HTTP cases executed and passed, verified individually from
  JUnit; no `-k` exclusions, deselections, skips, xfails, or parallel workers.
- Both-seat snapshot/restore, retained incarnation, rejected-action immutability,
  source/target projection and opponent hidden-information controls remain in
  the unchanged focused and affected tests.
- The focused run made zero SQLite connections. The affected run made 13,
  all to the initially absent checkout-local `backend/mtg_lab.db`.
- The audit rejected any other SQLite path or socket connect/bind; zero blocked
  attempts occurred. SQLite read-only integrity verification returned `ok`.
- Existing HTTP TestClient lifespan startup, deck seeding, persistence, explicit
  restoration, and original rejection assertions were not bypassed or patched.
- The archived state-only receipt reproducer was rerun successfully with its
  required output argument. Its first argument-less invocation failed at output
  writing, after simulation; that invocation is recorded separately, not a gate.

The 72 affected-run warnings concern existing `datetime.utcnow()` defaults in
Pydantic fields, not test failures.

From checkout `backend/`, with `E` pointing to the archived evidence harness:

```sh
PY=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
PYTHONPATH="$PWD" AUDIT_OUTPUT="$E/focused-audit.json" PYTEST_ADDOPTS='' \
  "$PY" "$E/qualification.py" -q \
  tests/test_color_consumer_goldens.py \
  tests/test_retained_source_type_projection.py --junitxml="$E/focused.xml"

PYTHONPATH="$PWD" AUDIT_OUTPUT="$E/affected-audit.json" PYTEST_ADDOPTS='' \
  "$PY" "$E/qualification.py" -q \
  tests/test_color_consumer_goldens.py \
  tests/test_retained_source_type_projection.py \
  tests/test_basic_land_hooks.py tests/test_basic_land_layer_goldens.py \
  tests/test_basic_land_replacement_composition.py \
  tests/test_colored_mass_exile.py tests/test_static_parser_cache.py \
  tests/test_targeting_advanced.py tests/test_static_ability_suppression.py \
  tests/test_counterability_scope.py tests/test_copy_stack_characteristics.py \
  tests/test_cant_prevent_scopes.py tests/test_prevention_replacement_edges.py \
  tests/test_hexproof_variants.py tests/test_combat_ability_provenance.py \
  --junitxml="$E/affected.xml"
```

## Frozen handoff and limits

Evidence archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/color-consumer-current-requalification/20261006-3ccbdf2`.
It retains the exact committed baseline archive, qualified source, original
frozen integration, current-base production and complete integration patches,
separate qualification-prerequisite and report patches, JUnit, logs, connection
audits, stopped local database copy, source manifests, and AST-only graph refresh.
The older frozen archive remains untouched.

The complete current-rebase patch contains the unchanged integration plus the
two missing new-file prerequisites and this new report. The separate production
patch contains no prerequisite or documentation changes. No additional production
compatibility adjustment is proposed.

This qualifies only committed `3ccbdf2` plus the frozen integration and exact
test prerequisites. It does not qualify the parent's later dynamic-death,
remaining-guard, or cycling composition, all color readers, all Song of the
Dryads interactions, or entire corpus coverage. Existing controlled setup seams
remain labelled as such; no sorcery-in-response legality is asserted.
