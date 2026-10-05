# Decision-local Destruction Projection Reuse

## Implemented Scope

Checked friendly-destruction forecasts and their settled public baseline can be
reused inside one synchronous decision for the exact root and acting seat. The
private cache retains one full root byte snapshot and scalar outcomes, not
mutable projected states. It does not change search depth or force matchup wins.

The fingerprint includes RNG, incarnations, alias structure, extra state fields
and the complete announced action. Serialization failure bypasses reuse; root or
action mutation invalidates it. True, false and unknown remain distinct. Missing
and available choice policies have separate keys, so a previously unknown
continuation cannot hide a newly resolvable choice.

Any projection invoking a choice callback is recomputed, including the shared
baseline. No purity assumption is made about agent objects, closures or bound
methods. Existing ContextVar isolation handles nested decisions, exceptions and
concurrent threads. Pickle serializes trusted local state for private byte
comparison only; no supplied data is unpickled.

## Verification

249 focused checks pass: 207 existing projection/search/removal/information-boundary
checks and 42 new reuse regressions. Real paid destruction cases retain harmful
removal rejection and profitable death-trigger wins. Canonical vanilla creatures
share one baseline; simultaneous own trigger-order choices remain unknown without
a policy and bypass caching when the policy executes.

Two reproduced defects were repaired before the final candidate was frozen:
missing-policy unknown reuse, and storing a root snapshot per target. Their
failed runs, corrected tests and the intentionally stopped superseded timing
experiment are preserved, not counted as passing final-source evidence.

The independently reproduced 1422 hotspot falls from 84 forecast invocations to
12 actual computations and one baseline settlement, with the same checked
decision and unchanged root. The complete isolated candidate gate passes all
7,352 backend tests. A separate 32-call, eight-state check compares full decisions,
including reasoning and paid states, across both versions and verifies hidden
identity invariance for both actors. Its first verifier mistakenly compared JSON
string keys with Python integer keys; comparing the actual saved JSON objects
proves equality. Both the failed verifier and corrected validation are retained.

## Pinned Benchmark

Reference: archived current main `a6c08fd`. Final production file SHA-256:
`6a391a8207722c850b49ea9b67bb7471993b100c9fedd09e7a667e6b240046b8`.
Eight states, ten fresh paired processes each, two decisions per process: 320
decision calls across 160 processes. Version order alternates; CPU 0 and
`PYTHONHASHSEED=0`; no profiling. Owned heavy gates run only after timing finishes.
All actions, legal counts, source and paid-result fingerprints match.

Predeclared gates pass: at least 50% overall median wall reduction at positions
1396 and 1422; elsewhere no median CPU increase greater than max(15%, 0.02 seconds).
Each first/warm cell below is a median of ten decisions; the reduction column
uses the overall twenty-decision median per version.

| Position | Reference first / warm | Reuse first / warm | Overall wall reduction |
| --- | ---: | ---: | ---: |
| 1169 | 2.122 / 2.127 s | 2.108 / 2.112 s | 0.6% |
| 1234 | 7.212 / 7.164 s | 7.199 / 7.179 s | 0.3% |
| 1396 | 19.855 / 19.870 s | 6.583 / 6.553 s | 66.9% |
| 1422 | 21.043 / 21.078 s | 4.632 / 4.614 s | 78.0% |
| 1169-successor | 0.842 / 0.819 s | 0.847 / 0.823 s | -0.6% |
| 1396-successor | 0.034 / 0.013 s | 0.034 / 0.013 s | -0.7% |
| red-seat1 | 0.051 / 0.019 s | 0.051 / 0.019 s | 0.7% |
| ramp-seat2 | 0.048 / 0.016 s | 0.048 / 0.016 s | 0.5% |

Timing excludes hydration, legal generation and checked execution. First means
the first decision in a fresh interpreter, not a cold OS cache. Host scheduling
is not exclusive; these are workload measurements, not an HTTP latency SLA.

## Combined Backend and Replay Acceptance

The final combined gate includes subsequent public land-allowance and explicit
human progression repairs: **7,354 backend tests pass**, independently of the
earlier 7,352-test cache-only run. The six-deck replay uses verbatim unions of
three verified resolved manifests: Blue Control, Ramp, Tempo, Tokens, Mono Red
Aggro and Dimir Control. Fifteen pairings run both seat orders, with two repeated
executions per sample: thirty logical samples and sixty executions, BO1, Master,
6,000-tick unresolved policy, three bounded workers. Name-derived seeds are
unchanged by sharding. Complete private match traces are retained, including
actor hands, boards, legal action types and announced actions. Repeated runs are
not independent balance samples. All thirty samples complete without timeout,
drift or matching announcement/cost/target error lines. Independent verification
compares every full repeated result, exact manifest subsets and both-seat schedule;
all 36,234 decision traces retain their hands, boards and action metadata.

The outer matrix tool session reports termination 143 after all child reports and
the final summary were emitted. The final independent verifier passes; no missing
wrapper exit is invented and no completed games are rerun to manufacture one.
The complete final-source browser harness passes with the corrected async
readiness helper, including natural human/AI and human/human BO3 and restart
recovery. This is a separate accepted run, not an inference from earlier runs.

Recorded-action reconstruction also matches complete events and logs for all
thirty logical samples and 18,117 decisions. It finds zero passes with a legal
land opportunity and 138 passes with a cast opportunity. Such passes are not
automatically mistakes: holding counters or avoiding harmful friendly removal
can be correct. Forty captured review states are biased toward Control and Ramp;
a balanced per-style strategic review remains necessary before quality claims.

Completed source copies, raw benchmark distributions, failed development checks,
full browser output and private replay traces are archived and verified under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-destruction-reuse/20261005T001012Z/`.
The archive includes checksum readback and tar-to-source comparison. Live SQLite
and running development services were not moved or mutated by these checks.

## Known Limitations and Next Upgrades

This optimization preserves decisions; it does not prove they are optimal.
Complex policy-bearing continuations deliberately remain uncached. Whole-root
fingerprinting still costs work and is not a general semantic dependency cache.
Several measured decisions remain multiple seconds. Broader uncertain-outcome
forecasts, opponent beliefs, resource strategy, long-session latency and
arbitrary-card rules fidelity remain open.
