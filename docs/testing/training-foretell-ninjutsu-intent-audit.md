# Foretell / Ninjutsu Intent Audit

## Scope And Provenance

Test/report-only audit of source copied from
`/home/nick/.hermes/cache/scratch/mtg-combat-next-composition-OtpupZ`.
The parent root was read-only; no main, parent, live DB, engine, schema,
producer, AI helper or training production file was edited.

The parent's graph report was read first. It is inherited and titled
`mtg-next-backend-milestone-Cc4vy3`, not an independently refreshed OtpupZ
graph. The isolated copy's graph was refreshed after adding tests.

The copy includes 959 backend source/data files, excluding dependencies,
databases, caches and graph artifacts. Parent source manifests before/after
copy and a subsequent read are identical:
`cd52e9d98ed909830361208b2d8d61b57602a8992c662bd8ccdb9b557bf3f05e`.
The copied production files still match that manifest at completion.
The final tested manifest includes the one new test module (960 files), and
its before/after hashes are identical:
`2d853ab583fdbc31eb936d723ee1d540bd30e5f3c3fbd2123dfb4ef1c7112632`.
`backend/training/environment.py` is byte-unchanged, including all 17 existing
guards: `51053fc95f921958af7b2026a5bd87e3c5aaa163590587e08ba3af50ff298bb7`.

## Public Contracts

`backend/api_contracts.py` defines distinct public action types:

- `ForetellAction`: `type='foretell'`, `card_id`.
- `NinjutsuAction`: `type='ninjutsu'`, `card_id`, `return_card_id`.

Both inherit `InputModel(extra='forbid')` through `CardAction` and appear in
the public `Action` union. Neither is in the current `lookup_intent` guard
map. `ai/action_contract.py::complete_action` filters fields to the public
model before validation. That helper was read, not modified.

Actual producers are `rules_engine/foretell.py::action_options`,
`rules_engine/keyword_actions.py::ninjutsu_moves` and `move_generator.py`.
The dispatcher invokes `take_special_action` / `activate_ninjutsu`.

## Foretell Finding

**16 consumer RED, 18 independent controls PASS, 97 warnings, 54.35s; exit 1.**
The entire new 34-case module ran serially with a 900-second bound and fresh
source-local SQLite. No skips, xfails or deselection. External socket
connections were forbidden. This is a diagnostic baseline, not a green
release qualification.

Both seats reject unsupported non-null and null `return_card_id`,
`cost_choice`, `selected_face_index` and `resolving_item` with strict
`lookup` and actual HTTP 422. Each raw rejection preserves full root,
controller snapshot and SQLite dump. The sole consumer rejection assertion
then fails with `DID NOT RAISE`: `lookup_intent` silently discards the same
requested fields. Trial lookup preserves the authoritative root and input
dictionary; it does not execute the unsupported action on that root.

Independent valid controls use the unchanged Doomskar row in
`backend/tests/fixtures/foretell.json`: printed `{3}{W}{W}`, complete Oracle
text, actual foretell `{1}{W}{W}`, no invented Oracle or game card.
Fixture file SHA256:
`dca40879cb924e898a487390f4a541c945930dcdeaa87c44ef02d7ce348d00e2`.
The reused factory omits keywords, so the test hydrates `keywords` directly
from that same canonical row and asserts canonical card-field equality.

Passing controls cover both seats: bare/whole engine and HTTP-view intents;
exact `{2}` payment; retained priority without stack; owner-only face-down
identity and no name leak in log; canonical encode/decode and snapshot
replay; persisted HTTP restart; same-turn casting rejection; deliberate
later-turn `foretell_0` casting/payment and actual Doomskar creature
destruction; insufficient mana, wrong turn/zone, stale/null IDs;
zone-incarnation permission invalidation; actor-input byte equality under
opposing hidden identity/order permutations, and opposing-observer byte
equality under a trusted-copy face-down name perturbation.

The actual engine foretell display adds `card_name`, `mana_cost`,
`fixed_costs`, `granted_reductions`. HTTP adds the actor-authorized
`card_view`. Independent controls verify all engine fields and the canonical
HTTP card view, without stripping the latter to manufacture a valid control.

## Ninjutsu Blocked

No copied backend JSON contains `ninjutsu` or `Ninja of the Deep Hours`.
Existing `test_expanded_keyword_mechanics.py` constructs a Ninja with only
`Ninjutsu {1}{U}` as Oracle text. That is not the requested full canonical
fixture, so it was not used. This is a fixture-availability block in this
source snapshot, not a claim that the engine cannot perform ninjutsu.
No Ninja tests were fabricated or skipped; no ninjutsu execution, cost,
timing, incarnation, privacy or restart qualification is claimed.

## Narrow Proposal Only

Add a `ForetellAction` pre-normalization guard in `lookup_intent`, allowing
only qualified real producer display metadata, and preserving known-model
validation before completion. In particular, reject unsupported fields even
when null, and never derive a requested card/face/cost/context. Qualify actual
whole HTTP `card_view` handling explicitly rather than treating any object as
authoritative input. Keep the existing 17 guards and strict lookup/HTTP
unchanged. Ninjutsu needs a verified complete canonical fixture before its
parallel guard/execution qualification. No production implementation is
included or authorized by this audit.

## Preserved Draft Ledger

- Draft 1: 34 failures / 36.29s at the canonical keyword assertion only;
  not consumer evidence. A preliminary progress inference was corrected.
  Its initial manifest command used the wrong working directory; the saved
  manifest was captured during that run and matched its end, not before it.
- Draft 2: 16 consumer RED plus four test-only integer-key serializer errors;
  14 controls PASS / 51.91s.
- Draft 3: 16 consumer RED plus four exact HTTP-hint comparison errors
  (`card_view` is genuinely added); 14 controls PASS / 55.74s.
- Final: only the 16 sole consumer rejection assertions fail; all 18 controls
  pass. Original draft sources, logs, exits and manifests are retained.

Artifacts exclude local DB/cache files from the integration patch. Archived
SQLite files are closed, isolated diagnostics only, never runtime inputs.
No policy competence, dataset expert provenance or exhaustive action-family
coverage is claimed.
