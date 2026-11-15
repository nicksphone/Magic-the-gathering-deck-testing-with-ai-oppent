# Native Precombat Static-Buff Preference

This derives from the Forge Team/Card-Forge contributors' rules, canonical card
programs and baseline AI, under GPL-3.0-or-later. Their original source headers
remain intact. See NOTICE, LICENSE and the repository THIRD-PARTY-NOTICES.md.

The shared permanent timing gate now recognizes an incoming unconditional,
friendly continuous power bonus when it benefits an attack-ready creature.
Existing timing reasons, native legality, spell evaluation and payment remain
in charge. There is no card-name exception or fabricated AI card-data hint.

The preference uses the existing side-effect-free basic-land/mana-pool funding
witness rather than querying the stateful test payment planner. Creature mana
does not fund that witness. The helper's body is unchanged; its package visibility
allows reuse. This is not a general mana planner or a payment-source override.

Default battlefield static scopes and both canonical selector forms are handled.
Unknown selectors/conditions, ability/type/stat replacement, changed mana rules,
attack taxes and unsupported combat constraints do not create this new reason.
Source visibility precedes new body inspection. No speculative static layers are
applied to the live game.

Apply `precombat-buffs.patch` only over the exact parent in SOURCE-PINS.json,
on a fresh source copy, and rebuild with the existing guarded native harness.
PAYLOAD.json pins the complete thirteen-source/twenty-one-class closure. Two
sources and two physical classes differ; this is not a standalone installer.

The three Java mains take one fresh report-directory argument. They preserve the
distinction between an ordinary AI choice and a separately paid manual rules
control. Read the declaration comments: established readiness is a trusted pose,
not proof of a naturally played prior turn. Preservation12 judges only its two
Main 2 choices; its other ten rows are native controls/observations, not ten
independent strategic wins. ManaPreservation8 tests two full canonical lords,
both seats, ordinary land-funded casts versus creature-funded alternatives.

From this directory, `sha256sum -c SHA256SUMS` checks artifact bytes only. It
does not execute, install or promote an AI. Full-game playing strength, arbitrary
combat/mana contexts and live application adoption remain separate requirements.

See the repository's `docs/testing/native-precombat-buff-ai.md` for measured
results and their limits. Archived game traces remain private.
