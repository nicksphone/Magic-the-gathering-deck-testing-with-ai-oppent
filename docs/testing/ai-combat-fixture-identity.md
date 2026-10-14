# AI Combat HTTP Fixture Identity

This test-only correction is based on immutable source
`f102874ff5e7a1d9c77873054eb194e8261998d7`.

The HTTP cases in `test_ai_combat_intents.py`, `test_ai_combat_responses.py`,
`test_ai_combat_setup.py`, and `test_ai_defensive_responses.py` previously
overwrote a constructed state's genuine game ID with the HTTP controller's ID.
Captured sideboard facts still belonged to the original Factory ID, so their
strict serialization validation rejected the fixture before the intended
combat/payment assertions ran.

Use the existing `adopt_fixture_state` helper to retain the constructed state's
identity, validate it, and explicitly move the controller's registry and
persistent binding. No facts are reset, reconstructed, or exempted. The four
HTTP setup functions and their imports are the only test-code changes. Every
other function, default stock, canonical row, action, replay path, and all 135
assertions are preserved.

## Observed Qualification

The exact whole-module cohort is 44 intent, 44 response, 70 setup, and 103
defensive-response cases: 261 unique IDs, without pruning or skips.

- Unchanged baseline: 251 passed, 10 failed, 0 errors/skips, 155.17 seconds.
- Corrected candidate: 261 passed, 0 failures/errors/skips, 165.75 seconds.
- All ten baseline failures reached `ai/sideboard_facts.py:28` before the
  respective combat assertions; the genuine identity is preserved in the fix.
- Baseline 40 and candidate 48 native SQLite connections were all closed.
- Source, pinned runtime, and guard inputs were unchanged during each run;
  owned workers, threads, descriptors, journals, PID identities, and external
  file-use checks closed cleanly.

Both runs used the reviewed archived physical private-NET/read-only-host guard,
with SQL restricted to the owned default, its authenticated capacity backup,
and memory. Only root/catalog/count/grant metadata changed in that harness.
The original trusted restore verifier supplies `uri=True`; the audit hook is
not claimed to validate URI flags independently. Process inventories cover
observed descendants, not an assertion that every short-lived child was seen.

This qualifies these fixtures and their existing combat/payment/restore
assertions. It does not certify AI strength, the entire hosted CI suite, a full
benchmark, or a new native/chooser measurement allocation. The measurement
frontier remains 10213 native / 3900 chooser; these ordinary fixture tests are
not charges against that separate benchmark scope.
