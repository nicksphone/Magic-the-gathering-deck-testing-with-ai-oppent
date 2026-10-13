# Runtime Data Must Stay Outside Served Files

The Linux operator launcher previously rejected a frontend build inside the
runtime directory, but allowed the reverse: runtime data below the frontend
build directory. Caddy's unchanged static file server serves that build tree.
That configuration could therefore expose runtime backend files and game data
to an authenticated browser. This is a demonstrated settings-admission bug,
not an observed data leak or authentication bypass.

`ops/caddy/run.py::settings` now rejects containment in both directions. Equal
directories remain rejected; separate siblings and an external runtime with a
source-tree frontend build remain valid. No listener, authentication, binary,
certificate, origin, backend or database permission changes.

The new real-settings, file-only cohort first ran eight cases: six passed and
both runtime-under-dist rejection cases failed with `ValueError not raised`.
After the minimal check, all eight passed. The original twelve real
prepare/inventory controls also passed unchanged. SQL, socket, subprocess and
native dynamic-loader attempts are denied by the new test's audit hook.
Its explicit fixture bytes and syntactic hash are not executable provenance,
TLS credentials, native authentication or HTTPS acceptance.

Run both regression scripts from the repository root:

```sh
python ops/caddy/test_runtime_dist_boundary.py
python ops/caddy/test_runtime_inventory.py
```

Both are now ordinary backend CI steps. No live server, user data or global
trust setting was changed. Current native HTTPS, selected LAN topology,
browser trust and the full Linux release still require their separate gates.
