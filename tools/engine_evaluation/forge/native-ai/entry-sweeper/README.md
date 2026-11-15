# Native Self-Entry Creature Sweeper Priority

This derives from the Forge Team/Card-Forge contributors' card implementations
and baseline AI, under GPL-3.0-or-later. See NOTICE, LICENSE and the repository
THIRD-PARTY-NOTICES.md. Local changes do not claim their original work as ours.

Forge already gives direct board wipes a shared priority bonus. This extension
applies the same bonus once to supported unconditional self-entry creature
debuffs. It does not select X, reserve mana, change payment, or bypass normal
spell and entry-effect evaluation. No card-name policy or card-data hint is added.

The classifier reads only known source/context identities and native parameter
metadata. It does not construct a trigger ability or forecast prospective layers
on the live game. An existing overriding ability is authoritative; unsupported
overrides never fall back to a printed Execute body. Unknown conditions, chains,
selectors, changed text/type/ability contexts or trigger suppression do not earn
the new bonus. Pure parameter parsing can populate Forge's existing parser cache;
this is not a claim of zero process-level cache writes.

The existing comparator tiers and all previous priority rules remain unchanged.
The new default-condition comparison checks actual typed metadata, not just the
printed parameter map. Ordinary legality and tactical evaluation remain in charge
of whether the AI casts a prioritized spell.

Apply `entry-sweeper.patch` only to the exact base source in SOURCE-PINS.json and
rebuild the two declared classes with the existing guarded native harness. The
complete schema11 prefix has fourteen sources and twenty-three physical classes;
the inherited thirteen sources/twenty-one classes remain byte-identical to C8.
This patch is not a standalone installer or a live profile switch.

`NativeEtbSweeperPriority10.java` is the unchanged registered ten-case native
choice/effect regression. Its trusted established poses are not natural played
history. It plays only the AI's actual first selected action; no substitute spell
or manual X assignment can turn a refusal into success. Full canonical programs
and source hashes accompany it; generated hands/RNG/game traces remain private.

`NativeEntrySweepProtocol24.java` is separately labelled internal protocol, not
twenty-four games or strategic wins. It checks effective overrides, protected
condition metadata, typed phase/source filters, unknown selectors/chains/X,
public suppression and hidden-body read boundaries. Its two printed-path
negative fixtures explicitly reset cached override metadata; they do not pretend
to be naturally played cards. No AI callback, payment or game outcome is scored.

From this directory, `sha256sum -c SHA256SUMS` verifies artifact bytes only.
Measured evidence and limits are in `docs/testing/native-entry-sweeper-ai.md`.
Full strategy quality, learning generalization, BO3 acceptance and application
adoption remain separate requirements.
