# Basic/Nonbasic Graveyard Selector Product

One production function only: `_graveyard_card_matches_selector` in
`backend/rules_engine/continuous.py`. Preimage
`355e74fedc60c4368c65e22d1de4964784ac022f679eebd7a1ba153775e34303`,
postimage `3ff90a5aed8f193b2098cf5695192dd1dbd4126d39825fbf238d543b47b3d9c8`.
Additive anchored `basic|nonbasic land(s)` branch requires printed Land type
and checks exact Basic token in the front type-line head using the existing
printed-type parser's separator convention. No land-subtype/name inference.
All AST outside this function is identical, including `_stat_resource_count`.

## Dependencies

Immutable own source-only archive `7f36cf395d3856d586667192215c6658accbd8f559ed72c1eba18750b9405943`.
Unchanged original48 audit/official fixture patch
`3bf3bcd74488878bdb2c8d6dee193a45accd81872dceda99a7401de300d39795`;
original audit module SHA `efb2e2769f28b51ea2624b4363c5cd4cefd0b43ddc211323a96b5709fa7d1cc1`.
The source tar omitted the shipped import-time generic-token SVG. Exact asset
SHA `a3114095c760517186807f8753d109000174460a20ee72693ff9b9a69efc5e85`
was restored from the completed frozen own MviIr7 checkout and verified on NFS
before neighbor tests. No moving-parent source, DB or dependency was copied.

## Actual Ledgers

- Original unchanged48 baseline: 20 PASS / 28 strict FAIL, 0.83s, exit1.
- Product focused whole2: 84 PASS, 1.01s, exit0 (unchanged48 + NEW36).
- First whole9: four missing-SVG collection errors, 5.50s, exit2.
- Corrected whole9 product: 209 PASS / 3 FAIL / 6 SQL-blocked setup ERROR,
  11.38s; pytest exit1, guard exit98. All six connection attempts were denied.
- Exact preimage same whole9: 159 PASS / 53 FAIL / identical6 SQL-blocked setup
  ERROR, 11.52s; pytest exit1, guard exit98. The three old assertion failures
  reproduce; the product removes the other50 selector failures.
- Final whole8 pure modules: 141 PASS / same3 baseline FAIL / 2 warnings,
  5.43s, exit1; no subsequent SQL/socket attempts. No SQL grant was used.

The three retained nodes are `test_tribal_static_buff_applies_to_subtype`,
`test_state_actions_repeat_when_a_lord_dies_and_its_buff_disappears`, and
`test_self_scales_from_other_creatures_you_control` in
`test_continuous_static_effects.py`. They are ordinary failures, not xfailed,
skipped, adapted or declared product regressions. The mixed land-layer whole
module remains explicitly unqualified under this no-SQL contract; none of its
tests were filtered to claim green. Final pure scope is eight whole modules.

## Bounded Coverage

Full canonical Detritivore/Terravore both seats, printed CDA public stats and
snapshot replay, native counter layering, owner/opponent/all graveyards,
Basic/nonbasic singular/plural selectors, Dryad Arbor subtype discrimination,
unknown suffix negatives, unrelated battlefield inventory and full query-root
purity. Synthetic SimpleNamespace cases are labeled selector ABI probes, not
game-card fixtures or canonical gameplay claims. No full-card/Suspend-X,
schema, engine, AI, other selector grammar or SQL lifecycle claim.

Ray timing proposal/adaptation is independent and not part of this artifact.
