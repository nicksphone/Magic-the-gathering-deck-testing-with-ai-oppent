# Mill And Selected Sacrifice Committed Batches

Qualified isolated composition on published milestone `cb1ba8f`.
Main checkout and running services are not replaced by this milestone.

## Product Scope

Only `effects.handlers.mill_cards` and the selected sacrifice branch in
`keyword_actions.finish_mechanic_choice` change. Existing private entry receipt
collection and event batching are reused; no collector, executor, schema,
payment, AI or frontend production changes.

Mill retains the original selected top-card set and preflights all replacement
plans/static causes before any removal. Actual replacement shuffles therefore
do not cause sequential repops from the new library order. Genuine graveyard
entries publish after all selected moves commit.

Selected annihilator sacrifice preserves explicit defender selections and the
existing plan/cause/LBF preflight. Entries publish after the complete cohort,
before existing sacrifice/death publication. Library/exile replacements do not
produce fabricated graveyard-entry or death receipts.

## Actual Current-Source Acceptance

- 1,263 PASS across all 37 declared whole modules, 3395 warnings, 627.44s, exit0.
- JUnit verifies 1263 cases / 37 modules with zero failures, errors or skips.
- Original 52-case timing audit remains unchanged; new 48-case controls pass.
- Canonical early/second self-replacing mill cards, two real static shuffles,
  selected annihilator, actual memory/file HTTP, owner/controller, APNAP, private
  views, invalid-action atomicity and restart are included.
- All pre-gate backend source hashes match; no external network attempts.
- Module AST outside the two authorized functions is unchanged; the existing
  destruction helper is also source-byte identical.
- Frontend lint, configured tests and build pass using existing dependencies.

The initial frontend attempt lacked required `MTG_TEST_PYTHON` and stopped at a
test setup assertion. Its log is preserved separately; the full configured
rerun passes without a product change. Backend testing used fresh owned local
SQLite and forbade sockets/external DNS/foreign database writes. No fresh
dependency install, live deployment or browser certification is claimed.

Worker frozen-source results (100 focused / 414 neighbor passes) remain
independent evidence, not sums used to claim this current-source result.

## Remaining Boundaries

Simultaneous SBA/destruction publication, colored-damage protection, human
legend choices, full stack-face/canonical cast-trigger behavior, resumable
competing replacement choices and broader shuffle-observer ordering remain
separate work. Unsupported resolution may reject after an activation was already
paid; this does not imply that historical payment is rolled back.

Private source, JUnit/logs and closed synthetic database evidence are archived
under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/mill-sacrifice-current-20261006/`.
Active databases never run on NFS. This is not all-card correctness, a universal
simultaneous event model or professional AI validation.
