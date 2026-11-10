# Target mana value follows characteristics, not payment estimates

The reusable target restriction predicate currently sums `parse_mana_cost` payment estimates. This counts each `{2/W}` as one and omits `{S}` entirely. Spectral Procession has mana value six even when paid with three white mana; Icehide Golem has mana value one. Native stack callers already supply the target spell's chosen X. Preserve that contract rather than substituting the responding spell's X.

Use the existing rules `mana_value` function in the restriction predicate, with the same caller-supplied target X. Do not alter payment planning, printed facts, alternative costs, target bounds, selected/copy characteristics, stack identity, rules admission or AI scores. The correction must apply through the common predicate to all supported mana symbols, without card-name exceptions.

Prove actual paid casts, legal target hints, checked counterspell/exile admission, atomic illegal-target rejection, restored queued resolution and current root purity. Use existing complete canonical native readers and MatchFactory constructors. Keep runtime/fixture bodies and opaque captures unread by tooling. Declared old-board graveyards and snow creatures are explicit setup, not paid births or natural reachability claims.

This is movement toward the original full rules/arbitrary-deck goal. All three RC gates, all five AI/data phases, thirteen expert styles and backend/native/browser/install/build/deploy acceptance remain required. No unchanged-environment full backend/HTTP/TCP/Forge or frozen matrix retry, no remote-write bypass, no broader privacy or performance claim.
