# Two-Target Immediate Return

The additive compiler recognizes the complete two-target artifact, creature,
and/or land exile-return instruction, not a named-card branch. Unknown trailing
instructions remain unsupported without partially executing the blink. Public
admission requires two distinct currently legal controlled permanents; conflicting
player, stack and distribution fields are rejected before payment.

The resolver retains each actual announced object reference. A paid bounce or
single blink can invalidate one target without invalidating the other; two stale
targets fizzle. Real copied spells can change individual targets or literally
keep their old references. A departed token cannot return.

The executor captures the complete PRE departure cohort, exiles all legal
targets, and prepares all private land and counter replacement choices before
any return. Per-card printed entry counters stay separate. Incoming Magus of the
Moon cannot retroactively change another simultaneous entry choice. Lore events
use a private optional receipt sink in the existing counter helper and are
collected only after every returning card and counter is committed. Default
single-counter and single-blink behavior remains unchanged.

These semantics follow [the official Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
particularly 608.2b, 614.12 and 111.8. This implementation is deliberately bounded
to the complete supported two-target body; it does not certify arbitrary blink
counts, unknown compound bodies, animated entry characteristics or every card.

## Observed Component Qualification

Frozen base: `6df6811b409af07cd75407eabb88e9b7452c4391`.
The expanded whole core module passes 68 cases in 14.02 seconds. The final
13-whole-module API/copy/entry-counter/Saga cohort passes all 341 cases in
153.71 seconds, exit 0, with 113 warnings and no failed, errored or skipped nodes.
All 1,978 pre-gate source manifest entries match after execution.

The 20 new HTTP cases use genuine checked payment, memory/file SQLite, wrong-seat
and malformed-choice atomicity, and application eviction/restore. Publicly seen
bounced cards remain known; other hidden hand/library identities stay private.
This is in-process application restore, not a cold-process certificate. Existing
neighbor snapshot subprocesses were not child-audit instrumented.

The native harness permits only local declared SQLite scratch, its owned default
database, exact 32-hex capacity-backup names and explicit read-only owned URIs;
external socket connections are denied before project imports. The default
database was reused locally, not presented as a clean-install test. All 38
closed local databases examined after the gate pass SQLite integrity checks.

Earlier semantic failures, new-fixture mistakes and harness-only denials are
preserved separately. In particular, a Saga-first collector observed an incomplete
board before the receipt correction; copied `keep` initially lacked any alternate
target to make the public prompt appear; known bounced identities were initially
incorrectly expected to be hidden. No original neighbor assertions were changed.

Independent nine-production-path review verifies 206 unaffected definitions
byte-identical and the remaining module ASTs unchanged. Review and these gates
are bounded component evidence, not whole backend CI, expert-AI quality or
release Gates 1--3 completion. Protected CI game traces remain private.

## Current AI Composition

The AI materializer previously assumed every required-distinct target instruction
was an ordered creature-counter allocation. Its additive permanent-candidate
branch now selects the advertised distinct permanent IDs without inferring a
missing domain or count. Existing explicit choices are not silently repaired.
The old ordered-counter body is unchanged, as are the public materializer wrapper
and 163 other functions. The changed method is
`_materialize_action_without_resources`, not its wrapper.

The 22-case focused AI gate passes in 3.63 seconds after eight semantic failures.
The final current composition executes all 363 cases in 14 whole modules:
363 PASS, 49 warnings, 81.29 seconds, exit 0, no failures/errors/skips. Its source
manifest entries match after execution. This includes both seats, creature-plus-
land and land-only public legal moves, actual `choose_action`, checked payment
and resolution. This proves action compatibility, not strategic quality.

The worker's separate 218-case code-only snapshot has 198 passes and 20 failures:
six denied main imports, four omitted media assets and ten older captured blink
assertions. Those failures and their earlier source remain historical, not
relabeled as the current 363-case result. Independent AI review clears only
the one-method increment. No protected input or native provider authority changes.
