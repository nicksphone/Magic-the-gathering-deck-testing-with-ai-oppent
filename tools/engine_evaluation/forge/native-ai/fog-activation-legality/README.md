# Native Fog Static Activation Restrictions

Status: **16 controlled cases and two privacy pairs PASS under the paired contract**.
No profile adoption, natural-game victory, deployment or completed AI acceptance is
claimed. See [NOTICE.md](NOTICE.md), [LICENSE](LICENSE) and [DESIGN.md](DESIGN.md).

## Source-Matched Defect And Increment

A public Spore Frog disabled by a correctly named canonical Pithing Needle
remained affordable to sacrifice, but its nonmana ability could not legally
activate. The Fog threat forecast checked cost feasibility without the native
activation prohibition. Both actual Default attack decisions targeted Jace
instead of the declared player-lethal expectation. This measures a false Fog
forecast/target redirection, not a resolved counterfactual win.

The production change is exactly three lines before the existing cost query:

```java
if (sa.isActivatedAbility() && !sa.checkRestrictions(defender)) {
    continue;
}
```

Knowledge filtering stays before ability inspection; spells do not enter the
new branch. No blanket `canPlay`, native clock, cost policy or other function
changes. This checks **static activation restrictions only**. Detain,
suppression, other playability and future response-window legality remain
outside this correction. The patch restores the exact preimage under zero-fuzz
inverse checking. Skipping a prohibited ability's cost forecast may legitimately
change RNG history; no full internal-memory/global-purity claim.

| Artifact | SHA256 |
| --- | --- |
| Parent ComputerUtil source | `a01fe06b0ceb8e1d2e6ecfbd719e16d59a33cf9cab57874e051f381d425beaf6` |
| New full source | `257cb44971161566ea23296c179e7728827a96f5f63ffa339fcf5ad61ba055ff` |
| Incremental patch | `589403450a01615b4d7c9f1be35ee562aaf559caafba260e9cd0047ee3f54528` |
| Compiled ComputerUtil class | `c198a18b6837a0daf7dbc2d98c63f0f6f0b29a2219ad76edce158bac106e0eb2` |

## Initial Strict Witness And Final Contract

| Cohort | Parent Baseline | Candidate |
| --- | --- | --- |
| Original eight unchanged cases | 6 PASS / 2 POLICY_RED | 8 PASS |
| New eight preservation cases | 6 PASS / 2 CONTROL_FAIL | 6 PASS / 2 CONTROL_FAIL |
| Additional hidden-manifest privacy pairs | 2 PASS | 2 PASS |
| Harness errors | 0 | 0 |

Those initial invocations exited **2**, not a normalized green: the two funded-instant
diagnostic RNG-purity assertions remain failed on baseline and candidate.
Actual instant forecasts, owner forecasts and attack decisions are correct.
Passive fields added after the baseline distinguish unchanged actor view from
RNG consumption; no assertion or expectation changed. All eight supplemental
rows match baseline in every originally recorded field, including actor view,
incoming/ending attack RNG fingerprints, forecasts, decisions and failure
classification. This is preservation evidence, not query-purity proof. Native
mana forecasting can reach `isManaSourceReserved -> MyRandom.percentTrue`.
No mana/RNG behavior is repaired here. Initial source/logs/failures remain
unchanged in a verified private HOLD archive.

A separately authorized [test-contract correction](control-contract/README.md)
retains that strict witness. The final fresh baseline has six original passes
and two policy RED, eight local preservation passes and two privacy pairs; it
is only a reference until paired. The final candidate has **16 PASS**, two
privacy-pair PASS, **all eight exact full-row comparisons PASS**, zero control/
harness failures, exit0 in11.017s. Every actor/input, first attack, forecast/
restriction and physical-root field is paired, with full before/after serialized
RNG values, not just digests. No fields/RNG values are dropped or normalized.
Non-spell query RNG purity remains asserted. Native spell-route mutation is
accepted only through mandatory actual baseline comparison, not a scene-name
exception or a claim of within-run spell-query purity.

The original `NativeFogActivationAudit.java` remains byte-exact (`14890b4f...`).
The coupled driver invokes its private original checks without changing them,
with the same order/initial seed/model setup. It is not relabelled as a rerun of
the predecessor standalone main. Original cases are both seats for Needle naming
Frog, naming another card, genuinely leaving the battlefield, or absent. Native
Needle entry/NameCard effects choose a legal name; no named-card/SVar mutation.

New cases use actual canonical Scroll of Fate tap payment/stack/resolution to
manifest a sole hand Spore Frog or Forest. Controlled tapping isolates blockers;
this setup is not an AI choice or natural history. Native Default then makes one
attack decision before diagnostics. Both pairs have equal actor views and actual
incoming/ending serialized RNG state without late reset or repair. Fresh fixture
seeds are declared before game construction. Other new cases expose instant Fog
with Future Sight, with funded/unfunded Forest and Needle naming Fog. The first
genuine Default attack always precedes diagnostic queries.

## Reproduce Without Editing Qualified Inputs

Requires the pinned built Forge/Q runtime, cached JDK21, Python standard library,
GNU patch, timeout and bwrap. No dependency install, SQL/app/browser or network
service. Every output below must be a fresh local path outside the repository.
Run from this directory:

```sh
python3 run.py /qualified/Q/BUILD-IDENTITY.json /qualified/candidate2 /fresh/baseline
python3 build.py /qualified/Q/BUILD-IDENTITY.json /qualified/candidate2 /fresh/candidate
python3 run.py /qualified/Q/BUILD-IDENTITY.json /qualified/candidate2 /fresh/green /fresh/candidate /fresh/baseline
```

The runner returns actual native exit codes: final baseline1 for two policy RED,
final paired candidate0. Unpaired candidate execution rejects. The builder checks the exact parent
content `0c04d1b1435472432cfb377db47595ca3b3ff76c18eeb6d6db57ec4f076f8ef1`,
patches without fuzz/offset, compiles only ComputerUtil with Java17 target,
and preserves the other14 classes/7 sources, including strict worker `d991...`.
Its full 8-source/15-class hash bundle is not operator approval or a profile.

One JVM per run: 300-second outer bound, 1500m heap, one active processor,
qualified native 5-second AI clock, read-only native inputs and isolated network.
All listed inputs match before/end. Eight of15 candidate classes were observed
loaded from the candidate shadow; no claim all15 executed. Parent owns any new
profile/application/resolved-outcome qualification. No natural-game result,
private generated actor/RNG data or checkpoint/persistence claim is published.

## Independent Composition And Existing Controls

The parent independently reproduced class `c198a18b...` from source
`257cb449...`, with the other fourteen classes and seven sources unchanged.
The explicit eight-source/fifteen-class profile has build identity
`953e8cd2f26af06a5177532650a7c25c7376b65cb8254df815d66e2677577e30`.
It is built, not application- or save-qualified. The producer diagnostic
manifest and parent approval bundle use different, verified content-ID formulas;
their full source/class maps are identical, but the IDs are not aliases.

Five existing whole Java mains ran unchanged on that independently built prefix:

| Main | Actual Result |
| --- | --- |
| NativeFogBoundaryRegression | 8 top-level passes |
| NativeFogKnowledgeControls | 12 top-level passes; 4 separate owner-helper checks |
| NativeHiddenManaFollowup | 6 top-level passes; 12 native attack decisions |
| NativeKnownManaControls | 4 top-level passes; 2 owner-payment and 2 remembered-source checks |
| NativeEmptyKnownSources | 4 separately labelled synthetic passes |

These are 30 top-level knowledge rows plus eight separately named checks, not
38 top-level rows. The four synthetic cases are separate. All five mains exited
0 with zero RED/errors; the actual ComputerUtil origin/hash was checked in the
four knowledge mains. The empty-source main did not load ComputerUtil. All
fifteen physical payloads and eight source files matched before/end; no class
was forced to load for coverage.

The first private launcher completed the boundary eight, then reached its
original 180-second deadline during knowledge-model initialization, before any
case verdict. That launcher remains incomplete. A separately declared
300-second phase ran only the three unfinished mains. Its initial private
class-copy error is retained; correcting only that copy command allowed all
three to finish. No valid completed boundary run was repeated. The synthetic
main separately finished within its predeclared 300-second limit. No original
Java assertion, production code or current deadline changed during these runs.

Private network/SQL canaries and input/process checks are preserved. Denied
native socket attempts were recorded, not described as zero attempts. No
successful network or SQL connection occurred. No app was started and no private
model body was read. Thirty-two observed owned PIDs ended. These controlled programs do not
establish a win rate, global privacy or application adoption.
