# Task33 Canary In Ordinary Backend CI

The original Task33 canary intentionally requires TASK33_PURE_GUARD=1. Archived
precollection guards supplied it, but ordinary backend CI did not. Reuse the
existing tests/conftest.py call-scoped audit hook for exactly its original name
and test_log_priors_archetype.py path. Set/restore only that environment key,
use the expected `pure guard` prefix and add process/openai-import denial only
inside this target. A cached openai module still rejects through a temporary
import wrapper. Existing five canaries retain their exception types, message,
thread check, revocation and socket constructor restoration. Other tests and
runtime permissions are unchanged; there is no global provider/process guard.

The original Task33 file, its assertions and conditional skip statement remain
byte-identical. Its actual tuple has TEN operations (three SQLite aliases, four
socket constructors/bare aliases, Popen, system, openai import), not twelve.
New direct-scope coverage executes those ten unchanged, adds actual DNS denial
and one synthetic connect audit-event denial without creating a network socket.
Do not claim twelve original/native IO operations. Environment/context/import
and socket identities restore after success/failure; unknown paths/names do not
activate the flag, and copied contexts remain thread-bound and are revoked.

Ordinary pytest starts without TASK33_PURE_GUARD, plugin autoload disabled,
with owned temporary/log paths. A private safety ceiling forbids physical SQL,
unscoped network/process and foreign writes; it delegates scoped IO to the exact
source conftest handlers under the two real pytest import names. It is not a
published/global test policy or an independent hostile-child isolation proof.
No physical SQLite, network/provider initialization, subprocess child, native
SDK capture or game execution occurred. Ordinary backend module imports and
existing synthetic AI/component tests did execute under this bounded task.

Actual baseline three whole modules:121PASS1SKIP2.41. Strict new-scope RED:
125PASS7FAIL1SKIP2.73 (four whole modules). Initial launcher logging-to-dev-null
setup INTERNALERROR is retained; corrected launcher owns its pytest log. Initial
candidate131PASS2FAIL2.70 retained: private ceiling used only tests.conftest while
pytest also loaded conftest; uninitialized connect raised bad-family before its
audit event. Only private launcher and NEW fixture corrected; public guard did
not change between that gate and final133PASS0FES2.55. Main90+scope29+finalization3
original cases remain intact, plus11 NEW cases. Backend source before/end equal.

This closes only ordinary-CI canary execution coverage. Original Task33 pipeline
qualification and benchmark/native/learned-data/source-epoch claims remain their
separate immutable receipts. No production files or original test assertions
were changed; no test selection, exclusions, xfail or additional skip introduced.
