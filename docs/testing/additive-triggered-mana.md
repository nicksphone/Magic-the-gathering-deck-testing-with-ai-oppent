# Fixed Additional Triggered Mana

The engine now handles supported mandatory, targetless mana triggers with fixed
colored symbols. It captures the trigger when a mana ability taps its source and
resolves the additional mana immediately. Manual taps, automatic payment,
affordability checks and legal moves share the same activation/output model.

One activation produces a whole vector: Tropical Island with the supported
Forest trigger can produce U plus G, not two U. Base production replacements
apply before additional triggered production. Spending restrictions and snow
provenance remain separate for the base and bonus mana; a restricted base does
not restrict an otherwise unrestricted bonus. Canonical controls cover Nissa,
Wild Growth, Overgrowth, Leyline, Reflection and Sphere interactions, effective
land types, source suppression and activation-cost departures.

## Acceptance

- Worker qualification: 1,865 checks across 48 affected modules.
- Parent composed qualification: 1,284 checks across 28 modules, then 581 across
  the remaining 20, using the same frozen disposable source and sequential
  database access. A separate mana/selection/training/corpus gate passes 300.
- The retained natural Ramp position now reports 11 available mana rather than
  seven, exposes Ugin as legal, and successfully pays its cost in both seats.
  The second seat is a controller/owner mirror, not an independent natural game.
- Canonical fixtures remain unchanged. Read-only queries leave the original
  position unchanged. Tests do not use the user's live database.
- Live backend restart preserves the previously ended match's complete stored
  game/controller JSON byte-for-byte, revision 1884 and 2-1 series score. Both
  direct backend and frontend-proxied health checks pass after restart.

Evidence is archived under RCHFiles `holding-spells/additive-mana/` and the
parent composed qualification directories. Regression results and a corrected
retained decision do not establish broad strategic quality or matchup balance.

## Remaining Coverage

Choice-dependent or produced-type bonuses, including the relevant clauses of
Utopia Sprawl, Verdant Haven and Mana Flare, remain unsupported by this increment.
Cavern-style chosen subtype/uncounterability provenance is a separate gap.
Legacy plain-color UI hints may omit secondary bundle components; mana ability
views expose `output_bundles`, while actual casting/payment uses complete vectors.
These limits are not permission to approximate unsupported card instructions.
