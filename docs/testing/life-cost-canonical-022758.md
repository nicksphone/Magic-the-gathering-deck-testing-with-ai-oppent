# Canonical Life-Cost And Sacrifice Fixtures

This test-only component uses immutable
`022758e64debeeab8b8e698cce2cd76d35ba82d5`. Five named positive constructor
sites become complete official cards: Toxic Deluge, Font of Agonies, Platinum
Emperion and Giant Spider in `test_variable_life_cost_audit.py`, and Rest in
Peace in `test_additional_costs.py`.

All 15 original functions, 55 assertion ASTs, engine actions, announced X,
payments, resources, seeds, IDs, owners/controllers and target operands are
retained. The only original-module changes are those five constructor calls
and two local imports; their finite inversion restores the complete module
ASTs. Anonymous numeric creatures, Additional Cost Spell/Test Creature,
Artifact Sacrifice Spell/Treasure Artifact and deliberate Oracle/name-collision
vectors remain unchanged and unwaived.

Four complete RAW objects and their provenance are reused from existing
committed fixtures. Toxic Deluge is the exact complete 65-field object at
line 26,437 of the already-pinned Scryfall bulk JSONL. The compressed bulk,
whole original line including its newline, and canonical full-object hashes
were all verified. Its full original line is committed without projection or
rule edits. An initial administrative extractor incorrectly stripped the
newline before comparing the raw-line hash; it stopped before writes, and
the corrected exact-byte extraction and original reference are preserved.
There was no HTTP/provider request. All five RAW/provenance inputs were
NFS-archived and byte-readback verified before offline imports/tests.

The finite helper follows the existing real Factory-template pattern:
complete normalized canonical deck before birth, then only runtime
ID/owner/controller/zone on a new `dataclasses.replace` instance. It never
retags, clears or reseals captured stock and does not consume the original
game's RNG. No production, shared helper, schema, ranking or AI code changes.

The new tests capture the actual original first consumers and actual Factory
input/result. They check every retained printed field, full unknown RAW fields
in the Factory entry, the complete body, real snapshot roundtrips and strict
rejection of Oracle/cost/color corruption. Those observers stop before the
consumer; all original gameplay tests execute their real consumers normally
in the separate whole-module run. Complete Font activation text and Rest in
Peace's entry clause are retained, but their presence does not newly qualify
an activation or an entry-trigger route that the original tests do not run.

Actual ledger: new fidelity against untouched original fixtures gives
29 FAIL / 5 PASS in 3.44 seconds. Identical new test bytes then pass together
with both whole original modules: 49 PASS, zero failure/error/skip, in 5.44
seconds. All 147 setup/call/teardown phases pass exactly once. No real
canonical semantic RED remained, and no old assertion/action was adapted.

The 200-case unit ceiling, 900-second guard/outer deadline and 15-second
TERM/KILL grace are finite. Nine preimport canaries deny native SQLite
aliases/direct constructors, sockets, processes, provider imports and App
startup. Source/FRESH bytes, links and directories remain equal; there is
no unexpected denial, database, child, new thread or FD drift. This is
cooperative trusted-source enforcement, not hostile-code OS isolation.

This document was written after the gate and is outside its source-BE claim.
This is a local pure fixture component, not SQL/HTTP, browser/native,
protected replay, whole-backend, Task1.3 literal-zero or Phase1 acceptance.
Parent integration owns the derived graph update; W/index and the earlier
Bounce30 packet were not modified.
