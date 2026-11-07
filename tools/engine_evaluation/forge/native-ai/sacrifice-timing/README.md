# Native Winning-Sacrifice Decisions

Opt-in, source-pinned correction for the common decision gates around a
sacrifice cost that already wins through a public death-drain trigger. Forge
Team/Card-Forge supplies the underlying engine, AI and canonical card programs;
this package modifies their work, not an independently authored rules engine.
See `NOTICE`, `LICENSE` and the repository's `THIRD-PARTY-NOTICES.md`.

The final candidate identity is
`7998ea519b319759b22abe1db526229be053914ffce643aa7d6f802e366a77d9`:
12 sources / 20 classes. The preceding counter prefix's ten sources and
seventeen classes remain byte-identical. Schema 9 requires both new sources
and all three newly overridden classes; incomplete closures are rejected.

## What Changes

- `SpellAbilityAi` can prefer an immediate, bounded sacrifice-cost win over
  discretionary timing and API-specific random reluctance. The normal API
  still assigns targets; current announced target validity, native restrictions,
  payment willingness, conditions and the controller's affordability checks remain.
- `AiController` does not discard a card marked `AI:RemoveDeck:All` when the
  same shared forecast establishes that cost win. The ordinary filter remains.
- The forecast only reads actor-visible sources before inspecting their bodies.
  It uses native typed costs and complete, literal loss/gain trigger bodies,
  not card names or a new Oracle-text interpreter. Effective native overrides
  take precedence over printed SVars; their API types must agree with the
  admitted body. It does not call `ensureAbility`, allocate abilities, simulate
  an actual hidden hand/library, or pay costs while forecasting.
- Replacement, protection, trigger-disable and unknown-body uncertainty withhold
  this override. That is not a comprehensive Magic threat forecaster.

## Runnable Cohort

All three frozen Java sources are unchanged from their independently declared
audits. The candidate-only runner compiles them once, then executes three fresh
native JVMs, sequentially, under a shared 300-second limit, 1,500 MiB heap and
one active processor each. It admits at most one other host JVM. Inputs are
read-only inside a network-isolated bubblewrap namespace; output must be fresh,
local and disjoint from inputs. This portable runner does not instrument native
SQL or claim zero attempted I/O.

```bash
python3 -B run.py /path/to/base/BUILD-IDENTITY.json \
  /path/to/old10-17/prefix /local/fresh-evidence \
  /path/to/final12-20/candidate
```

The old prefix is a pinned reference, not executed or silently substituted.
All 22 rows are mandatory; every observed override origin is checked, and
`AiController` / `SpellAbilityAi` must actually load from the candidate.
No unrelated class is forcibly loaded to inflate coverage.

- **Drain8:** ordinary first choices followed by real native payments and
  resolution, including Oven death-drain wins and usable/unusable Food.
- **Timing6:** Token, Draw and Scry cost wins, both seats. These repeat some
  Oven witnesses; they are not six independent bugs.
- **Preservation8:** eight ordinary choices are observations only, never judged
  or played. Afterward, the helper must refuse the supposed immediate win and
  an independently manual native Oven control must remain nonterminal under
  Rest in Peace, two opposing life, Platinum Angel or Hushbringer.

The final portable execution completed all 22 with exit 0 in 47.36 seconds.
Separate private internal-protocol suites passed 8 + 4 checks; those are not
ordinary AI decisions, natural games, or additional expert-play evidence.
Thirty-two synthetic runtime-profile tests also pass.

## Limits

This is not live adoption, trained-policy or strategic-strength acceptance.
The direct Oven/Food/Familiar two-action line without a death-drain observer
still fails both-seat ordinary-choice tests even though manual native controls
win. Four preceding-revision matched natural Drain games all completed without
native errors and all lost; they do not demonstrate stronger play or qualify
this final revision's natural-game behavior. Public delayed-trigger registry
interactions and self-sacrificing-creature outlet preferences remain unqualified.
See `KNOWN-ISSUES.md` and `docs/testing/native-sacrifice-cost-wins.md`.

`history/` retains the previous candidate3 manifest. Current source/class pins
are exclusively `CANDIDATE-PIN.json`; do not apply both a complete source
replacement and `SacrificeTiming.patch` to the same preimage.
