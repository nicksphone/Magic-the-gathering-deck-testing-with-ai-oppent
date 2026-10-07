# Affected-Player Ordered Resolution Goldens

## Scope / Source

NEW tests, one additional unchanged canonical Moment of Heroism record/provenance, and this report ONLY. Frozen dependency source: `soulscar-preflight-rules-audit/mtg-soulscar-audit-6jcwcP/source-tested.tar.gz`, SHA256 `8a21ea751a4ebb1e526a41d2d8137904b374e978e44c35a543901fbcde14b89d`; parent7f immutable tar pin5723. The previous49 tests and ALL existing backend Python/JSON files are byte-verified unchanged. No prod/schema, handler, replacement, API, events, AI, SQL, browser, main, moving-root or live edits.

Official rule basis remains frozen CR20260925 120.4/614.6/616.1/704.5f and Wizards Soul-Scar rulings (source=wotc). Moment of Heroism's full existing canonical Oracle/metadata is extracted unchanged from `fixtures/defensive_responses.json`, IDb17da4d0-f9fd-43af-85fc-ede9fa3962bf, source hash/provenance included. No new network intake, guessed keywords, Oracle rewriting or fake StackItems.

## Actual Terminal

ONE NEW whole module20: **4PASS/16ordinaryFAIL**,8.80s,exit1, zero errors/skips/xfails. All16 fail at the exact initial `pending_replacement_choice is not None` assertion. This is the existing missing affected-player choice, not16 newly distinct engine bugs. Both seats, two competing paid families (Boon of Safety/shield and Furnace of Rath), each with two order goldens and two genuine damage paths (paid Lightning Bolt; paid Moment of Heroism granting lifelink to Prodigal Pyromancer then its printed paid tap ability).

The first authoring gate is preserved:2PASS/18FAIL,8.28s; its generic NEW paid-spell helper wrongly required a resolving enchantment to reach GRAVEYARD. Furnace setup failed for10 cases, while8 shield desired cases already hit missing-choice. Correcting only the NEW helper's destination by canonical Instant/Sorcery versus permanent types closes that harness mistake. No old49 assertions or product semantics changed.

Four positive controls have NO Soul-Scar source: actual paid Moment grants real lifelink; actual paid shield prevents one-damage tap packet, removes shield, produces zero actual damage/life/event; actual paid Furnace doubles it to2 actual damage,2 life gain and one real damage_dealt event. These controls also pass full snapshot deserialize/serialize equality and immutable checked-action root assertions.

Sockets and ALL sqlite3.connect (memory/file) are rejected by the inherited audit hook BEFORE pytest imports. No new server, socket, DB, dependency install or SQL slot. Space was checked before the gate (above1GiB; actual2.5GiB). No active gate is interrupted for cleanup. No expensive neighbors or repetition of the49 baseline.

## Desired Outcomes (Not Yet Executed Past Blocker)

- Shield + conversion first:3 Bolt/1 Pyromancer -1/-1 counters, shield stays, zero marked damage, lifelink and damage-dealt event.
- Shield first:shield removed, zero counters/marked damage, no further conversion or life/event.
- Furnace + conversion first:3/1 counters, no multiplier after damage ceases to exist, zero lifelink/event.
- Furnace first:affected player must choose again against6/2 remaining damage; used Furnace not offered again; then conversion gives6/2 counters, zero lifelink/event. Six counters reduce canonical Gearhulk toughness to0 and actual SBA must move it to graveyard with exact LKI counters.

Every golden requires a real announced frame with original controller/source/stack ID at initial pre-pop pause, exact full snapshot roundtrip at each reached boundary, no mutation of complete original checked_action roots, rejected wrong-seat/unoffered choice atomicity, legitimate offered choose_replacement only, final zone/tap/counter/life/event and snapshot parity. Post-choice negative/outcome/resume assertions are intentionally present but MASKED by current missing-choice RED; they are NOT claimed qualified. No forged pending state or direct damage shortcut bypasses this blocker. Event observation calls through to actual emit_event; it never fabricates or suppresses events. No emitted damage_dealt event is the damage-trigger prerequisite check, not a claim of every bespoke trigger parser.

## Handoff / Reproduction

Apply this NEW-path increment OVER the existing49 audit dependency, not instead of it; no production patch is included. Use archive evidence/run-pure.py and existing qualified external Python:

```sh
MTG_SOULSCAR_ORDER_RECEIPTS="$OWN_ROOT/evidence/receipts.jsonl" \
 "$PY" "$OWN_ROOT/evidence/run-pure.py" -q tests/test_soulscar_affected_order_goldens.py
```

Report/actual logs/JUnit/first flawed helper ledger/full synthetic snapshots/root source preimages are frozen privately on verified NFS. Read-only candidate callsite plan for Jason is separate `CALLSITE-PLAN.md`; no implementation/schema grant or warning-clear follows. Existing49 baseline ledgers remain immutable and were not rerun/adapted.

Graph report was read before source navigation. Full graph refresh is deferred under the urgent storage/no-new-cache constraint; no graph-current claim or optional extraction/cache workload accompanies this increment.
