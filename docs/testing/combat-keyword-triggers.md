# Combat keyword triggers and delayed sacrifice

The subsequent [combat-provenance increment](combat-ability-provenance.md) adds
counterable Bushido/Rampage/Flanking instances, declaration event multiplicity and
response-time resolution. The Exalted/Decayed scope below remains valid; neither
increment closes general combat effects or expert AI.

## Scope

Exalted and Decayed are application-code abilities, not SQL rules or invented
Oracle effects. Their attack triggers use the ordinary APNAP/stack system and
existing ordering/priority controls. Neither resolves at attack declaration.

Exalted triggers for each supported instance on a permanent controlled by the
attacking player when exactly one creature is declared as an attacker. Lands
with Exalted participate. Leaving the battlefield or losing Exalted afterward
does not cancel an announced trigger. The non-targeted bonus applies to the
original attacker, not a new incarnation returning under the same card ID.

Decayed prevents blocking through the effective-ability adapter, including
keyword counters. Removing the ability also removes that keyword restriction;
its parenthetical reminder is not treated as an independent printed ability.
Its attack trigger creates a separate delayed trigger at the next end of combat.
Both stages can be countered. The delayed record survives snapshots and SQLite
restart, retains the original controller/object incarnation and fires once.
Blinking the creature or transferring control does not sacrifice a new object
or a permanent no longer controlled by the resolving ability's controller.

Public card views retain a unique keyword list and also expose positive integer
`keyword_counts`. Multiple physical counters of one keyword grant one ability,
not one per counter. Supported printed, static-source and temporary grants
contribute independent instances. Existing timestamp-aware keyword removal and
can't-have overrides still apply. Base metadata is not overwritten.

## AI scope

Master's bounded combat search settles announced attack/block triggers before
damage and includes delayed end-of-combat consequences before evaluating a
line. Small Exalted boards can use search before turn five even with no opposing
blockers. Search still has existing candidate/blocker bounds. Unknown pending
choices and hand/library changes make a projection unsuitable for ranking;
there is no guessed opponent response or newly drawn hidden-card optimization.
This is not certification of expert combat decisions or unrestricted boards.

## Rules and fixtures

Reference: Wizards' [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
702.83 (Exalted) and 702.147 (Decayed). The fetched reference is archived on
RCHFiles. Five actual Scryfall fixtures retain IDs, API URLs and retrieval dates:
Akrasan Squire, Sublime Archangel, Noble Hierarch, Cathedral of War and Stifle.
Existing canonical fixtures supply Rot-Curse Rakshasa, Humility and Grizzly
Bears. These are rule fixtures, not fabricated competitive decks or a claim of
complete semantics for every clause of those cards.

`test_combat_keyword_triggers.py` covers both seats, actual priority passes,
HTTP/SQLite restart, counters and multiple sources, noncreature sources,
non-targeted references, removal/blink/control change, countering either Decayed
stage, one-shot timing, legacy snapshots, cleanup expiration and AI projections.
Frontend boundary checks reject malformed counts without changing alpha layout.

## Acceptance evidence

October 2, 2026: the isolated full backend suite passed **2,641 tests** with
289 deprecation warnings. The focused pre-HTTP suite passed 131 checks; the
final keyword suite passed 27, including four both-seat HTTP/restart cases.
Frontend lint, unit boundaries and TypeScript/Vite build passed. The sequential
Chromium harness passed, including natural AI, human-vs-AI and human-vs-human
BO3 controls. The harness uses DOM actions, not pointer/visual certification.

A four-deck, six-pair seat-balanced smoke completed **12 logical games**, each
repeated twice, with zero reported determinism failures or timeouts. The sampled
decks were Aetherdrift/Foundation Aggro templates, Duskmourn Tempo and Bloomburrow
Tokens. This is narrow repeatability evidence, not a broad matchup or keyword
corpus certification; targeted fixtures establish the new keyword semantics.
Dependencies were reused rather than freshly installed. Evidence, the official
rules text and closed isolated source copies are archived on RCHFiles under
`diagnostics/combat-keyword-triggers/20261002T023819Z/`.

## Known Limitations and Next Upgrades

- Arbitrary conditional/multiple grants in one clause, dependency/type layers,
  full non-keyword ability suppression and keyword variants remain unfinished.
- Printed Oracle triggers beyond supported families still require independent
  compilation and acceptance fixtures; intrinsic keywords are not a general
  trigger-language implementation.
- Simultaneous replacement/prevention ordering, broad strategic AI evidence and
  operational release gates remain on the finish plan. UI redesign is deferred.
