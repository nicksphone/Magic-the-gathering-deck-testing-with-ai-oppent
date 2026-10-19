# Damage Replacement Resolution Boundary

The noncombat-damage-to-counters replacement branch performed an immediate
lethal check even while the existing stack-resolution trigger stage was active.
The ordinary damage branch already deferred this check. The replacement branch
now uses the same staging predicate; normal end-of-resolution state-based
checks remain responsible for removing zero-toughness creatures.

Canonical fixture cards are unchanged. Four core-operation regressions cover
both controller seats with and without snapshot restore: Soul-Scar Mage replaces
a two-damage event to opposing Winding Constrictor with three -1/-1 counters.
The creature remains on the battlefield during staged resolution and moves to
its graveyard at the subsequent state-based check. This is an explicit core
operation, not a claim that Lightning Bolt's printed damage is two.

The unchanged production baseline fails all four new tests. The one-predicate
fix and three neighboring whole modules pass 147 checks in 9.29 seconds.
This does not certify every replacement or all intermediate resolution choices.
Main/live source was not changed by this isolated qualification.

Rule reference: Comprehensive Rules 704.4, effective September 25, 2026:
https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt
