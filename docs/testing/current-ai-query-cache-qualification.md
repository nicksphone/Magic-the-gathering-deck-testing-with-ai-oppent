# Current query-cache qualification

The six-path query-cache increment was qualified on published
`2f7a55599773f97f7c57d9b5965b365ef55bf615` before integration. The subsequent
documentation and shutdown-fixture commits did not change these production
preimages. All six integrated postimages match the qualified source.

- Seven whole query/cache/destruction modules: 108 passed, 3 warnings, 10.14s.
- Four whole attached-characteristic, predicate, suppression and Changeling
  modules: 121 passed, 3 warnings, 10.79s.
- These are separate cohorts, not a summed whole-suite result.
- Native guards recorded no unexpected SQL, socket or subprocess activity;
  original source inputs were unchanged during both gates.

Only immutable printed-text parsing is retained across calls. Mutable layer
results remain query-scoped, and dynamic type effects are checked live. The
existing performance test observes the new printed predicate instead of its
cached leaf parser; its strict work-reduction and state-purity assertions remain.
No AI heuristics, search depth, decisions or models changed.

The exact patch and preserved collection-failure history are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/current2f7-ai-query-qualification-20261008/`.
Earlier single-position profiling is diagnostic evidence, not completed natural
games, expert strength or final browser/release qualification. The later
clone-scope experiment produced no retained-position work reduction and is not
included here.
