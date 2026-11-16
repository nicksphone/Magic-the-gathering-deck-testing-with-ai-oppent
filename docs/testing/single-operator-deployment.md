# Single-operator, single-worker deployment contract

Supported scope: one trusted operator identity, one application worker and one
local SQLite database/runtime on one host. Multiple tabs are clients of the same
operator, not separate protected accounts. Match IDs, seat controllers and revision
headers are game/concurrency state, not user authorization. No per-user database,
tenant isolation, account login, role ACL or secure multi-user service is claimed.
Do not expose the raw backend/Vite server as a public multiplayer service.

## Enforced boundaries

- `ops/caddy/run.py` starts Uvicorn with an explicit `--workers 1`, backend bind
  `127.0.0.1`, no reload, no access logs and no forwarded-header trust. The learned
  entrypoint uses `uvicorn.run(..., workers=1)` and accepts only loopback host;
  inherited worker-count settings do not raise its worker count.
- `persistence.capacity.DatabaseOwner` holds a nonblocking lifetime file lock
  for the exact canonical local database. Another process cannot acquire that
  same database while the owner lives. It also binds the owner to its process,
  engine pool and database identity. This guards storage ownership; it is not
  a distributed lease, network-filesystem lock guarantee or account-auth system.
- The operator holds a second runtime `operator.lock`. The packaged Caddy route
  has one configured BasicAuth identity before API, images and static files;
  authorization is stripped before upstream proxying. The raw backend does not
  supply equivalent access control. Using different database copies evades a
  same-file lock and is **not** an allowed scale-out configuration.
- Do not run multiple workers, multiple backend replicas, rolling overlapping
  owners, a shared NFS/SMB database, or a production reload process. Never delete
  a `*.lock` file to force startup. Locks release on actual process/file-handle
  closure, not PID age. Back up/restore with the reviewed operator procedures;
  do not copy or replace a live database underneath its owner.

## Running and exposure limits

For direct local development, make the scope explicit:

```sh
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 9999 --workers 1
```

This starts an unauthenticated local developer backend, not the HTTPS package.
For packaged use follow `ops/caddy/README.md`, validate private configuration,
and launch its supervisor. Keep keys/config/runtime private; the default proxy
bind is loopback. Use the built dist, not Vite dev/preview, for packaged serving.
One BasicAuth identity is shared across the whole table/API; changing browser
seat selection is not authorization between people.

Private LAN binding is an optional *configuration* subject to the package's
validation. Certificate trust on the client, actual interface routing, firewall,
HTTPS/auth/browser behavior and the chosen topology still need end-to-end
acceptance. A passing settings/loopback test does not qualify a LAN host. No
public-Internet or multi-tenant security claim follows from BasicAuth alone.

## Enforcement tests and limits

```sh
cd backend
python -m pytest -q tests/test_single_operator_deployment.py tests/test_operator_learned_startup.py tests/test_capacity_bootstrap_policy.py tests/test_capacity_policy_environment.py
```

The new native test owns a temporary SQLite file: while its real owner is active,
a separate Python process's acquisition is rejected, the database and lock inode
remain unchanged, and a successor can acquire only after release. It never opens
the application database. Launcher tests check the real default command expression
and inert learned entrypoint with hostile worker environment values. A static
proxy contract catches removal/reordering of the single configured auth block;
it does not authenticate a live HTTP/TLS request or qualify a Caddy binary.
Existing package security and native topology tests remain separate requirements.
No production behavior or source pin is modified by adding these tests/docs.
