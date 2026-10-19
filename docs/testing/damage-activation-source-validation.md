# Native Damage Activation Source Validation

This is a bounded reader correction, not authentication of arbitrary persisted
frames or certification of all source-characteristic and replacement rules.

`stack_engine._validate_damage_activation_source` runs immediately after reading
the real top stack item, before target hints, conditional fizzle, pop, staging or
replacement choices. It applies only to the existing generic activation markers
`__activation_source_reference` and `__ability_target_text` and supported damage
keys, including damage inside the existing sequence/conditional packet shapes.

The native reference must contain exactly `incarnation` and
`zone_change_sequence`, both nonnegative exact integers (not booleans). A live
same battlefield object may genuinely change controller. A departed source or
same CardID/new object requires the existing retained battlefield LKI. Present
LKI, including damage-child overrides, is validated even when the source remains
live: controller is an exact integer in the match and `battlefield_incarnation`
matches the native original incarnation. The LKI producer does not store an old
zone sequence; the reader neither invents nor recomputes one.

Explicit hand/discard activations identified by the existing activated-ability
extractor retain their nonbattlefield contract. Legacy frames missing either
native marker, spells/copies and genuine triggered frames remain outside this
guard. Removing markers is not a valid external action or a proof of integrity.
No new frame/schema fields, Oracle grammar, damage execution or query inputs are
introduced by this increment.

## Qualification

The unchanged original eight corrupt paid-source tests now pass ordinarily.
Paid Sorcerer/Ray/Unsummon/Bolt/Cloudshift episodes cover both seats, live control
change, true departed LKI and new incarnation. Additional controls cover exact
integer/reference shape, bad present live LKI, actual target bounce/fizzle,
missing source, complete-root rejection and snapshot round trips. Publicly
remembered returned cards are checked against the existing exact observation;
other opponent hand/library contents remain unknown.

Containing-packet corruptions and removal of a card from the state map are
explicit controlled reader tests, not newly claimed legal card episodes. The
unchanged canonical Twinshot Sniper hand-discard assertions and original
Ballista/Goblin Dynamo hint/X-cost neighbors check compatibility.

Final-source union: 330 PASS in 116.90s, twelve whole modules, no exclusions,
errors, skips or xfails. Earlier focused 218/neighbor 110 gates are separate
ledgers, not additional distinct cases. SQL/native SQLite connections and socket
audit events are denied before collection; the final harness also blocks bare
socket constructors and propagates its guard to cold JSON restore children.
Unknown conditional packets are not recursively promoted into known damage
instructions. No HTTP or SQLite restart qualification is claimed here.
Pre-change and failed pre-collection launcher ledgers are retained separately.

Exact production scope is one new function plus one early call in
`stack_engine.py`; byte equality outside those additions is verified. Query,
parser, transport whitelist, finish logic, numeric receipts and Ray guards remain
unchanged. Other workers' additive transport keys must be composed surgically.
