# Live devotion resources and payoff resolution

## Implemented Scope

One pure, controller-relative counter reads colored mana symbols on battlefield
permanents. Hybrid/monohybrid/Phyrexian symbols contribute once to the selected
color set; generic/colorless symbols and color indicators do not. Copied tokens
retain copiable costs, ordinary tokens do not invent costs, and the current face
defines a double-faced permanent's cost.

Exact supported instructions cover devotion-based targeted temporary pump,
opponent damage, life gain, opponent loss with linked actual-loss gain, self
+1/+1 counters and fixed-characteristic token creation. The value is determined
when resolving, using the spell/ability controller, not the source's later
controller or an announced mana-cost X. Existing handlers still perform damage
prevention, life restrictions/replacements, counter replacements and token entry.
Pending replacement choices retain the materialized event amount instead of
recounting devotion or repeating the preceding life loss after recovery.

Transform and modal double-faced instances now start with front-face costs,
stats, Oracle text and identity, not partially populated combined-card fields.
Initialization preserves an unchosen casting-face marker rather than silently
claiming the human selected a face.
Clipped trigger proxies cannot reselect the entire face, and effect inference
uses current characteristics unless casting explicitly selects another face.
Split-card casting retains its separate behavior. This does not finish full
copy-layer, type-changing or double-faced mana-value semantics.

Grounding: seventeen fresh Scryfall responses with normalized field parity,
including Aspect of Hydra, Gray Merchant, Fanatic, Reverent Hunter, Evangel,
Setessan Petitioner, Abhorrent Overlord and mana-symbol boundary cards. The
[official Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
sections 700.5 and 712.8 define the tested resources/face boundaries. Canonical
fixtures exercise instructions and interactions, not whole-card certification.
No production deck or card is fabricated or changed to force matchup balance.

## Acceptance Checklist

- [x] Reproduce fourteen canonical spell/entry payoff failures in original source.
- [x] Verify both seats, resource/controller changes, source departure and re-entry,
  current faces, copied token costs, combined hybrid counts and snapshot purity.
- [x] Verify linked actual life loss, locked life, gain/counter replacements and
  replacement-choice recovery without repeated loss or recounted gain.
- [x] Verify all three AI difficulties choose a friendly devotion-pump recipient.
- [x] Cast, pay, resolve and restore pump/entry-counter through HTTP and SQLite.
- [x] Verify seventy-nine focused checks and the broader face/hydration selection.
- [x] Complete fresh-cache backend suite, frontend gates and complete Chromium,
  including fourteen actual casting/payment/payoff/reload cases for both seats.
- [x] Complete repeated seat-balanced Drain/Tokens/Tribal/Midrange replay matrix.
- [x] Refresh Graphify and verify/archive evidence on RCHFiles.

Development diagnostics are preserved separately from acceptance: the initial
test setup incorrectly placed a hand-helper card directly into a nonexistent
player stack list; the corrected original-source baseline fails fourteen payoff
cases. Old copy tests constructed Elvish Mystic by partially mutating a Valki
instance and retained its restoration metadata; they now construct the actual
Mystic through the factory. Front-identity assertions now require the front name.
Two instruction-proxy test errors (reminder-line selection and pre-existing pool
mana) were corrected before the final full run. Two superseded full runs were
explicitly stopped, not counted as passing. Browser setup initially used partial
mana pools incompatible with its snow-mana contract, then matched cast labels
without their displayed costs; fixture/control checks were corrected without
weakening payment or result assertions.

The first completed full run exposed five regressions (three partial/non-card AI
action fixtures and two unchosen-face metadata contracts). The AI guard now
accepts missing names, and front initialization preserves the original selection
marker. All 255 affected checks pass; final-source full/browser/replay gates are
rerun, not inferred from that focused selection.

Final-source results: 5,361 backend checks pass (541 existing deprecation
warnings, 1,005.11 seconds). Frontend lint/runtime contracts/production build
pass. Complete Chromium passes fourteen new both-seat casting/payment/payoff
and reload cases plus existing actions, sideboarding and natural BO3 flows.
The final Drain/Tokens/Tribal/Midrange matrix passes twelve seat-balanced
samples, each repeated twice, in 479.769 seconds with no reported anomaly,
timeout or replay drift. The earlier matrix and repaired browser run also pass;
those earlier gates preceded the two final contract corrections. Final source
byte comparisons, not old green logs, establish parity for the final gates.

Evidence, failures, canonical inputs, source and a consistent online backup of
live SQLite are preserved under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/devotion/20261004T002750Z/`.
SQLite runs only locally; archived backups are compressed bytes on NFS.
Publication and disposable-scratch cleanup receipts accompany the archive.

## Known Limitations and Next Upgrades

At this payoff milestone, devotion-based creature type removal remained open;
the subsequent [conditional-type batch](conditional-creature-types.md) implements
and tests the supported self-only clause, with full acceptance completed.
The [mana-ability batch](mana-abilities.md) adds bounded devotion mana sources.
Arbitrary static/global type changes, broader mana abilities, other variable expressions/targets, unsupported composite
clauses and devotion-increasing modifiers retain admission warnings. Existing matches with
already-resolved approximations are not retroactively repaired. Start new matches
for acceptance. Full-card correctness, expert devotion deck planning, broad AI
strength and balanced win percentages are not established by these fixtures.
The alpha UI redesign remains deferred.

A separate public-state decision probe at this milestone identified a Master
bug: with a known unblocked 2/2, opponent at four life, devotion two and one
green mana, Strong casts the pump while Master passes in both seats. The
cast-and-priority line is validated through checked actions and wins at combat
damage for each seat. That bounded post-block gap is subsequently fixed by
[checked combat-response forecasting](ai-combat-responses.md); broader strategic
and adversarial planning remain open. No engine statistics or cards are changed
to force the decision or matchup balance.
