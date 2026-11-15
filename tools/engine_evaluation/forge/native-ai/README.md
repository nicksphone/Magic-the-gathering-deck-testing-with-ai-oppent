# Isolated Native Fog Knowledge Candidate

## Status And Scope

This is a frozen, separately tested shadow candidate, **not deployed** and **not
save-compatible-qualified**. The parent's durable-save work continues against
the unchanged native build. Later composition requires a new qualified build
identity and save/reconstruction qualification; the base ID below is not reused
as a candidate build ID.

Only `ComputerUtil.hasAFogEffect` changes: one source hunk in one native body.
The original pinned Forge tree, qualified class directories, existing nine
`ai-boundary/` files, backend, frontend, and save/store code are unchanged.
No caller API, second production body, card rule, cost logic or simulation policy
is edited. No commit/push or parent graph update is performed.

See [GPL attribution and complete canonical card sources](NOTICE.md) and the
[original source-trace audit](../ai-boundary/README.md).

## Correction

The helper still collects native battlefield and external-zone options. It now
also collects the hand, then, when `checkingOther` is true, removes candidates
whose native `CardView` fails either actual-observer identity gate:

```java
view.canBeShownTo(ai.getView()) && view.canFaceDownBeShownTo(ai.getView())
```

Filtering happens before abilities, Fog API, or costs are inspected. The existing
remembered-reveal hand path runs afterward, unchanged. Thus legitimate remembered
cards are not confused with currently visible cards or unknown private cards.
`checkingOther=false` retains owner-side private knowledge. Native owner/may-play,
convoke/improvise, and affordability gates remain unchanged. Public external cards,
currently revealed hands, and known Fog permanents are not disabled. There are no
card-name branches or hand/permanent visibility defaults in the patch.

The loop uses an iterator, avoiding a new lambda/synthetic production method.
The complete original source header is retained, and the changed block carries
a dated modification notice.

## TDD Evidence

Both seats are included. Tests run the real ordinary native Default controller,
with shuffle cheating, filtered hands, simulation and all flat Monte Carlo modes
off. No attack override, forced result, full game, random cohort or live match.

| Frozen Cohort | Original Native | Shadow Candidate |
| --- | --- | --- |
| Unchanged original eight paired checks | 2 RED / 6 PASS / 0 errors | 0 RED / 8 PASS / 0 errors |
| Twelve added knowledge/cost controls | 2 RED / 10 PASS / 0 errors | 0 RED / 12 PASS / 0 errors |

Original RED nodes remain the exact original family/seat checks:
`concealed-library-frenzy`, seats 0 and 1. Their assertions were not edited.
On the candidate, Fog-top and Forest-top both attack the opponent with equal
actor snapshots and equal ending RNG. Original no-grant library and hidden-hand
controls also remain invariant. The original explicitly remembered Fog control
still attacks Jace rather than the opponent; this permitted public-knowledge
dependency and its ending-RNG difference are retained.

The original Java test source SHA-256 and every original nine-file input are
pinned in the archive before and after. Compiled test payload hashes also match
between baseline and candidate. There is no assertion weakening or replacement.

Added attack controls, each in both seats:

| Control | Literal Native Expectations |
| --- | --- |
| Future Sight, payable public top | Fog: known, attack Jace; Forest: not Fog, attack opponent. Actor views correctly differ. |
| Future Sight, tapped Forest | Fog and Forest: no affordable Fog, attack opponent, equal ending RNG. Public top identities remain visible. |
| Telepathy, currently visible opposing hand | Without reveal memory, Fog: known, attack Jace; Forest: attack opponent. Actor views correctly differ. This is the two additional pre-patch RED nodes. |
| Tapped public Spore Frog, concealed library permutation | Sacrifice Fog ability remains known/payable; attack Jace in both variants, equal actor views and ending RNG. Tapping removes it as a blocker without preventing its native sacrifice cost. |

Owner controls call the real helper with `defender` as the actual observer and
`checkingOther=false`, for own hand and Experimental Frenzy owner-private top,
both seats. Each checks all Fog/Forest and payable/tapped-Forest combinations.
The literal result is `payable && fogFirst`; actor snapshots remain unchanged
by the query. These are four helper checks containing sixteen helper invocations,
not sixteen attacks or games.

Per baseline/candidate cohort there are sixteen actual attack pairs (32 actual
attack decisions) plus the sixteen owner helper queries. Repeated executions are
not additional independent coverage. Every actual position remains nonterminal.

## Exact Pins And Runtime

Forge revision: `61e9442c433711a82258daca3236f936a1d6f70e`.

Base identity input:
`U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json`,
where `U=/home/nick/.hermes/cache/scratch/mtg-jev-ui-clarity-20261025-krVbf5Hv`.
Base qualified build ID:
`59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605`.

| Artifact | SHA-256 |
| --- | --- |
| Complete native Java preimage | `10aa934b5efca931d34d39cbcf5dcd9a703ff0145edfad3466ffbd9dc3a4937d` |
| Frozen patch | `221ac0ec7c0cedd3e72392bdae7692f052ac2fe6a51c7b445852e762fc030cf3` |
| Complete patched Java source | `7a9341bc13900a1ad8a47a96ad29a5cba3110340ecb38895bef98669760f18d8` |
| Original qualified `ComputerUtil.class` | `d20f288d1d3cc576c9aab9ecedf80a918d7aef2830b23a0df27b79d829aa6160` |
| Candidate `ComputerUtil.class` | `60ec0579438008e0c5a1eba4ef0ffde6b77f3eaf7ab9865c8fa3a2a1b97a1bfc` |
| Unchanged original eight-check Java source | `fa912331a97b10a28352425da37b0bef870a76df5804d5ee0ea0924db0c7ea54` |
| Added control source | `7ed27f8c218515230f31d03e52ddb1ca06797d52860e41d2edfb3e0ccae706a8` |

JDK is the exact qualified Temurin `21.0.13+9`. The single-source compile uses
`--release 17 -implicit:none`, explicit sourcepath, and the exact ordered
102-entry qualified classpath. Applying the patch requires the complete preimage
hash and zero fuzz. The builder requires exactly one emitted production file:
`shadow/forge/ai/ComputerUtil.class`.

Runtime order is **candidate shadow : unchanged qualified CP : appended test
classes**. Only that shadow is prepended; test compilation uses the unmodified
qualified CP and cannot implicitly compile native sources. Both test JVMs record
twelve loaded class resource origins/digests before and after. `ComputerUtil`
loads from the fresh candidate shadow with the exact candidate digest. All other
recorded native resources match baseline, and all before/end resources match.

The candidate's default javac debug metadata differs from the Maven-qualified
class. An untouched-source rebuild with the same default flags is not raw-byte
identical: the qualified class has 100 local-variable tables, the default rebuild
has none. Both target class version 61. Full normalized `javap -c -p` instruction
comparison of qualified versus untouched rebuild is empty. Comparing every method
except `hasAFogEffect` between untouched rebuild and candidate is also empty after
constant-pool-index normalization. The failed raw-byte diagnostic and subsequent
instruction/debug investigation are retained, not relabelled as byte identity.
A separate diagnostic recompilation of the untouched preimage with `-g`
reproduces the qualified `d20f...6160` class byte-for-byte, confirming the metadata
cause. That diagnostic is not the candidate: the frozen candidate retains its
original compiler flags and `60ec...a1bfc` class pin.

Each JVM has a fresh local home/tmp, sanitized environment, read-only external
filesystem, PID/network namespaces, 1,500 MiB heap and 180-second wall bound.
Syscalls are traced using seccomp-BPF filtering. All four qualification JVMs
record zero IP connects and zero non-netlink sends; each records three IP-family
socket creations. This is not a zero-attempted-socket/IO claim.

## Reproduce Without Deployment

With only the already installed tools/resources:

```sh
# Expected RED: original eight 2 RED/6 PASS; added controls 2 RED/10 PASS.
bash tools/engine_evaluation/forge/native-ai/qualify.sh \
  "$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json" \
  /absolute/fresh/local/scratch-parent original

# Expected GREEN: original eight 8 PASS; added controls 12 PASS.
bash tools/engine_evaluation/forge/native-ai/qualify.sh \
  "$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json" \
  /absolute/fresh/local/scratch-parent candidate
```

The builder can be called separately as `build.sh BUILD-IDENTITY.json NEW-OUT`.
It never writes to K or Q. Do not prepend this candidate shadow to application,
store, recovery, or parent qualification commands without later authorization.

## Evidence And Limits

Private evidence destination:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/native-fog-knowledge-candidate-20261106-LAdkaFRI/`.
It contains frozen patch/build/controls, all original nine inputs, all eight full
canonical programs, exact pre/post source/class/JDK pins and CP/argv, original RED
and candidate GREEN observations, actor views/RNG, syscall logs and raw compiler
diagnostics. The mounted NFS archive is read back and byte-compared before owned
local scratch is cleaned. No generated hands/traces are repository fixtures.

This qualifies one controlled heuristic correction, not broad fairness, strength,
every reveal-memory lifecycle or external-zone/cost/visibility configuration.
The original remembered-hand semantics are deliberately retained, not globally
certified. No SQL, app/HTTP service, dependencies, external network access,
protected model bodies, secrets, or full-game simulations were used. Parent
runtime/save compatibility and shared graph refresh remain unqualified/deferred.
