# Native Own-Library Bottom Selection

## Reproduced Defect

Review of the C14 sixty-game study raised a Tempo allocation lead: a playable
Bolt was retained while an exiled counter expired. The original root choice
options were not recorded, so that observation alone was not a certified error.

A new controlled native reproduction exposed a simpler direction error. After
a genuine land play and actual UR Iteration payment, the ordinary AI retained
Pierce but selected Bolt for the library's bottom and exiled an unusable Island.
The remaining red mana could instead pay for the exiled Bolt. Separate manual
allocation controls demonstrated that legal alternative in both seats, retaining
Pierce and dealing three actual damage. No winner or altered card text was used.

The selector used its generic best-card helper even for the card being put on
the bottom. The correction uses the existing worst-card helper for the generic
empty-hint, self-activated, self-related-player `Library` destination at default
or explicit position -1. Other directions and special/opponent paths remain.
This is not a full joint hand/exile planner or proof of the original game's
unrecorded three-card counterfactual.

## Independent Review And Correction

Hermes t3 found a source-derived P2 edge: the discard-oriented worst-card helper
can filter protected permanents and return null despite a nonempty mandatory
choice. A new native controller min1/max1 regression with unchanged Illusions
of Grandeur/Bolt metadata reproduced empty selection in both seats.

The final fallback calls the existing cheapest-card helper over the original
valid collection when that nullable helper declines. Both unchanged regression
rows now return an actual card and preserve the tested input/RNG boundaries.
The reviewer made no production edits and did not independently execute those
games/tests; parent-native reproduction and static review remain distinct.

## Executed Qualification

The final fifteen-source/twenty-four-class prefix passed four serial groups:

- Twenty internal selector-protocol rows, including preserved hand/top/opponent/
  hint/null-related routes and explicit/default bottom behavior.
- Four paid real-card controlled rows: two ordinary AI allocations/followups and
  two separate manual rules controls. The AI actually casts the exiled Bolt
  through its ordinary chooser and spends native UR then R.
- Two mandatory-controller regressions, not full Illusions gameplay.
- Eight whole existing native lifecycle/privacy/stack/input/checkpoint/journal/
  completion classes: 101 passes, no failures or skips.

All four groups exit 0: 127 checks, **not 127 games**. Compile and every native
group retain the existing bwrap/JNI/kernel guards, CPU0/1500 MiB/one JVM at a
time. Source/prefix hashes match before and after. All 59,971 base resource
files were reverified; the inherited fourteen sources/twenty-three classes are
unchanged. Forty-five synthetic profile tests pass separately, retaining all
42 old test methods/assertions and adding strict schema12 checks.

Historical results remain recorded: original four rows had two allocation reds
and two passing manual controls; baseline direction controls were 16/20; the
first 125-check candidate passed before the mandatory edge was added. Its later
two-row mandatory failure is not hidden or relabelled as already covered.

## Delivery And Limits

Source, patch, card/program attribution, exact inputs, portable probes and
`QUALIFICATION.json` are in the [native source package](../../tools/engine_evaluation/forge/native-ai/dig-direction/README.md).
Forge rules, canonical card programs and baseline AI remain the **Forge Team/
Card-Forge contributors' work**, under their preserved GPL notices.

Final content ID: `940a13aa7bd0a5bd56d19117a4c9bba4913575255e259f1f48feb14899c4f193`.
The profile has a new identity; no old save/build is relabelled and no live or
default runtime is changed. The old C14 sixty-game study is not transferred to
this candidate. No new natural-game comparison, expert playing strength,
complete root-candidate tracing, useful trained policy, broad fairness or human
BO3 acceptance is claimed. The overall AI checklist stays open.
