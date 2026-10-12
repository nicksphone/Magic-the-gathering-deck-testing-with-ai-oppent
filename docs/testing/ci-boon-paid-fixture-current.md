# Paid Counterspell Fixture

The protected backend run for `8b1bffa2` reports 25,997 collected nodes:
25,308 passed test bodies, 73 failed bodies, 532 setup failures, 82 skips and
two missing call-phase records. Its metadata audit is incomplete, not a release
certificate. Only the allowlisted sanitized metadata was retrieved; protected
raw logs and the private synthetic trace remain private.

One reproduced failure is an obsolete fixture in `test_api_input_contracts`.
Its manually injected empty-payload stack item is correctly classified as
`legacy_unknown`, not an announced creature spell. The repaired test uses a real
paid opponent Grizzly Bears cast, checks its retained announcement and snapshot
roundtrip, then passes priority before Withering Boon. All original target,
HTTP, life-17 and Font of Agonies stack assertions remain. Production targeting
and payment code are unchanged.

The unchanged whole API module reproduced 45 passes and one failure. The adapted
whole API module plus two new provenance controls passed all 48 cases in the
worker (174.448 seconds) and independent parent (170.54 seconds), using isolated
local SQLite and cached dependencies. There were no skips or expected failures.
An existing audit-hook shutdown warning is retained in the parent ledger.

The shared 532 setup failures point to capacity backup startup, but did not
reproduce in these fresh isolated runs. Local backup accumulation is a measured
candidate, not proof of a hosted timeout or disk-full cause. This fixture repair
does not close that cluster or the other backend failures. Full combined hosted
qualification remains required.

Private verified evidence is under `diagnostics/ci/current-8b1-backend-terminal-
sanitized-20261012-1mTTYusT`, `current-8b1-boon-paid-fixture-20261012-EoQyyuGd`
and `boon-paid-parent48-20261012-BN34KMwY` on RCHFiles. No private payload is
included in this commit.
