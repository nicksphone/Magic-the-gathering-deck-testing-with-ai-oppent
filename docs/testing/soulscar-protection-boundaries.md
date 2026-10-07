# Soul-Scar Protection/Prevention Boundaries

Tests-only on immutable 7f source with prior49 and prior20 dependencies. No replacement product changes.

Run from an isolated source checkout with the prior pure runner (SQL/socket audit hook before pytest imports):

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$MTG_TEST_PYTHON" ../evidence/run-pure.py \
  tests/test_soulscar_protection_boundaries.py -q --tb=short -p no:cacheprovider
```

Actual checked cast/activation episodes use canonical full raw records, real mana/tap payments and real priority passes. Initial battlefield and mana pools are explicit rules fixtures, NOT natural games. Human ordering flags request affected-player choice; no fabricated option identities, stack items, damage packets or prevention counters are supplied.

38 cases: 16 PASS / 22 ordinary FAIL (11.49s). Eight strict shield/conversion cases fail at absent pending choice. Twelve Salve cases fail earlier: the actual offered prevention mode is rejected as unsupported spell resolution. Two actual paid Pyroclasm cases incorrectly damage the opponent player (18 life) instead of each creature. These are three causal groups, not 22 independent bugs. Post-choice order assertions remain unexecuted/unqualified.

Passing controls: red Bolt cannot legally target protection-from-red Firewalker (atomic root rejection); actual green Hornet Sting and blue Prodigal Sorcerer can legally target it and convert with Mage; real paid white Boon prevents damage without Mage (both damage families/seats). The Sorcerer genuinely receives lifelink via paid Moment of Heroism: prevented/converted damage produces neither damage event nor lifelink. Actual paid Humility before announcement, flash Dress Down in response, and paid Naturalize removing Dress Down before Bolt resolution each obey suppression at resolution, ordinary damage versus counter conversion, and SBA death. Complete checked-root/snapshot restoration equality is asserted.

Protection-matching damage is attempted only through actual paid untargeted Pyroclasm. Its compiler error blocks this runtime ordering witness. Do not infer universally forced protection-first ordering from the old handler's early return. The green/blue episodes are legal nonmatching sources, not a substitute proof of red protection ordering.

Rules pin: Wizards Comprehensive Rules effective 2026-09-25, SHA256 8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca, official https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt . Relevant 702.16b/e (targeting/prevention), 616.1/e/f (affected-player ordering/re-evaluation), 614.6 (replaced event never happens), 608.2b (target revalidation), 704.5f (zero toughness). No universal forced-first category for protection is established by these rules.

Raw provenance is in `fixtures/soulscar_protection_boundaries/provenance.json`; committed records are copied intact and new intake uses public Scryfall full raw objects. Mending Hands is intake-only: current full Oracle also says any target, so it was not substituted or shortened to fabricate compiler support.

Original49/20 files remain byte-identical. No hidden-library policy access, HTTP/browser/SQLite test, full-game completion, latest-source qualification, preflight warning clearance, or overall replacement support is claimed.
