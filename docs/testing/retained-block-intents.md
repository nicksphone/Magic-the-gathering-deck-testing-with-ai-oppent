# Retained Block Intents

Master can exhaust its shared combat allowance while ranking a block declaration.
Previously, ranking evaluated an allocation but returned the original unselected
move descriptor. Final materialization searched again, now without an allowance,
and could replace that allocation with the greedy fallback.

## Correction

Ranking copies block descriptors and keeps the allocation with the intent it
scores. A private completion marker distinguishes a selected empty plan from a
generic descriptor's empty map. Materialization consumes that marker before
returning the action. Existing generic-descriptor selection and bare complete
empty-block actions retain their prior behavior. The caller's legal-move list
remains unchanged.

A partial search that has established only defeat does not displace the legal
fallback after denial. Native draws (`winner == 0`) are not classified as defeat.
Existing final declaration normalization and native validation still apply.

Only `_rank_moves_query`, the block branch of
`_materialize_action_without_resources`, and `_search_block_assignments` changed.
Other method bodies and module bytes outside those methods are unchanged.
There is no new cache, allowance, evaluation weight, difficulty or learned model.
Card rules, action schemas and engine execution are unchanged.

## Focused Evidence

The new canonical Hill Giant/Grizzly Bears checks use declared old-board poses,
real checked attack/block declarations and actual combat resolution in both
seats. They are not naturally drawn games or complete deck-inventory certificates.

- The final twelve-case module exercises public `choose_action`, private ranking,
  complete empty actions and compatibility with empty generic descriptors. Exact
  preimage code failed four and passed eight. At three life, its public decisions
  lost in both seats; the correction blocks lethal damage and survives. The
  corrected module passes all twelve. Baseline-safe public choices and existing
  descriptor semantics are not counted as newly fixed cases.
- Six separately labelled endpoint-utility checks distinguish a native draw,
  defeat and victory under denial. The endpoints come from genuine checked,
  paid Crypt Rats/Bolt outcomes, delivered at the finishing seam. These checks
  isolate ranking utility; they do not claim the vanilla combat fixture produces
  those terminal outcomes. The draw cases first failed, then passed after review
  corrected the draw classification.
- The two new modules, unchanged terminal-outcome module and unchanged learned
  empty-proposal module pass together: **56 passed in 22.21 seconds**.
- The final affected pure qualification covers **34 whole modules** in three
  independent, timing-balanced process shards: **237**, **213 plus six passed
  subtests**, and **483** ordinary passes. The union is **933 ordinary passes
  plus six subtests**, with no failures, errors, skips or deselections. This is
  three cohorts, not a single serial run of all 34 modules. All 915 inherited
  ordinary node identities and inherited test bytes match the unchanged input
  modules; the eighteen new checks account for the remainder.
- The final two whole HTTP-backed combat modules pass on a fresh isolated local
  database: **114 passed in 83.75 seconds**, with source equality and no remaining
  database descriptors, jobs or new threads after disposal.

These are distinct cohorts, with overlap in the focused checks. They are not a
summed full-suite result. SQL, networking and subprocesses are denied before
project imports in the pure cohorts; the HTTP cohort permits only its declared
owned local SQLite paths. No live database is used or restored.

Two final-version, source-pinned, default-Master decisions used the original
reconstructed Drain/Tribal position and a 105-hidden-card-body variant. Both
retain the same checked action and native outcome. The trace confirms zero
`_choose_blocks` or `_search_block_assignments` calls after ranking returns;
the selected allocation survives sticky denial into final materialization.
Original state, legal offers and RNG remain unchanged; the private completion
marker is absent from the public decisions. These are two fresh-agent diagnostics,
not restored AI-memory histories, whole games or latency benchmarks. Earlier
candidate diagnostics are preserved separately rather than relabelled final.

## Limits

The original observed Drain/Tribal block involved a real life/material tradeoff.
Its evaluated allocation and later fallback happened to agree. This correction
does not establish that allocation as optimal or fix a proved mistake at that
particular position. Historical unavailable block-quality metrics remain
unavailable, rather than being retroactively replaced by the new checks.

An interrupted first broad run is retained as partial evidence, not a pass. It
was explicitly stopped for the draw-classification review finding. A subsequent
serial thirty-module run completed with **830 passed, two failed and six passed
subtests**: the two existing learned-proposal checks exposed the generic empty
descriptor contract. Those tests were not changed. The local completion marker
corrects that regression. Two earlier new-test expectations incorrectly treated
a full generic empty descriptor as a completed action; their original tests and
results are retained as superseded assumptions, not legitimate consumer bugs.
An earlier six-failure test-boundary mistake bypassed the public declaration
normalizer and is likewise retained separately. Whole-game playing strength,
sideboarding, current UI behavior and overall AI acceptance remain separate.
