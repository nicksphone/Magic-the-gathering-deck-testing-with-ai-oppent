# Targeted ETB Trigger Boundary

Supported single-target ETB clauses choose a target when their triggered ability is put on the stack, after simultaneous trigger ordering and before either player receives priority. The permanent spell itself does not announce the target. The target choice is serialized with the match, restricted to the controlling human seat, and validated against current target type, protection, hexproof and shroud. A trigger with no legal target is not placed on the stack. If the chosen target becomes illegal before resolution, the ability does not resolve.

Supported optional triggers then offer the controlling human an accept/decline decision as the ability resolves. The target is still chosen even if the controller plans to decline. Declining skips the effect and its replacement interactions; an illegal target fails before the optional decision. The pending decision survives snapshots. Unattended play retains deterministic acceptance/decline defaults.

The bounded interpreter recognizes ETB sentences with one artifact, enchantment, creature or permanent target and an implemented effect key. Reclamation Sage is the canonical regression fixture: both a friendly Sol Ring and opposing Smuggler's Copter are legal; a human can select either. For unattended play, destructive effects prefer opposing legal permanents. The AI fallback is deterministic, not a claim of optimal strategy.

`backend/tests/test_trigger_target_choices.py` covers timing, both seats, rejected choices, snapshot recovery, simultaneous ordering, target loss, unattended selection, no-target behavior and optional accept/decline. `frontend/tests/browser-human-actions.mjs` covers production-component/API target and optional-choice paths in a loopback-only isolated fixture.

Validation on 2026-09-27: 854 isolated backend tests, frontend production build/unit checks and twelve browser paths pass. The seeded two-game Aetherdrift Aggro/Karlov Manor Control BO3 replay finishes in 40 turns without timeout or deterministic drift; it is not a strength or balance measurement.

Still open: non-ETB targeted triggers, modal and multi-target triggered abilities, complicated controller/type qualifiers, nested triggers during pending choices, and comprehensive last-known-information handling when a source changes zones or faces.
