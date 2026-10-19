# Selection and Suspend fixture birth

This test-only increment is based on immutable commit
`e1dda1bb0fc3c2d10a22f0385e079003e636f838`. It changes no engine,
AI scoring, advisory profile, canonical Oracle row or production validator.

The untouched two whole modules produced 102 PASS and 64 FAIL in 64.59s:
16 ineligible selection cases rejected a zero-quantity starting row, and
48 Suspend composition cases rejected a Vision appended after Factory
inventory capture. These were snapshot inventory failures, not evidence
that all hosted CI failures share the same cause.

The selection fixture now omits only the ineligible zero-quantity Lions
row. Its optional keyword-only `additional_own_rows` defaults to `None`
and copies additional canonical rows before Factory birth. Suspend passes
the unchanged full canonical Vision row through that argument and uses
the existing `relocate` helper to move the born card from library to hand.
It no longer creates a new card or edits starting stock after capture.

All 44 original ordered assertions remain AST-identical. Every other
function in the two original modules is unchanged. Original seed 321,
scenario/style/difficulty order and expected production action choices
are retained; no RNG rewinding is used.

The construction witness compares actual old and corrected states:
all 12 selection seat/scenario combinations retain identical physical
card IDs, zones, captured inventory and RNG state. Only the two
ineligible submitted inventories lose their nonphysical zero row.
All six Suspend combinations retain the same submitted quantities and
canonical rows but change physical card IDs/order and captured inventory.
Their RNG state changes for seat 1 and is equal for seat 2; this is an
observed comparison, not a promise of legacy RNG parity.

Ten NEW pure controls cover both-seat pre-birth inventory, genuine checked
paid Suspend and snapshot roundtrip, copied inputs/repeatable seeded
birth, and strict rejection of cold quantity-zero corruption and
post-capture stock edits. The separate private construction witness is
not an additional public test. The two whole original modules plus ten
NEW controls are the acceptance roster; the private run also includes
one evidence-only witness. SQL, sockets, subprocesses and providers are
denied before backend imports. This scope is not HTTP, BO3, native SDK
capture, whole CI or AI strength qualification.

## Measured final cohort

The unfiltered private whole run passed 177 ordinary tests in 84.08s:
166 original cases, ten NEW public controls and one private construction
witness, with zero failures/errors/skips. Its source map of 3,213 files
was equal before/end, unexpected I/O was empty and no SQLite database
was created. The public roster has 176 cases; this is not a claim of a
separate public-only execution. A future mixed 356-case composition is a
separate qualification, not part of this result.

The legacy witness calls the original `position` and unchanged Factory
before correction, and records states without serializing their invalid
stock. No Factory/capture toggle, permissive birth projection, RNG
rewinding or validation bypass is used. Successful construction does not
certify those legacy states as valid cold snapshots; their unchanged
serialization rejected the stock in the preserved baseline.
