# Canonical kicker goldens and coherent removal targets

## Acceptance checklist

- [x] Fresh canonical fixtures retain Oracle IDs, printed text and Scryfall provenance.
- [x] Eject the Warp Core, Final Flourish, Stomped by the Foot and Vayne's
  Treachery exercise artifact-or-creature sacrifice and their actual conditional
  negative-stat effects. Hypnotic Cloud exercises mana kicker and discard one/three;
  it does not have a discard kicker cost.
- [x] Both seats, paid/unpaid and normal/free casting, explicit artifact/creature
  payments, ineligible payment rejection, spell copies and snapshots.
- [x] HTTP legal options, checked payments, atomic rejection and SQLite restoration.
- [x] Read-only negative-stat projection matches actual resolution/SBAs with counters,
  Glorious Anthem, marked damage and Darksteel Myr's indestructible.
- [x] 204 focused tests pass (83 deprecation warnings, 15.55 seconds).
- [x] Frontend lint, API contracts and production build pass.
- [x] Twenty-four before/after checked AI casts across both seats and all difficulties:
  the published baseline spends kicker on a surviving 8/8 in every case; the update
  selects and kills the available 4/4 in every case. Hands, boards, actions and logs
  are retained. Each probe materializes a supplied legal spell move and executes
  the checked cast; it does not measure whether autonomous action selection casts
  at the best time. These are constructed decision-quality probes, not win rates.
- [x] Complete browser suite, including twenty new both-seat canonical cases,
  process restart, sideboard transition and natural BO3 for all three modes.
- [x] Full isolated backend suite: 4,340 passed, 370 deprecation warnings,
  621.36 seconds. Twenty HTTP/SQLite cases were added after that suite started;
  the expanded 204-test file passes separately, including those twenty cases.
- [x] Twelve seat-balanced BO1 samples, each executed twice, finish without reported
  timeout, anomaly or determinism failure (484.082 seconds). Existing Aggro, Tempo
  and Tokens archetype templates are a smoke matrix, not a test that these new
  kicker spells autonomously appear or a measurement of deck balance/AI strength.

## Shared behavior

The existing kicker parser and checked cost/effect paths are unchanged. The engine
now exposes its existing lethal-creature predicate, and the AI projects the actual
negative-stat handler on a copied target. Effective toughness, continuous buffs,
counters, marked damage and indestructible therefore use the same calculation as
state-based actions. No departures, triggers, random choices, private-library reads
or mutations of the real state occur during this one-target projection.

Both kicker gain estimation and selected-target ranking use that predicate. Within
recognized single-target negative-stat instructions, a lethal legal target takes
precedence over an unproductive higher-threat target. Existing threat ranking chooses
among eligible lethal targets. This is shared behavior, not named-card logic.

The fixtures are isolated semantic scenarios, not invented competitive decks or
altered printed statistics. Counters and marked damage are explicit legal game state.
The fresh raw API responses and initial failing regressions are retained with evidence.

## Known Limitations and Next Upgrades

This does not certify entire cards, arbitrary conditional Oracle clauses, all
continuous layers or expert play. Payment-induced board changes (such as sacrificing
an anthem), death replacement/payoff value, responses, racing and future resource
retention are not included in the one-target projection. Mixed costs, X/multikicker,
unusual face permissions and wider knowledge-driven planning remain unfinished.
Canonical scenario outcomes do not imply a desired or forced matchup win rate.

Verified source, raw canonical responses, initial failures, before/after traces,
frontend/browser checks and replay results are archived on RCHFiles under
`diagnostics/kicker-goldens/20261003T132459Z/`. Installed dependencies were reused;
fresh dependency installation and broader release certification were not tested.
