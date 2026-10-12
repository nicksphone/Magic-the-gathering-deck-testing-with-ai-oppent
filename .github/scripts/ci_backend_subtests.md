# Pytest Subreport Evidence

Pytest 9 emits exact `_pytest.subtests.SubtestReport` instances for individual
`unittest.TestCase.subTest` observations. They share their collected parent's
node ID and `call` phase but are not additional executions of that parent.

The observer preserves each such report, in order, in `subtests.jsonl`. Ordinary
reports remain in `phases.jsonl`; their existing duplicate-phase rejection is
unchanged. Only the exact imported subreport class is routed separately.
Missing `_pytest.subtests` on pytest 8 or a stdlib-only auditor is supported;
other dependency import errors are not silently ignored.

The safe artifact remains schema version 1 with an additive `subtests` array.
Each row contains the hashed complete parent identity, a zero-based
`subtest_index` within this ledger, `phase`, unchanged `outcome`, `xfail_marker`,
and finite numeric `duration_seconds` in 0..86400 or null. Context, message,
keyword arguments, parameters, log excerpts and exception representations are
not read or exported through this channel. The ordinal identifies an observed
report occurrence, not an independently collected or parametrized test case.

When subreports exist, coverage additionally exposes `subtest_report_count`
and `subtest_counts`. Failure rows include each failed subreport with
`report_kind: subtest` and its ordinal. A failed subreport vetoes release
consistency even if the parent passes and the recorded pytest exit is zero.
Skipped subreports retain `skipped`; they are never counted as passes. Invalid
subreport outcomes/phases or unknown collected-parent identities fail closed.
No subreport repairs missing or duplicate ordinary phases.

The original 7c artifact is not rewritten or deduplicated: it remains a failed
qualification with 15 duplicate call rows. The prospective corrected pipeline
retains those observations as 15 subreports plus six ordinary reports for the
two collected public SQL-guard methods. Actual local pytest 9 reproductions
cover passing, failing and skipped subreport outcomes.

## Qualification

The original 146 script checks plus seven new controls pass together on the
isolated correction: 153 passes in 19.134 seconds. Independent parent execution
records 151 passes and two unchanged snapshot-cleanup failures in 45.085 seconds.
Both failures reproduce on exact pre-correction `7c711d23`: zero passes, two
failures in 26.240 seconds. Their five-second `fuser` check times out and correctly
retains the backup. The cleanup policy and original assertions are unchanged.
An independent closed-file probe completes with empty output and status 1 after
13.510 seconds; this measurement does not establish an OS or storage cause.

The original duplicate guard and all seven subreport controls pass in the parent
run. This supports the reporter correction, not a green overall release. A new
hosted full-backend run must qualify the actual composed revision.
