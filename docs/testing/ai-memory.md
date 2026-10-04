# Revealed-Hand Memory and Selective Private Copies

## Completed Checklist

- [x] Store authorized observations in private snapshots, not public card views.
- [x] Record supported whole-hand reveals before filtering selectable cards;
  excluded lands remain legally known. Record supported public zone events,
  revealed searches, and public returns to hand through the shared effect path.
- [x] Reconstruct remembered hand data from the observation, not current hidden
  metadata. Track zone-change incarnation; a hidden library trip invalidates
  physical-ID recall even after the card is drawn again.
- [x] Remove inaccessible stale ledger records from AI views, including hidden
  libraries and face-down exile. Forecasts cannot create authoritative knowledge.
- [x] Seed selective deepcopy before traversal; do not copy unseen card metadata
  or another pilot's submitted deck. Preserve aliases, normal planning copies,
  visible mutable-data isolation, and the authoritative root.
- [x] Count owned non-library land copies across controllers, excluding tokens,
  in the existing known-list land-search upper bound.
- [x] Validate both seats, actual reveal/cast/response legality, six archetype
  search paths, old snapshots, HTTP/SQLite startup recovery and repeated matches.

## Runtime Contract

`MatchState.card_observations` records per-viewer last authorized printed/object
data. Supported hand reveals, public events, searches and public-to-hand effects
populate it. Snapshot serialization preserves it; public match serialization does
not expose it. Legacy snapshots default to an empty ledger.

Agent copies restore an opposing hand identity only when its observed incarnation
is still valid. Restored data comes from the ledger, not subsequently altered
hidden fields. Ordinary unexposed cards remain opaque unknowns. Library ordering
is never reconstructed from stable physical card IDs, and stale private ledger
entries do not escape through the decision copy. Owner-authorized inspection and
foretell behavior remain separate existing permissions.

The existing submitted-list land estimate remains an upper bound, capped by
library size. Stolen owned lands consume submitted inventory; token land copies
do not. This does not model all hidden removals or future resource uncertainty.

## Acceptance Evidence

Baseline is committed revision `a69233fa5e037ae90320a972da6f5d601ac2bfcd`.
The selective-copy/known-inventory reproduction gives six failures and one pass
on that source. Final code adds 32 tests: five selective-copy cases, 25 observation
cases and two inventory cases. Synthetic private metadata raises if deep-copied,
demonstrating that hidden data is skipped rather than copied and erased afterward.
Canonical card fixtures exercise actual revealed-counter reply availability;
six-style search checks inspect actor-correct materialization rather than claiming
strategic superiority from an archetype label.

Final source passes 7,053 backend tests across 291 files in four disposable-source
shards: 1,941 + 1,375 + 1,742 + 1,995. Source-relative SQLite paths are isolated.
Frontend lint, five unit-contract scripts and build pass; all 41 Chromium scripts
pass on the pre-final ledger-filter stage. The final filter is additionally checked
through human-action, surveil and human BO3 browser follow-ups after fixture API
restart. No frontend or public API contract is changed by this batch.

An HTTP probe resolves actual Coercion and its owned discard choice, then starts
a fresh TestClient lifespan after clearing the in-memory match. Startup restores
the exact SQLite snapshot and six remaining revealed Swamps; the public response
omits the ledger. The initial probe incorrectly expected GET alone to restore a
removed in-memory match and failed with 404; corrected evidence tests the actual
startup recovery contract, not a nonexistent lazy-GET restoration feature.

Pinned Blue Control/Ramp, Tempo/Tokens, Mono Red Aggro/Dimir Control, Tribal/Drain,
and Midrange/White Weenie inputs each run both seat orders at seed 4182, Master,
with a 2,400-tick cap. Each of ten samples repeats twice on both the earlier and
final code stages: 40 executions, not 40 independent balance samples. Complete
results/logs match within each repeat; zero timeouts and zero lines matching the
recorded cast/payment-error scan. Inputs are resolved offline seed metadata, not
whole-card Oracle certification or tournament-strength evidence.

Ten opening snapshots measured 21 calls per copy function. Selective-view median
preparation time is 48.2-84.5% lower than the prior copy-then-mask implementation;
single-call tracemalloc peaks are 36.3-37.1% lower. Card-view parity and unchanged
root snapshots are checked. These measurements ran under concurrent test load;
they do not establish whole-game speedups, RSS bounds, or worst-case search latency.

Private terminal logs, exact source-stage archives, pinned manifests, benchmark
records and recovery probes are archived under RCHFiles
`diagnostics/ai-memory/20261004-working/` after verification.

## Remaining Boundaries

- Public library-card pools/order knowledge require an uncertainty model; this
  implementation deliberately does not restore shuffled identities by instance ID.
- Opponent deck priors, sampled unseen replies, bluffing, and belief updates from
  public play remain unfinished. Known hand memory is not information-set search.
- Not every reveal/inspection mechanic records durable observations yet. This
  batch certifies the tested paths, not arbitrary Oracle wording or whole cards.
- Complex replacement/trigger continuations, long-game planning latency and expert
  decision quality still require their own acceptance gates.
- The frontend redesign is delegated through `uiplan`, not delivered here.
