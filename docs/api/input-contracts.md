# External input contracts

Public models live in `backend/api_contracts.py`. Mainboard entries are names and strict positive integer quantities, not arbitrary Oracle/effect definitions. Normal boards contain 60-250 cards; `sandbox: true` permits 1-250, never empty. The 250 ceiling limits application resources; it is not a general Magic maximum. Sideboards have at most 15 cards. Start and batch admission require usable cached/canonical card metadata. Metadata lookup may update the cache even if a later deck fails admission.

## Actions and errors

`POST /matches/{id}/action` requires `player_id` (1 or 2) and a discriminated `action`:

- Priority: `pass_priority`.
- Pregame: `mulligan`, `keep_hand` with exact `bottom_card_ids` after mulligans, ordered bottom-most first. Seven mulligans produce a zero-card opening hand; another is rejected.
- Cards: `play_land`, `cast_spell`, `cycle_card`.
- Permanents: `activate_ability`, `activate_loyalty`, `crew`, `ninjutsu`, `equip`.
- Mana: `tap_land_for_mana`, `tap_lands_bulk`.
- Combat: `attack`, `block` (blocker IDs are lists per attacker).
- Choices: `choose_mechanic`, `choose_replacement`, `choose_trigger_order`.

Use the current legal-move response for source, actor, ability indices, face/cost choices and selection candidates. Supported targeted human actions must explicitly announce targets/modes instead of relying on internal automated defaults. Ordinary permanent spells do not target with their later activated/triggered text; supported Auras require attachment targets. This does not certify permanent effect/trigger resolution timing. Divided damage uses a rules-derived fixed/X budget and positive shares for selected recipients; clients cannot override effect amounts. Internal effect fields and unknown input keys are forbidden. Combat damage is progressed by the engine, not a public action.

Malformed schemas return FastAPI 422 validation details. Rejected legality requests return 422 with `detail.code = illegal_action` and a human-readable message. Missing card metadata returns `card_data_unavailable`; manual requests for an AI seat return 403 `ai_controlled_seat`. Frontend error parsing handles both schema and domain responses.

## Mutation guarantees and limits

`checked_action` deep-copies authoritative state before legality helpers and engine execution. Invalid targets, costs and declarations discard that copy. Regression tests compare complete game/controller snapshots and database contents after rejected action requests. Local per-match reentrant locks serialize relevant reads/writes, including autoplay and sideboarding, in one process.

Match mutation endpoints commit history and snapshots in one repository transaction, holding the per-match lock until commit. Exceptions restore copied controller/game/AI state; SQL storage errors produce structured 503 responses. Revisions and the latest 100 write-key fingerprints are stored with the snapshot. Guarded clients supply `X-Match-Revision` and `Idempotency-Key` together; stale revisions and reused keys with different operations return 409. A matching retry returns current authoritative state without rerunning the operation, including after restore. Headerless legacy calls remain allowed but have no stale-version protection.

The frontend coordinates manual/autoplay/response-window writes, ignores incomplete mismatched state/legal reads and reconciles a failed/uncertain write via GET before another action. Restore/error pauses automatic play. This is not a distributed transaction or a guarantee for unguarded external callers. New-match creation idempotency, multiworker operation and public network exposure remain unsupported. Successful HTTP JSON still needs runtime contract validation. See [recovery browser checks](../testing/match-recovery.md).

Target semantics remain bounded by supported Oracle inference. Controller-qualified/multi-role targets, full crew stack timing and variable activated mana costs need further fixtures/implementation. Internal AI execution retains legacy defaults; checked human execution is not proof of complete AI legality.

## Extending the contract

Add a discriminated model, validate its selection/actor/cost rules in `rules_engine/action_validation.py`, and implement reusable engine behavior. Add rejected-request state-preservation tests and positive HTTP/component tests, then update the typed UI renderer. Never accept caller-supplied internal effect parameters to work around a missing mechanic.

Validation: 822 isolated backend tests, frontend error/gate/key assertions, production build, six component/HTTP action paths and App recovery checks passed on 2026-09-27. The validation milestone's two-game BO3 smoke has no timeout/drift. This is not a full browser game, broad balance study or universal rules certificate.
