# Known-Mana Native Increment

## Frozen Handoff

Content ID:
`74e0cc8af0915195b8a0a353439847206997c3c0f9ba9b520731ce3708ae8d9b`.

[FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json) is the machine-readable handoff.
It gives exact class names/paths/hashes for **every emitted payload**, all three
source preimages/postimages, raw-upstream preimages, patch/compiler/JDK pins,
base identity, retained directory, and bounded qualification results. The same
file is retained with the compiled candidate. Its `identity` object is hashed as
canonical `jq -cS` JSON, including the trailing newline, to obtain `content_id`.

The active candidate is retained locally at:
`U/native-known-mana-20261106-lgx5DMtw/qualified`, where
`U=/home/nick/.hermes/cache/scratch/mtg-jev-ui-clarity-20261025-krVbf5Hv`.
Its `shadow/`, complete modified Java `source/`, inputs/notices, payload inventory,
`MANIFEST.json`, `IDENTITY.json`, and qualification receipt stay local for the
parent's later profile composition. Only disposable scratch is cleaned.

Required parent composition inputs:

- Base build: `59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605`.
- Parent-specified base-launch SHA-256: `ee58d6110017448391e210c1722d6f1450904c239cc297282f34e4ed4c588562`.
- Parent profile builder/publication remains parent-owned. The launch digest is
  recorded as a composition requirement, not a claim that this test launcher is
  the application launch or that the parent profile was requalified here.

This is **not deployed, not application-qualified, not save-compatible-qualified,
and not a whole-engine fairness proof**. The old identity candidate/profile and
parent's profile/checkpoint/UI-game evidence remain immutable and independent.

## Exact Scope

Only three native source copies change, through the GPL-noticed
[new delta patch](known-card-affordability.patch):

- `forge-ai/src/main/java/forge/ai/ComputerUtil.java`.
- `forge-ai/src/main/java/forge/ai/ComputerUtilCost.java`.
- `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java`.

`preimages.sha256` pins the post-identity delta inputs; `upstream-preimages.sha256`
pins the raw pinned tree. The existing identity patch is applied unchanged before
this delta. All native source headers are retained. See [NOTICE.md](NOTICE.md).
No fourth production file, native card rule, K/Q/old candidate, frozen audit/test,
parent profile builder/test, backend/frontend/store, or parent graph is edited.
No commit or push is performed.

Exactly four class payloads are emitted, explicitly allowlisted by the builder:

```text
forge.ai.ComputerUtil
forge.ai.ComputerUtilCost
forge.ai.ComputerUtilCost$1
forge.ai.ComputerUtilMana
```

The anonymous cost payload is compiled, retained and loaded from the new shadow;
it is not silently borrowed from the old classpath. A separate fresh rebuild
reproduced all four hashes and the complete identity object exactly.

## Knowledge Boundary

The existing `hasAFogEffect` observer supplies a per-call `Predicate<Card>` when
`checkingOther=true`. Admission permits native observer-visible identity, using
both native visibility gates, or the existing legitimate remembered-hand rule
(remembered card, defender owner, current Hand zone). It does not inspect a
concealed candidate's name, color, cost or mana abilities to decide admission.
`checkingOther=false` and every old public API preserve unrestricted owner-side
semantics through null-scoped delegates; empty observer knowledge never falls
back to unrestricted evaluation.

The predicate travels through cost affordability, test-mode mana payment, shard
grouping and source collection. The source collector rejects unknown candidates
before `getAIPlayableMana`, `canPlay` or restriction queries. The scoped chooser
also filters any supplied ability list by host identity before inspecting it.
Native source legality, mana/cost arithmetic, payment ordering/reuse, public
floating mana, and real payment remain native. No zone/controller is swapped,
no simulation/global/thread-local policy is added, and no RNG is repaired.

The three direct hand-preference inputs are filtered before their consumers:

| Scoped Site | Ordering Of Reads |
| --- | --- |
| `sortManaAbilities` | Copy hand identities, filter by predicate, then calculate `AiDeckStatistics`. |
| `sparingSourcesFirst` | Check predicate before reading a hand card's color. |
| `setComboManaChoice` | Filter hand before `getMostProminentColor`. |

The caller/API/dataflow design and scope limits are in the unchanged
[approved proposal](../../ai-boundary/hidden-mana-followup/REMEDY-PROPOSAL.md).

## RED To GREEN

All original twenty checks and six follow-up checks are byte-identical ordinary
tests. The same compiled test payloads were used for RED and GREEN.

| Cohort | Identity-Only Baseline | New Increment |
| --- | --- | --- |
| Original eight | 8 PASS | 8 PASS |
| Existing twelve controls | 12 PASS | 12 PASS |
| Unchanged hidden-mana six | 2 RED / 4 PASS | 6 PASS |
| New same-ESG remembered/owner controls | 4 PASS | 4 PASS |
| Total | 2 RED / 28 PASS / 0 errors | **30 PASS / 0 RED / 0 errors** |

In both strict concealed-mana checks, actor snapshots, actual native attack
defenders, observer affordability and ending RNG now match. The separate
unrestricted owner-side source eligibility diagnostic still differs between the
concealed variants, as it should: the payer retains its lawful private knowledge.
Public/tapped controls remain sensitive, rather than disabling opponent Fog.

New controls are in the separate
[NativeKnownManaControls.java](../../ai-boundary/hidden-mana-followup/known-controls/NativeKnownManaControls.java).
One per seat reveals and remembers the actual Fog and ESG through the native
callback, then requires the actual native attack to respect that payable Fog.
The mana source remains in hand during forecasting; no payment is fabricated.

One legacy owner-payment check per seat contains three real native attempts:
ESG-funded Fog, public-Forest-funded Fog, and unpayable Fog. There are six attempts,
four actual paid native stack casts and two rejected casts, not six full games.
ESG exile, land tap, native stack/card state and ending RNG are checked. Complete
canonical JSON owner-state/RNG receipts are identical to the identity-only
baseline for all six attempts; remembered-positive receipts also match in full.
Native positions remain nonterminal; no game outcome is assigned or forced.

The first raw JSON byte comparison differed because `Map.of` key iteration order
varies across JVMs. Full canonical-key JSON comparison, without dropping any state
or RNG field, passes. Raw and canonical receipts are both archived; raw wire
serialization equality is not claimed.

The first unchanged legacy-runner attempt failed to launch cohort JVMs because
its host-root bind encountered an unrelated stale `/mnt/ai_db` mount. That failed
attempt remains archived. The new runner binds explicit read-only system libs,
the public engine/JDK cache, and qualified payload root instead of the host root.
The complete retry above succeeded without changing the frozen runner or tests.

## Runtime Evidence

The exact qualified Temurin `21.0.13+9` and ordered 102-entry base CP are used.
Only the new four-payload shadow is prepended; test-only classes are appended.
Each JVM has its own local home/tmp, sanitized environment, isolated PID/network
namespaces, 1,500 MiB heap and 180-second bound. Explicit source compilation uses
`--release 17 -implicit:none`; no upstream implicit compilation or dependency
installation occurs.

Before/end class-resource origins/hashes match within each suite. All four new
payloads, including `Cost$1`, were explicitly loaded and their actual origins and
hashes checked against the manifest. Supporting native resources match baseline.
Source/JDK/input pins match after execution. Old audit/native candidate/follow-up
inputs and the approved proposal remain byte-identical to their archived pins.

Eight completed retry/GREEN JVM syscall traces each record zero IP connects and
zero non-netlink sends, with three IP-family socket creations. This is not a
zero-attempted-IO claim. No SQL, app/HTTP service, external network, new family,
random cohort, protected model body or secret is used.

## Build And Verify

```sh
bash tools/engine_evaluation/forge/native-ai/known-mana/build.sh \
  "$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json" \
  /absolute/new/local/candidate

bash tools/engine_evaluation/forge/native-ai/known-mana/run-tests.sh \
  "$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json" \
  /absolute/new/local/candidate/shadow /absolute/new/local/tests
```

`MANIFEST.json` contains identity plus runtime locations; canonical `IDENTITY.json`
contains content-addressed inputs/payloads. `payloads.sha256` and `sources.sha256`
can be checked from `shadow/` and `source/`, respectively. Parent profile
publication must validate its own exact base launch and atomically publish a
distinct profile; no old profile/build ID should be relabelled as this increment.

Private evidence destination:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/native-known-mana-20261106-lgx5DMtw/`.
All stages, complete native/RNG/payment receipts, raw failures, source/patch
snapshots, source/class/JDK pins and rebuild outputs are archived privately.
Full mounted-NFS readback/byte comparison precedes disposable scratch cleanup.
The candidate itself is retained locally for the parent, not cleaned.

## Limits

The candidate closes the demonstrated unknown hand-mana-source input and scopes
the documented direct hand preferences. Additional-cost, global/conditional
source, replacement/reflection, held-piece and native-script dependencies are
not thereby certified observer-complete. Existing native hook logic is preserved,
not globally rewritten. The three preference branches have source/dataflow review;
the bounded G-cost gameplay scenes are not exhaustive branch qualification.

These 30 checks do not prove broad native-AI fairness/strength, arbitrary card/cost
coverage, full native/app lifecycle, save/reconstruction compatibility, or a
release-ready fair baseline. Parent composition/requalification and the full goal
remain separate work. No fourth production source file or fallback was added.
