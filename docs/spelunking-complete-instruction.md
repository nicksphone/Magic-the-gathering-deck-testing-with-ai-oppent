# Spelunking: Complete Instruction and Land Entry

This isolated patch is based on the 281-file capture whose bytes match public
commit `199b5842f89c0c5fc541190c61910adbd8bfefc0`. It changes five production
files, not the engine dispatcher, AI, models, or historical tests.

The compiler admits the complete supported instruction: mandatory draw, then
deliberate optional hand-land entry, then conditional life for the land actually
put this way. Unknown tails are not partially rewarded. The selected land's
pre-entry and post-entry object references accompany the conditional reward;
an existing Cave, declining, or a stale request does not qualify. The existing
draw, mechanic-choice, entry-choice, and gain-life replacement consumers remain
responsible for pauses and execution. JSON snapshot restoration tests are not
SQL restart tests.

## Entry Replacement Ordering

The [Wizards release notes](https://magic.wizards.com/en/news/feature/the-lost-caverns-of-ixalan-release-notes)
distinguish intrinsic tapped-entry replacements from an instruction that puts a
land tapped. With an active untapped-entry source, the controller can order
competing intrinsic replacements to choose either orientation. The static
replacement overrides an effect's tapped instruction. A source entering
simultaneously with a land does not apply to that land.

The shared entry seam queries an already-present, controlled, unsuppressed
source. Manual replacement mode exposes native `tapped` and `untapped` options;
automatic mode uses the existing default ordering. Shock-land payments remain
explicit and charge their actual life cost even when an untapped alternative
is free. Explicit final tapped choices are preserved. The only public schema
change is the additional `LandAction.entry_choice` literal `untapped`; choices
not offered by native entry rules remain rejected.

**Qualification limit:** this patch does not qualify the general simultaneous
multi-permanent entry pipeline. A source-in-hand negative control proves only
that an absent source is inactive, not simultaneous-batch replacement ordering.

## Evidence Scope

Canonical fixture provenance records the existing source paths, full raw or
complete printed-record distinction, object hashes, and public commit. Tests
cover both seats, public choice privacy, root and RNG preservation, mandatory
draw ordering, deliberate decline, selected Cave identity, replacement pauses,
ordinary and shock entries, ability suppression, and native life replacement
and prevention. Explicit synthetic handler/stale-request controls are labelled
as such. The unchanged original 24-case audit retains its separate Saga failures;
those are not Spelunking closure or permission to change existing assertions.

No trained-point, behavioral-quality, new-source checkpoint, or activation claim
follows from these mechanical component tests.
