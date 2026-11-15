# Six-Archetype Native AI Baseline

## Executed Scope

On 2026-11-07 the isolated native candidate completed all 24 declared games,
with zero native errors, zero incomplete games and dispatcher exit 0. No live
application profile changed. This reuses the Forge Team/Card-Forge contributors'
native rules, full card programs and baseline AI under GPL-3.0-or-later; see
[the third-party notices](../../THIRD-PARTY-NOTICES.md).

The unchanged built-in 60-card recipes are Burn, Dimir Control, Midrange, Tempo,
Ramp and Tribal. The six cycle pairings are Burn/Control, Control/Midrange,
Midrange/Tempo, Tempo/Ramp, Ramp/Tribal and Tribal/Burn. Each pairing runs both
seat orders with seeds 2026110701 and 2026110702. Burn covers the Burn/Aggro
category here; this is not a separate White Weenie qualification.

Native game execution took 25.547-35.635 seconds per game, 727.237 seconds
combined. Compilation and surrounding verification are not included in that sum.
Every game used the ordinary Default heuristic through the declared public-name
controller, with Monte Carlo disabled, an 80-global-turn cap, one processor and
a 1500 MB heap. Each game had a 180-second external bound.

## Identity And Evidence

- Host checkpoint commit: `3422b0ffac2fd2973114d6f13e34a7bf9417ae4e`.
- Candidate: `3973f642ee21856e748c23513dad120421e6a26c9ecde7acd6f0579bfee83f48`.
- Profile build: `aa624df73b49adc4181fcd437e6abb1f482e78a045a916633d501ace0d2e1375`.
- Thirteen source files and twenty-one physical override classes; actual loaded
  origins are recorded per game rather than assuming every class was used.
- Fifty-nine complete native card programs, exact declared decks, compiled probe
  classes and 59,971 base resource files passed before/after byte verification.
- Private operator archive: `native-six-archetype-and-cycle-20261107-i0iB5MXB`.
  Its manifest and all 779 tar member bytes were independently read back.

The unchanged legacy launcher blocked two system Python `.pth` startup attempts
before each JVM: 50 denied attempts across compile and 24 games. Its original
zero-attempt report concerns the JVM phase after the last installation marker,
not the entire launcher. There were no noncanary SQL/protected denials in that
JVM phase. The raw logs and this scope correction are both retained. A subsequent
focused probe uses Python `-S` without widening the guard, eliminating automatic
site processing; that does not retroactively change this baseline's logs.

## What Remains Unproven

This is stability evidence across six pairings, not all fifteen archetype
matchups, a source-matched old/new strength comparison, expert labels, a trained
policy, sideboarding or application best-of-three acceptance. Initial root
chooser actions and complete legal/affordable opportunity sets were not captured.
Opportunity metrics remain unavailable, not zero. A loss alone is not a defect.

Read-only review of the first eight games found funded Skullcrack held while
opposing Sheoldred life-gain triggers resolved, plus delayed nonlethal Bolt use.
These are concrete reproduction leads, not certified misplays. No friendly-fire
or action-proven missed-lethal defect was established by that bounded review.

A separate six-pose Oven/Familiar diagnostic observed one complete two-choice
AI cycle, three explicitly manual rules controls and two tapped-source refusals.
All actual paid cycles produced the expected life change and returned the same
physical card. Manual controls are not AI successes, and holding Oven on one's
own end step is not automatically wrong. The observed opponent-end-step seat
asymmetry and the life-gain response lead remain under investigation.
