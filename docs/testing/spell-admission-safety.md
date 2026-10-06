# Unsupported Spell Admission Safety

Baseline: exact archived frozen M+nth plus the extra-sequence tests-only audit.
No moving source, parent/main/live database, schema, AI, mana or handler edits.

## Contract

`AbilitySpec.unsupported_resolution` is an additive tuple of explicit gaps.
An empty tuple is NOT full-clause execution certification. Metadata readiness
and canonical provenance remain separate from runtime admission.

Full selected spell text is checked for bounded, observed unimplemented
operators: extra turns, additional combat/main phases, ending a turn, controlling
a player's turn, and top-library reorder followed by optional shuffle. These
are generic instruction schemas, not card-name dispatch. Cost/reminder text
uses the existing spell-resolution surface and reminder removal. Permanent
spells are not evaluated as their later activated/triggered text. Valid selected
faces and modes are respected; an unselected unsupported mode does not remove
supported modes. Arbitrary caller `mode_text` cannot hide a nonmodal instruction.

Legal generation withholds known schema misses. After actual casting choices
and before ward/cost staging, mana or additional costs, the engine rejects
typed fallback. Selected modal branches are individually checked: an outer
sequence must not hide an unrecognized selected mode. No-choice modal text is
still waiting for a choice, not automatically classified as fallback.

Unknown choice-dependent spells can remain discoverable before choices, then
fail closed at the pre-payment boundary. Successful parsing of other partially
recognized schemas is still not a completeness proof; this increment does NOT
claim every possible omitted clause is detected. Such cases need independent
compiler coverage audits. No fabricated resolver effect is added.

## Evidence

Full unmodified canonical raw/provenance fixtures cover Time Warp, Day's
Undoing, Worst Fears, Temporal Mastery, Relentless Assault, Ponder, Distorting
Wake and positive controls. The independently extracted full Primal Command
fixture shows that selected misses can hide in an outer sequence. Its supported
gain-life/search modes remain admitted; its unrecognized modes fail before
costs. Ponder's recognized draw does not mask its unimplemented reorder/shuffle.

Supported controls include damage, tokens, creatures, static enchantments,
Opt's actual private continuation, counters and later legal fizzle. Original
modal, kicker, aftermath, foretell, Suspend, self-cycle, readiness, turn and
HTTP neighbors are separate gates. No parser output is labeled learned quality.

Actual in-process API tests check 422 `illegal_action` with an explicit
unsupported message and unchanged whole root/card/player/stack facts,
configuration, RNG and SQL dump. Two-process startup/restore tests verify
snapshot/config/RNG/receipts and repeat rejection. Direct strict engine entry
is also byte-pure, including logs. Invalid face choices remain structured 422.
All data is synthetic local SQLite containing genuine canonical card rows;
no hidden-library or opponent-hand inference is used to decide admission.

## Packaging

Four-file core: ability_model.py, move_generator.py, engine.py, coverage.py.
Separate necessary adapters: a small action_validation.py diagnostic adapter,
and one oracle_effects.py line propagating the existing diagnostics flag through
modal recursion. The qualification is of the composed source including both
adapters; do not claim the four-file core alone reproduces the HTTP diagnostic
or strict modal log-purity contract. No effect handler is changed.

The previous audit's paid-noop witnesses are truthfully adapted to the new
rejection behavior. Original source, red logs and report remain immutable on
NFS. The scheduler's ten ordinary-red desired contracts are unchanged and
non-default-collected; rejection is safety, not extra-turn/phase implementation.
The old extra-sequence document describes that historical baseline, not current
runtime support. A separate scheduler proposal is unimplemented.
