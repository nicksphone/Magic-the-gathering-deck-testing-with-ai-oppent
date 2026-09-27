# Targeted ETB Trigger Boundary

Supported single-target ETB clauses choose a target when their triggered ability is put on the stack, after simultaneous trigger ordering and before either player receives priority. The permanent spell itself does not announce the target. The target choice is serialized with the match, restricted to the controlling human seat, and validated against current target type, protection, hexproof and shroud. A trigger with no legal target is not placed on the stack. If the chosen target becomes illegal before resolution, the ability does not resolve.

The bounded interpreter recognizes ETB sentences with one artifact, enchantment, creature or permanent target and an implemented effect key. Reclamation Sage is the canonical regression fixture: both a friendly Sol Ring and opposing Smuggler's Copter are legal; a human can select either. For unattended play, destructive effects prefer opposing legal permanents. The AI fallback is deterministic, not a claim of optimal strategy.

`backend/tests/test_trigger_target_choices.py` covers timing, both seats, rejected choices, snapshot recovery, simultaneous ordering, target loss, unattended selection and no-target behavior. `frontend/tests/browser-human-actions.mjs` covers one production-component/API target-choice path in a loopback-only isolated fixture.

Validation on 2026-09-27: 853 isolated backend tests, frontend production build/unit checks and eleven browser paths pass. The seeded two-game Aetherdrift Aggro/Karlov Manor Control BO3 replay finishes without timeout or deterministic drift; it is not a strength or balance measurement.

Still open: optional "may" choices at resolution, non-ETB targeted triggers, modal and multi-target triggered abilities, complicated controller/type qualifiers, nested triggers during pending choices, and comprehensive last-known-information handling when a source changes zones or faces.
