# Generated Image Cache Fingerprint Fix

**Goal:** Keep generated card image-index JSON from changing the training engine identity while preserving all existing source coverage outside that exact exception.

**Architecture:** Change only `training/environment.py::_engine_hash` to omit `.json` descendants of exactly the backend's `card_data/image_cache` path. Keep the uncached deterministic path-and-byte digest and every `.py`, including Python under that cache. No schema, dependencies, memoization, activation, old-dataset/model repin or unrelated policy changes.

**Base:** Owned copy of the frozen qualified parent `ci-native-dot-coupled-20261028-umDtGFzz/source` (23a plus native-dot patch5293), not mutable shared source or a preview. Environment preimage SHA-256 is `b3364d125c936adeb7948981bd07c4dff379715ac1d31ea6871a5721b39a0c7a`. Parent alone integrates/commits and supplies the next HEAD/engine. E13 remains prep-only.

## Three Paths

- Modify only `_engine_hash` in `backend/training/environment.py`.
- Add `backend/tests/test_training_engine_cache_fingerprint.py`.
- Add this pre-edit plan/documentation; no other source paths change.

## Execution

- [ ] RED: Run the whole new test module before editing production. Real owned temporary filesystem operations create/edit/delete root and nested generated JSON; only the module's `__file__` is monkeypatched to an explicitly synthetic backend. No live cache, model, database or game fixture.
- [ ] GREEN: Add only the exact-subtree `.json` predicate. All Python there remains fingerprinted. Canonical seed/other JSON, API and other source code, `ai/image_cache`, other same-named directories, and `image_cache_backup` remain fingerprinted. Preserve golden path/byte ordering and uncached edit/restore behavior.
- [ ] Verify with the frozen `a9328ccb` guard, cached F `-I -B`, owned receipt/log/TMP paths, no Torch, SQL, sockets or children. Preserve actual failures, do not widen the guard.
- [ ] Run whole nearest environment, decision-frame/context, multi-run corpus, corpus-byte-budget and Q/V output/source-boundary modules. Do not launch subprocess-dependent dataset CLI tests through a child-denying guard or falsely claim whole-repository qualification.
- [ ] Prove all source bytes/AST outside the one function unchanged, list only the three source deltas, preserve pre/post pins and RED/GREEN receipts, and update a scoped AST graph outside source.
- [ ] Freeze patch/pins for parent review/qualification; no old model retag or live update. The engine changes because its own source changes; fresh committed engine/native data/fit require separate parent admission.

## Limits

Tests establish a synthetic filesystem fingerprint contract, not gameplay quality, cache durability or fitted-model strength. The exception is case-sensitive `.json` under the exact declared subtree, not every directory named `image_cache` and not all files within the cache. No fallback or broad output-tree exclusion is introduced.
