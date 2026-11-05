# Native Forge Save Compatibility

This original GPL-3.0-or-later diagnostic uses the Forge Team and Card-Forge
contributors' unchanged engine, source pin
`61e9442c433711a82258daca3236f936a1d6f70e`. Upstream notices and license remain.

## Executed Scope

Evidence: `external-mtg-card-knowledge-20261105-1Uz704n2/native-save-audit-F2ax5LKR`.
The source distribution is unpacked, without `.git`; the pin is inherited from
the qualified source path. `SOURCE-BEFORE.json` and `SOURCE-AFTER.json` record
actual relevant source/card bytes and modes, plus the audit code/class pins.

Two registered, fully instantiated canonical 60-card decks: four Lightning Bolt
plus 56 Mountain versus 60 Plains. Both seat assignments were executed. Trusted
fixture setup moves an existing Mountain to the battlefield and an existing
Bolt to hand at turn-two MAIN1. This is not an opening draw or a natural game.
There is no fabricated Oracle, spell, stack item, event, or winner.

The real `ComputerUtil.playStack` pays the canonical cost and taps the Mountain.
Export captures the genuine pending spell, then native `resolveStack` deals
three damage and puts Bolt in the graveyard. Each of the four restores runs in
a separate JVM using `GameState.parse` and `applyToGame` on the native game
thread. No stack is reconstructed by this adapter.

## Results

- All six native JVM calls returned zero, each within 60 seconds, using one CPU,
  at most 2 GiB Java heap, an offline namespace and no resolved `java.sql` module.
  All six recorded process groups were absent after completion.
- Both settled placement controls passed: life totals, 60 physical cards per
  player, zone/card placement, library order, ownership/controller, tapped and
  face-down flags matched. Opponent life was 17 after the real paid resolution.
- Both pending-state requirements failed: original stack one, restored stack
  zero; caster physical inventory 60 to 59. Life correctly remained 20 before
  resolution, but the pending paid Bolt was not saved.
- The stricter raw observer comparisons remain four preserved red exits. Besides
  the missing pending spell, raw `hasSickness` flags changed. GameState serializes
  effective `isSick` on battlefield cards rather than every raw sickness flag.
  These differences are reported, not declared a Forge bug or hidden by a full
  save qualification.
- The observer also mistakenly recorded `ManaPool.toString()`, which is a JVM
  object-address string. Its inequality is a harness limitation, not evidence of
  a mana-state defect. Mana-content round-trip is explicitly unmeasured.

`ANALYSIS.private.json` names the narrower placement checks and preserves the
raw strict failures; it does not replace them. No RNG, controller/pending-dialog,
or BO3 restart capability was tested or qualified. No full-save invariant was
waived and no application/stdio/actor-boundary/upstream source was modified.

## Reproduction

The exact bounded compile and individual JVM/strict-check command lines, exits,
host PIDs/process groups, raw logs, private GameState text, and before/after facts
are in the evidence directory. `run_audit.py` performs serial native calls;
`compare.py` keeps the strict equality check; `analyze.py` separately measures
the explicitly narrower compatibility controls. Do not interpret the runner's
observation-complete exit as a successful complete-save assertion.

No dependency rebuild, commit, publication, graph update, or cleanup was done.
