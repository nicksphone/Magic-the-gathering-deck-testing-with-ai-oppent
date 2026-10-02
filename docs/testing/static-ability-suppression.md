# Static and replacement source suppression

## Implemented increment

Supported all-ability loss now gates additional readers of battlefield Oracle
abilities: continuous power/toughness bonuses, keyword grants/prohibitions,
counter and token replacements, counter prohibitions, ordinary draw limits,
extra-land/top-library permissions, recognized attachment discounts and spell
taxes, static timing locks and supported land-mana modifiers. The shared general
replacement-source iterator also excludes suppressed sources. Printed metadata
remains unchanged; effects return when the supported suppression ends.

Keyword source dependencies no longer let a suppressed creature restore its
own printed team grant merely because it entered after the suppression source.
Supported resolution-created keyword effects and physical counters remain
separate. Shield counters still replace damage on creatures that lost abilities.
The AI's recurring-reward valuation no longer credits suppressed printed rewards.

Loss-source preparation is local to each pure layer query, not a persistent
mutable-state cache. The boolean union does not sort source timestamps, and
layer queries prepare it once instead of scanning the whole battlefield for
each permanent. A regression checks the preparation count and unchanged snapshot.
The retained 50-creature canonical-fixture benchmark measures 5,000 direct
queries: published/final times were 0.3281/0.0713 seconds without suppression
and 0.3411/0.0767 seconds with it. This microbenchmark is not a whole-game or
worst-case AI latency claim.

The supported combined all-ability-loss/base-stat instruction begins in layer six
and continues into the base-stat layer, even when its source is a creature and
loses that ability. Continuation is limited to the actual instruction: an
independent second ability on the same source does not inherit it. Effective
stats and layer diagnostics use the same filtered instruction source. This is
not a general dependency graph or arbitrary cross-layer effect interpreter.

Counter replacement grammar also recognizes equivalent recipient wording,
`put on it` and `put on that creature`, without card-name dispatch. Tests verify
actual placement before/after suppression, not only parser classification.

## Canonical data and rules

`backend/tests/fixtures/static_ability_suppression.json` retains Scryfall IDs,
URLs and retrieval dates for twelve actual cards. Canonical fixtures exercise
Elvish Clancaller, Archetype of Imagination, Conclave Mentor, Adrix and Nev,
Rhox Faithmender, Spirit of the Labyrinth, Azusa, Realmwalker, Thalia, Melira and
Transcendent Envoy alongside the prior Humility/Dress Down corpus. The retained
Danitha row is inventory only: its compound Aura/Equipment discount does not
receive whole-card acceptance here. Synthetic animated-source, independent-
ability, direct-effect and cost-context tests are explicitly labeled; no decks
or Oracle texts are invented as competitive evidence.

Reference: Wizards' [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
604.1 (static abilities), 613.1f, 613.6 (one effect spanning layers) and 613.8a
(dependencies). The official text is retained with test evidence on RCHFiles.

## Validation

Both-seat golden fixtures cover timestamp-independent source suppression,
effective stats/keywords/trace, counter placement, token amounts, life gain,
draw/land/library permissions, poison prohibitions, taxes/discounts, snapshot
restore, AI recurring value, cross-layer continuation and shield independence.
October 2, 2026: **2,739 backend tests passed** with 295 deprecation warnings
in an isolated source checkout, plus **281 focused checks**, frontend lint/unit/
build and the final-engine full Chromium harness. Twelve logical seat-balanced
smoke games each repeat twice without reported drift, timeouts or anomaly labels.
The sample is narrow repeatability evidence, not balance/strength certification.
Reused dependencies and DOM-driven browser flows are not clean-install, visual
or arbitrary-card certification. Final evidence, canonical fixtures, runnable
helper benchmark, official rules and closed test copies are retained on RCHFiles
under `diagnostics/static-ability-suppression/20261002T042530Z/`. Earlier failures
and intentionally cancelled superseded runs remain labeled, not hidden or
reported as determinism/timeout outcomes.

## Known Limitations and Next Upgrades

- Suppression remains bounded by the recognized all-ability-loss grammar;
  conditional, targeted temporary and arbitrary gained non-keyword abilities
  require further integration.
- Full type/color/text/dependency layers and earlier-layer effect continuation,
  conflicting same-layer effects and simultaneous timestamp choices remain open.
- Pre-entry characteristics, competing simultaneous replacements, durable
  replacement decisions whose sources change, and remaining direct Oracle
  readers still need golden fixtures and integration.
- Compound attachment-spell discounts, broader statistical AI quality and
  operational release acceptance remain open. Alpha UI redesign is deferred.
