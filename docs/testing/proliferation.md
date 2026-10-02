# Proliferation and Multi-Kind Counter Events

## Implemented Scope

The registered `proliferate` instruction offers its controller any number of
eligible permanents or players, including none. It does not target. Each selected
recipient receives one additional counter of **every** existing kind, not a
counter for every physical counter and not a choice of one kind. Poison, loyalty
and Saga lore use their authoritative state fields; internal damage, temporary
buff and housekeeping markers are not counters.

Supported counter doubling, halving, addition and prohibitions prepare a vector
of counter amounts. A replacement ability applies once to all its matching
kinds in that recipient's event. Kind-specific modifiers cannot affect other
kinds, and a zeroed amount cannot be revived by a later plus-one modifier.
Affected-player decisions follow APNAP order; no selected recipient gets a
partial physical placement while another replacement choice remains pending.
Snapshots retain the selection, prepared packets, per-ability usage and spell
continuation. Incarnation and zone-sequence checks reject stale recipients.

All physical placements complete before chapter/counter triggers are collected.
A proliferation event occurs even when no recipients are selected. Supported
`Whenever you proliferate, draw a card` triggers use the stack, not an immediate
draw. Standalone `Proliferate` and `Proliferate twice` clauses work within effect
sequences; two instructions have independent selections. Canonical spell tests
preserve Contentious Plan's proliferation-before-draw order and Tezzeret's
Gambit's draw-before-proliferation order.

Bounded trigger clauses reuse the existing event matchers. Canonical regression
fixtures verify Thrummingbird's player-combat-damage trigger, Evolution Sage's
landfall trigger and Inexorable Tide's own-spell-cast trigger. This is not a claim
that every trigger condition or every clause of these fixture cards is covered.

The existing human choice control handles both seats and mixed permanent/player
selections, including none. This is functional glue, **not** the deferred UI
redesign or an ergonomic release acceptance test.

## AI and Evidence Boundaries

The shared public-counter heuristic evaluates every counter kind together. It
prefers beneficial friendly counters and harmful opposing counters, avoids
self-poison lethal and recognizes opposing poison lethal. Replacement ordering
evaluates supported amount transformations jointly; large replacement sets use
the existing bounded heuristic ceiling. Unknown resource-counter semantics are
neutral. General resource spending, replacement-aware selection forecasting,
Saga chapter lookahead and long-horizon counter strategies remain unfinished.

Fixtures are canonical Scryfall rows with source links, card/oracle IDs and
retrieval timestamps; setup counters are explicitly core-event fixtures, not
invented Oracle text. Focused checks cover both seats, legal/rejected choices,
mixed kinds, replacement ordering, APNAP batches, snapshots, HTTP/SQLite restore,
event atomicity, chapter thresholds, actual spell instruction order and AI
choices/casts across archetypes. Chromium verifies seat-two none/all-kind
selections and nested replacement completion through the real control/API path.
Historical deck replay is a regression smoke test, not feature coverage or
evidence of expert AI or matchup balance.

One repeated browser run failed in the pre-existing dropped-start-response test:
its cold Island cache initiated synchronous external sync and match creation
completed after the frontend attempts had timed out. The fixture now primes the
shipped canonical Island row with local fallback art. This stabilizes the
response-loss test without bypassing real match creation or inventing card text;
it does **not** repair production cold-cache sync latency, which remains on the
backend plan. Failed-run evidence is retained alongside successful checks.
Two additional superseded runs overlapped the fixed browser-test ports and are
retained as harness-interference evidence, not application failures. The harness
now takes an exclusive local lock before starting its owned services; browser
validation runs sequentially.
A further superseded run encountered a shell read-offset error because its
harness file was edited while it was running. That evidence is also retained;
the final acceptance runs use stable source files throughout execution.

Final validation: **2,490 backend tests passed**, with 295 existing Python
deprecation warnings, in an isolated tracked-source copy with its own initial
empty database/cache. The focused counter/proliferation set passed **183 tests**,
including 37 new proliferation checks. Frontend lint, boundary unit tests,
TypeScript/Vite build, shell syntax/lock checks and the full sequential Chromium
harness passed. Four historical templates produced 12 logical seat-balanced
smoke games across 24 repeatability executions: no timeout, anomaly trace or
determinism drift was reported. This matrix does not exercise a dedicated
proliferation deck or establish competitive balance.

Logs, source hashes, canonical-rule reference, failed browser checkouts and scope
are retained on RCHFiles under
`diagnostics/proliferation/20261002T002011Z/` in project storage.

## Known Limitations and Next Upgrades

- Tekuthal's replacement of the **proliferation event** is not counter doubling
  and is explicitly reported as unsupported. It is not implemented here.
- Ezuri's optional paid entry instruction is not implemented by its supported
  proliferation watcher; conditional proliferation is explicitly flagged.
- General simultaneous entry/damage/cost vectors, counter movement/removal,
  arbitrary replacement clauses and broad ability suppression remain open.
- Incrementing a named shield, stun or keyword counter does not itself implement
  that counter's prevention, untap or keyword-granting rules. Those mechanical
  consequences still need their own shared rule handlers and golden fixtures.
- Extend public-counter value with actual resource abilities and replacement
  forecasts, then measure tactical decision quality on supported real decks.

Rules reference: [Wizards Comprehensive Rules 701.34 and
616](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).
