# Turn-Local Land Entry History

Status: independent `codex/linked-landfall` candidate, not live. The ledger and
three complete alternative instruction families are implemented; linked damage
and broader landfall semantics remain open.

Single and simultaneous battlefield-entry events record lands using their
actual controller and effective types at entry. Counts do not consume a land
play, survive departure, and reset for both players at the real turn boundary.
Pregame entries do not claim an entry during turn one. Pending entry choices
record only committed entries; snapshot/resume preserves counts and knowledge.

Old snapshots missing this history remain explicitly unknown. A newly observed
entry proves presence even when prior absence cannot be established; a new turn
restores a complete empty ledger. `landfall_status` returns True, False or None,
not a guess based on current battlefield or land-play allowances.

Fourteen focused cases failed on the prior source. The expanded event, land,
priority, turn and discard regression selection passes 166 checks. Further
canonical Twincast and Ward-reference checks pass in a separate 139-check gate;
these figures are overlapping selections, not a combined full-suite count.
The separately frozen targeting branch's full gates do not include this ledger.

Canonical Groundswell, Rest for the Weary and Mysteries of the Deep API responses
are retained verbatim with SHA-256/provenance. Together with Searing Blaze they
supply pump, life, draw and linked-damage conditional families for the next batch.
The complete pump, life and draw forms now build durable alternative packets.
Resolution checks the spell or copy controller's history and invokes only the
selected existing handler. Entries after announcement and departed lands count;
an opponent's entries do not. Draw doubling and suspended dredge reuse ordinary
replacement/continuation paths rather than a separate draw implementation.

The new 27-case baseline failed nineteen cases on the previous interpreter.
Expanded canonical coverage adds draw replacement, resumable dredge and opposite
controller copies. The broader isolated selection passes 354 checks, including
the 39 new alternative cases; this is not the full suite or match evidence.
One attempted regression command named a nonexistent test file and ran no tests;
the corrected explicit selection produced the reported 354-check result.

Unknown legacy history is an explicit ActionRejected before a stack item is
consumed, with complete snapshot equality checked. Such snapshots cannot safely
resolve these alternatives until history is known. There is no invented default
or interactive repair UI. Fresh states and the next actual turn have known
history. This restriction is a migration limitation, not arbitrary-card support.

A subsequent two-case regression found that an illegal only target should fizzle
without consulting unknown history. Both cases failed before moving the guard
after target legality, and the corrected 111-check stack/alternative selection
passes. This increment brings the canonical alternative cases to 41. The running
312-file full suite was frozen before this last repair; it must not be reported
as verification of the newer source. A mistyped stack-test filename ran no tests;
the corrected explicit selection produced the 111-check result.

## Next Acceptance

- Complete full frozen-source validation and canonical life-replacement, copy
  retargeting, illegal-target and paid HTTP/browser acceptance.
- Complete the [linked-damage candidate](linked-controller-targets.md) through
  its remaining LKI, copy, event, API and human acceptance boundaries.
- Improve migration diagnostics/recovery for unknown legacy history and ensure
  AI forecasts value the new alternative packets correctly.
- Add linked controller-dependent target instances, legal hints, complete cost
  admission, partial resolution and snapshot/LKI cases.
- Validate real human controls and diverse fresh seeded matches; keep old illegal
  traces rejected rather than rewrite their announcements.

The official [rules page](https://magic.wizards.com/en/rules) links the
[September 25, 2026 rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
checked on October 5. Fixture provenance records the canonical Scryfall endpoints.
No cards or competitive decks are invented or adjusted for a desired win rate.
