# RC Handoff for Codex

Written 2026-11-15 by Claude (project manager for this push). Repo:
`nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent`. The user has asked me to drive
this to release candidate and to give Codex the work below. Read this whole file first.

## Where things stand (verified, not assumed)

- **PR54 is merged to `main`** as `0ef31940`. Before the merge, its branch CI (run `43672690660`,
  head `42e4a45c`) passed every job. The full backend suite is ~36.9k tests over four shards.
  `main`'s own CI on `0ef3194` is run `43730760816`; check its conclusion before relying on it.
- **PR55** (Battles, deferred upkeep payments) is merged as `e51ddb82` after green run `43751390849`.
  `main` CI on `e51ddb82` is run `43759790245`; check its conclusion before relying on it.
- **PR52** (paid-copy boundary) is merged as `ddd890ec`.
- Closed as superseded or contained in `main`: #5-#14, #46-#51, #53.
- Backend suite results are **local counts only where stated**; CI artifacts are the authority.

## Rules of engagement (do not skip)

1. **No pushes to `main`, no force pushes.** Work on a branch from current `main`, open a PR.
2. **CI is the authority and it is slow (~1h+, sharded).** Failing test names are redacted in
   public logs. Use `gh run download <id> --pattern '*diagnostic*'` for exception type + file:line.
3. **Never print, log or commit private inputs** (`MTG_HEAT_WITNESS`, `MTG_HEAT_REPORT`, the sealed
   witness JSON). Local runs of the heat/legacy tests need them; CI has them.
4. **Source-pinned review gates.** Changing `rules_engine/costs.py`, `keyword_actions.py`, `main.py`,
   `persistence/repository.py` etc. needs a new *layered delta* in
   `backend/tests/fixtures/interface_scope_compatibility/` replayed by
   `backend/tests/interface_scope_compatibility.py`. Do not edit existing pins to make tests pass.
   See `accepted_sacrifice_query_cost_delta.json` and `accepted_pr55_deltas.json` for the pattern.
5. **Never run `rm -f *.lock` in `backend/`** (it deletes the tracked `requirements-py312-linux.lock`).
   Only remove `backend/mtg_lab.db.capacity-owner.lock`.
6. **Honesty rules from `plan.md` stay in force:** no hidden skips or weakened assertions, preserve
   failure ledgers, never describe component passes as release readiness.
7. Report each task as: branch/PR, CI run id, exact pass/fail counts, what remains open.

## RC definition

RC = Gates 1-3 in `plan.md` plus the Completion Checklist in `docs/testing/release-acceptance-status.md`.
AI-STATUS.md is explicit that playing strength is not accepted and has no percentage; do not claim it.

## Work for Codex, in priority order

### P0 - Close the loop on what just merged
1. **Confirm `main` CI is green** on `0ef3194` and record the run id and counts in
   `docs/testing/release-acceptance-status.md` (new dated section, exact counts, no extrapolation).
2. **Independent review of the review-gate deltas** I added (read-only first, then report):
   `accepted_sacrifice_query_cost_delta.json` (commit `cc29147b`) and `accepted_pr55_deltas.json`
   (commit `bb3ebfa3`). Confirm they contain only the intended `costs.py` / `keyword_actions.py`
   changes and that the sacrifice slice in `keyword_actions.py` is untouched.
3. **Review the compat change** in `rules_engine/stack_engine.py`: unannounced stack items
   (`legacy_unknown`) now resolve as spells (restores pre-PR55 behaviour for old snapshots). Look for
   any case where an activated ability's source is wrongly moved off the stack.

### P1 - Gate 1 (reliable local human playtesting)
4. **Gate 1 #4:** malformed / stale / wrong-actor requests across the **new Battles actions**, with
   full state, controller and SQLite equality on rejection, including failed writes.
5. **Gate 1 #5:** refresh, backend restart, ambiguous timeout and manual/autoplay overlap acceptance
   (reconcile before retry; preserve revisions and idempotency).
6. **Gate 1 #7:** clean-checkout run: offline assets, API/runtime contracts, frontend tests, lint,
   build and the browser flow **without developer-only cache files**.
7. **Gate 1 #3:** extend the browser game cohort to cover Battles and deferred-upkeep payments;
   unsupported controls must warn explicitly.

### P2 - Gate 2 (rules, knowledge, AI)
8. **Gate 2 #2/#3:** canonical action goldens for Battles (defense, protector, siege/attack
   routing) through real HTTP/cold SQLite, not just pure modules.
9. **Gate 2 #6/#7:** predeclared seed/seat-balanced archetype matrix with uncertainty intervals,
   timeout and deck-out policy, and first-diverging replay diagnostics. The earlier 110-series run
   was closed and rejected (12 hit resource limits); do not reuse its partial prefix.

### P3 - Gate 3 (packaged release and operations)
10. **Gate 3 #4:** dependency advisory review for frontend and backend; clean installs and checks.
11. **Gate 3 #5:** clean-machine install, offline fallback, backup/restore and saved-game
    reconstruction.
12. **Gate 3 #1/#2:** document and enforce single-user/single-worker limits; HTTPS/LAN routing
    acceptance on a supported topology.
13. **Gate 3 #6:** reconcile README / plan / AI-STATUS with current source, list limitations, record
    changed files, checks, risks. (I will do a first pass on status docs after PR55 lands.)

## What I (Claude) will keep doing

Merging PR52 and PR55 when green, updating the status docs, watching `main` CI, and fixing any CI
failures Codex's PRs surface. Anything needing your private inputs or a human decision I will list
for the user rather than guess.
