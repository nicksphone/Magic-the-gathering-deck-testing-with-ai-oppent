# Canonical Self-Cycling Triggers

## Scope

The cycle event collects the cycled card's own anchored `When/Whenever you
cycle this card`, `this creature`, or named-card clauses outside the battlefield.
It compiles only the triggered instruction through the existing ability/effect
model, retaining the chosen cycling X and optional-effect handling. Other cards
in the graveyard are not scanned for this self-only event.

Canonical fixtures are exact archived Scryfall records for Shark Typhoon and
Renewed Faith; their identities and source archive are recorded in fixture
provenance. No printed text is modified.

## Qualification

- Ten-module isolated gate: **169 passed, 6 warnings, 26.38 seconds**, exit 0,
  without skips, expected failures or deselection.
- Both seats: Shark cycling X of 0, 1 and 3, mana consumption, draw, token stats,
  zero-toughness state-based death, snapshot restoration and instance matching.
- Both seats: actual HTTP actions and persisted snapshot restoration for Shark
  X=2, and Renewed Faith's deliberate accept/decline choice and two life gain
  rather than the spell's six life gain.
- Existing cycling, trigger choices, draw recursion, cast triggers, Suspend and
  replacement/layer neighbors pass on the same isolated source.

Early fixture/control errors and their corrected rerun are preserved separately,
not presented as successful checks. Counts overlap with prior gates.

## Dependencies And Limits

This increment is qualified over the mana/layer/source-identity milestone and
the remaining-family audit's canonical scenario helpers. Its test helpers depend
on `test_training_remaining_intent_audit.py`; the separate intent-rejection audit
is not made green or hidden by this cycling fix.

This is a bounded engine increment, not a deployment claim or certification of
arbitrary compound cycling mechanics, replacement interactions or strategic AI
timing. Dynamic self-death quantities and retained-source color consumers are
independent workstreams.
