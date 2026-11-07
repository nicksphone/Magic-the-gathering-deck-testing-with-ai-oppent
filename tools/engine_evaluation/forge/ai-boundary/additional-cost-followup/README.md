# Additional-Cost Held-Piece Follow-Up

## Finding

**An actual unknown-hand dependency remains on final candidate
`ff89fd32da4e011d9e8f9af613a07a484894171ba7e4045c3932fcfaed4de398`.**
With the same public board, legitimate native reveal knowledge and pre-decision
RNG state, the actual native attack and scoped Fog affordability change with one
concealed non-mana hand card. Both seats reproduce the same mechanism.

The suspect hook is `canPayShardWithSpellAbility` calling
`ComboPlan.holdsKillPiece(payer)` without observer knowledge. The public mana
source has already passed the new knowledge admission gate. The later held-piece
heuristic reads the payer's actual hand and vetoes a discard-cost mana ability.
The method tests **any CostDiscard**, not only whole-hand discard, despite its
whole-hand-oriented comment.

This is AI willingness/forecast affordability, not a claim that native game
rules make the printed payment illegal. The rules permit the single-card discard
in either variant. The observer should not know a hidden card's effect on the
opponent's strategic veto.

This task changes **tests/docs in this folder only**. No production fix or
proposal is made, no old test/patch/profile is modified, and no other hook/family
is investigated dynamically. The earlier unknown-source correction remains a
proven separate mechanism, not a whole-AI fairness proof.

## Primary Source Trace

Read-only sources are pinned Forge
`61e9442c433711a82258daca3236f936a1d6f70e` and the parent's final source directory
identified by `U/CURRENT-FORGE-EMPTY-SOURCE.path`. Here
`U=/home/nick/.hermes/cache/scratch/mtg-jev-ui-clarity-20261025-krVbf5Hv`.

| Exact Source Location | Relevant Boundary |
| --- | --- |
| Final `ComputerUtil.java`, `hasAFogEffect` | Known Fog/source policy calls the scoped native cost overload. |
| Final `ComputerUtilCost.java`, `canPayCost` | Retains payer context and forwards knownCard into mana affordability. |
| Final `ComputerUtilMana.java:1692` | `getAvailableManaSources` admits the visible source before checking mana abilities. |
| Final `ComputerUtilMana.java:1257` | Discard-cost branch calls `ComboPlan.holdsKillPiece(ai)`; `ai` is payer/defender, while knownCard is not forwarded to this hook. |
| Pinned `forge-ai/src/main/java/forge/ai/simulation/ComboPlan.java:2481` | Scans the actual payer hand. No deck-plan/archetype prerequisite. |
| Same file `:2472` | `isStormFinisher` checks nonland/noncreature and Storm keyword or native role. |
| Native `forge-gui/res/cardsfolder/s/skirge_familiar.txt:6` | Genuine single-card discard mana ability produces B, with no tap or instant-only activation cost. |
| Native `forge-gui/res/cardsfolder/d/darkness.txt:4` | Genuine black instant with native Fog API, cost B. |
| Native `forge-gui/res/cardsfolder/t/tendrils_of_agony.txt:4` | Full native Storm keyword supplies the held-piece condition. |

The initial obvious Lion's Eye Diamond candidate was **not used**. Its native
program has `InstantSpeed$ True`, and final `ComputerUtilMana.java:2035` excludes
that ability in `getAIPlayableMana` before this cost-source route reaches the
held-piece hook. That is a scoped source negative, not a general statement that
the card cannot be activated elsewhere. No fabricated LED failure was written.

## Native Controlled Position

The attacker has a nonsummoning-sick Craw Wurm and 20 life. The defender has two
life, Jace Beleren at its printed three loyalty, a face-up Skirge Familiar and a
Swamp. Familiar is tapped so it cannot block; its printed discard activation
does not tap, so it remains a native eligible mana source. The strict pair's
Swamp is tapped. There are no other sources or blockers.

Darkness is in hand. A real native reveal callback discloses only Darkness, and a
separate native battlefield reveal callback supplies the already-public Familiar.
The test asserts actual source visibility and exactly those remembered native
cards. The unknown card is not revealed or granted a viewing permission.

The private variant is Tendrils of Agony versus Forest, compensated by the reverse
placement in the library. Full card multiset, counts and identity creation order
are fixed. The test uses complete native card programs, born through
AITest/Card.fromPaperCard; [NOTICE.md](NOTICE.md) maps every canonical file to its
original source. All seven full card programs are byte-compared before execution.
Familiar's native `AI:RemoveDeck:All` annotation is retained; this controlled
position does not claim natural deck-builder/archetype coverage.

The actual Default heuristic controller declares attackers before any diagnostic
cost/source/held-piece query. The actor's physical-zone snapshot and exact native
reveal-callback projection are compared between variants. The public source is
confirmed natively eligible in both. The test requires an actual attack and a
nonterminal native position; no spell is cast, card discarded, mana manufactured,
source activated, or winner assigned.

## Results

Current final shadow, one successful bounded execution:

| Checks, Both Seats | Result |
| --- | --- |
| Same-view unknown held-piece invariance | **2 RED**, failing actual attack-defender equality |
| Reveal the actual otherwise-hidden card through a native callback | 2 PASS; differing legitimate knowledge permits the native affordability/attack difference |
| Independent untapped public Swamp, hidden variants still concealed | 2 PASS; known Fog is funded in both, with equal actor views/knowledge and decisions |
| Fixture/runtime errors | 0 |

This is six paired checks / twelve completed native attack callbacks, process
exit 1, not twelve games. In both strict pairs, actor snapshots, authorized
callback projections and pre-decision RNG states match. Attack choice,
affordability and ending RNG differ; the actual held-piece hook differs while
the public source remains eligible in both. No generated private hand/decision
rows or RNG values are reproduced in this public report.

One seed is installed at the start of each fresh fixture. The test serializes
the actual installed Random provider, including its delegate, before and after
the callback without consuming or restoring RNG. No late reseed, restored
generator, forced choice, RNG equalization or simulation override is used.
This measures that provider state, not an entire full-game RNG journal/global
call-counter reconstruction.

### Preserved First Attempt

The first attempt had **0 PASS / 0 RED / 6 fixture errors** before any attack
callback. `MyRandom.setRandom` wraps its argument in native CountingRandom, so
requiring equality with the external argument was invalid. The corrected fixture
captures `MyRandom.getRandom()` and retains the before/after identity checks.
Both source versions and all diagnostics are archived. The old summary's nominal
12-decision field was not an observed count; final code counts completed callbacks.
No first-attempt fixture error is relabelled as a fairness finding.

## Exact Runtime Evidence

Target is the parent's final `E/final/shadow`, from
`U/native-empty-source-guard-20261106-dQ2RSZLh`. This is not the earlier immutable
74e0 candidate. The parent-reported profile `1643` / published app `a005c056`
provide context; no app, HTTP service or profile launch was executed here.

| Artifact | SHA-256 |
| --- | --- |
| Final ComputerUtilMana source | `6928620486da73f525fc5eb5e9369d47a2ceeb444706f4711da173e481948c54` |
| Actual loaded final ComputerUtilMana.class | `24af388551ffdf891aac3bdf29647a6091095e6ad944416f8d8b80c05378aab0` |
| Pinned ComboPlan source | `e0c1571ed4763e8892043ddec81e95cdda2490ce5b2d632be67355fee1b1957d` |
| Actual loaded ComboPlan.class | `99ea60bfe13a148635a0067480d0ef57cf04ce8ce4a06dc4f6b044d28d0610e8` |
| Actual loaded CostDiscard.class | `f1d91cfa9c149a6287b097924fb9884f75f80f6aa851377c1e76278356ab6930` |

The exact qualified Temurin `21.0.13+9` and ordered 102-entry base CP are read
from unchanged Q/BUILD-IDENTITY.json. Final shadow is prepended and test-only
classes appended. Compilation is explicit `--release 17 -implicit:none`; no
native source or dependency is compiled/installed. All four final shadow payloads,
including Cost$1, load at their exact manifest origins/hashes. Seventeen explicit
class-resource origins/hashes match before/end, as do source/JDK/manifest pins.

Only one controlled JVM runs at a time, at nice level 10, 768 MiB heap, 192 MiB
metaspace, Serial GC, ActiveProcessorCount=1 and a 180-second wall bound. Explicit
read-only system/cache/Q/shadow binds, fresh local home/tmp, a sanitized environment
and isolated PID/network namespaces avoid shared application writes or host-mount
dependencies. The successful trace has zero IP connects and zero non-netlink
sends; three IP-family socket creations occur. No zero-attempted-IO claim is made.

## Reproduce And Evidence

```sh
E=$(cat "$U/CURRENT-FORGE-EMPTY-SOURCE.path")
bash tools/engine_evaluation/forge/ai-boundary/additional-cost-followup/run.sh \
  "$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json" \
  "$E/final" /absolute/new/local/test-output
```

This launcher deliberately requires the exact ff89fd32 final content ID. It runs
one native process, not a broad cohort or the parent's NativeMatchProbe. Generated
observations, serialized-provider digests and native diagnostic traces are private.

Evidence destination:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/native-additional-cost-followup-20261106-UxEJFxwd/`.
It retains both attempts, complete canonical inputs, native source attribution,
exact argv/classpath, source/class pins and all private observations. Mounted-NFS
write verification and full archive readback/byte comparison precede cleanup of
owned disposable scratch. Parent's final candidate and processes are left alone.

## Limits

One held-piece/discard-cost mechanism, one seed, one fixed board, both seats.
No additional-cost/global-condition family beyond this one was tested. Existing
30 checks, old patches, parent profile/native-match tools, K/Q/E, and all other
documentation are unchanged; they are not rerun or relabelled by this task.
This does not imply all discard sources or native contexts behave alike, nor
prove broad fairness/strength, full games, app or save compatibility. No production
fix, unapproved solver rewrite, SQL, network access, protected model body, secret
or TypeSafe call was used. Further correction requires separate authorization.
