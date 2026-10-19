# Creature-Only Damage Wrapper

This is a separate increment over the frozen ordered noncombat conversion
product. Only a new `handlers.damage_each_creature` and one registry binding
are production changes. Existing batch, replacement, protection, Ray source
transport, engine, keyword and compiler functions are unchanged.

The wrapper enumerates effective battlefield creatures at resolution and calls
`deal_damage_batch` once. It includes no player packets and forwards genuine
resolution metadata, including source ID, LKI and copied-spell context. A pause
uses the native batch continuation's already-computed remaining recipients,
source context and accumulated lifelink. Resume does not enter this wrapper.

Actual checked Pyroclasm execution requires the separately frozen Erdos compiler
dependency: `closed-damage-instruction-compiler/mtg-closed-damage-compiler-9jCuc3`,
integration SHA256
`db052b4481a4766e0c002180c28bf007e19afc187678d9567324eb72b75d7a7e`.
It emits `damage_each_creature` with only a positive constant amount. That
compiler delta is not part of this wrapper patch. Applying the compiler without
the registry/handler dependency is not executable damage support.

The new tests distinguish actual paid Pyroclasm and paid Mutavault responses from
controlled component seams. The Song attachment classification, nonpositive and
empty-cohort dispatch tests are component checks, not claimed legal episodes.
The pause test starts with a genuine paid spell and actual replacement choice;
its extra battlefield insertion during the choice is explicitly a controlled
protocol perturbation, not a claimed legal response. Both seats verify native
packet ordering, full snapshot restoration, private information, wrong actor and
unoffered-choice rejection, protection/conversion choice and no player damage.

All SQLite connect aliases and socket operations are denied before pytest
import/collection. There is no HTTP, database or browser qualification in this
increment. Original49, ordered20 and protection38 remain unchanged. Any newly
reachable numeric-shield ordering failures remain strict; this wrapper does not
invent independent prevention-source receipts. Battle semantics, controller
change while an activation waits, and opposing copied damage applicability are
not certified by the wrapper tests. Final executed ledgers and exact source pins
are in the archived report.
