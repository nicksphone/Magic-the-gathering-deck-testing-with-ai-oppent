# Loyalty Announcement Reachability

The generic Battlefield loyalty branch consumes the existing public
`ability_x_cost`, `ability_x_sign`, and `target_hints` contract. Its target
selector deduplicates creature, planeswalker, land, and permanent candidates
by their public ID. It never infers a target. Clearing the selector preserves
the optional zero-target choice, including Nissa's +1 decline.

An X-cost loyalty activation has an explicit numeric draft, initially zero.
For a negative X cost, its maximum is the actual source's public loyalty;
positive X costs are not incorrectly capped by existing counters. Negative,
fractional, and above-maximum drafts disable activation. The backend remains
authoritative for actual payment and target legality; no schema, parser,
rules, controller, or API policy changes are part of this correction.

`frontend/tests/loyalty-activation-controls.mjs` compiles the actual Battlefield
component and drives its actual handlers using public views from paid
canonical sources in `loyalty-activation-public-engine.py`. Both seats cover
Ugin X=0/2/all loyalty, existing player/creature targeting, Nissa's explicit
land/decline, and Teferi's enchantment/creature/planeswalker choices. Exact
JSON callback bodies are replayed through checked backend actions and cold
snapshot restoration, asserting real exile, damage, land animation, and
third-from-top library placement. Insufficient loyalty must reject without
changing the original snapshot; draft changes never submit actions and new
games reset drafts. These compiled component/checked core tests are not a
mounted-browser or SQLite/HTTP certificate.

The retained original whole-body regression is
`audit/complete-body/tests/test_loyalty_complete_expansion.py`, not a file in
`backend/tests`. Original public card/attachment/emblem controls are preserved.

Run with the qualified interpreter and dependency root:

```sh
MTG_TEST_PYTHON=/path/to/qualified/pure-fixture-python \
  node --experimental-strip-types tests/loyalty-activation-controls.mjs
```

Qualification evidence must preserve the initial RED, exact source pre/post
pins, original failures, denial canaries, and complete runtime/Node maps.
The first candidate accidentally selected the distinct dVB Node tree with
source-map-js 1.2.2 rather than the browser50-qualified main tree's 1.2.1.
Those preexisting cross-root package differences were not observed package
mutations; their ledger is retained separately. Only the isolated candidate
dependency symlink was subsequently rebound, without installs or cache edits.
The previously accepted d657 full50 result does not qualify this new UI.
