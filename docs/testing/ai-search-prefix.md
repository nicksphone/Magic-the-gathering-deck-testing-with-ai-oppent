# Actor-Correct Search and Pinned Replay Inputs

## Implemented Boundary

Strategic scores retain the original player's perspective while each simulated
reply is executed by its actual priority owner. Previously, the selected reply
was replayed through `_strategic_line_score` using the original player as actor.
Wrong-seat actions could become no-ops or rejected branches and corrupt the score.

Search now continues the selected, already executed child and its computed score.
Costs, triggers, identity allocation and RNG are not executed a second time.
The six-candidate reply beam, difficulty horizons, ranked stable tie order,
min/max perspective and invalid-branch handling remain unchanged. Unselected
states are released before continuing deeper. This is not a global state cache.

The test reference retains the old replaying algorithm but explicitly corrects
the recursive actor. Optimization acceptance compares against that reference;
preservation of wrong-actor behavior is not an acceptance requirement.

Resolved deck manifests pin card metadata and roster order, verify canonical JSON
hashes and record input provenance. Import bypasses database bootstrap/hydration,
validates every deck before selecting a prefix, and rejects names-only, malformed,
over-limit or tampered inputs. Required `type_line` matches the game factory's
actual input contract; an unused `types` array is not a substitute. Hashes are
consistency evidence, not Oracle authenticity or complete semantics.

## Acceptance

- [x] Both seats and depths zero through three; six archetypes using actual
  Lightning Bolt/Counterspell effects, costs, targets and priority.
- [x] Correct reply actor, exactly-once execution, stable ties, terminal branches,
  rejected candidates and unchanged authoritative snapshots.
- [x] Export/import integrity, selected/source corpus hashes, malformed data,
  validation outside the selected roster and CLI database bypass.
- [x] Fixed-snapshot action/legal-move/root-state parity with the corrected
  reference, separate timing measurements and an instrumented memory sample.
- [x] Full backend gate, final affected follow-up, frontend gates, complete
  browser harness and repeated seat-balanced cross-archetype replay comparisons.
- [ ] Bound worst-case latency across wider token, choice and long-history states.
- [ ] Improve real decision quality, pending-choice planning and future resources;
  enforce a fair hidden-information boundary throughout deeper reply generation.

## Evidence: 2026-10-04

The original committed implementation fails 42 of the 57 new search tests,
including 36 real counterspell comparisons; the corrected implementation passes
all 57. These are regression cases, not independent games.

The full four-shard backend gate passes 6,765 tests across 285 files
(1,856 + 2,181 + 1,305 + 1,423). After it started, manifest validation was tightened
to require the actual factory's type-line field and one case was added. All 41
affected final-source manifest/protocol/progress tests pass. This is an incremental
final-source gate, not a second complete suite run. Source checks preserve the
unaffected files; search code is identical across the full/follow-up/browser runs.
Frontend lint, five unit/contract scripts, production build and all 41 Chromium
scripts pass. Browser gates include existing live BO3 and recovery paths.

Six BO1 samples, seed 4182 and 2,400-tick cap, cover both seat orders of Blue
Control/Ramp, Tempo/Tokens and Mono Red Aggro/Dimir Control. Each corrected
reference runs once and optimized search twice: 18 executions, six samples.
All complete game results and normalized logs match exactly. No timeout or scanned
announcement/cost error occurs. One resolution-time Drown in the Loch target
invalidation also exists in the old baseline; this is not an illegal announcement.
The six old buggy-baseline sample traces happen to match too, which does not
invalidate the directly reproduced search defect or prove strategic competence.

The final manifest CLI is also run independently: two seat-balanced samples,
each repeated, complete without drift/anomalies; export/reimport preserves inputs.
No SQLite database is created in that clean runtime checkout.

Six previously captured Control/Ramp positions are measured three times per
implementation in separate processes after the heavy gates finish. All 18 paired
actions/legal sets match, and all root snapshots remain unchanged:

| Position | Corrected replay median | Prefix median | Shorter |
| --- | ---: | ---: | ---: |
| 0 | 0.628 s | 0.467 s | 25.7% |
| 1 | 0.448 s | 0.358 s | 20.1% |
| 2 | 2.599 s | 1.808 s | 30.4% |
| 3 | 1.635 s | 1.230 s | 24.8% |
| 4 | 1.299 s | 0.970 s | 25.4% |
| 5 | 1.133 s | 0.974 s | 14.0% |

Timing is workload/environment-specific, not an HTTP SLA. A separate tracemalloc
sample of position 2 reports peak tracked allocations of 3,317,004 bytes for the
reference and 2,862,994 for prefix reuse. It preserves the decision/root snapshot;
tracked allocations are not process RSS or a broad memory bound. Instrumented
timing is deliberately excluded from the timing table.

## Newly Exposed Strategic Risks

Position 2 still chooses Fatal Push targeting its own Nissa-animated Underground
Sea with an empty stack. Both reference and optimized search reproduce this
existing bad choice. Root search's forced non-pass fallback is a likely contributing
path; fix shared optional-action utility without banning useful self-sacrifice,
death triggers or friendly targeting. Acceptance must show before/after board and
resource outcomes, not just fewer casts or fewer timeouts.

Deeper reply generation calls legal-move generation on authoritative opponent
state. Fair play requires explicit unexposed-hand/library invariance tests and an
information-set model rather than assuming the public-board heuristics establish
that boundary. Do not invent opponent cards or claim expert AI from replay parity.

Private snapshots, executable comparison scripts, pinned manifests, hashes and
logs are archived on RCHFiles under
`diagnostics/search-prefix/20261004-working`. They contain hands and are not public
match views. Completed scratch is removed after verified archival; live SQLite and
LAN services remain local. The broader release goals in `plan.md` remain open.
