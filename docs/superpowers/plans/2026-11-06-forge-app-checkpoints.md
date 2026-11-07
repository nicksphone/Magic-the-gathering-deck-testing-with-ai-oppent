# Native App Checkpoints Implementation Plan

> **For agentic workers:** Use test-driven development and scoped independent
> review. Preserve unrelated changes and all existing failure evidence.

**Goal:** Save a native app game at a genuine pending choice, pause its worker,
restart the backend, and explicitly resume the same authorized game through
fresh native tokens only after full checkpoint-frontier verification.

**Architecture:** Reuse the existing GPL-noticed checkpoint store as one shared
backend implementation with an evaluation-path compatibility shim. Private
session metadata binds the capability hash, build, operation fingerprints and
checkpoint generation. The existing lifetime-owned reader replays original
semantic tickets, checks a newly captured frontier, then publishes fresh choices.

**Tech Stack:** Existing Python standard library/FastAPI, React/TypeScript and
unchanged pinned native worker. No new dependency, engine rule or AI policy.

**Spec:** The contract below; user delegated implementation choices. Broader
automatic crash-safe per-action persistence remains required for full adoption,
not silently equated with this explicit-save feature or overall AI completion.

## Contract

- Add `suspended` and `restoring` to the existing status vocabulary. Retain the
  eleven-field public envelope; never expose checkpoints, replay tickets,
  native state, private journals, capability hashes, commands or paths.
- `POST /forge/sessions/{id}/checkpoint` accepts exactly
  `{sequence, request_id, action_id}`. Validate the current pending question and
  version, fence answers, capture/validate the actual native acknowledgement,
  publish a durable private checkpoint, then reap the worker before reporting
  `suspended`. A failed capture preserves the live question and previous save.
- `POST /forge/sessions/{id}/resume` accepts exactly `{sequence, action_id}`.
  Capability and build compatibility are checked before spawning. Repeat
  operation IDs are idempotent; conflicting reuse rejects. A running/restoring
  worker is never duplicated. GET is read-only and never starts/replays a game.
- The browser keeps its existing private session/capability handle. Save is a
  deliberate action; unknown response delivery requires reconnect, not resend.
  Suspended/restoring sessions cannot answer choices. Poll during restoring;
  show a clear last-saved-point warning, not an unsaved-progress guarantee.
- Save original spec/deck text and semantic history, not old wire tokens. During
  recovery choose only unambiguous matching current offered descriptors. Require
  the full saved/current frontier comparison before exposing any new choice.
  Native timing/order exceptions require the existing trusted Java prefix proof.
- Optional operator-only `causal_verifier` argv extends RuntimeConfig; absent
  configuration retains strict comparison. No browser-supplied command/path.
- Keep the original session ID and monotonic sequence across backend restart.
  Persist accepted action fingerprints/receipts so an old duplicate cannot write
  again. Explicit close abandons resurrection; a natural completed result is
  persisted only after a genuine final frame and zero worker exit.
- All private storage stays local, owner-only, bounded, no-follow and atomic.
  Preserve earlier committed saves on I/O failure; mismatches fail closed without
  overwriting the saved checkpoint or releasing a post-prefix answer.
- One manager holds an OS lease for a configured runtime root while it owns
  workers. Another process cannot resume/create against the same root. A backend
  crash releases the lease; existing sandbox parent-death protection is retained.
- Use a new private run directory on resume; never overwrite the original native
  journals. The stable server metadata/checkpoint area is not worker-writable.
- No live service/DB changes, NFS SQLite/runtime use, copied dependencies, public
  generated game traces, forced winner, model deployment or increased native
  game limits. Original failed experiments remain separately recorded.

## Files And Ownership

- Parent: `backend/native_checkpoint_store.py`, original compatibility shim,
  `backend/native_forge_persistence.py`, `backend/native_forge.py`, routes and
  dedicated backend tests; docs and integration qualification.
- Frontend worker: `frontend/src/api/forge.ts`, `ForgeGame.tsx`, minimal scoped
  CSS and NEW `frontend/tests/forge-session-checkpoint.test.mjs`. No backend edits.
- Independent fairness audit: NEW native AI boundary tests/docs only; no overlap.

## Tasks

### 1. Shared Store And Private Repository

- [x] Run the unchanged 121 existing checkpoint/store-prefix tests before moving.
- [x] Retain one implementation and original GPL/Forge notices; make the old
  import path compatible and rerun all original tests without assertion changes.
- [ ] Write failing repository tests for capability/build/schema/size mismatch,
  no-follow/owner-only paths, no-replace generations, atomic metadata, root lease
  and failed-publication preservation; implement and verify.

The existing repository WIP passes all 20 tests. Its original RED history was
not reconstructed in this execution; new manager durability regressions did
run RED/GREEN. Do not substitute a current positive run for that historical step.

### 2. Actual Worker Save And Resume

- [x] Add failing labelled transport tests for save fencing, busy/I/O failures,
  idempotency, shutdown, wrong capability, old saved-action duplicates and restart.
- [x] Reuse the existing wire writer for checkpoint controls without treating
  them as human answers. Capture exact acknowledgement/hash and native frontier.
- [x] Reconstruct with original inputs and fresh tokens; keep public state in
  restoring mode until verified. Test mismatches, stale/superseded choices,
  ambiguous descriptors, nested starts/returns and a lost response.
- [x] Run complete owner/router/store tests and independent lifecycle review.

### 3. App Controls

- [x] Add strict checkpoint/resume methods, statuses and explicit controls with
  RED/GREEN regressions. Preserve all original session tests and legacy fences.
- [x] Test reload, uncertain delivery, malformed responses, reconnected suspended
  state, wrong actor and restored native choice. Run full frontend/lint/build.

### 4. Real Cold App Qualification And Publication

- [ ] Build a fresh isolated app, play real native choices, save after meaningful
  history, close the backend, start a separate backend using the same local save,
  and resume through rendered controls to a natural outcome.
- [ ] Independently verify new JVM, unchanged session/capability/actor, exact
  captured frontier, fresh tokens, no pre-verification answer, genuine outcome,
  source/runtime pins, privacy and full process/DB closure.
- [ ] Preserve failures and protected evidence on verified NFS, update the graph
  AST-only, publish source and verify the actual remote commit. Keep AI goal active.

## Current Evidence Boundary

The seven whole backend modules pass 258 tests, including 25 new synthetic
real-child transport checks. The full frontend package test chain, lint and build
pass. A real native manager smoke proves save/reconstruction/continued input;
it is not a separate backend-process or rendered-browser cold-resume game.
Task 4 therefore remains open. See
[the executed scope and limitations](../../testing/forge-app-checkpoints.md).
