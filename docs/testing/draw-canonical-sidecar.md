# Canonical Draw Fixture Inputs

The frozen `091+entry-copy` component supplied two existing pure modules:
`test_draw_restrictions.py` and `test_each_player_draw.py`. Their nine test names,
36 assertion ASTs, seeds, runtime IDs, resources and engine-action call ASTs are
preserved. Only fixture construction/imports and the named-card retag changed.

Seven full official objects replace partial printed inputs: Island, Spirit of
the Labyrinth, Thought Reflection, Narset, Stinkweed Imp, Vision Skeins and
Prosperity. Existing complete API objects are reused; three complete archived
official bulk rows are pinned in `fixtures/draw_canonical_sidecar/SOURCES.json`.
No provider request, rule-text shortening, production or shared-helper edit is
included. Prosperity now has its genuine Sorcery type, not the old Instant pose.

The new fidelity module observes original effect/inference/cast consumers before
execution and compares every shared `PRINTED` field with real Factory output.
The baseline whole-three result was 11 passed / 10 fidelity failures; all nine
original tests passed. The first whole-five candidate was 26 passed / 2 failures
because the new deck helper used a nested metadata envelope not consumed by
direct Factory construction. Only that helper was corrected to flattened full
facts; the new fidelity test bytes and all old assertions were unchanged.

Final whole-five: **28 passed, 0 failed/errors/skipped**, JUnit 4.006 seconds.
The other whole modules were `test_draw_triggers_no_recursive_draw.py` and
`test_sheoldred_draw_fixture_fidelity.py`. Precollection native SQL aliases,
sockets, subprocesses and providers were denied; all eight canaries passed and
there was no unexpected I/O. Source and locked runtime hashes were unchanged
during each gate. Display/media writes were confined outside the source tree.

These are constructed rule seams, including the retained deliberate `x`/`y`
draw-event protocol operands in the unchanged neighbor. They do not qualify
HTTP, browser, natural-game, full-card-mechanic or complete Phase 1 acceptance.
