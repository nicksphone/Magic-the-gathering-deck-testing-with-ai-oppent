# Lazy Restart Worker Interfaces On Frozen CurrentB

Four restored workers previously indexed a saved controller immediately after
startup, before calling any production match-ID endpoint. Lazy startup deliberately
keeps the cache empty. Each adapter now performs `/matches`, asserts saved-ID
membership, then GET `/matches/{saved-id}` and asserts200 before direct inspection.
No eager restore or engine/cache fallback is added. All original seed/action/read/
privacy/root/SQL/config/RNG/receipt/continuation assertions remain intact.

Affected files: queued_sequence_restart_worker.py,
spell_admission_safety_restart_worker.py (reject branch), nth_spell_restart_worker.py,
import_identity_fix_worker.py. Extra sequence delegates queued unchanged. Admission
reorder delegates already-adapted library reorder unchanged. Lazy wrapper unchanged.

Source: read-only frozen parent `/tmp/mtg-queued-global-lazy-current-FsvIQT`;
1793 static-source before/copy/end hashes match. No DB/dependencies copied;109SVGplaceholder assets inadvertently copied (provenance correction in report); final archive excludes image_cache.
Import identity is outside the parent's declared3717 and is qualified separately
within this worker gate. These adapters do not certify a complete3717 rerun.

New tests guard all original100 assertion ASTs, public discovery/by-ID lookup order,
unchanged delegation wrappers, and unchanged main/repository copied-source hashes.
The unmodified22-case before run retains ordinary failures (177.99s, exit1), not
converted to xfails/skips. Parent interrupted20FAIL1534PASS294.18s exit2 is distinct
partial evidence, not the same completed baseline or full qualification.

Additional discovered seam: shared loopback test-client Server.audit in
`test_private_choice_http_restart.py` calls private fixture audit before public
match lookup after restart. Its fixture-owned cache lookup is not a production
API bug. Proposed separate client-side cold publicGET before existing audit;
no private fixture-server/engine fallback, no privacy bypass. It is not changed
or qualified by this four-worker patch. Land/library consumers share that harness.
