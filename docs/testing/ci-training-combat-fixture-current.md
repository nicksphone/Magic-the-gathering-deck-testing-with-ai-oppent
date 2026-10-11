# Training Combat Fixture And Discard History Follow-Up

The legacy combat scenario declares an attackers/blockers step after creating an
ordinary precombat-main scheduler plan. Its stale phase cursor makes twelve
original cases fail at snapshot restore before their combat assertions. The
production restore validator correctly rejects the contradictory snapshot.

The repair adds only an import and a call to the existing test-only
`ordinary_position` helper after the scenario's explicit step/priority setup.
It does not repair imported runtime snapshots, alter production scheduling or
weaken the restore guard. All 34 original assertion nodes and the complete
original module AST remain equal after removing these two additions. The helper
still rejects queued turns and nonzero-group phases without mutation.

## Observed Checks

The frozen original 72-case combat audit reproduces twelve failures and sixty
passes in 97.82s. Sixteen new regressions first produce twelve strict failures
and four passes, then pass after the fixture correction. The whole original
audit, original guard and new regression modules pass all 152 cases in 234.13s,
without errors, skips or expected failures. The original guard bytes and final
1,929-file before/after source maps are equal. Initial shortened-module lookup
failure is retained as an administrative ledger, not a gameplay failure.

Parent review verifies tar/member hashes, both postimages, current preimage and
dependency equality, all original assertions, the two-node AST delta and every
JUnit outcome. On `1f08a6ca` plus only these two test paths, a fresh isolated
parent run passes the whole new 16-case module in 9.84s. Its source-field hashes
remain equal; the parent audit records no network denials or SQLite connections.
The subsequent whole current-source parent cohort passes all 152 cases in
242.54s with zero failures, errors or skips and equal before/after source-field
maps. Its parent audit records only owned local SQLite paths and zero denials.
An independent frozen review confirms unchanged current helper, restore,
environment and guard bytes. Neither gate executes in the running public root.

## Already-Correct Trigger Family

On exact `1f08a6ca`, all 119 unchanged cases across the four original trigger
compilation/self-trigger modules pass in 47.53s. The current trace fixture
already forwards the production `raw_entry_oracle` keyword. There is no new
compiler, events or original-fixture repair to apply for this family.

Two new both-seat regressions exercise a genuine paid Cloudblazer entry through
that fixture, checking exact printed-Oracle forwarding, the compiled trigger,
two drawn cards and two gained life. A separately labeled historical fixture
function projection makes both regressions fail at the old unsupported keyword;
the current fixture passes both in 3.17s. It does not overlay or import old
modules or alter current production. The unchanged 119-case cohort is not
rerun or relabeled as a combined 121-case result. This demonstrates the old
spy's failure mechanism, not every historical hosted failure's cause.

## Existing AI Repair Qualification

The separate unchanged 92-case discard-history module reproduces twelve
failures and eighty passes on `1a8e0869`, then passes all 92 in 20.96s with only
the already-published `ac860848` AI consumer postimage. Its test bytes and 78
assertions remain unchanged. The failures were optional rummage choices whose
owned pending draw continuation is intentionally absent from the public legal
view; the existing fix validates the owned pending context before using it.
There is no additional production branch or discard-test patch in this packet.

Both baseline imports generate 150 owned placeholder SVGs. Every original
source hash remains equal; generated files are explicitly recorded rather than
described as whole-baseline equality. Final gate source maps remain equal.

## Scope And Evidence

Frozen packets under RCHFiles `diagnostics/ci/`:

- `decision-quality13-ci-training-combat-fixture-20261011-6lfwmfd3`, tar SHA256
  `5c9ea66e92a0700ce9f4b598a86df3c48a198260d87f1cf8427b5f7f05c2164d`.
- `decision-quality13-ci-discard-history-qualification-20261011-rAs2zw4R`, tar
  SHA256 `cead8918a00e802229fac5bb62576b16b1fb81f73d5ed01c905fe40b38e7975e`.
- `decision-quality13-ci-trigger-qualification-20261011-m92T3z8b`, tar SHA256
  `f9f8d6f9e164b58b5d372fe5b730f77b043ad2445a0e8f029c8e5db7c6e73ae3`.

These are separate, overlapping component qualifications, not a summed full
backend result. The 92-case packet qualifies its exact older source plus the
existing AI patch, not every current production change. No protected trace or
raw private hosted log is published. Parent-only audits do not imply audit
inheritance by existing cold workers. Full combined CI, original release gates
and independently measured expert AI remain open.
