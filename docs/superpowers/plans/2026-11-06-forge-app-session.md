# Forge App Session Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Preserve unrelated work and the existing live app.

**Goal:** Play a real opt-in Forge game from the existing app's saved deck selectors, with native choices, authorized state, reload reconnection and a genuine result.

**Architecture:** A small Python process owner manages independent Forge sessions. Separate `/forge` routes expose only actor-authorized wire projections, never native journals or Python `LegalMove` conversions. A React panel uses the selected existing decks; Python remains the default and its saved-match identities stay separate.

**Tech Stack:** Existing Python/FastAPI, standard-library process/thread/select handling, React/TypeScript. No new dependency or native engine/rules/AI change.

**Spec:** User delegated implementation choices. The verified prototype and private publication's `APP-INTEGRATION-NEXT.md` define the prior evidence; this plan fixes the app-facing contract.

## Global Constraints

- Linux first; runtime disabled unless operator supplies `MTG_FORGE_RUNTIME_CONFIG`. Never accept argv, paths, actor IDs or engine state from browser input.
- Runtime JSON has `argv` (absolute executable/list, `{session}` substitutions), `cwd`, `sessions_dir` (local private storage), `build_id` (64 hex). Operator supplies/pins the existing qualified engine; no downloads or installation on a request.
- First app slice is one human/native-AI single game, exact 60-card mains, empty runtime sideboards, open decklists; stored sideboards remain untouched and unused. Label this explicitly. BO3, cold app restore and full callback/AI fairness remain requirements, not claimed here.
- Preserve legacy routes, saves and live services. Do not execute SQLite on NFS or publish generated game/hand/RNG traces.
- Native `started` is not action acceptance and `completion` is not a cast receipt. Publish answer processing status without inferring a successful game action.

## Interfaces

`backend/native_forge.py` owns `RuntimeConfig.from_file(path)`, `ForgeManager(config_or_none)`, `ForgeManager.from_environment()`, `ForgeError(status_code, code, message)`.

Manager methods: `create(payload: dict, capability: str, key: str)`, `get(session_id, capability)`, `answer(session_id, capability, payload: dict)`, `close(session_id, capability)` return detached snapshots; `close_all()` shuts down owned children; `available` is boolean. Tests may construct a config pointing at an explicitly labelled synthetic transport process, not a fake native game qualification.

Snapshots have exactly `engine:"forge"`, `session_id`, monotonic `sequence`, `status` (`starting|running|completed|aborted|failed`), nullable `actor_id`, nullable `state`, nullable `question`, `info`, nullable `last_answer`, nullable `result`, nullable `error`. State and question use the existing ActorBoundary schema. `last_answer` has `action_id,request_id,status` (`submitted|processing|processed|rejected|uncertain`), nullable `reason`. Result has `outcomes,turns,draw,win_condition`.

- Bearer capability: client-generated random 32-byte lower-hex, retained privately in browser storage; server compares hashes and never logs/echoes it. Start also requires bounded `Idempotency-Key`; same key/capability/body resolves the same session, conflicting body rejects.
- Start payload: `deck_a,deck_b` lists of `{quantity,card_name}`, `name_a,name_b`, `human_seat:0|1`, optional integer `seed`. Aggregate duplicates, require exactly 60 per main and reject name line/section injection before launching. Native engine still verifies imported identities.
- Answer payload: `request_id`, ordered `tokens`, current `sequence`, bounded `action_id`. Validate actual current offered tokens/bounds/uniqueness. Duplicate action returns its receipt without another pipe write; conflict rejects. Never resend automatically after uncertain writes.
- Public endpoints: `GET /forge/status`; `POST /forge/sessions`; `GET /forge/sessions/{id}`; `POST /forge/sessions/{id}/answer`; `DELETE /forge/sessions/{id}`. Protected operations use Authorization, start uses Idempotency-Key. No-store responses. Wrong capability cannot read or mutate a session.
- Only choice/state/result/error projections cross HTTP. Keep choice's own state coherent while views arrive; do not combine a previous question with a later state. Strip replay offers, native journals, provenance, stdout and paths. Bind state/question actor to the process's original actor.
- Track native started/completion IDs internally, allowing nested dialogs while a parent callback remains open. A fresh question may precede the parent's return. EOF/result exit must agree before declaring completion.
- Use private per-session directories, bounded frames/transcripts and at most two live workers. Idle/wall closure and app shutdown must reap process groups, close pipes/files and join readers. Reads never write stdin.

## Review Focus

- Lost start/answer HTTP response must reconnect or retrieve the same receipt, not create/send twice.
- New choice during a still-running parent callback must remain usable; stale rejection must not remove a newer question.
- Browser reload and React StrictMode must not create or abort another worker.
- Native activation must stop legacy autoplay/manual writes and use a separate storage namespace.
- Malformed output, partial lines, unexpected EOF, nonzero exit and shutdown must fail closed without leaked processes or hidden state.

## Tasks

### 1. Process Owner

- [x] Write failing pure transport tests in `backend/tests/test_native_forge.py` for capabilities, start/action idempotency, native-only projections, nested receipts, malformed output and closure.
- [x] Implement `backend/native_forge.py` with the interfaces above, using standard-library processes and one bounded reader per live child.
- [x] Run the complete new module, retain RED/GREEN evidence and review process closure. No main import/SQL/live HTTP in this task.

### 2. HTTP And Legacy Isolation

- [x] Write failing router tests in `backend/tests/test_forge_routes.py`, using an isolated FastAPI app and injected manager; no main lifespan or SQLite.
- [x] Implement `backend/forge_routes.py` with strict public models and manager dependency injection. Include router in `main.py`; lazy-configure one manager and close it at existing app shutdown.
- [x] Verify exact payload/auth/no-store/error boundaries and absence of legacy match mutations.

### 3. App Native Board And Choices

- [x] Add `frontend/src/api/forge.ts`, strict response parsing and transport tests; no capability in URLs/logs.
- [x] Add `ForgeGame.tsx` and scoped CSS using existing visual patterns, native board/stack, explicit native choice/selection/order controls, result/error/reconnect/close. Use `mtg.forge.*`, not `mtg.activeMatch`.
- [x] Modify `App.tsx` minimally: selected decks/human seat feed native panel, native active ref gates legacy timers and mutations, existing Python board is hidden while native is active. Do not edit legacy action contracts.
- [x] Run new checks, original affected frontend tests, full lint/build and browser interaction.

### 4. Real Vertical Qualification

- [x] In a fresh isolated owned app/runtime, use the exact frozen Java worker, current new process owner/routes and selected saved decks; no live service/database change.
- [x] Submit genuine opening/card/dialog choices through HTTP and built UI, verify native state changes, reload reconnect to the same session, wrong capability/stale/duplicate rejection and actual native outcome.
- [x] Verify source/runtime pins, native/frame privacy, no duplicate actions/processes and complete shutdown. Record any failure honestly; do not force results or enlarge native budgets.
- [x] Archive private evidence on verified mounted NFS with byte readback, update graph/docs/status and publish source. Overall AI goal remains active.

## Executed Acceptance

See [the app-session qualification](../../testing/forge-app-session.md). The
corrected-source game completed naturally on turn 20 through 433 accepted UI
answers in 225.84 seconds, within the unchanged 240-second bound. Native exit,
the rendered result, same-session reload, negative protocol purity and closure
were independently checked. Owner 63/router 12/frontend-native 35 and full
frontend test/lint/build passed. Earlier setup, audit, stale-driver and native
lifetime failures remain separate private evidence, not relabelled passes.

This completes this single-game implementation plan, not the persistent AI goal,
native BO3, cold app recovery, general choice coverage or RC qualification.
