# Retained Activation Source Reference

Base: immutable published `55ebc8c6cba982300f85289bdbe3d114fa29b2e5`.
Only `RulesEngine.take_action`'s `activate_ability` branch and
`shuffle_actions.shuffle_library` change. No costs, AI, animation, handlers,
stack transport, events, schema, or existing tests change.

## Internal ABI

The actual activation producer captures `__activation_source_reference` after
target/payment availability validation, before ward capture, cost staging, or
payment mutation. Its exact keys are `incarnation` and `zone_change_sequence`;
both must be nonnegative integers (not booleans). The producer attaches this
reference to the real created StackItem payload, overriding any effect payload
field of the same name. Real source ID, controller, and stack ID are unchanged.

Existing retained resolving-item and private-choice transport preserve the field,
including snapshot/HTTP restore. The shuffle reader validates the complete
reference before RNG/log/event mutation, requires the activation's nonempty
ability body, rejects trigger/reference and non-activated copy-kind conflicts,
and uses the retained identity rather than the source's current zone identity.
The source must still exist in the card table and the real controller must exist.
Current target/library ownership is not replaced by source ownership.

No new public action input or fabricated StackItem/cause is introduced. Existing
static replacement receipts and graveyard-trigger reference contracts are intact.

## Executed Qualification

- Baseline original 40 + prior reader 12: 20 PASS, 32 FAIL, 23.41 seconds.
- First post-fix whole 84: 66 PASS, 18 FAIL, 25.95 seconds. Two new test setup
  errors used the wrong canonical Azure Mage helper; the import alone was fixed.
- Final 13 whole modules: 469 PASS, 16 FAIL, 283 warnings, 116.00 seconds.
  Original 40: 24 PASS/16 FAIL; unchanged reader 12: 12 PASS; new 32: 32 PASS;
  ten whole neighbors: 401 PASS. No exclusions, skips, or expected failures.

Eight lawful paid Unsummon failures now pass across both seats, checked/HTTP,
memory/file repositories. They preserve actual paid cost, original controller,
stack ID, opponent-private chooser, wrong-actor atomic rejection, chosen tapped
basic, snapshot/cold local SQL restore, and final emitted source reference.
The prior reader's departure/reentry transitions are explicitly controlled seams,
NOT lawful blink or ETB episodes. The new producer controls use full existing
canonical Fertilid/Lux Cannon, paid Viscera Seer self-sacrifice, and paid Colossal
Skyturtle hand-discard activations in both seats.

Neighbors include targeted-search resolution, graveyard shuffle references,
activation payment choices and HTTP, hand activations, source/compound counter
costs (including last-counter SBA/LKI), activation modifiers, and shuffle
resolution/HTTP. Python 3.12.3 and pinned dependencies were verified; pip check
is clean. Offline guard rejects network and any SQLite outside the owned local
root. Existing tests and inherited files outside the two owned functions were
independently compared to immutable source; assertions/ASTs remain unchanged.

## Explicit Limits

Sixteen canonical Cloudshift/Ray response failures remain strict ordinary failures:
this patch does not implement those effects or certify lawful reentry/control
change. Older frames without this field keep their legacy live-reference fallback;
no original identity is reconstructed. Dedicated cycling, loyalty, and other
activation branches are untouched. No all-ability/all-LKI claim is made.

Malformed controls qualify rejection before mutation in the shuffle helper, not
arbitrary direct handler calls with corrupt internal frames. Search-handler
preflight currently validates only its existing graveyard-trigger reference ABI;
aligning that private preflight would need separate handler ownership if requested.
Public checked actions retain their existing copy-on-write root boundary.
