# BO3 Cold Worker Portability

The controlled intergame regression previously invoked uncommitted `gate.py`.
An isolated current source reproduced 14 passes and one missing-file child
failure across the whole 15-case module (19.86s).

The committed test worker performs a public ASGI lookup in a fresh subprocess,
without lifespan/bootstrap. It binds only the marked isolated source's declared
default database through a read-only SQLite URI, denies writes, network and
further children, closes the client/engine, and compares database bytes. Parent
memory and complete SQL roots remain unchanged. This is not a native network
server restart or a naturally completed game certificate.

All 46 original assertion ASTs and their order are exact. Two both-seat controls
verify partial confirmation, actual distinct PID and restored controller; two
negative controls reject foreign source/database inputs. First corrected whole
17 passed (31.69s), reusing the baseline owned database. A separate fresh source
and database passed all three whole modules, 22 cases (30.76s), including the
unchanged sideboard neighbor. No skips, deselections or xfails.

Every pre-existing tracked source hash is unchanged across the final gate.
Generated media and owned databases/backups are additional runtime files;
whole filesystem equality is not claimed. Direct fuser on all 19 closed database
files returned 1 with empty output. Cooperative Python audit is not a kernel
sandbox. No production, capacity, rules, controller or AI changes.

Evidence is verified on private NFS under
`diagnostics/ci/bo3-cold-parent22-20261012-CTxkkmpP`. Full backend CI and all
original release/AI quality requirements remain open.
