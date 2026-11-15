# Terminal Master Block-Flag Triage

Status: triage complete; strategic adjudication and AI improvement remain open.
All fifteen recorded block flags remain in the original
[terminal matrix](full-master-matrix-20261108.md). No game was restarted, no
counter or availability value changed, and no policy was changed.

## Recorded Scope

The original `a4f8df9` matrix has 267 natural games and four deadline partials.
Its fifteen available block flags occur in thirteen decisions in thirteen natural
games. The denominator of 484 is available **game-seat samples**, not block
opportunities; neither `15/484` nor `13/267` is an error rate.

The incremental intake reuses the hashes of 192 previously inspected natural
receipts, revalidates their five flagged contexts against five original receipts,
and inspects the remaining 75 natural receipts. Those eighty content reads retain
the earlier six flags and find nine further flags. All eighty opened receipts
match the final hash manifest; all 2,691 frozen backend source files verify,
including Git blob IDs. No AI,
rules, games or metric recomputation runs during this intake.

The decision contexts contain the acting player's hand, both public battlefields,
current life/mana/stack/turn, chosen action and reasoning. Opponent hands and
eventual outcomes are excluded. A separate thirteen-receipt read selects only the
last public attack action before each flagged decision. It does not restore
attack targets, subsequently created attacking tokens, graveyards, continuous
effect operands or other missing state. These compact traces cannot support
exact decision-state replay.

## What The Counter Establishes

`analytics.decision_quality._validated_bad_blocks` checks copied native outcomes
for the selected allocation and no block. It counts an accepted attacker that
survives while at least one assigned blocker reaches the graveyard, provided
neither outcome loses for the defender. Unresolved outcomes remain unavailable.

That establishes an observed life/material trade under the counter's bounded
resolution. It does not establish that preserving the blocker is strategically
better. It also does not compare each flagged assignment against a plan that
retains other useful blocks. Eight recorded decisions have another assigned
block group beyond their one flag; five have as many assigned groups as flags,
accounting for the remaining seven flags. These are allocation-shape counts,
not independent native outcome adjudications.

The visible cases include substantial life saved, mixed allocations and recurring
creatures. Missing state prevents a complete tactical comparison. None of the
fifteen flags has been certified here as either a mistake or an optimal choice.
The existing metric name and historical counts are retained.

## Separate Canonical Counterfactual

A new controlled old-board fixture uses full pinned canonical records for Elvish
Warmaster, Bloodtithe Harvester, Hopeful Initiate and Adeline, Resplendent Cathar.
Warmaster has two explicitly declared runtime `+1/+1` counters. There are no
intervening plays or hidden-hand inference. This is an analogue of a mixed
allocation, not a reconstruction of an old game, paid-entry test or strength
benchmark.

Both seats produce the same checked outcomes:

| Allocation | Defender life after combat | Friendly losses | Opposing losses | Fixture flag |
| --- | ---: | --- | --- | ---: |
| Initiate blocks Warmaster; Adeline blocks Harvester | 20 | Initiate | Harvester | 1 |
| Retain Initiate; Adeline blocks Harvester | 16 | None | Harvester | 0 |
| No block | 13 | None | None | Not recomputed |

All three lines finish with no winner. The six direct checked combat lines and
four metric calls run only on these two new fixture positions. Metric calls keep
their own bounded internal projections. These operations leave the roots
unchanged and make zero AI choices or natural games. All 5,132 public source
file hashes and recorded Git blobs verify before and after execution. The full
2,697-file backend and thirty operator files match candidate `fec27003`.

A subsequent, separately declared diagnostic permits exactly one top-level
current Master Tokens choice per seat, with default internal planning and its
limits unchanged. Both choices
select the first allocation above. A delegating search observer records that
the native two-attacker/two-blocker search returns that allocation; its retained
plan reaches the checked action unchanged. Each direct chosen combat completes
with the corresponding one fixture flag. Root state, offered moves and global
RNG stay unchanged. This is two diagnostic choices, not an old/new comparison.

The source explains a candidate mechanism: the search's nonlethal chump
rejection/penalty uses aggregate friendly and opposing losses. The mixed plan
loses one creature on each side, so it is not rejected by that aggregate check;
life saved contributes to the score. This source observation and controlled
diagnostic do not prove that this branch caused each historical flag or that
changing it would improve play. A policy change needs a tactical objective and
counterexamples for lethal survival, profitable blocks, triggers and racing,
followed by meaningful matched evaluation.

## Execution And Limits

The first analogue attempt stops during fixture placement: the existing helper
does not recognize the Adventure card's Factory name. It executes no combat
comparison or AI choice. A preceding metadata precheck also used an incorrect
expected file count; it is not source qualification. Both setup observations are
retained. The corrected, non-Adventure fixture verifies its actual 2,727-file
backend/operator comparison before launch; the executed worker separately
verifies all 5,132 packet files.

The actual extracted native audit guard passes thirteen denial controls for SQL
constructors, sockets, children, shell execution, OpenAI import, newly created
synthetic protected-name files and a foreign content write. The same guard AST
is bound to both successful native drivers. This is a content-write/runtime-I/O
fence, not a general filesystem sandbox. Runtime denial counts are zero. All
three supervised workers—the intake, failed setup and successful counterfactual—
plus the separate choice worker are directly reaped with explicit process-group
absence and no outer stop. The short public-attack metadata reader exits zero
without launching a child.

Private evidence is retained in
`/home/nick/mtg-rc-evidence-20261108/block-flag-review-final/`; raw receipts, hands
and context bodies are not committed. The collection, counterfactual and choice
budgets remain separate. No pytest suite, full game, A/B improvement, expert-AI
qualification or release gate is claimed by this diagnostic.

The next step is a lossless, actor-visible tactical benchmark for mixed blocks
with explicit survival and material objectives. It must cover useful chumps as
well as wasteful ones before a production scoring change. The original four
partials, unavailable metrics, 106 unused-mana flags, thirteen-style coverage,
timing, matched gameplay and broader AI/data requirements remain open.
