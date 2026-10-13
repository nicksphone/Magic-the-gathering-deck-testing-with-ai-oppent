# Bounded Private CI Storage

The hosted `c2590095` backend job ends with a runner disk-exhaustion annotation
and only `EVIDENCE_MISSING` metadata. Its test counts and dominant storage
consumer are unknown. A public synthetic stream separately proves the old
launcher duplicates 16 MiB of pytest output into 32 MiB of private logs; this
does not establish that logging caused the hosted failure.

## Reviewed Infrastructure Scope

The launcher now keeps separate private shell and pytest streams, each bounded
to 8 MiB across current/previous files. Receipts record observed, retained and
dropped bytes, a whole-stream hash and explicit truncation. Truncated output
is never described as fully retained RAW. No private stream is published.

A 64 MiB fresh, identity-pinned reserve is allocated before protected input
decoding. The evidence output path is retained before that preparation. A
cooperative watcher samples storage once per second, releases the reserve and
interrupts its supervised pytest child at 1 GiB available bytes, 4,096 available
inodes or an observation error. Interrupted or incomplete phases keep a nonzero
result; missing nodes cannot become a passing suite. Sampling is not a kernel
quota or a guarantee that ENOSPC cannot occur between samples.

The existing 20 GiB admission floor, pytest argument list, discovery, observer,
metadata exporter, passed-snapshot cleanup and failure/unknown-owner protection
remain unchanged. The watcher does not scan/delete other scratch roots. The
privacy fixture uses the real bounded writer boundary for its existing failed
sink controls; its two observer-error assertions read `pytest.log`, not the
removed duplicate in `runner.log`. All error messages and strict publication,
metadata and exit-precedence assertions are preserved.

Independent review found that a background pytest process can inherit ignored
SIGINT before its configuration hook runs. The corrective native producer
prefix restores SIGINT before Python starts; all original pytest arguments
remain exact. Two genuine slow-startup controls prove interruption before
configuration. No watcher retry/escalation or new gameplay limits are added.

## Actual Acceptance

The owner's complete script suite passes all 169 tests: the original 153 plus
16 new controls, in 32.611 seconds, exit 0. The earlier 167-case compatibility
failures remain separate ledgers. A fresh parent composition over
`68d81bdd85b7a38615aebccfc3e4a76af82cb3c0` independently runs the same complete
discovery: **169 passed in 34.019 seconds, exit 0**, with unchanged non-graph
source. Bash syntax passes and the four parent code/test postimages equal the
tested composition. The new end-to-end public 16 MiB stream retains exact
metadata coverage and no public private-payload output.

Verified frozen owner evidence is under
`diagnostics/ci/current-c259-bounded-ci-storage169-20261013-2JP0LJUQ/` on RCHFiles;
the parent's source and unit evidence are separately archived under
`diagnostics/ci/68d81-ci-storage169-composed-20261013-gehh8a6T/`.

The owner's corrected complete suite passes **171 cases in 33.027 seconds**.
The first independent parent run has 169 passes and two failures: a public-FD
runner exits 2, and the startup control exceeds its unchanged four-second wait.
These exact cases then pass a retained diagnostic, and a single unchanged full
parent retry passes **all 171 in 95.773 seconds**, exit 0, with source equality.
The transient parent failures' cause is unresolved; they are not removed or
relabelled as passing. The corrected source has a separate static CLEAR receipt,
not a claim of hostile-process isolation or guaranteed CI timing.

The corrective increment and 171-case owner evidence are archived under
`diagnostics/ci/current-ci-pressure-startup171-20261013-9SD0nppG/`; the failed
parent cohort is separately preserved under
`diagnostics/ci/68d81-ci-startup-parent171-failed-20261013-fO5Y7yIb/`.
The unchanged passing parent retry is separately byte-verified under
`diagnostics/ci/68d81-ci-startup-parent171-passed-20261013-GKlmMGMT/`.

No protected trace was decoded for this unit qualification. No full backend,
application, hosted job or game was executed by this increment. A complete
current-source hosted backend result is still required; a truthful pressure
stop improves diagnosability, not release readiness or measured AI strength.
