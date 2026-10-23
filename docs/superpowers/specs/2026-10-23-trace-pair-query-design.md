# Single Pair Query In Battlefield Traces

The closed native evaluation is not accepted: 98 resolved series and 12 resource
limits. This change targets observed repeated work, not the acceptance policy.
Each battlefield row currently asks for power and toughness separately; both
wrappers compute the same complete pair. The selected design calls the existing
pair query once, at the original power-query position, and retains both integer
conversions. Types, tapped state, keywords, damage and row order stay unchanged.

Considered alternatives: caching across snapshots risks stale layers; dropping
trace fields loses evidence; changing caps or compressed-byte accounting changes
the contract. None is part of this work. This design is the implementer's choice
under the user's instruction to proceed autonomously, not a new user-approved
performance claim.

No policy, trace schema, resource limit, deadline, actor, model or metric changes.
No SourceB/F writes or retry of the rejected matrix. Native tests must first fail
on redundant call count while preserving row values, then pass with exact legacy
row/payload bytes and fresh results after counter changes. A controlled timing
sample may measure this primitive; it cannot explain the 11 deadlines or qualify
natural-game improvement. Full CI and eventual all-series acceptance remain open.
