# Batch Graveyard Publication Audit

## Frozen Scope

Tests/report only. No product, events/LKI, handlers, SBA, cost, keyword, combat,
schema/API or AI edits. Source-only extraction of immutable
`holding-spells/direct-audit-sba-observer-compatibility/mtg-sba-observer-diagnosis-hi5Rm1/observer-qualified-source.tar.gz`,
SHA256 `1bbf1ce918dfbadec7025d38ab0ef7a11a831a324425b9a2e434f5876413cadc`.
Graph was read before source inspection. No moving parent root was read.

Exact requested product pins, all unchanged through the audit:

- SBA `0484c86f6a41da3b7cb68f84d0223bd70ddf62b609e8ad26056c57e68e3ac3dd`.
- Handlers `e03f643abc930342a1242e65d3043272b6cb684e2aca0ec54e79168eb1fb3034`.
- Entry executor `3b317d5e1a830849a60ee4bde4042632133c7ecd946bfd90eb428f57e12c00fb`.
- Collector `890f0d1d23d62a17607f7437f302a0a4216fd1a49eacbcc6599dda5673a638e3`.

The parent's later discard `_entry_receipts` adapter and Erdos LKI readscope are
NOT inputs here. No readiness claim is made for those later compositions.

## Terminal Ledger

Whole new module, no exclusions/skips/xfails: **18 ordinary FAIL / 24 PASS,
422 warnings, 31.43s, exit 1**, 600-second wall bound.

| Family | Direct | Memory/file HTTP | Meaning |
| --- | ---: | ---: | --- |
| Batch publication frontier | 4 FAIL | 8 FAIL | Both paid families/both seats observe partial committed movement |
| Outcomes/from-anywhere/death/self observer counts | 4 PASS | 8 PASS | Correct final destinations/sequence, real triggers, private restart |
| Explicit APNAP/order/target choices | 4 PASS | - | Both seats, checked wrong-actor reject and durable ordering |
| Wrong-actor root/controller/SQL | - | 8 PASS | Complete immutable rejected paid action |
| Separate Progenitus damage protection | 2 FAIL | 4 FAIL | Genuine additional strict red, not hidden by changing expectation |

No whole-backend/coupled gate was duplicated. Qualified existing Python 3.12.3
and dependency pins were reused; pip consistency checked; no dependency install.
Network and SQLite-outside-owned-root audit guards were enabled. SQLite stayed
local, with fresh memory/file repositories and real in-process HTTP requests.

## Actual Canonical Episodes

Full unchanged raw rows come from existing direct-graveyard/self-graveyard
fixtures with their existing provenance hashes. No invented or shortened Oracle,
synthetic event or StackItem. Controlled starting position uses the existing
Index canonical fixture's `size=16` parameter and explicit ordinary phase cursor.
This is a fixture configuration, not a modified real saved decklist or balance
claim. Hand positioning happens before gameplay; no runtime repair.

Sickening Dreams genuinely casts/pays 1B, announces X=12 and discards twelve
existing cards as its additional cost. Each seat has canonical Kozilek, Doomed
Traveler and Blood Artist; all six legally become lethal. Darksteel Colossus
survives actual damage because it is indestructible. Progenitus is not included
in the clean SBA batch fixture; its protection assertion is preserved separately.

Wrath of God genuinely casts/pays 2WW. Untargeted destruction legally replaces
Progenitus's would-be graveyard entry with owner-library reveal/shuffle; it does
not illegally destroy indestructible Colossus. The same six ordinary creatures
enter their owners' graveyards. Two real Psychogenic Probes observe the static
self replacement shuffle in this family.

Both families preserve one real Kozilek from-anywhere trigger and one Traveler
death trigger per seat, six Blood Artist triggers per seat, correct controller
ownership and actual post-entry source references. Explicit ordering proceeds
active player then nonactive player, with reversed declared order choices and
only actually offered checked target choices. No trigger is forced to resolve
to fabricate an outcome. Snapshot roundtrip, cold HTTP restore, opposite-seat
hidden-hand/library views and full rejected root/controller/SQL checks execute.

## Measured Publication Boundary

The wrapper calls the real `_collect_triggers` unchanged and records its actual
return plus every cohort member's zone, sequence, owner and real zone-list
membership at that callback. State indices distinguish independent deterministic
action clones; observations from clones are not duplicate gameplay events.

For clean direct episodes and APNAP controls, each of twelve independently
recorded states per family has the same callback frontier:

- SBA: **1, 2, 3, 4, 5, 6 of 6 moves committed** at successive GR entry callbacks.
- Wrath: **2, 3, 4, 5, 6, 7 of 7 moves committed**. Progenitus's library move is
  already committed before the first of six GR entries.

Only the last callback sees the complete cohort. Earlier SBA callbacks see
sibling cards still marked battlefield even though all battlefield memberships
were removed. Earlier Wrath callbacks see later siblings still battlefield and
still listed there. Final destinations and observed trigger counts pass; these
are strict collector-state timing failures, not a claim that the measured Kozilek
or death triggers are absent. Full HTTP traces independently reproduce the same
desired publication assertion failures.

Frozen source-grounded seams: `zone_actions.execute_graveyard_entry:56-72` moves
one card and immediately emits entry. SBA `_resolve_lethal_creature_batch:123-135`
and handlers `_destroy_all_permanents_of_types:549-562` call that executor in a
loop, publishing before later commits and before the existing death batches.

## Rules Grounding

The already archived official September 25, 2026 Comprehensive Rules are reused
with full raw SHA256 `8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`.
Rule 704.3 treats applicable SBAs as a simultaneous event; 603.10 normally checks
the resulting state for triggers, while 603.6c excludes from-anywhere triggers
from the LTB category. Rules 603.3b/101.4 define APNAP stack ordering. Rule 608.2c
governs following the single destruction instruction with replacements. The
all-committed frontier is the bounded inference from these rules and the actual
same-event cohorts, not a universal simultaneity implementation claim.

## Separate Protection Discovery

Original broad Dreams control included protected Progenitus. Actual paid X=12
damage sends it to LIBRARY through its self replacement, instead of leaving it
on the battlefield. Six separate desired assertions retain the unchanged
protected-control expectation across direct/HTTP/both-seat execution. No alleged
legal damage killing protected Progenitus is used to qualify the clean batch.

Rules 702.16e/j require preventing this damage; 702.12b supports Colossus's
indestructible control. Source `handlers.damage_each_creature_and_player:2271`
uses `deal_damage_batch`; `deal_damage:198-204` checks protection from individual
source colors, but no protection-from-everything check exists there. This is a
source-grounded additional prevention reader gap, NOT repaired or claimed fully
diagnosed for every protection/prevention interaction. That consumer requires
separate review/ownership; no production workaround is in this artifact.

## Preserved Setup Evidence

Two initial whole-36 attempts each reported 24 failures/12 passes: eighteen new
Dreams fixture failures (too few basics; then the mistaken assumption that the
compact fixture retained exiled originals), plus six genuine Wrath publication
reds. They are preserved and not relabeled as gameplay failures. The corrected
size-16 initial36 run reported 20 failures/16 passes: six Wrath timing reds and
fourteen Dreams failures stopping at the real protected-control assertion. That
exact module and raw output remain in evidence. Final fixtures separate the
same protection expectation into six explicit tests and keep the clean timing
matrix independent. No expectation was reversed, skipped or xfailed.

## Minimal Proposed Next Scope, NOT Implemented

After receiving the exact qualified private-ledger executor ABI, each caller
could retain entry payloads while committing the whole cohort, then publish the
complete entry batch once before existing permanent/creature death batches.
Preserve every current preflight, static cause PRE capture, LBF/LKI batch,
counter reset, owner destination and trigger staging/order. Do not query/cache
source abilities across departures or enqueue fabricated library/exile entries.

Request only SBA `_resolve_lethal_creature_batch` and handler
`_destroy_all_permanents_of_types` caller integration, coordinated with their
owners. Executor ledger belongs to Lagrange; events LKI readscope belongs to
Erdos. No events writer or whole-file overlay is proposed. Single/legend/global
SBA simultaneity, other handler batches and static-shuffle interleaving are not
certified by this matrix. The extra protection reader remains a separate ledger.

## Frozen Evidence

New test module plus this report only. Archive includes immutable source input
and product pins, complete command/output/exit ledgers, canonical fixture
provenance, actual full snapshots/collector traces and frontier measurements,
all inherited backend hash checks and AST graph update evidence. NFS readback,
source restoration and tests-only apply-check precede owned scratch cleanup.
Source archives exclude databases, dependency and runtime caches. This remains a
strict-red audit artifact, not a green product integration or deployment.
