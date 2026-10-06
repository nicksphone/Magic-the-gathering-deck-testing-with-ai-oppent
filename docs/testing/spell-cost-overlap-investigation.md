# Spell-Cost Reservation Overlaps

## Parent Candidate Follow-Up

The isolated parent candidate now reserves the announced spell ID alongside
selected fixed additional-cost cards and escape payments. Shared planning and
payment replay preserve the source too; explicit and automatic delve respect
consumption reservations without forbidding convoke/improvise taps. The latest
core/neighbor gate passes 230 cases with only two known mana-created escape-fuel
gaps expected to fail. Four HTTP cases run separately in an empty-database source
copy all pass, returning 422 with complete state/database invariance. The former
source-consumption and four delve-reservation expected failures are ordinary
passing tests, not excluded. Joint fixed additional-cost availability is separate
follow-up work; this is not a live deployment or unrestricted rules certification.

The investigation below records the original frozen baseline, not current
parent-candidate behavior. Its archived hashes and failure evidence remain intact.

Investigation only. Own NEW tests/fixtures/report on isolated `d88dbf0`.
No engine, costs, mana, AI, importer, model, or main checkout edits.

## Qualified Source

Tests execute on a separate LOCAL extraction of `d88dbf0` overlaid with the
parent's already-reviewed source archive, not by changing the investigator's
tracked engine files. Parent artifact:
`parent-integration/spell-reservations-d88dbf0/qualified-source.tar.gz`,
SHA256 `31c4e7dd8f135bdf874f7365f642a93ab05587cadda062e2cb3b296f976db3bd`.
The associated `engine-spell-reservation.patch` SHA256 is
`732707f6b014f4f8890bdf1690cdb3a45030412a699d4f4185cab9a6d3c42925`.

| Module | Qualified SHA256 |
| --- | --- |
| `rules_engine/engine.py` | `81147c80bd2520f937d60f620bca0b61e45c4a3b5e1ef92f1ff7370d5a83b3d0` |
| `rules_engine/costs.py` | `c477f674881bd92e76114e1e086c89af31670b34651ae65d0195336c7dd39302` |
| `rules_engine/mana.py` | `73633dcfdd4c9ffc1429d61a7b65849fa9e09a59d5778e563d4934a42476f1b8` |
| `rules_engine/mana_abilities.py` | `aa5bac623e5d6c2a286110447725807e89b2aeaf4402b0e5d8ee8508f61189e8` |
| `rules_engine/mana_triggers.py` | `23c189cccd020271af113575f9bcaa98a51e928dc3741d2315aea6f54786ffdd` |

Parent's 550 serial checks are prior evidence, not a test count claimed for this
investigation. The archived source includes Sagan's executor and parent's
subtype-cost dependency as well as the reservation fix.

## Findings

### P1: Casting Source Remains Consumable For Mana

Canonical Village Rites, Skirge Familiar, and Raging Goblin: Familiar and Goblin
on the actor's battlefield, Village Rites as the only hand card, zero mana.
Announce Goblin as Village Rites's additional sacrifice. The parent reservation
set preserves Goblin but omits the announced Village Rites. Automatic Familiar
payment discards Village Rites itself for B; the cast then reaches
`engine.py:1099` and raises plain `ValueError` removing an absent hand ID.

Canonical Tormenting Voice gives the same result: actor has R, Familiar,
Tormenting Voice, and an Island selected as the additional discard. That Island
is protected, but Tormenting Voice itself is consumed for generic mana.

Both seats reproduce both cases. `checked_action` leaves the complete root
snapshot unchanged because payment runs on a copy. Safe memory-DB ASGI tests
return HTTP **500**, not the application's expected `422 illegal_action`.
Controller state, revision/receipts, full persisted database dump, and original
spell-in-hand identity remain unchanged. This is a controlled-rejection bug,
not evidence of a successful double cast or live database corruption.

Generic proposal for parent: make the announced source unavailable to consuming
mana abilities at every casting payment boundary, including availability
witnesses. Correct announcement-zone staging is the broader solution. Do not
globally catch every ValueError or add named-card exceptions. Explicitly passing
source plus selected-cost reservations into `auto_pay_cost` correctly rejects
these impossible payments; a separate disjoint fuel card makes the casts work.

### P2: Native Escape Cannot See Mana-Created Fuel

Canonical Woe Strider in the graveyard, three other Island cards there, Tower
and Goblin on battlefield, and three C in pool. Tower can sacrifice Goblin for
BB, creating the fourth other graveyard card before escape payment. An automatic
escape request is rejected as not currently legal. Explicitly activating Tower
first, then escaping using the three Islands plus that Goblin, succeeds.

The pre-mana count gate is `costs.py:463`; escape IDs are also validated before
mana in `engine.py`. Root purity holds for the refused automatic request and
the explicit preparation control. This is an automatic-payment/eligibility
limitation with a legal manual workaround, not an assertion that Woe Strider
can never escape or that a supplied currently-invalid exile ID is valid.

Generic proposal: planning must produce a post-mana resource witness before
validating payments that can use resources created by those mana abilities.
Keep explicit resource announcements versioned and fail closed; do not silently
replace caller selections. This needs a joint phase-aware cost model, not a
Woe Strider exception or unconditional relaxation of the graveyard count gate.

### P2 Contract: External Delve Reservations Are Dropped

For canonical Treasure Cruise, actor has U and seven Island graveyard cards.
Mark one graveyard card externally reserved. The low-level `resource_payment`
correctly refuses using it; `_spell_payment_plan` still returns a witness using
all seven cards, for both explicit and automatic delve. Reservation forwarding
only reaches the physical mana callback at `mana.py:616`; the substitution
search call at `mana.py:620` does not forward them to
`casting_resources.py:150` or `casting_resources.py:167`.

This is a pure planner contract reproduction, not a fabricated native
escape-plus-delve spell. Canonical Underworld Breach plus graveyard Treasure
Cruise is a rules-valid route to that overlap, but this qualified engine does
not admit Breach's granted escape at all. Its empty cost options are recorded
as an unsupported prerequisite; no Oracle text or keywords are altered to
force the composite cast through the engine.

Generic proposal for parent/Sagan: propagate consumption reservations through
both explicit validation and automatic substitution search. Separate forbidden
zone changes from forbidden taps; simply forwarding every sacrifice reservation
as a blanket no-touch set risks disallowing legal tap-then-sacrifice payments.
Qualify Breach's generic grant separately before claiming an all-cost cast fix.

## Controls And Timing Boundary

Crop Rotation's selected Forest can provide G by tapping, then be sacrificed;
both explicit and implicit selections pass. Reservations must prevent consuming
a fixed victim twice, not prevent all use of its mana ability.

Kaervek's Spite's exhaustive costs are correctly recomputed after mana. Tower
sacrifices Goblin for BB and Swamp supplies B; the additional sacrifice pays
only the remaining Tower/Swamp, not the already-departed Goblin. Familiar can
discard three distinct Island fuel cards for BBB, then Spite discards the
remaining Forest and sacrifices Familiar. Explicit subsets for exhaustive
discard/sacrifice are rejected. Sources are appended last in these controls to
avoid the separately reproduced source-consumption bug; hand order is legal
fixture state, not a card-data rewrite.

With four pre-existing Island escape cards, Woe Strider pays those exiles while
Tower's sacrificed Goblin remains in the graveyard. Their destinations and
complete original roots are checked independently.

Crypt of Agadeem counts the escaping black creature while it remains in the
graveyard before announcement. A copy with that source moved to STACK has one
less black creature for Crypt. Escape fuel itself may legitimately be counted
for mana before being exiled. This is an announcement-view timing boundary,
**not** a claim that every observed auto-cast is illegal: activating Crypt
before announcing Woe Strider can be a valid separate sequence. No production
fix or blanket exclusion of reserved-but-not-yet-exiled graveyard cards follows
from this observation alone.

Deathrite Shaman's instruction targets a graveyard card and is not an automatic
mana ability in this engine. It is not used as a fake targetless exile-cost
source to manufacture a reservation bug.

## Canonical And Rules Provenance

The NEW fixture holds 27 unchanged raw Scryfall records extracted from the
already-qualified September 27 public Oracle bulk. Its compressed source hash
is `17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13`.
The extractor verifies that digest, scans all 38,690 JSONL records with a 2 MiB
line cap and 1 GiB total decompressed cap, and emits only the selected records.
`provenance.json` pins archive identity/date, every Scryfall/Oracle identity and
raw canonical hash, and the resulting fixture hash. Hashes identify retained
source bytes, not publisher authentication or live freshness. No HTTP request
was made and no shared bulk archive was deleted or copied into the patch.

Crypt reuses unchanged `fixtures/mana_abilities.json`, SHA256
`5816392ac61f204eb9e059e36aecc47a11a6e7b8977bce4f33eec0ef3b38b3d1`,
Oracle ID `4fe8af73-c84a-44bd-9739-ee5c8b027874`. No other source fixture is
overwritten by the NEW fixture loader. Partial test positions use real printed
card characteristics; these are not submitted competitive decks or AI scores.

Rules are checked against the previously downloaded, hash-verified
[official September 25, 2026 CR](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
SHA256 `8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`.
CR 601.2a places the announced card on the stack before mana production;
601.2g permits mana activation before total-cost payment; 601.2h requires full
payment and permits ordering nonrandom costs. CR 702.66a-b permits delve only
against generic mana in the locked cost; 702.138a defines escape. CR 605.1a
excludes targeted activations from mana-ability status. These references support
the test boundaries, not universal engine or trained-competence certification.

## Execution

Core: 31 controls pass, 10 strict known-gap xfails (4 source, 2 escape fuel,
4 reservation-forwarding). `--runxfail` independently produces exactly those
10 failures and 31 passes; they are not counted as successful mechanics.
Optional ASGI: four expected source-overlap failures, status 500 and full
root/controller/DB invariance independently recorded. Defaults skip HTTP.

The guarded core gate combines the NEW core tests with existing
`test_cast_resource_payments.py`: **94 passed, 10 xfailed**. Python audit hooks
deny all SQLite and socket connections; no forbidden attempt occurred.
The separate guarded HTTP `--runxfail` gate produces exactly four status
assertion failures, verifies all four independent invariance receipts, permits
only `:memory:` SQLite, and denies network connections. These expected failures
are not successful mechanics or successful HTTP handling.

An earlier broader collection could not import the parent test dependency
`tests.test_produced_type_mana`, which is absent from both d88 HEAD and the
qualified-source bundle. That run collected no usable gate result and is
retained in the evidence. No missing helper was invented or taken from an
unqualified moving checkout; the parent's prior 550-pass claim is not rerun here.

```sh
# In a fresh LOCAL source tree with the pinned parent source composition:
PYTHONPATH=backend /path/to/external/.venv/bin/python -m pytest -q \
  backend/tests/test_spell_cost_overlap_investigation.py

MTG_COST_OVERLAP_HTTP=1 MTG_COST_OVERLAP_ROOT="$PWD/backend" \
  PYTHONPATH=backend /path/to/external/.venv/bin/python -m pytest -q \
  backend/tests/test_spell_cost_overlap_http_investigation.py
```

HTTP refuses an existing default `mtg_lab.db`, requires an explicitly approved
isolated source root, and redirects both persistence and main engines to a
fresh in-memory SQLite engine before lifespan. Startup seeding/restoration is
disabled in the NEW test fixture. No network server, paid call, private data
submission, live SQLite open, NFS SQLite open, or production deployment occurs.
All root snapshots include RNG, logs, cards, payments, and pending state.

Strict XPASS is intentional: remove/requalify the corresponding known-gap mark
only after parent/Sagan fixes the generic boundary and audits the control cases.
No existing production or shared test modules are changed by this handoff.
