# Captured Master decision investigation

The saved turn-29 Control position still exposes a practical latency problem.
On the `21f41aa8` backend, a separately bounded single-choice profile matches the
retained complete decision, action, fresh-agent history and authoritative
root/RNG. All 2,694 bound source files match before/after, no denied SQL, socket
or child operation occurs, and the supervisor reaps its worker and verifies the
process group is absent. No new natural game is executed.

The choice takes 49.47 seconds **under cProfile**, compared with the earlier
approximately twenty-one-second uninstrumented witness. Profiler timing is
allocation evidence, not an uninstrumented latency result. Cumulative figures
overlap. The profile has 945 total state copies, including 917 planning copies:

| Planning-copy caller | Calls |
| --- | --- |
| Stack-response lookahead | 305 |
| Pending-effect projection | 257 |
| Exact position-score cache keys | 148 |
| Strategic branch simulation | 64 |
| Other callers | 143 |

Pending-effect projection itself includes 140 settled-position forecasts,
96 pending-removal forecasts and 21 friendly-destruction forecasts. The existing
root rules-query scope is already present; adding it again is not a fix.

## Ranking-cache experiment, rejected

A candidate adds a temporary projection scope around an immutable ranking batch,
reusing a matching outer state/actor memo and inheriting the existing shared
combat allowance. In a canonical both-seat three-counterspell fixture, actual
counter-outcome computation falls from three to one with identical ranking and
source state. New root reuse, nested actor/state, error restoration, budget,
mutation-sensitive projection and thread-isolation controls pass.

The initial eight-case RED includes one new fixture mistake: it compares pickle
alias encodings across a deepcopy, which can differ without changing values.
After correcting that comparison to complete root values and RNG, unchanged
production reports five failures and three passes; the candidate reports eight
passes. A separate complete 23-module cohort passes **510 ordinary tests and
39 subtests**, zero failures/errors/skips, in 170.11 seconds, with 2,878 source
hashes equal and zero denied operations. JUnit reports 549 in its aggregate
attribute but contains 510 ordinary testcase elements; those are not 549 unique
tests. The initial metadata-verifier count assertion is retained, not rerun away.

The candidate's uninstrumented captured choice takes 20.23 seconds and matches
the complete baseline decision, action, fresh-agent history and root/RNG. Its
separate allocation profile still makes **945 total, 917 planning and 257
projection copies**. This is no demonstrated improvement to the targeted slow
choice. Passing regressions and the small counterspell fixture do not establish
practical latency acceptance.

Independent read-only review finds no actionable correctness defect and agrees
to retain the experiment without adoption. The private patch reproduces its
exact experimental Git tree. Both changed production files, its new test and
plan are restored/removed from the checkout; the backend/audit tree remains
exactly `21f41aa8`. The complete failed/passing epochs, candidate source,
allocation profiles and normal closure receipts remain retained. No natural
game or original matrix coordinate is retried.

## Scope and next investigation

Original whole-game AI history was not captured, so fresh-agent equality is not
that history's reconstruction. The original 998 accepted actions reconstruct
exactly, but their resource-limited game remains a partial. No strength,
completed-game, whole-matrix or release certificate follows from this work.

Continue with measured costs in actual simulated branches, including state-based
checks and the copy required for exact position-score keys. Preserve all search
lines, callbacks, state/RNG and information boundaries; do not lower allowances
or weaken cache keys to make a timing result look better.

Private evidence is under
`/home/nick/mtg-rc-evidence-20261108/master-decision-profile-21f/` and
`/home/nick/mtg-rc-evidence-20261108/ranking-projection-reuse/`. Raw game, action,
agent and snapshot bodies remain private and are not public fixtures.

## Adopted attachment preflight follow-up

The later [attachment check preflight](attachment-check-preflight-20261108.md)
finds and removes repeated classification work in the actual captured state:
one helper invocation makes 32 battlefield-scan generator calls instead of 992.
Its complete 317-test attachment/layer cohort, 998-action reconstruction and
fresh complete-decision comparison pass with source and process closure checks.
This leaves the rejected ranking experiment rejected. The single 19.54-second
choice witness does not close practical latency or establish a general speedup.

A separately declared post-change profile on `68b9fffb` matches the complete
fresh action/decision/agent-after and root/RNG, with all 2,695 source files and
input hashes unchanged and normal supervised closure. Instrumented duration is
47.56 seconds; total/planning copies remain 945/917. Layer-four scan-generator
calls fall from 5,803,456 to 4,795,845 across the entire choice. Attachment-check
calls remain 1,072, with less aggregate classification work. Profiler times overlap and are
not an uninstrumented latency comparison. Remaining caller data is retained for
choosing the next pure-query or allocation investigation; no speculative cache
or weaker position key is adopted.
