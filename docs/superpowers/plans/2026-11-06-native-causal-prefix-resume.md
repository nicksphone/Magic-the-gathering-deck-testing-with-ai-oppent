# Causal Checkpoint-Prefix Resume Plan

**Goal:** Resume the real saved pending choice without discarding a legitimate producer-proven completion inversion or weakening any other checkpoint check.

**Initial evidence:** Checkpoint source `e3d4e309` reconstructed all 186 starts, whole completion rows, native/RNG state, actor view and pending choice. Only completion arrival order differed. The existing `permitted` predicate mechanically accepted the sole pair (53,51); that initial diagnostic was not executed prefix verification or a finished resumed game.

**Approach:** Reuse the existing Java causal verifier through an explicit balanced-prefix mode and a bounded local CLI. The host retains exact equality for every other field and every typed completion row. Only trusted deployment configuration may supply the verifier command; no executable or path is read from checkpoint data. ID sorting and an invented game-final marker are rejected alternatives.

## Invariants

- Existing public full-game constructor, `accept`, `permitted` and `finish` behavior remains strict. A prefix requires zero final rows and cannot certify a game outcome.
- Both checkpoint invocation domains must be closed and complete for order equivalence. Open callbacks retain the original strict-equality path only.
- Validate start order, typed parent edges, entire completion rows, exact stream exhaustion and each displaced pair using the existing producer rule. Do not port or broaden that rule in Python.
- Replay starts remain ordered; replay completion arrivals remain in their actual order. Interleave only as required by declared deferred-parent dependencies, never by sorting IDs.
- The Java proof binds the exact stdin bytes by SHA256 and reports its exact displaced pairs, completed arrival IDs, zero final rows and `game_complete:false`.
- The Python helper stays exact-by-default. Its optional operator-owned absolute argv invokes only the pinned local Java verifier, with no shell, a minimal environment and a timeout. Before invocation it rejects any other frontier or whole-row mismatch; afterward it checks every proof field against its actual inputs.
- No native AI, rules, costs, worker callback, live app, database or protected model changes. Generated game/checkpoint traces remain private.

## Implementation

1. Add a labelled pure Java prefix-contract unit; observe failure against the existing helper. Add a mode-aware private constructor, explicit prefix factory/finish, ordered prefix feeding and bounded stdin CLI to `CausalCompletionVerifier`. Reuse unchanged `accept` and `permitted`; do not fabricate final rows.
2. Add optional trusted `causal_verifier` argv to `checkpoint_store.verify_frontier`, with new pure synthetic transport/negative tests. Preserve all 63 original store tests and 29 client tests unchanged.
3. Compile the explicit public source list. Run the inherited whole 243-case domain, unchanged full causal-protocol units and the new prefix units. Execute the new verifier on the archived order-only witness and reject mutated producer/state controls.
4. On fresh fixed source, save the actual one-of-two-selected Memory Deluge choice, close the original process, reconstruct the prefix in another JVM, verify before any new response, and finish the game. Run the declared uninterrupted reference only after successful resume. Preserve any failure without automatic retry.
5. Verify source/build/resource pins and process closure, archive private evidence to mounted writable NFS with byte readback, update graph/docs and publish. This closes only its observed resume scope, not broad AI quality, every pending callback or application adoption.

## Executed Result

- Existing native regression: 243 passed; all original test bytes and 209 inherited invocation identities retained. Python client/store: 150 passed, including 58 new labelled synthetic transport checks and the unchanged 92.
- Pure Java: 31 prefix, unchanged 60 full causal and unchanged four reply assertions passed. The actual verifier accepted the archived real inversion and rejected altered producer/RNG controls. The mode-confusion failing stage is preserved.
- Fresh actual save/disconnect at 186 starts/returns, cold continuation and uninterrupted reference all met their distinct contracts. The original aborted with EOF; the latter two completed naturally at 236, Ramp win at turn 16. Every captured frontier field matched exactly in this fresh run, so no causal exception was needed there.
- All five complete-game streams plus observations/outcomes/native identity matched the uninterrupted reference. A separate pure adapter used full constructor/accept/finish in actual wire order, not a fake final or prefix-only completion proof.
- Game processes ended and source/runtime pins remained equal. Private trace archives are separate from public source; no live app/database or native AI policy changed. App adoption and broad AI quality remain open.
