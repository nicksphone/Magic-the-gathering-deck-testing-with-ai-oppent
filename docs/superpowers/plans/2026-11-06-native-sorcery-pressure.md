# Native Sorcery Pressure Implementation Plan

> **For agentic workers:** Use test-driven development and independently verify each runtime composition before publishing it.

**Goal:** Stop withholding player-only sorcery damage at own MAIN2 solely because the actor has two or fewer cards, without spending flexible removal or overriding useful planeswalker targets.

**Architecture:** Preserve the existing four-argument player-target policy. Add an explicit opt-in used only by the final damage-target fallback, after native safety checks and its existing forecast. Keep actual target selection, payment and resolution in Forge.

**Tech Stack:** Pinned Forge Java sources, existing JDK/native build, Python operator-profile verifier.

**Spec:** The preserved two-seat three-cast diagnostic and independent source review in `tools/engine_evaluation/forge/native-ai/sorcery-pressure/chain-supplement/README.md`.

## Constraints
- No card-name, deck-name, hand-size-specific or seed-specific exception.
- Only direct targeted DealDamage sorcery spells at the actor's own MAIN2, with positively classified player/planeswalker selector roots and positive forecast damage.
- Preserve earlier planeswalker selection, four-argument callers, cost/tax/backlash checks and existing target/prevention/lifegain guards.
- No live opponent, private model, checkpoint, workflow or game-budget change. Generated game evidence remains private.

## Tasks
- [x] Mencius: write canonical positive and preservation controls, execute their baseline, and retain the unchanged original eight and two-case diagnostics. Corrected baseline: 60 passes/10 expected pressure failures.
- [x] Mencius: minimally modify copied `DamageAiBase` and `DamageDealAi` sources in the new policy subtree; compile and verify genuine choices/payment/resolution with one native JVM. Candidate: 70 passes.
- [x] Parent: test-first approval schema 4, requiring exactly six sources/eight classes; retain schemas 1-3 and all existing publication safeguards. Two new tests rejected schema 4 before implementation; all 22 synthetic tests now pass. No native runtime is qualified by this result.
- [x] Parent: independently review/rebuild the two-source delta, compose the exact runtime, and execute coupled native regressions before app qualification or publication. Eight-class prefix: 70 + 38 + 48 + 4 passed as separate cohorts; one actual built-UI game completed naturally, 248 answers/138.752 seconds.
- [ ] Parent: archive/read back private evidence, update graph/status, and publish only reviewed changes. Passing bounded checks is not AI completion.

## Review Focus
- Preserve useful planeswalker kills and creature removal rather than redirecting them to nonlethal face damage.
- Exclude instants, activated abilities, compound effects and mixed/generic target selectors from the new preference.
- Verify prevention, hexproof, unavailable/taxed mana and lethal own-cast backlash through native behavior.
- Deterministic pressure changes RNG consumption within its admitted domain; do not claim universal RNG or strategic parity.
