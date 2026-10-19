# Retained Control Source Producer And Scheduler

Dependencies: frozen pure stage78d62, independent handler correction3ced445e,
and Jason consumer integration4be00c00 (production8168b1fc). Apply each once.
This incremental changes engine.take_action and keyword_triggers.schedule_control_loss_tap;
it does not contain or replace the shared resolver dependency.

Capture the physical reference immediately after the source moves to STACK,
before callbacks. Bind announcing ID/controller/label/source to the actual returned
add_to_stack item, never the current top (which may be a genuine cast trigger).
Copies inherit this announcing receipt unchanged. The consumer transports the
actual popped item as __resolving_item; its ID/controller/label/copy markers are
separate from announcing provenance. The scheduler reads the retained physical
reference from that transport, never the current source card in the graveyard.
It validates before delayed-record publication. The existing sequence interpreter
already propagates __resolving_item; no registry or copy-hook edit is needed.

Strict pure acceptance:199 ordinary PASS across12 whole modules,64.47s,exit0.
The original eight genuine paid copy episodes are unchanged and ordinary passing,
verified individually in JUnit. New protocol wrappers are explicitly internal
tests, not claims about an invented canonical compound card. Malformed root rejects
before pop; conflicting leaf rejects before scheduler publication and leaves the
checked-action root unchanged. No irreversible direct-core rollback claim.

Separate unchanged13-module250 diagnostic under the strict audit guard:
242PASS8SQL-fixture setupERROR,72.83s,exit1. Eight original SQL cases remain intact.
Prior monkeypatch-only guard missed sqlite3.dbapi2; previous all-SQL-denied claims
for mixed modules are withdrawn in a separate immutable ledger correction, not
retroactively relabeled as pure successes. The new audit hook is installed before
collection and proves both SQLite aliases blocked; socket connections also denied.

SQL250 is a separately proposed own-source-default-DB/startup contract, not granted
or executed here. Original Ray149 no-default-DB/no-startup declaration remains HOLD.
Original first-cleanup timing witnesses and old review archives remain unchanged.
No broad duration/layer, death-route, shared-copy or whole-release claim.
