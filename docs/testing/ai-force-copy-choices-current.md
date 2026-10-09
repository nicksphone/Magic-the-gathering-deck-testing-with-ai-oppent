# AI Force Copy Choices

Production source: `a53e76a31c214e2f9b882d3496721bd27af1e7fc`.
This increment adds only `audit/bounded-spells/test_ai_force_copy_choices.py`;
the AI policy and gameplay production code are unchanged.

## Observed Qualification

The exact-current isolated qualification ran three whole modules: NEW 12 AI
copy-choice cases, the unchanged 24 paid Force/Twincast cases and the unchanged
16 copy-boundary cases. All 52 passed in 27.03s, exit zero, with no skips,
xfails, filters or deselections. The NEW file was executed verbatim outside
the source tree while importing the exact repository helpers.

The subsequent repository-placement run executes the same three whole modules
under `source/audit/bounded-spells` with the unchanged repository bootstrap:
52 passes in 28.50s, pytest and wrapper exit zero. All 156 setup/call/teardown
records pass. The 2,746 original source files plus the one NEW test, runtime,
canonical seed, inputs, RNG, threads, descriptors and imports match their
recorded pins before and after.

Four controlled-goal cases make actual public AI choices and resolve the copy
against opposing artifacts or enchantments rather than friendly targets.
Four paired counterfactual cases compare explicit legal keep and retarget
choices. Four cases swap opposing hidden identities while checking public
moves, decisions and input-state invariance. Both seats and one/two targets
are covered, with actual paid Force of Vigor, Twincast and Secure the Wastes
execution. Removing Intangible Virtue changes the created tokens from 2/2 to
1/1. Original spell payloads remain unchanged.

The recorded 14 `AIAgent.choose_action` calls are observations inside these
12 cases, not 14 independent matches. The other two modules cover zero-target
behavior, malformed and wrong-actor requests, opposite copying, and a real
Flicker response with a new incarnation of the same card ID.

## Evidence

Immutable archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/gate2-corpus-readiness/repo-copy52-a53-ub2j9I-20261009/`.

The parent independently verified the archive SHA, all 94 regular members,
the data-only checker result, the complete 156-phase pytest ledger and the
NEW test bytes. The NEW test SHA256 is
`a29ad5b64f77c8ab519b0484875a84a958012d275067f50136765cb22524e86b`.
The production `ordered_targets.py` SHA256 remains
`e6d2433418323801fb26a8e02a918af40bbb7c4f7bb0f85fb54aa90123e64aae`.

Final repository-placement evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/gate2-corpus-readiness/repo-placement52-qualified-a53-KTQaTk-20261009/`.
Its complete source/controls/evidence archive SHA256 is
`a79f5caec56c05137b5f99e4bbe45b14590172e14b0e7e649cd2feecb7b20537`.

The first placement attempt recorded 52 test passes in 27.26s, then wrapper
exit one when available disk fell below the unchanged 3-GiB floor during
ledger saving. Its incomplete closure is explicitly unqualified and retained
separately. After verified archival and cleanup of a closed owned checkout,
the successful rerun retained the same runner, assertions, I/O policy, cap
and floor. No gameplay code changed to address the resource failure.

The native precollection guard denied both SQLite aliases, socket creation
and child launch. No SQL connections, listeners or children were admitted.
Source, canonical seed, runtime, RNG, thread and file-descriptor checks match
before and after. These Python-native controls are not an OS sandbox claim.

Repository invocation uses the existing bootstrap and these whole modules:

```sh
python -B -m pytest -p no:cacheprovider \
  audit/bounded-spells/test_ai_force_copy_choices.py \
  audit/bounded-spells/test_paid_force_twincast.py \
  audit/bounded-spells/test_force_copy_boundaries.py
```

Use an isolated local checkout and the reviewed native guard for qualification;
never execute archived SQLite evidence on NFS.

## Limits

No product defect or policy change is claimed. These controlled positions do
not establish alternative pitch-cost behavior, all copy/target families,
complete natural games, optimal play, 13-style strength, browser acceptance
or release completion. The current browser gate remains separately pinned
to its immutable `a53e76a` checkout.
