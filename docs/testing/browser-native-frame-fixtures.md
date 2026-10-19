# Browser Fixture Native Stack Frames

The workflow on `f64ba88b` passed the configured frontend job and progressed
through the corrected BO3 readiness checks, then failed while waiting for the
copy-target continuation. Its manual browser fixture had constructed a legacy
stack frame without the native spell/ability kind. The strict copy resolver
correctly refused to treat that unknown frame as a spell.

Five existing manual fixture producers now declare `__announced_stack_kind`:
four spell frames and the Azure Mage activated frame used by two cost scenarios.
The existing modal fixture helper's whole-function source hash is explicitly
repinned to those changed fixture bytes. No gameplay engine, validation,
targeting, browser assertion or production frame producer is relaxed.

The six new fixture-contract checks first fail on the unchanged fixtures, then
pass with the explicit native metadata. They exercise the actual fixture
function, including the real copied stack objects and offered continuation.
These are trusted CI setup checks, not paid-cast or whole-card certification.

One fresh complete declaration of 23 backend modules passes all 447 checks in
171.09s, with two warnings, no skips or expected failures, and exit zero.
All 2,813 source files and the file set are equal before/after; two native SQLite
denial controls execute and gameplay attempts no SQL, socket or child I/O.
The initial four-case draft included one wrong new fixture selector; that ledger
and the corrected six-case failing baseline are retained separately.

Evidence: mounted RCHFiles `mtg-deck-testing-lab/parent-integration/
browser-native-frame-fixtures-20261009/`. The original remote failure remains
under `diagnostics/ci/f64ba88b-37920074106-20261009/`.
The full corrected remote browser/backend workflow is still required; this
component does not close the release gates or the broader rules/AI objective.
