# Soul-Scar Mage Preflight / Rules Audit

## Frozen Scope

Tests/report only on `parent-integration/intrinsic-exporter-current-composition-20261007/qualified-source.tar.gz`, SHA256 `5723fdb02e430c0faae056cecf677f708cb605706e373cebc47d44e1a239b327` (parent published 7f1fa9c). No production/source flags, replacement/event/schema edits; no current-main reads, SQL, HTTP server, browser rerun or live actions. The original natural browser remains immutable6c35 and blocked, not current7f browser qualification.

Canonical data: unchanged committed compact Scryfall-backed seed/fixture records with IDs and file hashes in `fixtures/soulscar_consumer_audit/provenance.json`; three complete fresh raw Scryfall records for Boon of Safety, Vampire Nighthawk and Stigma Lasher. Soul-Scar's current raw record matches frozen name, cost, types, full Oracle, P/T and colors; compact seed omits the redundant keyword array, while its Oracle includes Prowess. No invented/shortened Oracle, altered printed stats or named branches. Runtime boards, mana pools, turn/priority and sickness are explicit rules-fixture setup, not natural-game claims.

Current official rule document: https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt (CR120.4,614.6,616.1,704.5f). Wizards-authored card rulings obtained unchanged from https://api.scryfall.com/cards/a8003786-6e2a-4e2d-a915-f23293c7273a/rulings (`source=wotc`,2017-04-18). Direct Gatherer fetch was unavailable; this limitation is not hidden.

## Actual Gates

- NEW original45 module `tests/test_soulscar_preflight_rules_audit.py`: **39PASS/6ordinaryFAIL**, 5.67s, exit1. Frozen unchanged after this run.
- NEW supplemental `tests/test_soulscar_rules_boundaries.py`: **4PASS**, 1.32s, exit0. Combined disjoint NEW cases **43PASS/6FAIL**, not whole green.
- Six WHOLE unchanged neighbor modules: **144PASS/2ordinaryFAIL**, 9.35s, exit1; no skips/exclusions/xfails/adaptations. Modules: `test_resolution_conditions.py`, `test_damage_counter_replacements.py`, `test_damage_replacement_resolution_boundary.py`, `test_expanded_keyword_mechanics.py`, `test_departed_damage_sources.py`, `test_lifelink_gain_events.py`.

The two neighbor failures are `test_resolution_conditions::test_departure_history_resets_at_real_turn_boundary[1/2]`, at deserialize `Invalid phase cursor`. Their fixture manually sets `state.step=PRECOMBAT_MAIN` after running a real cleanup transition, without matching the scheduler cursor. This is separate from the six Soul-Scar replacement-choice REDs; no scheduler/fixture correction is authorized or included.

Every invocation installs a Python audit hook BEFORE pytest imports: reject ALL `sqlite3.connect` (including memory), ALL `socket.*`. A separate self-check proves file and memory SQLite plus socket construction rejected and no DB created. No SQL/network runtime, no servers/PIDs/ports. Public rules/card intake occurred before deny-gated testing. Original backend Python/JSON inventory verifies unchanged after all gates.

## Passing Rules Boundaries

Both seats: genuinely paid Lightning Bolt and Unholy Heat casts via checked_action, real priority/stack resolution, selected own versus opposing creature, snapshot restore, immutable original root; printed Prodigal Pyromancer tap ability with real paid tap and controller retained; zero-toughness SBA death; opposing controller's Mage not applicable; Humility suppresses printed replacement without rewriting Oracle; actual Skullcrack paid cast makes damage unpreventable but conversion still replaces it.

Explicit core-operation controls (NOT claimed printed Nighthawk activation or natural combat): a genuine Vampire Nighthawk noncombat packet credits its actual source controller, gives no lifelink or damage_dealt event when replaced; normal damage gives life and emits damage_dealt. Combat packets remain combat damage in Soul-Scar's presence; real Wither/Infect sources still return damage while making counters. Actual unblocked core combat Nighthawk gives normal lifelink. No blanket Wither/Infect equivalence and no guessed Oracle/StackItem.

## Strict RED / Causal Seams For Jason

1. Both-seat `replacement_options(damage_to_permanent)` offers Furnace of Rath but omits applicable Soul-Scar. `_permanent_damage_candidates` only collects multiplier/reduction/prevention/shield sources; the conversion is segregated into `replace_noncombat_damage_to_creature`.
2. Four genuinely paid Boon of Safety -> deliberate Scry keep -> Lightning Bolt episodes (both seats, with/without restore) retain the shield, put three -1/-1 counters on the opposing creature, and expose NO required affected-player replacement choice. This outcome is legal if that player chooses conversion first, but silently choosing it is not the required CR616.1 deliberate human choice. The strict assertion is missing choice, not incorrectly banning the counter outcome.

`stack_engine.resolve_top_of_stack` asks `replacement_options` and pauses only when >1; because Soul-Scar is absent, shield is the sole offered source. `handlers.deal_damage` then invokes conversion BEFORE `apply_permanent_damage_replacements`/numeric prevention, and the conversion chooser accepts neither selected replacement ID nor prior-used IDs. Merely adding a display option is insufficient: execution must honor each affected-player selected order, used-once tracking, re-evaluation and pause/resume on real frames. Batch damage shares the options seam.

Proposed future GENERIC repair for replacement owner Jason, not implemented: integrate supported source-controlled noncombat event-conversion candidates with the existing affected-player damage replacement protocol and continuation; explicit conversion consumes the event (zero actual damage/trigger/lifelink) but retains counter placement/SBA authority. Multiplier/prevention first must re-evaluate conversion only against remaining damage. Preserve controller/LKI, printed suppression, source incarnation, root/restart and existing counter replacement machinery. No card-name dispatch, parser flag whitelist, fabricated resolving frame or new action schema. Review precise owned files/hunks separately before any grant.

## Read-Only Natural Preflight Diagnosis

Sealed actual response: POST `/simulate/batch/preflight`, HTTP200, `status=exploratory`, `known_unsupported_cards` has five deck-specific rows for three distinct cards. Soul-Scar's `mechanics` are exactly `counter replacement route fidelity` and `unsupported counter replacement clause`; Rift Bolt: `suspend`; Searing Blaze: `controller-linked damage targets`, `conditional land-entry damage`. There are NO numeric warning codes or response version fields. These strings are the actual fields, not invented codes. Source FastAPI metadata version is0.1.0, not an independently captured deployed response version.

Producer route `main.simulate_batch_preflight` -> `_validated_deck_cards` -> `coverage.deck_pair_coverage` -> `known_unsupported_mechanics`. The broad If/counters/instead scanner consults `counter_replacements.counter_modifier`; Soul-Scar's damage-conversion clause is not that counter-amount modifier grammar. This is a classification-routing mismatch, BUT the six genuine ordering REDs show a real remaining semantic gap too. Do not clear the warning solely because isolated damage conversion works.

Historic6c35 browser made ONE preflight POST, ZERO match-start/action POSTs; no warning acknowledgment, match, gameplay or winner. Services/PIDs/ports closed and source inventory unchanged are verified by its sealed REPORT/receipts. Four relevant production files (`coverage.py`, `replacement.py`, `handlers.py`, `stack_engine.py`) match between6c35 and7f by SHA; this narrow equality does not certify the whole current application or transfer browser qualification. No retry or alternative deck.

## Reproduce / Limits

Extract qualified source LOCALLY; apply `integration.patch` (NEW paths only), use existing external `/home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python`. Archive `evidence/run-pure.py` supplies the deny hook; its source path is relative to `OWN_ROOT/source/backend`.

```sh
MTG_SOULSCAR_RECEIPTS="$OWN_ROOT/evidence/replay-receipts.jsonl" \
  "$PY" "$OWN_ROOT/evidence/run-pure.py" -q tests/test_soulscar_preflight_rules_audit.py
"$PY" "$OWN_ROOT/evidence/run-pure.py" -q tests/test_soulscar_rules_boundaries.py
```

No actual HTTP/private API or human ordering completion is certified by these pure tests; no global replacement-order, full Soul-Scar interactions, Wither/Infect library or deck certification. Counter modifiers/prohibition and trigger/lifelink families are bounded controls only. Full future selected-order execution/prevention-trigger interactions need Jason's separately scoped product plus qualification. All ordinary failures/logs/JUnit/receipts and canonical rules/data intake are preserved privately on mounted verified NFS before successful own disposable cleanup.

Graph refresh: AST-only `graphify update .` attempted after all terminal gates with its own30s bound; exit124. Extraction completed but graph finalization is not qualified. Exact log preserved, no optional fullgraph retry or source/SQL changes.
