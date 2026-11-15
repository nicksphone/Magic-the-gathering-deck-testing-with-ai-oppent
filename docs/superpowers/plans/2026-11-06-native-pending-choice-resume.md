# Native Pending-Choice Resume Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or subagent-driven-development. Retain failing checks and actual outcomes.

**Goal:** Preserve a native human/AI session through a process restart at an unresolved choice, then continue genuine native play without losing selected cards, costs or provenance.

**Architecture:** Capture a private, atomic checkpoint at the actual current native question. A trusted host replays its accepted-choice prefix into the same pinned engine and compares the complete captured frontier before releasing any new response. Existing complete-reference replay and causal validation remain unchanged. This is not Java heap serialization or replacement of old Python saves.

**Tech Stack:** Existing Java 17-targeted Forge adapter, cached JDK/dependencies, Python standard library.

## Design And Constraints

- The user delegated implementation choices. Replay reconstruction is the selected approach; in-memory undo is not durable, and arbitrary Java object serialization is not a supported existing interface.
- Add the separate strict local command `{"checkpoint_request_id":"CURRENT_REQUEST"}`. It neither answers nor invalidates the human choice. Legacy answer parsing remains strict and unchanged.
- Only a live, current, unresolved native question may be captured. Stale, terminal, failed, aborted and replaced-input requests reject without a checkpoint or action.
- Write `CHECKPOINT.json` atomically and privately in the host-owned session directory. Its complete schema is `schema`, `spec`, `decks`, `starts`, `completions`, `pending_offer`, `actor_view`, `native_state`, `journals`.
- `schema` is integer 1; `decks` maps the imported deck basenames to their exact initial text. The five journal keys are `starts`, `completions`, `native`, `paid-pending`, `final`. An unfinished checkpoint has an empty final stream.
- Capture genuine native physical/mana/stack/RNG state and the actor-filtered view, not just a board image. Keep full private data out of wire frames, GitHub and public fixtures.
- The host archive pins a trusted deployment build ID (64 lowercase hexadecimal characters), checkpoint bytes, match spec and decks. It is local-host data, not a browser upload/command interface or automatic engine installation.
- Fresh restore uses fresh opaque tokens from actual offered choices. Only prefix-equal accepted tickets may replay; after all retained starts, compare the entire checkpoint frontier before new user play.
- No native AI, card rules, budgets, costs, existing causal/full-reference verifier, live service, database or saved-match changes.
- A successful pending-choice experiment is not broad resume coverage, app integration or AI release acceptance.

## Review Focus

- Save after selecting one of two required cards: preserve the first choice and require only the second on restore.
- Changed engine identity, actor, RNG, mana, selected objects, truncated journals and altered checkpoint bytes must fail closed.
- Capture must not consume existing tokens, dispatch a callback or advance native play.
- Preserve genuine paid/pending native costs; no replayed response may be sent twice.
- Save/restore metadata and generated game traces stay private; original tests and old archives remain immutable.

## Task 1: Native Checkpoint Boundary

**Files:** `tools/engine_evaluation/forge/stdio/NativeHumanWorker.java`, new `stdio/unit-source/NativeWorkerCheckpointTest.java`, explicit build manifest/count.

- [x] Add failing strict-command and genuine native-question checkpoint units; run against the unchanged worker.
- [x] Capture initial spec/deck text and implement the strict checkpoint command, current-question validation and atomic private state/journal snapshot.
- [x] Verify capture leaves the question and native state unchanged, and invalid requests produce no snapshot.
- [x] Run the inherited domain with the new units: final 243 cases in thirteen whole classes, zero failures/skips; 28 loaded payload pins. Three additional race/I/O failures were reproduced and corrected. Four standalone protocol checks preserve the busy/legacy distinction.

## Task 2: Private Host Checkpoint Store

**Files:** new `stdio/checkpoint_store.py` and `stdio/tests/test_checkpoint_store.py`.

- [x] Write and observe failing labelled synthetic format/boundary tests: 63 failures before implementation.
- [x] Implement `save_checkpoint(snapshot_path, destination, *, build_id)`, `load_checkpoint(directory, *, build_id)`, `restore_inputs(checkpoint, destination)` and `verify_frontier(saved, current)` using only the standard library.
- [x] Enforce fresh private destinations, exact schemas/counts, safe imported basenames, byte hashes, pinned build ID and complete frontier equality. Restore only spec/deck inputs, never opaque tokens or executable commands.
- [x] Run the complete new unit module plus unchanged client protocol checks: 92 passed. Atomic fresh-directory publication uses Linux `renameat2` via `ctypes`, without a weaker fallback.

## Task 3: Actual Cold Reconstruction

- [x] On fresh current-source native Control/Ramp play, save a real two-of-four choice after its first selected card, then close the original process without inventing a game outcome: 186 balanced invocations, explicit abort/exit 2.
- [ ] Start a separate current-build JVM, replay only retained accepted choices with fresh native tokens, capture the recovered frontier and compare complete private state and journals.
- [ ] Only after a match, continue the remaining native choice and game to an actual outcome. Keep any mismatch strict and preserve its evidence.
- [ ] Verify process closure and immutable inputs, archive private evidence to verified writable NFS with byte readback, refresh the code graph and publish source/tests plus precise limits.

## Actual Continuation Blocker

The fresh process reconstructed the same pending offer, actor view, native-state
projection, spec, decks, accepted starts and native/RNG/paid-pending rows. Whole
completion rows match by start ID, but arrival order differs. Strict verification
stopped the resumed process before any new choice; the third JVM was not started.
This is not qualified resume support. Next, use the existing narrowly reviewed
producer/parent causal rule to prove any permitted inversion. Do not sort away
differences, discard row fields, manufacture a final outcome or relax other state
checks. Existing full-reference replay must remain strict and regression-tested.
