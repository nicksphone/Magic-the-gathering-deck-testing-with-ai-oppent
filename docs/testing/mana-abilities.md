# Shared mana abilities: acceptance checklist

## Scope

This backend-first batch shares targetless tap-mana instructions across legal
actions, automatic payment, AI payment, public views and both human seats.
Canonical fixtures are normalized from nineteen Scryfall responses; card names,
Oracle text and characteristics are not invented or changed to fit an outcome.

Supported families include live single/two-color devotion; controlled permanent
counts; Swamp/basic-Swamp counts; colored creatures in the controller's graveyard;
fixed-mana-plus-tap activation costs; and complete pure twice/three-times mana
replacement clauses. Independent pure multipliers compose once each. Basic land
subtypes grant intrinsic mana abilities, not substrings in a card's name. The
existing exact-name dual-land fallback is retained only when Oracle/type-line
metadata is absent; it does not infer arbitrary land abilities.

Targetless indexed mana abilities resolve immediately, including legal zero
output. Automatic payment excludes already-pending sources from recursive
funding. Recognized spending restrictions and activation modifiers remain in
the shared payment path. Library-moving abilities are not treated as mana
abilities under Comprehensive Rules 605.1a (2026-09-25).

Actual payments compare supported paid-source plans against the free-source
plan using remaining usable resources and the player's own hand. This is a
bounded sequencing heuristic, not optimal planning or hidden-hand inspection.

## Checklist

- [x] Reproduce eight failures against the previous implementation, with
  corrected canonical fixtures in both seats.
- [x] Implement the shared source reader, indexed immediate activation and
  automatic paid-source funding without hardcoding individual card names.
- [x] Reproduce and fix two second-spell sequencing failures.
- [x] Pass 274 targeted checks, including 41 new regressions, HTTP rejection
  without mutation, SQLite restore, zero output and source exclusion.
- [x] Pass frontend lint, runtime contracts and production build.
- [x] Verify raw/normalized fixture parity and 84 actual AI decisions across
  fourteen archetypes, three difficulties and both seats. This controlled
  affordability fixture is not a broad strategic-strength assessment.
- [x] Pass 135 affected AI/mana checks after repairing identity/zone bookkeeping
  in old policy-test doubles, preserving their decision assertions.
- [x] Pass the entire isolated backend suite: 5,650 passed, 456 warnings,
  2,000.05 seconds. These are installed-dependency checks, not a fresh install.
- [x] Pass the complete browser harness against the last compatibility fix,
  including eight new mana scenarios, both-seat natural BO3, reload, actual
  backend restart and sideboarding.
- [x] Run 24 seat-balanced BO1 samples across Tempo, Dimir Control, Tokens and
  Ramp twice each: all resolve, with zero timeouts, anomalies or determinism
  failures. The preceding matrix has the same bounded result.
- [x] Archive canonical inputs, failures and acceptance evidence to RCHFiles;
  refresh Graphify and prepare the verified milestone for publication.

Two complete browser runs and the first 24-sample repeated matrix pass before
the final exact-name compatibility fix; their evidence remains archived.
The full run reached 5,649 passes and one missing-dual-fallback failure; the
138-check compatibility retest, third complete browser run and final matrix pass.
Final backend acceptance passes all 5,650 tests. Full-suite
attempts exposed inconsistent old fixture zones and metadata-reader regressions.
Failed/interrupted runs are retained, not counted as successful acceptance.

## Remaining limitations

Non-tap mana abilities, mixed-color bundles, any-combination outputs, triggered extra mana (including
Nissa's actual Forest trigger), arbitrary resource costs, noncommuting replacement
ordering and full timing/prohibition coverage are not certified by this batch.
The old fabricated Nissa-style test is replaced with canonical Mana Reflection;
that does not implement Nissa. Automatic resource valuation remains heuristic,
including future generic/snow needs and larger paid-source boards.

Completed evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/mana-abilities/20261004-working/`.
Backend source hashes match the full-suite, matrix and final browser copies.
Runtime varied across runs; the final full suite took 33 minutes, so the small
paid-source stress probe is not a broad performance certification.

Targeted success does not establish arbitrary-card correctness, professional AI
strength, matchup balance, production readiness or an ergonomic alpha UI.

Rules reference: [official 2026-09-25 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).
