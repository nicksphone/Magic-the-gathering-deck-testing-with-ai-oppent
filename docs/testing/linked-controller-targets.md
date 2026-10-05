# Controller-Linked Conditional Damage Candidate

Status: independent candidate, not live; focused human casting flows verified.
Canonical Searing Blaze supplies the complete instruction family; parsing is
structural and uses the source's name, not a card-name dispatch table.

## Implemented

- Legal hints enumerate complete player-or-planeswalker plus controlled-creature
  pairs. Announcements must match one complete pair before paying mana; missing,
  wrong-controller, mixed and reordered selections reject without mutation.
- Existing target fields suffice: player plus creature uses `target_player` and
  `target_card_id`; planeswalker plus creature uses ordered `target_card_ids`.
  No new untyped client effect arguments or SQL gameplay logic is introduced.
- Ordinary/landfall damage is selected once at resolution using the controller's
  turn-local land-entry ledger, and valid recipients share existing damage batch,
  replacement and state-based-action paths. No ordinary-plus-landfall summation.
- Captured object references distinguish a returning permanent from the target.
  Illegal creatures do not prevent damage to a still-legal player. A newly shielded
  player does not prevent damage to its legal creature. Controller changes on a
  still-present planeswalker recheck the creature dependency against current
  control. All-illegal targets fizzle without requiring unknown landfall history.
- All four tested AI style labels materialize complete planeswalker pairs when a
  player is shielded. At most sixteen complete hostile pairs use paid public
  checked-outcome projections; unknown continuations use an explicit threat-score
  fallback. This is bounded tactical choice, not seasoned-player certification.
- Shared Ward reference filtering prevents copied old targets from triggering
  Ward on a new object that reuses the same card ID.
- Copies now offer two durable independent choices. Primary targets can switch
  between player and planeswalker; new creatures must satisfy the selected
  controller dependency. Unchanged illegal references may be kept, never silently
  recaptured. Wrong owners/dependencies reject without mutating snapshots. Paid
  Twincast suspends and resumes through the real stack; countering the original
  does not erase the copied source. Ward targets only the appropriate copy.
- Copy AI uses at most sixteen complete public continuation outcomes (4x4 beam),
  discards hidden draw/hand-changing projections, and retains a deterministic
  legal threat fallback. Four style labels and both seats redirect harmful copies;
  this is bounded tactical coverage, not expert-play certification.
- Shared single-source damage batches combine identical recipient packets before
  replacement/prevention. A creature/planeswalker in both target roles receives
  one combined damage event, with independent target legality. Canonical Urza's
  Armor and Furnace of Rath fixtures verify distinct chosen replacement orders
  and durable continuation. Multi-type positions are constructed continuous
  layers, not a claim that arbitrary animation-card Oracle text is implemented.

The current family has 58 canonical tests. The first baseline had 30 failures
and 8 passes, but eight failures were fixture-setup errors, not engine evidence:
the assumed strategic fixture container/card was wrong. A new verbatim canonical
Ugin response/provenance corrected that setup. The corrected paid player/PW and
alternative selection then passed 79 checks. Eight new AI pair tests failed
before materialization integration. A 345-check broader selection passes; a
subsequent overlapping 139-check Ward/copy selection passes. These are not summed
or substituted for a full current-source suite.

The pre-copy frozen backend gate passes 7,688 tests across all 313 discovered test
files, each included exactly once. At that gate, all 594 compared backend source/fixture files
matched the frozen source and four isolated shards. Frontend tests, lint and build
pass. Eight Chromium cases cover both human seats, player and planeswalker
primaries, and ordinary/landfall damage: complete pair selection, paid casting,
pending-stack reload, priority passing, effective damage and final reload. Each
case also rejects a wrong-controller pair with 4xx and unchanged public state.
The initial browser failure was invalid fixture snow-mana bookkeeping, corrected
without weakening the contract. Its full browser gate subsequently passes,
including natural AI, human-AI and human-human BO3. This precedes the latest
copy/damage increment and is not substituted for its separate gates.

The newer copy suite has 28 cases; all 18 initial cases failed before integration.
An intermediate paid-case assertion incorrectly expected suspended resolution to
return true, and another setup added a new target after choice options were already
frozen. Both were corrected without relaxing server checks. Four new paid Chromium
copy cases plus all eight damage cases pass. Six initial same-object/prevention
cases failed before coalescing; the family now has fourteen cases including human
replacement order/resume. An overlapping 306-check selection passes. The frozen
copy/damage backend gate now passes 7,736 tests in 316 files, each included once;
601 source/fixture files match all four shards. Its full browser gate passed,
including the natural BO3 controller modes. Discovery was
corrected from 310 top-level files to 316 recursive files before the waiting last
shard began; no active run was restarted or tested source edited.

Six later AI regressions verify that the existing public counter forecast
rechecks controller landfall history at resolution, values enhanced lethal damage
above ordinary damage, preserves authoritative snapshots, and keeps conditional
hidden draws unknown. These pass in an overlapping 105-test isolated selection;
they are not included in or added to the earlier 7,688-test frozen gate. No new
card-specific forecast heuristic was necessary. An initial four-case setup failure
was a wrong fixture return arity, corrected before asserting forecast behavior.

The earlier frozen landfall source passed all 7,628 tests in 312 files, but it
predates the last legacy guard adjustment and all linked-target work. It cannot
certify this candidate. Successful command outputs and failed/mistyped commands
are retained separately in private evidence, not rewritten.

## Remaining Acceptance

- Determine and verify the departed/replaced planeswalker dependency rule with
  authoritative interpretation and departure-time, not cast-time, LKI fixtures.
  Current unresolved cases explicitly reject before consuming the stack item;
  they are a genuine playability limitation and must not be called supported.
- Complete the fresh full gates for the now-implemented paired copy choices and
  same-object/replacement event fixes; extend protection/LKI corner fixtures rather
  than treating bounded coverage as universal certification.
- Run fresh retained seed/seat-balanced games against the verified frozen source;
  reconstruct checked decisions and inspect actual card use. Preserve old illegal
  trace failures; do not fabricate targets or tune decks to desired win rates.

All four logical capability games repeat identically across eight executions,
without reported timeouts or anomalies. The 2,217 logical decisions include one
Searing Blaze cast, six Groundswell casts, four Rest for the Weary casts and three
Mysteries of the Deep casts. Every execution reconstructs under strict checks.
The reversed-seat draw-opportunity audit has no legal Mysteries casting opportunity
in that particular game, so absence of its cast there was not called an AI bug.
These runs use the pre-copy frozen source and two 60-card exercise decks, not
competitive recommendations. They do not certify new copy behavior or balance.

## Subsequent Conditional-Copy Repair

Further inspection exposed stale branch recipients: generic copy retargeting
changed the announcement but not the two conditional effect payloads. Both
branches now follow the selected legal target, while the alternative is still
chosen from the copy controller's history at resolution. AI evaluates the current
known effect branch rather than blindly keeping harmful copied pumps/life gain;
unknown history does not justify guessing a branch. No card-name dispatch was added.

Twenty-four new cases failed before this repair. The corrected family and older
copy/Ward/landfall cases pass an overlapping 188-test selection. An intermediate
test incorrectly expected Rest for the Weary's ordinary gain to be two rather than
the canonical four; only that test expectation was corrected, not printed data.
These latest two runtime-file edits and the new test file were outside the
316-file copy/damage frozen gate. A subsequent frozen gate now passes 7,760 tests
in all 317 recursive files, each included exactly once; all 602 backend
source/fixture files match the current candidate and every shard.

Eight additional Chromium cases use paid canonical Twincast, not direct copy
effects. Both seats deliberately redirect Groundswell and Rest for the Weary,
with ordinary and enhanced copy-controller history. Reload preserves the pending
choice and selected target; the original is unchanged, the mana is spent,
Twincast is in the graveyard, and only the copied spell resolves to the expected
effective stats or life total. The test harness includes these cases by default.
This is focused browser acceptance, not another complete browser run.

A fresh seed/seat-balanced capability matrix is running against this latest
frozen backend. It replaces four Memory Deluge with four canonical Twincast in
the previously validated 60-card control exercise. No other card metadata changes,
no forced hands or target win rate, and no competitive-deck claim. Retained
decisions and actual copy use require inspection before promotion.

## Evidence Sources

Canonical Scryfall card responses and fixture provenance are retained verbatim.
[Searing Blaze rulings](https://api.scryfall.com/cards/f659d464-13dd-49e2-a842-098dcba49659/rulings)
were freshly fetched on October 5. The old player-only partial-target ruling
does not alone settle every modern planeswalker dependency case. The
[September 25 rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
were fetched successfully with curl after the browser tool could not access them.

A single sanitized TypeSafe request supplied three evidence-support judgments
(Jev 1.13, request `req_01a109dfcfcd736f997ecbcef24246b0`). Its low-concentration
no-creature answer and insufficient-evidence answers do not override printed
rules/rulings, prove implementation, or authorize code actions. The worker
independently treats the explicit two-target ruling as admission evidence and
keeps departed-planeswalker semantics open. No credentials or private match
hands/logs were sent. Raw request/response/provenance remain private evidence.
