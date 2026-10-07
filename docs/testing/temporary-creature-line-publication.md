# Temporary Creature Line Publication

This separate increment applies the previously frozen publication-condition
proposal over the exact BarioC partial product, not a moving parent or Ray tree.
Only `basic_land_layer._resolve` changes: effective lines are also published when
an existing explicit creature-subtype operation is present. Type computation,
timestamp/dependency ordering, record schema and all other algorithms are unchanged.

Layer preimage SHA256:
`f2c2e66d08fbd3a19b355abea342dc919857d328b8f914861b466893670f13c8`.
Postimage SHA256:
`b8bdfa21b694b3f414786083aa2b22a3d4c20b75676c3fd181076242bf328305`.

## Qualification

Original 42 strict tests, earlier 26 controls and four whole 148 neighbors are
unchanged. A new 16-case module exercises canonical Creature, Artifact Creature
and actual animated Creature Land targets, both spells/seats, real paid changes,
effective lines/subtypes, sacrifice/affinity readers, snapshot restore and native
cleanup. Canonical Prospector's actual selected Goblin cost becomes unavailable
for a transformed Goblin Instigator and recovers after cleanup. These are real
cost-availability queries, not a new fabricated affinity spell or certification
of all mana-activation execution paths. Existing 26 controls cover paid Jump
ordering/removal and actual Cloudshift reentry; original 42 cover stale-target
whole-spell fizzle/no draw and complete Snakeform change before draw.

- Precondition baseline of the new 16: 4 PASS / 12 FAIL, 5.51s.
- First whole 232: 228 PASS / 4 FAIL, 2 warnings, 42.13s.
- Corrected same whole 232: 232 PASS, 2 warnings, 41.89s, exit0.

The four first-whole failures were a NEW test's incorrect Goblin-only cleanup
expectation. Full retained canonical Goblin Instigator is Goblin Rogue. Only
that restoration assertion was corrected to the full printed subtype set;
product bytes and all original assertions unchanged. Both ledgers/source versions
are archived. Repeated gates are not extra distinct coverage.

All SQLite and socket connections denied. Own local source/import paths and
RNG-bearing root snapshots are recorded; no app lifespan, database import or
HTTP qualification. No new source-frame/protocol keys, target relaxation, model,
Oracle helper, metadata module, AI, cost or schema edits. Existing Jason 55283
target-reference dependency is consumed unchanged; no newer source-frame or Ray
composition is inferred. Published type query ABI/record fields remain unchanged,
so no Sagan metadata/query hook is needed.

This is a bounded two-family pure-core qualification, not all temporary effects,
all layers, whole API/privacy menus, natural gameplay or trained competence.
