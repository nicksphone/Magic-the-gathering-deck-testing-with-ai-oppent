# Bounded spell kicker

## Contract

A shared compiler recognizes one fixed mana kicker on an instant or sorcery,
with supported `If this spell was kicked` instructions. It separates unpaid
and paid effect text without mutating printed Oracle text or faces. Supported
conditional instructions are numeric damage replacement (including divided
damage), fixed temporary pump replacement, fixed draw counts, numeric life gain,
scry and surveil. Recognition is bounded, not a complete semantic parser.

The chosen cost controls targeting and effect construction. Free casting waives
the original mana cost, not the optional kicker cost. Alternative method identity
is preserved. Stack payloads retain the kicked choice; copied spells retain that
choice without paying again, while supported new-target menus use the paid
effect surface. Snapshot restoration preserves announced choices and allocations.

Rules grounding: Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules),
effective 2026-09-25, rules 702.33, 118.9d and 707.10. Rules live in application
code, not SQL. The downloaded primary rules text is archived with test evidence.

## Canonical fixtures and validation

`backend/tests/fixtures/kicker.json` retains freshly obtained Scryfall identities,
Oracle text and source URLs for Burst Lightning, Into the Roil, Shivan Fire,
Gift of Growth and Fight with Fire. No fabricated playable cards or changes to
competitive decks were introduced. A syntax-only alternative-method fixture
tests cost composition; it is not used as a playable card or deck entry.

`backend/tests/test_kicker.py` covers ordinary/free casting at both seats, unpaid
and paid resolution, exact costs, illegal targets, immutable Oracle text,
conditional draw after target legality, sequential untap/pump, snapshot recovery,
copies, human retarget choices and actual AI materialization at all difficulties.
The final focused gate passes 397 tests across kicker and related regressions.

`frontend/tests/browser-kicker.mjs` exercises 24 real App/API cases: both seats,
ordinary/free casts and unpaid/paid variants for bounce/draw, pump and divided
damage. Each refreshes with the spell on the stack before checking resolution.
Frontend lint, runtime contract tests, build and the complete Chromium suite
pass, including natural human/AI and human/human BO3 flows. These functional
checks do not certify the deferred alpha UI's ergonomics.

Final validation on 2026-10-03: 3,896 full-suite tests pass in 616.61 seconds
(364 warnings). The four-template Master matrix completes twelve seat-balanced
logical BO1 samples, each repeated twice, in 509.133 seconds with no timeout,
anomaly, drift or determinism failure. Eight additional traced Tribal/Drain and
White Weenie/Burn games in both seat orders finish in 10-17 turns. Review of
3,240 decision traces finds no invalid cost/target log lines or main-phase passes
with an available legal land play. Available quality counters are zero; one
blocking measurement is unavailable, not passed. These small samples do not
establish matchup balance, optimal decisions or expert strength.

All 148 backend production files are byte-identical across the final full suite,
matrix, browser copy and traced-game copy. Superseded failures are retained
separately, not counted as passes. Evidence and source are archived under
RCHFiles at `diagnostics/kicker/20261003T111127Z/`.
Tests use disposable local source/database copies and the installed venv; this
is not a fresh dependency-install or network-deployment certification.

## Known Limitations and Next Upgrades

- Permanent kicker/ETB effects, cast-trigger kicker consumers, multiple costs,
  multikicker, variable/nonmana costs and arbitrary conditional instructions.
- Broader per-face kicker acceptance and complete any-target families, including
  battle lifecycle/defense integration. Unrecognized forms retain coverage gaps;
  no warning is not a guarantee of complete semantics.
- AI uses limited public/known-resource lethal, kill and card-gain breakpoints.
  Life/scry/surveil valuation, response-mana retention, racing and adversarial
  multi-turn planning remain unfinished. No expert-strength or balance claim.
- Damage allocation budgets need clearer UI feedback. Server-side validation
  rejects invalid totals; passing functional controls is not a redesign.
