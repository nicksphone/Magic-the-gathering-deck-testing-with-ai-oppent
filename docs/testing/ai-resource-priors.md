# Known-Composition Draw and Rummage Priors

## Scope

The AI now uses its own submitted deck composition minus known owned non-library
cards to estimate unknown draws in supported discard/draw decisions. It does not
read hidden library identities or order. A forecast returns expected land/nonland
counts and the exact hypergeometric probability of drawing at least one land
without replacement. These are priors, not actual future card instances.

The same nonland curve/archetype retention function prices held cards and known
submitted nonland descriptors. Discard/draw trades therefore do not award a fixed
five-point credit to an equally expensive replacement card. Land credit uses the
public board and hand after the proposed discards. Supported optional rummaging
and whole-hand draw admission share this forecast; actual resolution still uses
ordinary engine effects, replacement/cap counts, legal choices and payments.

Forecasts require the matching pilot's private decision view and fully reconciled
inventory. Old snapshots, unresolved or conflicting metadata, unsupported card
faces, inaccessible non-library cards, inconsistent population, known inspection
candidates, and out-of-bounds draws return explicit unknown. The existing generic
draw valuation remains the fallback; no invented cards or fabricated certainty
are introduced. Tokens do not consume submitted inventory; owned stolen cards do.

During an owned resolution choice, the public spell source remains in the stack
zone even after its queue item is removed. Private views now retain that public
source, rather than making its identity opaque and breaking inventory accounting.

## Acceptance Checklist

- [x] Reproduce real discard decisions on the committed baseline.
- [x] Check both seats, six style labels, and Casual/Strong/Master decisions.
- [x] Preserve useful expensive cards in a land-heavy remaining composition.
- [x] Retain productive recycling when the public board is land-light or remaining
  composition is spell-heavy; do not ban rummaging or force deck win rates.
- [x] Check exact probabilities, hidden-identity/order invariance, snapshot parity,
  private actor ownership, known-candidate invalidation and conservative fallbacks.
- [x] Preserve public resolving-spell visibility through durable choices.
- [x] Pass the 468-check focused gate, including existing draw restrictions,
  information boundaries, memory, linked discard and actual effect resolution.
- [x] Complete final production-source isolated full backend suite and frontend gates.
- [x] Review terminal pinned seed/seat replay results, drift and error scans.

Publication evidence is retained with the archive receipt; this checklist does
not establish broader release readiness or expert AI.

## Evidence

Baseline: `f35cb4bc8fc21f6f166e2eb4ec621fc875ce08ad`.
The final 82-case selection on that source produces 66 failures and 16 passes.
Failures include missing new forecast APIs, not 66 independent gameplay defects.
The actual optional-rummage decision cases fail across both seats, six styles and
three difficulty levels; existing positive recycling behavior is retained.

Fixtures use canonical Cathartic Pyre, Tolarian Winds, Dangerous Wager, Ugin,
Lightning Bolt and Mountain metadata from existing sources. These are controlled
interaction positions, not claims of balanced competitive deck construction.
Cathartic Pyre is actually cast, paid, and resolved to the owned discard choice;
accepted selected-card actions run through checked engine resolution.

All tests run from disposable source because database paths are source-relative.
No live database, frontend source or public API contract is modified by this batch.
This isolated heuristic follows the capability-batch protocol: frontend gates run,
but unchanged browser layouts do not receive another full visual regression claim.

The corrected production source passes 7,135 tests across 292 distinct files in
four isolated shards: 2,372 + 1,405 + 1,461 + 1,897. The earlier gate caught six
missing-zone compatibility failures in lightweight fixtures; all pass after the
shared defensive read. A subsequent fixture-only improvement replaces black
lands with Mountains alongside red spells. The 468-check affected selection
passes again; the production files are byte-identical to the frozen full gate.
Both fixture versions and their results are preserved rather than presenting the
earlier full gate as a later all-file rerun.

Frontend lint, five unit-contract scripts and build pass. Two-seat HTTP probes
verify atomic wrong-actor rejection, exact pending-choice SQLite startup recovery,
unchanged priors and the checked keep-hand decision. Private lists/observations
remain absent from the public response. The probes are rerun after fixture cleanup.

Ten pinned seed/seat samples cover Blue Control/Ramp, Tempo/Tokens, Mono Red
Aggro/Dimir Control, Tribal/Drain, and Midrange/White Weenie at seed 4182, Master,
with a 2,400-tick cap. Each repeats twice on the pre-compatibility-guard stage;
the final production source gets ten further executions matched to those complete
results/logs. Thirty executions represent ten samples, not a balance study.
There are zero timeouts, result/log differences, or lines matching the recorded
cast/payment-error scan. Resolved offline input provenance does not certify all
card semantics.

Exact source stages, terminal logs, manifests, probes and publication receipt are
archived privately under RCHFiles `diagnostics/ai-resource-priors/20261004-working/`.

## Remaining Boundaries

- Land utility remains a heuristic, not color-specific future payment feasibility,
  multi-draw diminishing utility or an optimized horizon policy.
- The exchangeable prior is not an ordered-library or belief-state model. Persistent
  scry knowledge, opponent priors, sampled responses, bluffing and inference remain
  unfinished. Current authorized library candidates invalidate this forecast.
- Nonland credit reuses the existing curve/role heuristic, not full tactical value
  of every card or graveyard strategy. Broader optional-draw and kicker planning
  still have their own limitations.
- Replay repeatability and decision probes do not establish tournament strength,
  arbitrary-card rules correctness, matchup balance or worst-case planning latency.
