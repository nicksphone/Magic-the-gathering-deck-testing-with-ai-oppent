# Permanent kicker entry and conditional ETBs

## Status

The isolated full suite passes 3,958 tests (364 warnings, 630.23 seconds).
The focused 226-test gate, frontend lint/contracts/build and complete Chromium
suite pass. The two-sample
seat-balanced seeded replay smoke passes with repeated execution and no anomaly,
timeout or determinism failure (43.921 seconds). All 148 backend production files
are byte-identical across full-suite, browser and replay copies. This is not a large
statistical matchup study or evidence of balanced/expert AI.

## Shared contracts

- One fixed mana kicker plus a recognized self-entry counter instruction or
  conditional self-ETB payoff. Canonical cases use +1/+1 entry counters, fixed
  card draw, targeted creature damage and noncreature-permanent destruction.
- Entry counters use the existing replacement/prohibition pipeline before the
  permanent enters. Conditional targeted ETBs choose targets only after entry,
  using the ordinary controller-owned trigger choice and stack paths.
- Actual paid kicker history survives stack-to-battlefield transition and saved
  snapshots, but not a later zone change. A copied permanent spell carries its
  announced paid choice into its token without paying again. A new uncast entry
  cannot inherit an older payment. Existing triggers retain their original
  instruction when their source leaves; targeting still revalidates normally.
- Noncreature-permanent destruction shares legal hints, trigger choices and
  effect resolution. Artifact creatures remain creatures and are excluded.
- All AI difficulties use bounded known-board payoff estimates for supported
  permanent kicker. This is not optimal racing, resource retention or expert AI.

Rules grounding: Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules),
effective 2026-09-25, 400.7d, 603.4, 702.33 and 707.10. Casting history belongs to
the relevant original object; these changes do not implement general intervening
conditions or arbitrary linked-ability transformations.

## Evidence

`backend/tests/fixtures/permanent_kicker.json` preserves Scryfall/Oracle IDs,
source URLs and unmodified canonical data for Baloth Gorger, Citanul Woodreaders,
Torch Slinger and Mold Shambler. A misspelled lookup returned 404 and was corrected
before fixture generation; no card was invented to replace it. These fixtures
do not alter competitive decks.

`backend/tests/test_permanent_kicker.py` exercises both seats, exact normal/free
costs, snapshot recovery, unpaid entries, copies, counter doubling/prohibition,
actual AI materialization and human post-entry target choices. The free cases
exercise shared effect-authorized admission directly: they do not grant a new
permission to an existing spell whose printed scope is instant/sorcery only.

`frontend/tests/browser-permanent-kicker.mjs` adds sixteen real ordinary App/API
cases: both seats, paid/unpaid variants and all four canonical fixtures, including
stack refresh and targeted ETB-choice refresh. All sixteen pass, as do the existing
browser cases, process restart recovery and natural human/AI and human/human BO3.
An older combat-payment browser wait raced a legal-move refresh and read state
before the submitted action completed. The wait now requires an authoritative
revision increase and the submitted attacker before asserting exact mana payment;
the entire browser rerun passes without changing that gameplay assertion.

The focused test run initially caught missing snapshot history and the shared
noncreature target gap. Later failures were fixture errors: a missing Solemnity
fixture import and a copy test with only one opponent creature, which legally
forced the second damage trigger to target a friendly creature. Corrected cases
retain real canonical cards and do not change legal mandatory targeting.

## Known Limitations and Next Upgrades

General permanent kicker clauses, multiple/nonmana/X costs, multikicker,
cast-trigger consumers beyond the [recognized payoff batch](kicked-cast-payoffs.md), granted/changed linked kicker abilities,
face-specific acceptance and arbitrary intervening conditions remain open.
Most payoffs and spell semantics are still bounded by recognized Oracle grammar.
AI counter-size/card-gain/removal estimates do not prove optimal play. The alpha
UI redesign remains deferred; functional browser checks do not certify ergonomics.
Tests reuse the installed venv rather than proving fresh dependency installation.
Source, canonical API responses, passing checks and superseded failures are
archived on RCHFiles at `diagnostics/permanent-kicker/20261003T113824Z/`.
