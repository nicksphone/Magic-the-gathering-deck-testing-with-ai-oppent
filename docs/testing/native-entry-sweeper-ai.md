# Native Self-Entry Sweeper Priority

## Reproduced Decision

The declared Ramp/Tribal position has five usable lands and an enemy four-Elf
army. Meathook's normal Main 2 spell evaluation approves X=3 and its real cost is
affordable. The existing comparator nevertheless ranks Nissa's printed mana
value above Meathook's lower printed value. The first ordinary choice therefore
spends those lands on Nissa instead. Separate manual Meathook payments prove
the rules outcome, not an AI success.

The correction extends the existing direct-sweeper priority bonus to supported
self-entry creature debuffs. It does not alter Main 1 timing, choose X, change
mana evaluation or reorder the controller's list outside the shared comparator.
The normal native evaluator still rejects an inappropriate wipe.

## Verified Component Evidence

- The unchanged ten-case native regression on C8 has two policy failures and
  eight passes, with zero harness errors. On the final C10 prefix all ten pass. Both threatened
  positions select and actually pay for Meathook at X=3, kill four enemy Elves
  and gain four life. Meathook-only eligibility, empty/friendly-board Nissa
  choices and Main 1 deferrals remain, in both seats. No manual substitution or
  X override supplies an AI success.
- The exact profile-delivery suite passes all forty-two tests, including all
  thirty-eight inherited cases. Schema11 requires exactly fourteen sources and
  twenty-three classes; missing, extra or relabelled inherited inventories reject.
  Profile schema3 and native manifest schema1 remain unchanged.
- The separate twenty-four-case internal protocol passes on the corrected
  prefix. The prior draft has four proper protocol failures: typed phase state
  and actual source/type validity were not checked. Both are now checked through
  existing native APIs. All expected classifications, game/RNG/object counters,
  override/X state and hidden-body read assertions remain. These are labelled
  metadata/spies, not ordinary AI choices or extra games. Two earlier fixture
  setup failures and a wrapper's unused-class requirement remain historical;
  they are not additional AI defects or silently counted passes.
- Four new final-C10 fixed-seed Ramp/Tribal games complete with zero native errors or
  incomplete games, using the same decks/seeds/budgets as the archived C8
  four-game cohort. The new case18 actually casts and pays for Meathook on turn8
  Main 2 and clears the four-creature enemy board. Earlier land choice already
  differs, so this is not a unique-causality or initial-chooser replay claim.
  Case17 also casts Meathook earlier in the public action sequence. Cases16/19
  do not supply a Meathook-cast witness. Event description text prints X=0 in
  these natural logs; exact X=3 is independently asserted only in the focused
  native cases, not inferred from that description.
- The final prefix passes the unchanged 186-case regression declaration in
  330.90 seconds: pressure70/knowledge38/boundary48, gain-response6,
  preservation10, lord-mana8 and original lord6. All five stage runners exit0
  with unchanged inputs/base resources and owned-process closure. Observational
  lord controls retain that label; 186 checks are not 186 strategic victories.

The earlier C9 draft independently passed the same original ten cases and a
separate four-game cohort before its two metadata guard gaps were corrected.
Those stages remain separate, not summed into final-source game coverage.

## Preservation And Limits

The original comparator tiers, constructor, comparison and prior priority body
are byte-identical after removing only the additive classifier/imports and its
one new predicate. All inherited thirteen sources/twenty-one classes remain
exact. Conditions and overrides are conservative admission checks for this
additional priority, not a general ability-equivalence or prospective-layer
solver. Parser caching is not game-state mutation.

The boundary protocol makes no ordinary AI callback and need not load the
unused SpellAbilityAi evaluator. Every actually loaded override must still have
the declared origin; both new comparator classes must load from the prefix.
This is not force-loading an otherwise unused class. The separate ordinary
choice/game cohorts retain their original evaluator-origin requirement.

[Source delta, unchanged native regression, canonical programs and attribution](../../tools/engine_evaluation/forge/native-ai/entry-sweeper/README.md)
retain Forge Team/Card-Forge credit and GPL notices. No live profile is installed.
Full strategy, learning generalization, BO3 acceptance and application adoption
remain open.
