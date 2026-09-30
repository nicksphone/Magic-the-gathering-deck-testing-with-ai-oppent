# Oracle-grounded AI heuristics

Date: 2026-09-30 UTC. This milestone removes semantic shortcuts, not card names
from the application. Names remain useful for display, canonical-data lookup,
stable tie-breaking and explicitly recorded per-card historical timing priors.
No new gameplay cards were invented or added to built-in decks.

## Changes

- Spell ranking and rollout recognize burn/counter roles from printed text and
  the announced cast face, not words such as bolt, spike or counterspell in a
  display label. Counter recognition also handles typed and nonblue counters.
- Forced interaction, end-step card advantage, closure, opening-hand quality,
  X timing, modal-face evaluation, permanent/stack threat and board-value
  heuristics no longer prepend the card's name to its rules text. Named bonuses
  for particular sweepers, draw spells, engines and token makers were removed.
- Counter cards no longer add an unconditional blue color-demand bonus. Actual
  mandatory/hybrid printed costs drive the existing color-demand model.
- Fixed player-damage estimates read printed numeric clauses. Lightning Strike
  now receives a damage estimate despite not being in the old name table;
  Boros Charm's printed player mode is four damage, not the old three estimate.
  Spike Weaver and Bolt Bend do not become burn spells because of their names.
- Deck identity uses role density and deck shape instead of named packages or
  creature-name guesses. Typed tribal support requires a creature-type cluster
  and printed support reference, not merely a token of that type. Small burn
  or drain packages do not automatically dominate the deck classification.
- Flat hydrated card entries and nested import metadata share face/layout
  analysis. Land-only faces are excluded from nonland acceleration signals;
  a modal land face is a source, not evidence that its spell accelerates mana.
- Reports expose `type_metadata_coverage`; completely missing type metadata
  returns a zero-confidence Midrange fallback with `missing_card_metadata`,
  rather than asserting an archetype from names. This coverage measures type
  data only, not Oracle completeness or supported engine semantics.

## Evidence

`tests/fixtures/ai_oracle_semantics.json` contains twelve real Scryfall canonical
rows from the existing knowledge cache, retaining Oracle IDs and source
provenance. Tests deliberately change only labels or remove Oracle text to
verify missing/conflicting data handling; those adversarial fixtures are not
new card definitions. Tests cover printed damage, real nonblue Withering Boon,
Shark Typhoon/Memory Deluge valuation, canonical Jwari Disruption/Jwari Ruins
face adaptation, flat/nested parity and unchanged analysis under label changes
for all eleven built-ins.

The preceding focused tests caught an incorrect loop variable and mismatched
test assumptions about hydration shape; these were corrected before final
gates. Intermediate deck inspection exposed insufficient Tempo-density handling
and land-face acceleration contamination; the role-density and face boundaries
were corrected rather than forcing archetypes from deck names.

The regression matrix uses seeds 73–76, both seats for Dimir Control/Tempo,
Tokens/Ramp, Midrange/Drain Deck and Tribal/Burn, Master difficulty and a
1,600-tick cap. It repeats each game to check full identity-sensitive results.
Changes to outcomes/decisions relative to the preceding heuristic version are
expected and are not treated as evidence of better win rates. These are offline
shipped lists/metadata, not current tournament decks or independent samples.

Final backend gate: 1,787 tests pass in a fresh isolated source/database copy.
Frontend lint, TypeScript/Vite build and unit contracts pass. Eight logical
games repeated across sixteen executions have identical complete results,
zero timeouts and zero logged cost/target rejections. Compact [replay evidence](ai-oracle-semantics-evidence.json)
retains seeds/turns/ticks/hashes without full hands or gameplay logs.
The full Chromium action/recovery harness was rerun after the last face-role
change and passes, including AI autoplay and complete scripted human-vs-AI and
human-vs-human BO3 flows. Both LAN services respond; competitive browser games,
long-session soak and broad archetype accuracy remain separate acceptance work.

## Remaining Limits

Classification confidence is a relative heuristic score scaled by type-data
coverage, **not a calibrated probability**. Mixed and unusual decks can still
be misclassified, and Combo-lite and strategic synergy recognition need deeper
graph/interaction modeling. Multi-face role aggregation is not a proof of
optimal dynamic face selection. Historical priors still legitimately use
canonical card identities and need provenance/quality evaluation.

Text tags and damage estimates do not fully evaluate conditional clauses,
mode requirements, variable damage, prevention, replacement interactions or
combat racing. The engine still determines legal targets/costs and real
resolution; heuristics are not a substitute for those rules. A fixed printed
damage estimate is potential damage, not proof of immediate lethal. Broad
decision-quality matrices, knowledge-score consumers, arbitrary mechanics and
the independent timeout-diagnostic interpreter crash remain open.
