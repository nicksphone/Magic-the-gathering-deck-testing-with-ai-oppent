# Dynamic Self-Death Token Quantities: Tests / Proposal Only

## Frozen Input and Scope
Parent source-only input:
parent-integration/spell-reservations-d88dbf0/current-surviving-access/qualified-source.tar.gz
SHA256 4b311ff58b60cf569bab13b8f4c5d8a3be2703d2d2725a7274a5e8cfec599153.
929 original .py/.json/.svg files pinned, no DB/cache/dependencies copied.
Existing reviewed identity dependency costs-only.patch:
053c2928fed76c5c7fbb1b3fcb46a35a625a39b59552a478dc8e53360a53b024.
Applied to own NEW local scratch; costs.py final hash
4ba22bbe98802ad0abd6af50efd09db8ab844a5e19631a9420dbce18d0bbc748.
928 other existing files byte-identical. NEW work changes no existing product file.
No main/live, AI, engine, parser, handler, planner or public API edits.
Incremental patch contains two NEW tests, NEW canonical/provenance fixtures and this
NEW report only. Apply AFTER reviewed identity patch, not instead of it.

## Canonical Provenance
Seven unchanged raw records: Hangarback Walker, Hooded Hydra, Nested Shambler,
Reef Worm, Phyrexian Tower, Rest in Peace, Raging Goblin.
Offline bulk from knowledge-corpus/workstream-a-0214bb9/sources/
oracle-cards-20260927090157.jsonl.gz, compressed SHA256
17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13.
Verified complete38690-record scan with2MiB line/1GiB expanded bounds, no HTTP.
Provenance pins raw card IDs, Oracle IDs, exact canonical JSON and each row SHA.
No edited Oracle, fabricated aliases/decks, competitive match or hidden AI input.
Positions are explicit small canonical diagnostic states; counters represent
existing battlefield counters, not guessed casting X. HTTP controller is directly
installed/persisted around that state; NO /matches/start/deck qualification claim.
Source printed stats/costs/keywords/colors/Oracle come from the raw payload helper.

## Ordinary Strict Before Results
Exact FINAL same-source invocation (no xfails, deselection or cutoffs):
57 collected:42FAILED15PASSED3.77s, exit1.
frozen-before.log / frozen-before.exit.

Failure groups:
24 exact count tests = both seats x3 cards xcounts2/3 xdirect/JSON snapshot resume.
6 returned-incarnation count cases, both seats x3 cards.
6 two-death same-card-ID context cases, both seats x3 cards.
6 actual HTTP/SQLite resume cases, both seats x3 cards.
Passing controls:
1 provenance;6 correct death-context-to-parser;6 RIP exile/no death/no tokens;
2 fixed Reef Worm count/stats controls.

Hangarback and Hydra: expected2 or3, actual1. Nested Shambler: expected2 or3,
actual0. Correct LKI counters/effective power/incarnation, actor BB pool2, exactly
one printed self-death trigger and root immutability checked before count failures.
For Nested, the correct effective power2/3 is actually received in parser input.
Counter/power quantities already wrong when trigger is created, not lost by restart.

All56 non-provenance cases have separate JSON receipts. They include immutable
setup/full snapshot, checked action, raw events and readonly parser input/output,
source LKI, original/returned incarnations, queued stack payloads, public warning
fields, resolved snapshot and actual counts as appropriate to each test.
No synthetic replacement count is injected. Old count tests use explicit Oracle
expected quantities; no sequence+1 guessed oracle.

## Source Identity Context Failure
Initial self-death trigger has no __source_lki.
After helper-mediated return/reentry, existing old trigger stays initially unchanged.
Second actual Tower checked activation kills same card-ID in new incarnation:
capture_last_known_battlefield (events.py:35-63) uses setdefault on every existing
same-source stack item. Since first trigger had no frozen LKI, it gains NEW LKI.
Receipts: old incarnation2 -> captured3; counters/effective power belong newer death.
Actual newer/older token increments (after snapshot resume and both real resolutions):
Hangarback1/1 expected3/2; Hydra1/1 expected3/2; Nested0/0 expected3/2.
Six tests fail FIRST on incorrect old-trigger incarnation, after saving all counts.
They are not retroactively counted as count-only failures.

Return setup uses existing move_to_zone + assign_static_order_on_battlefield_entry,
not guessed identity arithmetic. It is a controlled internal return/reentry fixture,
NOT a claimed public reanimation spell protocol or legal priority sequence.
Actual death/payment/trigger formation and resolutions are genuine engine calls.
JSON snapshot resume preserves queued metadata exactly.

## Actual HTTP, Root Privacy and Restart
Six actual ASGI requests qualify strict both-seat canonical positions:
public /cards/completeness; invalid resource choice422 with byte-identical root,
controller snapshot and local SQLite dump; valid exact Tower choice200; remove
controller and restore via real Repository/_restore_active_matches; two real
pass_priority requests200 with restore after each; then strict token assertion.
Controller revision3, stack resolved; actual counts1/1/0 respectively.
No external socket calls permitted; startup/test DB is local isolated scratch.
AI objects merely match normal restore metadata; both controllers are human,
so no AI move or hidden-information choice is made.

Exploratory before.log:30fail9pass1.95s (39-case earlier module).
final-before.log:36fail9pass4.77s included6 HTTP FIXTURE failures, because empty
ai={} became default metadata on restore. It did NOT qualify HTTP token outcomes.
Fixture corrected by initializing the same default AI metadata, not by weakening
equality or editing production. corrected-before.log:42fail9pass3.66s includes
6 two-death context failures before their receipts were moved before assertion.
strict-final-before.log:42fail9pass3.68s, receipts complete; final six passing
context controls added afterward. All logs retained. Earlier progress claim about
HTTP completion was corrected in-thread; final57-case evidence is authoritative.
No green-after claim: implementation is not authorized/started.

## Public Warning / Support State
Measured real cached-canonical /cards/completeness responses:
Hangarback: rules_coverage=not_certified, unsupported_mechanics=[].
Nested: rules_coverage=not_certified, unsupported_mechanics=[].
Hydra: rules_coverage=known_unsupported, unsupported_mechanics=["morph"].
Readonly serialize_card_view effect_warnings=[] for all three quantities.
Existing "not_certified" is NOT a supported/certified rules promise.
However there is no quantity-specific warning; actual trigger effect=create_token
and bodies resolve (or zero amount), rather than an explicit unsupported quantity.
Hydra's morph warning does not describe its normal-face death count.
Snapshots/public hints do not mutate the checked root.
Tests qualify quantity/context, NOT full token metadata, recursive Reef Worm token
death chain, morph, arbitrary count expressions or broad public escape protocol.
Hangarback output also names "Thopter Artifact", with type_line token Creature and
no Artifact in types; visible in receipts, ancillary metadata not changed/qualified.

## Minimal Shared Hook Proposal (NO Product Implementation)
Requested next production ownership, if parent reviews/approves:
1. rules_engine/events.py self-death trigger materialization only.
Freeze deepcopy of already captured last_known_battlefield into existing
__source_lki before that trigger is parsed/queued. Limit to actual self-death
source/event identity. Pass the same context to the existing ability parser and
retain it in the resulting StackItem payload. It must include actual controller,
counters, effective power and battlefield incarnation; never read a returned
live object's counters/power for the older self-death trigger. Normal snapshot
serialization already supports this dictionary; no new public fields/schema.
Existing departure setdefault then preserves the first incarnation naturally.
2. rules_engine/oracle_effects.py one shared token BASE-quantity compiler.
Recognize structurally bounded self references:
"for each <counter> counter on this creature/it", and
"create X ... tokens, where X is this creature's power".
For self-death, evaluate using frozen source LKI, NOT announcement x_value,
current pool, returned object or card name. Produce scalar amount before normal
create_token handler/replacement application. Preserve zero, clamp negative power
to zero; no fallback1/0 guessing for unrecognized dynamic expressions.
Counter literal grammar must preserve actual names (+1/+1 etc.) and avoid counting
all counters or conflating token power with source power.
No engine.py/stack_engine.py/handlers.py production edit appears required for these
specific families: existing handler consumes integer amount and applies token
multipliers exactly once. Retain existing fixed amounts and unrelated X-casts.
Optional separate coverage.py ownership only if unsupported dynamic variants need
an explicit public gap guard. Not needed to certify all variants; no implicit
scope expansion beyond reviewed grammars.

Required after gate (not executed): these57 become ordinary green; add canonical
zero/negative-power, alternate counters, effective-power modifier, suppressed
ability, controller/owner, token replacement, fixed-X spell controls. Never special
case Hangarback/Hydra/Shambler, never inject token amount from diagnostic observer.
Do not fix only parser scalar while leaving older-trigger LKI attached to new
incarnation. Family seam is shared compiler + creation-time context freeze.
Larger phase-aware escape witness/public future resource protocol remains separate
proposal/audit scope; no engine production or new witness schema in this artifact.
