# Resource Event Fidelity

## Candidate Scope

Actual taps share one transition helper across convoke/improvise, mana and
activated costs, crew, attack declaration and resolving tap effects. Only a
battlefield object changing from untapped to tapped emits an event. Entering
tapped, including token creation and ninjutsu, does not.

Self-tap clauses use full/short self names or this creature/artifact/permanent;
there are no card-name branches. Basic land taps check matching clauses before
expensive ability-suppression queries. Crew and attack declaration stage cost
triggers until the original action is complete.

Graveyard departure operations capture matching battlefield abilities before
movement. A returning watcher does not see its own departure; returning Humility
does not erase a trigger that already occurred. Capture/emission cover delve,
escape, graveyard casting, dredge, exile and return-to-hand/battlefield handlers.
One-or-more clauses fire once per batch; separate moves remain separate events,
with controller-owned graveyards and APNAP ordering. Capture objects are
ephemeral and never stored in snapshots.

Canonical Tormod creates a black tapped 2/2 Zombie; Emmara creates a white 1/1
lifelink Soldier. Card data and decks are unchanged.

## Evidence

- Twenty both-seat canonical tap/departure cases cover convoke, effects, attack,
  crew, duplicate taps, batch/separate departures, wrong-owner graveyards,
  pre-move Humility checks, real casts, stack order and snapshot reconstruction.
- The overlapping payment/mana/vehicle/combat selection passes 175 tests.
- Eight HTTP/SQLite cases pass: four new trigger/restart cases plus four existing
  strict resource payment cases. Tests ran in this isolated worktree, not the
  live database; this is not a fresh-install full-suite claim.
- Predecessor ed61cd6 passes 8,603 complete backend tests and the complete browser
  gate. Those results do not qualify the changed event runtime.
- Six initial tap tests and four departure tests failed before implementation.
  Test-driver mistakes (returned checked state, fixture shape, misplaced
  assertions) were corrected without weakening gameplay assertions.

## Remaining Acceptance

- Exact frozen-source full backend and browser/recovery parity for this follow-up.
- Wider tap subjects, conditional/once-per-turn clauses, granted abilities,
  optional/targeted choices and more creature-filtered departure cards.
  Supported textual families are not complete Oracle interpretation.
- Ordered compound costs, escape-plus-delve/newly available cost resources and
  full graveyard casting permissions need broader golden fixtures.
- Actual AI opportunity-cost evaluation and unchanged-deck natural decision
  review remain open. Constructed positions are not expert-play proof.

## Rules References

The [Commander Legends release notes](https://magic.wizards.com/en/news/feature/commander-legends-release-notes-2020-11-06)
confirm Tormod's per-batch behavior. Timing and pre-move ability checks must follow
the [Comprehensive Rules](https://magic.wizards.com/en/rules), including
casting/activation completion, APNAP and graveyard departure triggers.
