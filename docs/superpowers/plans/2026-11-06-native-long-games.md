# Native Long-Game Boundary Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or
> superpowers:executing-plans. Parent owns commits and runtime composition.

**Goal:** Let legitimate native games continue past global turn 30 without
weakening process ownership, inventing a result or permitting unbounded journals.

**Architecture:** Keep the qualified base and nine AI classes unchanged. Add a
bounded worker overlay with a fresh content-derived profile identity.

**Tech Stack:** Cached JDK 21 compiling Java 17, pinned Forge revision
`61e9442c433711a82258daca3236f936a1d6f70e`, Python 3.12 standard library.

**Spec:** The design, limits and ownership below are the self-contained spec.

**Approach:** Remove only the worker's arbitrary turn cutoff. Replace its
indirect disk-growth restriction with a fixed 512 MiB aggregate UTF-8 journal
budget (536870912 bytes), checked before appending a row. Keep every existing owner, native AI,
input, memory, wall, idle, action, frame and transcript bound unchanged.

The 512 MiB choice is an engineering limit, not a Magic rule or demonstrated
worst-case game size. Prior own session metadata showed 17.4 MiB of journals at
the old turn-31 failure and 5.2 MiB in a completed ten-turn game. This provides
headroom while bounding further journal growth. It is not a global disk quota.
No private game contents belong in public tests or this document.

Raising the cutoff to 80 still truncates plausible ordinary deckout games.
Raising it to 128 remains arbitrary. Removing it without a byte bound would
increase an existing direct-file resource gap: the owner's transcript budget
does not include the worker's journal files.

## Constraints

- Native outcome and balanced causal completion remain the only success path.
- Quota exhaustion marks failure before further append; no win or draw is set.
- Serialize/write each accepted row once; count exact UTF-8 bytes including LF.
- Preserve the old writer's strict rejection of malformed UTF-16. Use a strict
  UTF-8 encoder, not String.getBytes' silent replacement; fail before appending.
- The already synchronized journal method owns one counter across its streams.
- Preserve causal verifier, mismatch diagnostics, replay and checkpoint semantics.
- Do not modify the owner, frontend or unfinished persistence/checkpoint drafts.
- Do not mutate old compiled runtimes, frozen identities or approved bundles.
- Derive a new opt-in profile, retaining the exact qualified base launch.
- Do not push another RC update while the current full CI is running.

## Implementation

- [x] Add `stdio/unit-source/NativeWorkerJournalBudgetTest.java` controls that
   fail on the original worker: observation
   after turn 30, exact byte accounting across streams, UTF-8 and inclusive
   byte-limit boundary, rejection before write, and failed/no-result behavior.
   Counter fault injection is an internal unit check, not a real 512 MiB game.
- [x] Remove the turn clause and enforce the journal budget in
   `tools/engine_evaluation/forge/stdio/NativeHumanWorker.java`.
   Keep every other method and source unchanged where possible. Compile only
   into fresh local output; never replace the qualified base files.
- [x] Independently rebuild and check all six worker class payloads. Compose with
   the unchanged seven-source/nine-class AI prefix, making eight sources and
   fifteen classes. Add explicit profile schema 6 for this exact complete set;
   `native-ai/runtime_profile.py` and `native-ai/test_runtime_profile.py` own
   that explicit admission. All old schemas, launch checks, negative controls
   and atomic publication stay.
- [x] Run worker regression classes and profile boundary tests. Verify source,
   resource bounds, actual loaded origins, no completion after quota failure,
   and owned process closure. Do not equate a unit pose with natural gameplay.
- [x] Qualify a genuine built-UI game progressing beyond turn 30 on that new
   profile, and claim completion only if the native engine actually completes.
   Preserve any incomplete result. Keep the external run bound declared before
   launch; do not raise limits or rerun merely because observation expires.
- [ ] Archive private evidence on mounted writable NFS, verify bytes, update the
   knowledge graph, and publish only reviewed source/tests/notices and aggregate
   results. Native strategy, positive cold saves and BO3 remain separate checks.

## Ownership

Worker implementation and new native controls: Mencius, narrowly scoped.
Profile admission, independent rebuild/composition and app qualification: parent.
Resource/contract review: independent workers, read-only unless reassigned.

These are implementation requirements, not passing results or release approval.
