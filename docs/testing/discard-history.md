# Bounded rummaging and discard history

## Scope

The shared linked-discard reader supports complete self-discard instructions with
a printed upper bound followed by drawing the actual discarded count, and whole-
hand discard followed by drawing once per card discarded this turn. Canonical
Cathartic Pyre, Daretti, Scrap Savant and Change of Fortune are fixture cards, not
name-dispatched handlers. Modal and loyalty surfaces use the normal engine paths;
this does not certify Daretti's other abilities or arbitrary modal combinations.

`discard_simultaneous` records successful discards for both players before the
shared event batch. Spell costs, cleanup and supported replacement exile count;
mill and direct hand exile do not. Repeated discards of the same card count as
separate events. Counts persist in snapshots and SQLite and reset for both players
only when the turn changes, not at cleanup entry. The history-dependent follow-up
reads the current controller's count after its own discard completes. Copies and
counters retain ordinary stack semantics and owned choices.

The API exposes the public counts; the frontend validates nonnegative integer
counts for both seats when the optional field is present. Old snapshots have no
history to reconstruct and restore zero counts. Start a new game for reliable
history-based behavior after upgrading from a snapshot made before this feature.

## AI Boundary

All difficulties compare known hand retention against a heuristic unknown-draw
value, bounded by printed count, public library size and supported draw forecasts.
Good hands can retain every card; excess lands can be exchanged. Draw caps and
doubled-draw exhaustion affect choices. Per-turn history affects whole-hand draw
admission. A modal spell with no usable removal mode and no beneficial rummage is
held rather than spent to discard zero. Usable removal remains available instead
of blocking the entire modal card. This is not trained graveyard-combo valuation,
adversarial response planning or tournament-strength evidence.

## Acceptance

- [x] 92 new canonical tests; combined AI/draw/cost/cleanup selection: 381 passed.
- [x] Both seats, zero/short/full hand, illegal-choice atomicity and copy ownership.
- [x] Replacement exile/draws, prior/current discards, payment/cleanup history,
  simultaneous batches, counters, HTTP and SQLite restart.
- [x] All-difficulty resource decisions; frontend lint/contracts/production build.
- [x] Complete Chromium with six new actual action cases and natural BO3 flows.
- [x] Twelve seat-balanced BO1 replay samples repeated twice: zero reported
  anomaly/timeout/drift, 337.662 seconds. This does not measure competitive strength.
- [x] Full isolated backend suite: 4,674 passed, 414 deprecation warnings,
  738.93 seconds; no failures.
- [x] Graphify refresh, verified RCHFiles archive and milestone docs.

Three new canonical fixture records match saved Scryfall responses field-for-field.
Two additional empty-hand history probes finish without a discard choice and draw
the count of earlier discards in the same turn. Source parity checks compare every changed
backend file against the copy used by the full suite. The AST-only Graphify update
reports 9,470 nodes and 24,317 edges; no external AI was used.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/discard-history/20261003T170423Z/`.
Preserve source copies, canonical responses, failed and final logs, source hashes,
replay output, empty-hand probes and closed browser artifacts. Verify tar contents
and SHA-256 before deleting local scratch. Preserve the pre-existing user plan
separately and exclude it from the milestone commit.

Preserve failures as evidence: initial probes reproduced missing bounded/history
semantics. Early fixtures used an unadvertised mode value and nonexistent helper
names; fixes use actual cast hints and existing production methods. An older
Boseiju browser test treated a temporarily hidden button as completed mutation;
it now waits for authoritative choice/stack completion before checking results.

## Known Limitations and Next Upgrades

Broader opponent/random/simultaneous variable instructions, conditional linked
clauses, paid replacement choices, discard characteristics history and graveyard
payoff planning remain incomplete. Existing unsupported instruction warnings are
retained rather than guessing at those effects. The four-archetype replay is smoke
repeatability evidence, not a balanced-matchup or expert-AI certificate. UI redesign,
dependency/release hardening and arbitrary-card correctness remain separate gates.
