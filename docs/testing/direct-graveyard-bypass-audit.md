# Bounded direct-graveyard bypass audit

This is a strict tests/report-only diagnostic, NOT a green release gate or a
production migration. Baseline is the readonly source copy of
`/tmp/mtg-static-current-compose-jry07R`, pinned before/copy/after. Production,
combat, live, moving parent, costs/parser/planner and event consumers are untouched.

## Two families

1. `effects/handlers.py`: actual canonical Wrath of God paid casts (untargeted)
   against Progenitus; actual canonical Lightning Bolt lethal damage against
   Doomed Traveler. Wrath/Murder against unsuppressed Darksteel Colossus preserve
   indestructibility; Murder against unsuppressed Progenitus rejects targeting.
2. `rules_engine/keyword_actions.py::finish_mechanic_choice`: real resolver on
   canonical Kozilek's annihilator-4 ability sets a pending sacrifice. This is a
   TRUSTED pending-trigger position, NOT a natural attack or combat qualification.
   Actual HTTP exercises selection of that existing pending choice only.

Retained foreign ownership boards are trusted setups, not naturally played
control-changing spells. Full raw official objects remain unchanged. Existing
5a74-derived self-graveyard fixtures remain unchanged and exact relevant objects
are independently selected from their same pinned full official bulk.

## Current strict results

94 cases: 54 PASS, 40 ordinary FAIL; 394 warnings; 19.36 seconds. No xfail, skip,
deselection or weakened desired assertions. Six whole neighboring modules:
255 PASS, 1042 warnings, 54.96 seconds. Neighbor scope is recorded in evidence.

The 54 passes include 8 observation-only recordings, NOT rules acceptances.
The 40 failures retain owner-library, real static shuffle cause, false death,
source zone sequence, competing replacement and HTTP persisted-state assertions.
No claim that every assertion after a first failed assertion executed.

HTTP runs actual application ASGI routes, owned memory/file SQLite repositories,
real paid casts and two real priority-pass requests. No invented HTTP replies or
production cold-cache fallback. Cold GET reloads through the real API using the
same owned engine as the write dependency. Snapshot continuation also roundtrips
in a separate Python process; this is NOT a restarted Uvicorn/HTTP server claim.
Invalid actor and duplicate selections preserve full root/controller/SQLite dump.
Private opponent decision views retain unknown own hand/library identities.

## Narrow proposal, not implemented

Reuse existing `graveyard_entry_plans` / `select_graveyard_entry_plan`,
`prepare_graveyard_entry_causes`, and `execute_graveyard_entry` rather than making
`replace_die_zone` return library to old grave/exile-only consumers.

For mechanic sacrifice, preflight the complete selected batch and prepare real
replacement causes before LBF; execute those retained plans after LBF, preserve
sacrifice events, emit dies only for actual graveyard destinations, finish the
existing paused stack item exactly once. No Ninjutsu/entry or API edits proposed.

For destruction/damage consumers, retain prevention/indestructible/protection
checks and simultaneous eligibility/LKI capture. Preflight actual destinations
before departures, execute the same plans after LBF, and filter real dies. Any
broader handler migration, replacement-choice UI, combat or schema changes need
separate ownership. No broad graveyard support claim.

## Retained harness failures

First collection failed because the copy filter accidentally excluded canonical
`.jsonl` fixtures. Restored all 13 inherited canonical fixture files with exact
before/copy/end hashes. Second attempt mixed real Wrath failures with two NEW
harness errors: paused annihilator returns False; cold GET needs owned main.engine
binding because it has no repo argument. Corrected only NEW harness code. Those
ledgers remain archived, not counted as product failures or qualification.
