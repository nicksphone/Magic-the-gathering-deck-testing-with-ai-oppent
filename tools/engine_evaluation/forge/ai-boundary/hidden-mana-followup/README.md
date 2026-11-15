# Known Fog And Concealed Mana Follow-Up

## Finding And Scope

**Open affordability channel confirmed on both original and frozen candidate.**
A legitimately remembered Fog is evaluated with the defender's actual mana
sources. A concealed hand mana enabler changes that affordability result and
the actual native attack defender, despite equal attacker snapshots and equal
Fog-only reveal knowledge. Both seats reproduce it. Ending RNG also differs.

This is not an objection to remembering a genuinely revealed Fog, public mana,
or open decklists. The complete deck multiset is fixed; the mana source itself
is never revealed. It is a different input channel from the private Fog identity
filtered by the frozen candidate. That one-mechanism correction remains frozen
and passes its existing twenty checks; this follow-up does not broaden its claim
into whole-AI fairness.

Only new tests, this report, attribution, a launcher and one complete native card
program are added in this folder. No production correction, second body/API
change, general mana audit, app/save qualification, parent graph update, commit
or push is performed. No frozen `native-ai/` file or original nine audit files
is changed; both sets are verified against the previous NFS archive's hashes.

## Real Call Path

All paths below are relative to pinned Forge
`61e9442c433711a82258daca3236f936a1d6f70e`:

| Exact Source Location | Relevant Behavior |
| --- | --- |
| `forge-ai/src/main/java/forge/ai/AiAttackController.java:600` | Actual native assault check calls `hasAFogEffect(defendingOpponent, ai, true)`. |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java:1585` | Original legitimate remembered-hand path admits the revealed Fog; candidate retains this path after its identity filter. |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java:1611` | Original calls `ComputerUtilCost.canPayCost(sa, defender, false)`; unchanged call is at candidate line 1617. The payer context is defender, not attacker's knowledge. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilCost.java:544` | Cost overload delegates using the actual payer and sets the activating player if absent. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilCost.java:649` | Calls `ComputerUtilMana.canPayManaCost` with that payer. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java:64` | Affordability delegates to native test-mode payment; lines 74-76 prepare and forward the cost. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java:675` | Native test payment obtains sources through `getSourcesForShards`. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java:1111` | Calls `groupSourcesByManaColor(ai, checkPlayable)` where `ai` is the defender. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java:1806` | Enumerates `getAvailableManaSources(ai, checkPlayable)`. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java:1647` | Combines the actual defender battlefield **and hand**. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java:1651` | Native `canPlay` and restriction checks use defender context, not an observer-knowledge projection. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java:1978` | `getAIPlayableMana` accepts the native Mana ability with a non-mana exile cost. |
| `forge-game/src/main/java/forge/game/cost/CostExile.java:173` | Native additional-cost eligibility; lines 188-189 accept the source card being present in the applicable zone. |
| `forge-gui/res/cardsfolder/e/elvish_spirit_guide.txt:5` | Actual ability produces G, costs exiling itself from hand, and has Hand activation zone. |

The mana engine is not patched or replaced. The source trace preceded the new
test; the native cost channel and actual decisions were then executed, not
inferred from the existence of a hand scan alone. No other mana/cost families
were explored dynamically.

## Controlled Checks

Native Default AI controls both seats, one acting as attacker. The attacking
Craw Wurm faces an opponent at two life with Jace Beleren at printed three
loyalty and a Forest. There are no blockers. Fog remains in the defender's hand.
The native reveal callback receives **only Fog**, not the hand. The attacker
memory is asserted to contain exactly Fog before and after the decision.

Elvish Spirit Guide and a non-mana-in-hand Forest are created in identical
identity order, then assigned to hand/library in compensating variants. The
complete deck multiset and all zone counts stay fixed. Both cards remain hidden
to the attacker. The strict pair uses the same public tapped Forest in both
variants. Native actor snapshots and legitimate Fog knowledge match exactly.

The test calls the actual `declareAttackers` callback before any diagnostic
affordability/source-list query, resets RNG to `2026110601` before each decision,
and samples ending RNG immediately afterward. It asserts an actual attack,
retained Jace, and a nonterminal native position. ESG is not activated/exiled,
Fog is not cast, no public land is tapped by the test query, and no mana pool
or outcome is fabricated. This is not a full game or a strength benchmark.

| New Follow-Up Checks | Original | Frozen Candidate |
| --- | --- | --- |
| Strict concealed-mana invariance, seats 0 and 1 | 2 RED | 2 RED |
| Untapped public Forest masks concealed variant, both seats | 2 PASS | 2 PASS |
| Public untapped/tapped Forest toggle, no concealed enabler, both seats | 2 PASS | 2 PASS |
| Runtime errors | 0 | 0 |

Each new cohort is six paired checks / twelve actual attack decisions, process
exit 1. The two RED nodes fail specifically on the actual native attack-defender
equality assertion. Actor snapshots match; affordability, source eligibility,
attack choice and ending RNG depend on the concealed variant. Public controls
retain the expected public mana/cost sensitivity and hidden-variant invariance.
Generated hand/variant/decision/RNG rows remain private archive evidence and are
not reproduced in this public report.

The unchanged existing cohorts were rerun separately on both builds:

| Existing Frozen Checks | Original | Frozen Candidate |
| --- | --- | --- |
| Original eight | 2 RED / 6 PASS / 0 errors | 8 PASS / 0 errors |
| Added twelve | 2 RED / 10 PASS / 0 errors | 12 PASS / 0 errors |

No preexisting assertion, node, fixture or candidate file is weakened or edited.
The new RED results are separate coverage of an open mechanism, not a regression
introduced by the visibility patch and not a relabelling of the twenty checks.

## Exact Runtime Evidence

Base input remains
`U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json`,
where `U=/home/nick/.hermes/cache/scratch/mtg-jev-ui-clarity-20261025-krVbf5Hv`.
The exact qualified Temurin `21.0.13+9` and ordered 102-entry CP are reused.
Only the unchanged candidate's single production shadow is prepended in the
candidate run; follow-up test classes are appended. Fresh local home/tmp,
read-only external filesystem, sanitized environment, isolated PID/network
namespaces, explicit `--release 17 -implicit:none` compilation, 1,500 MiB heap
and 180-second per-JVM wall bounds are retained. Simulation/flat Monte Carlo,
filtered hands and shuffle cheating remain off.

| Exact Artifact | SHA-256 |
| --- | --- |
| Frozen visibility patch, unchanged | `221ac0ec7c0cedd3e72392bdae7692f052ac2fe6a51c7b445852e762fc030cf3` |
| Candidate `ComputerUtil.class`, unchanged | `60ec0579438008e0c5a1eba4ef0ffde6b77f3eaf7ab9865c8fa3a2a1b97a1bfc` |
| Original `ComputerUtilMana.java` | `46d8b049cb68379f1968fd5eac95fdd7f0544fa37551a1f21c2f9944f071d436` |
| Native `ComputerUtilMana.class`, unchanged in both runs | `be85674769897c78dc008eca3a5949ae331dff9724e98318ffc6c76a02a8d398` |
| Full native ESG card program | `8e62249f6ef32a9fadc68074d8bca47abfa563d4e75fc5685336291609953b27` |
| New follow-up Java source | `764aab983344e4cd41ea6487bfb27db26e0044306d6a11c1f700d78ee02d625b` |

Thirteen explicit loaded class-resource origins/hashes match before and after
each follow-up. Across original/candidate, every recorded resource other than
the intentionally shadowed `ComputerUtil` is equal, including the real native
mana/cost/exile classes. All original nineteen frozen files and traced native
source/class pins remain unchanged. Six JVM syscall traces, including existing
cohort reruns, each show zero IP connects and zero non-netlink sends; each has
three IP-family socket creations. This is not a zero-attempted-IO claim.

## Reproduce And Limits

```sh
bash tools/engine_evaluation/forge/ai-boundary/hidden-mana-followup/run.sh \
  "$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json" \
  /absolute/new/local/run-directory
```

The existing frozen qualifier is invoked unchanged for its original/candidate
cohorts; its recursively collected audit input manifest naturally includes the
new child folder. The original nine and candidate ten files are additionally
checked byte-for-byte against the previous archived freeze, independently of
that expanded input inventory.

Private evidence destination:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/native-hidden-mana-followup-20261106-JbHtrWQu/`.
It preserves all original/candidate observations, native/RNG data, frozen input
receipts, actual class origins, full canonical source and source trace evidence.
Mounted-NFS archive readback and byte comparison precede owned scratch cleanup.

Coverage is limited to this known-Fog/ESG hand-mana channel, both seats, one seed
and constructed context. It does not certify all costs, mana sources, reveal
lifecycles, other cards or broad native-AI fairness. The producer/source identity
fix is still one proven mechanism only. No new application/save build identity,
deployment or compatibility qualification is claimed. No production edits, SQL,
app/HTTP service, new dependency, protected model body, secret or external network
access was used. Further correction requires separate authorization.
