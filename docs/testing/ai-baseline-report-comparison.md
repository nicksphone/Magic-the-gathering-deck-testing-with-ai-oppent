# Bound Baseline Report Comparison

This is an additive artifact-validation capability on source
`aa7fdc6250a0770f225ec8c704740b709f03527d`, not a measurement of improved AI,
a complete BO3 matrix, Phase 2-4 acceptance or release qualification.

The latest combined qualification passes all 155 ordinary cases in both whole
modules, including the original CLI subprocess. The earlier 139-case child-denial
ledger below remains historical evidence; it is not the final corrected result.

The existing report shape, report-building functions, original CLI and entire
original baseline-report test module are unchanged. Opt in with:

```sh
python scripts/baseline_report.py compare --before before-package.json --after after-package.json
```

Each file is a regular non-symlink JSON file bounded to 1 MiB. Duplicate object
keys and nonfinite values are rejected. Each package has exactly `report` (the
existing report) and `measurement` (the new comparison-only receipt). No raw
trace, SQL, provider, simulation or child launch is used by this mode.

## Receipt Contract

Receipt schema version 1 requires all of these fields, with no unknown fields:

- `schema_version`, `source_base_commit`, `backend_before_sha256`, `backend_after_sha256`.
- `corpus_sha256`, `export_sha256`, `metric_definitions_sha256`, `report_sha256`.
- `engine_rules_sha256`, `controlled_policy_sha256`, `experimental_features`, `policy_configuration_sha256`.
- `difficulty`, `max_ticks`, all 14 `limits`, `sideboard_mode: fixed_no_swaps`.
- `schedule_kind: fixed_games`, `roster`, `seeds`, `seats: [1, 2]`.
- `complete: true`, `status: completed_schedule`, `planned_games`, `attempted_games`, `not_run_games: 0`, `samples`.

Each roster row has exactly `name`, `archetype`, `content_sha256`. Each sample
has exactly `deck_a`, `deck_b`, `seed_token`, `deck_a_seat`, `evidence_complete`,
`status`, `winner`. Every unordered declared deck pair, seed and seat must occur
once. Samples are explicit resolved games (integer winner 1 or 2) or completed
fixed-game timeout outcomes (null winner); a resource stop is not an outcome.
Each sample must have complete evidence. Report matchup totals and Wilson
intervals must agree with these outcomes. Fully unresolved pairs are unavailable.

Digests use SHA-256 of UTF-8 JSON with sorted keys, compact separators and
`allow_nan=False`. The source-before and source-after digests must agree within
each measurement. Baseline and candidate sources may differ; data, definitions,
roster, seeds, seats and caps must match. Cache/Oracle/priors summaries must be
complete, typed, internally consistent and identical across the comparison.
All anomaly/quality counters must be explicit nonnegative integers; unavailable
metrics, booleans, floats-as-counts, missing evidence and duplicate samples fail
closed. Limits may not exceed the existing resource policy.

Engine/rules and the unchanged remainder of the AI policy are controlled inputs
and must match. `experimental_features` is a nonempty map of explicitly declared
original-plan slices (`task2.3`, `task3.2`, `task4.1`, `task4.2`, `task4.3`,
`task4.5`) to per-measurement feature/configuration SHA-256 identities. Both
measurements must declare the same feature keys; their values may differ.
`policy_configuration_sha256` is the canonical digest of the object containing
exactly `controlled_policy_sha256` and `experimental_features`. The resulting
whole policy-configuration identity and whole backend-code identity may differ
across A/B; neither is required to equal the other measurement's identity.
Output retains both provenance records. No caller-controlled mismatch list,
unknown feature, engine change, data change, mode change or budget change is
admitted. Feature hashes can bind changed policy-weight artifacts; unaffected
policy components remain controlled. The producer must independently establish
the truthful reviewed feature/control partition, not label arbitrary changes
as a permitted experiment. No actual source/config partition is inferred from
an opaque hash by this validator.

Receipts are declarations bound to reports, not cryptographic proof of actual
execution or verified source-file bodies. The producer/operator must supply
authentic closed source/data/measurement evidence separately. This does not
create such evidence from an old report or convert a round-robin summary into
a qualified fixed-game report. Declared-roster coverage is not all-builtin,
BO3 or thirteen-style coverage. Unequal or incomplete real measurements still
need resolution outside this validator; no budgets, metrics or AI are changed.

## Results And Limits

Output distinguishes comparable artifacts from unavailable evidence, lists
every quality/anomaly delta and counter regression, and flags pair movement
strictly greater than 15 percentage points using unrounded ratios. Reported
ordinal labels avoid echoing input deck names, paths or bodies. Non-regression
is not strict improvement. Explicit original metric directions include
post-P2, post-P3, lethal, unused-mana, play-order/spread and final metric checks.
Unexplained pass-priority clusters remain unavailable: the existing report has
no such metric. Exit 0 requires comparable artifacts meeting the final metric
checks; otherwise exit 2. This is not a full-plan acceptance verdict.

The immutable September pre-baseline has unknown `bad_blocks` and zero recorded
`lethal_misses`; this tool does not replace unknown with zero or manufacture a
strict decrease from zero. Authentic comparable measurements and any explicit
measurement-design reconciliation remain required.

## Bounded Pure Evidence

Two whole modules were executed under pre-import SQL/socket/child/provider and
foreign-write denial, at 900 seconds with 15 seconds cleanup, with no pruning.
The original module has 29 cases. Its real CLI subprocess case cannot pass
under blanket child denial; it remains an ordinary failure, not a skip or
invented child result. No child exception was granted or used.

TDD: all initial 85 new cases failed before production changes; then all 85
passed. Nine additional data-summary negatives reproduced a real admission gap
before its correction; that 96-pass epoch remains immutable. A separate
controlled-experiment correction reproduced 10 new-module failures/100 passes
before correction. Final new-module result: 110 ordinary passes. Final
whole-two-module result: 138 passes, one preserved child-denial failure, zero
errors/skips, 139 ordered identities and 417 phases in 3.60 seconds. Thus full
whole-original CLI qualification is still HOLD, not GREEN.

All seven native denial canaries passed before project/pytest imports. Full
source and fresh runtime inventories (3,674 files, four links, 429 directories)
matched before/after; no database was created, no unexpected denial occurred,
and FD/thread/child/process closure was verified. No App, real match, SQL,
network, provider, browser or native lease was executed. A separate exact-child
scope and qualification would be needed to clear the unchanged CLI test.

## Oracle Coverage Correction

Independent review found that the preceding validator accepted empty status
maps alongside a positive measured card count. This was reproduced, not waived:
11 new strict controls failed while115 cases passed on that source. The minimal
admission correction requires the sum of unique status counts to equal the
cache summary's total cards, identical unique/weighted status support, strictly
positive unique counts, and weighted counts at least as large as unique counts
per status for the current positive-quantity measured corpus. Legitimate multiple
status categories and greater copy-weighted counts remain valid; status names
are not hardcoded. Existing shipped deck literals and catalog quantities were
checked read-only; this is not a new corpus execution or coverage certificate.

The real Oracle producer permits an empty diagnostic corpus. Legacy reporting
of that case is unchanged. It is not comparable nonempty measurement evidence:
comparison already requires a positive corpus and no unavailable metrics. The
baseline report omits the producer's `corpus.total_copies`; this correction does
not invent that value or claim an independent exact weighted-total join to a
field absent from the report. Genuine packaging must retain the original input
and its provenance separately.

The preceding110-pass/whole139 child-denial epoch is immutable historical
evidence, not the corrected source. This correction ran the entire NEW comparison
module only:126 ordinary passes, no failures/errors/skips,378 phases,3.06 seconds.
All110 earlier case identities and test-function/assertion ASTs are retained;
only the NEW positive receipt fixture's inconsistent empty status maps became
explicit one-card/one-copy status counts. Sixteen additional controls cover
missing/partial/multi-status/nonzero-inconsistent/zero/empty evidence. Original
report functions, CLI path and original test module are byte/AST-preserved.
The original CLI child and combined two-module gate were not rerun or authorized
here. Their separate qualification remains HOLD. No actual A/B measurement or
phase/full-program completion is established.

## Original CLI And Combined Qualification

The corrected reporter, unchanged original 29-case module and complete new
126-case module ran together once under the independently reviewed, finite
original-CLI role. All 155 ordinary cases and 465 phases pass, with zero
failures, errors or skips. Pytest takes 7.84 seconds; the driver takes 8.092
seconds and the outer wrapper exits 0. The 900-second outer limit and 15-second
cleanup allowance do not change any game, AI or BO3 budget.

The one child admission is the original synthetic-input CLI invocation, not a
bootstrap overlay, mocked subprocess or manufactured child result. Its existing
output assertions pass. Admission binds the original collected test/call chain,
native subprocess implementation, arguments, environment, working directory,
script/bootstrap/runtime identities and four small synthetic input identities.
Other child launches remain denied in the parent. Seven original denial probes
pass before project imports. The child is explicitly trusted and unaudited:
there is no child-PID observation, child audit-hook, separate stream quota or
per-child timeout claim. The ordinary original subprocess wait and the owned
outer timeout remain in effect.

Full source and fresh-runtime metadata match before/after. Parent FDs match;
there are no remaining child processes or extra threads, no unexpected denial,
and neither the source default database nor the owned never-created database
exists. Actual existing owned directories have a quiet external fuser receipt;
there is no fictitious database-file scan for absent files. The reporter and
both test modules in the integration checkout are byte-identical to the tested
files. This is a component result, not a whole-current-backend result.

Closed evidence is verified under
`diagnostics/ci/baseline-trusted-cli-ACTUAL155-QUALIFIED-20261017-021708`
and its separate `-parent` archive in the project's NFS storage. Forward tar
readback checks all 2,791 component members and 18 parent members. The immutable
139-case HOLD, oracle admission failures and harness protocol epochs remain
separate, without rerunning or relabeling those old results.

This clears original-CLI component qualification only. Authentic matched
before/after gameplay packages, the producer's controlled-source partition,
missing historical metric reconciliation, complete matchup data and measured
strength improvement remain unfinished. No real A/B game was played by this
qualification.
