# Wave2 synthetic position stock

The shared `tests.regression_agent_wave2.support.position` creates bounded
canonical library filler, then deliberately assigns a synthetic scenario ID.
Its `add` helper injects independently hydrated canonical cards, not certified
original mainboard stock. The original Factory capture therefore cannot certify
this scenario. The setup now explicitly declares unknown original-stock facts
before changing the ID. It does not rewrite a capture's game ID or inventory.

Only this test-helper function changes. Production Factory/validators, all other
shared helper functions, original actions/assertions, browser endpoints/driver,
and canonical RAW card data remain byte-identical to the frozen parent source.
The caller audit covers the browser fixture and every direct helper import.
Three pure position-consuming test modules are exercised whole. The separate
SQLite restart module is source-audited but not executed under the pure grant;
the actual HTTP/browser run requires separate parent qualification.

NEW both-seat controls: actual shared-position snapshot/resume and exact browser
route FunctionDef projected across inert HTTP/SQL boundaries, actual checked
Incremental Growth payment/priority/resolution, deliberate ordered 1/2/3 counters,
native Factory v3 preservation, and strict mismatched-ID rejection. RED:4F4P1.37s;
GREEN:8P1.40s. Four whole pure modules:102P17.09s, 0 failures/errors/skips, SQL0,
seven actual pre-import physical denials, source equality, MainThread only.
This is synthetic setup repair, not competitive-deck or natural-capture proof.
