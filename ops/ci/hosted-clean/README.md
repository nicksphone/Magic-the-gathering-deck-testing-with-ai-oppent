# Hosted Clean Ubuntu Component

This is a candidate for one clean Ubuntu userspace on a fresh GitHub-hosted
Ubuntu 24.04 VM. It is not a physical-machine, local coordination/sandbox,
separate-device LAN, browser FULL50, or AI-strength certificate. Local protocol
results exercise stdlib functions and mocked commands, not Docker or installation.

## Inputs And Activation

The reviewed App base is `6bbb41befd565e7686a9e4974f3bee1edaa50557`, tree
`4b35aa81a628da9b43a101609e5835fcfb983128`. This replaces the initial `a95e2cd`
binding explicitly; only three frontend files differ between those commits.
All candidate paths are new. The eventual reviewed candidate commit, including
these paths, is the runtime `GITHUB_SHA`; no earlier installation result transfers.

The workflow allows manual dispatch, or the first creation (`before` all zeroes)
of exactly `codex/hosted-clean-install-20261022` in the named repository. Later
pushes do not run the job. This permits an initial unmerged-workflow test without
automatically rerunning subsequent candidate heads. Publication/execution still
requires the parent's separate authorization.

Only a public Git archive and its own depth-one, credential-free Git capsule
enter the container. `read-tree` populates that capsule's real index. Before a
pull, the host requires every index path/mode/object to match HEAD, with no missing,
empty, partial, duplicate, or unmerged entries. No shared Git index is used.

## Original Checks

The copied Python5 helpers perform a fresh venv, pinned offline pip bootstrap,
hash-locked 28-application-wheel install, pip check, and actual metadata inventory.
The metadata helper requires 29 distributions including pip. The public
`python_packages: 28` field means application distributions only.

The copied Build5 actor performs fresh `npm ci`, type checking, lint, full npm
tests, and production build. `VITE_API_BASE_URL` is absent: this is a same-origin
build. The copied HTTPS client/observer and one-shot driver retain their checks,
arguments, timeouts, HTTP/2, rejection, media, restart, authentication, and closure
assertions. They use newly created local guest DBs, never NFS DBs or private inputs.
The final check count is observed, not a hardcoded 563 or 617 target.

## Boundaries And Evidence

One Docker container has a writable root during provisioning and application
execution. It is **not** a Docker `--read-only` runtime. Root setup has only
CHOWN, DAC_OVERRIDE, FOWNER, FSETID, SETUID, SETGID, SETPCAP, and KILL. These cover
APT/file ownership, dropping identity, and init signal forwarding. There is no
SYS_ADMIN, host namespace, Docker socket, published port, or host HOME mount.
The application/client run as actual admitted UID/GID 1001, no supplementary
groups, all five capability sets zero, and NoNewPrivs 1. `/proc/self/status` is
parsed before App commands into a schema-1 numeric identity receipt. PID1's
status and the host's admitted init birth/cgroup remain private control evidence.

`/public` is a kernel readonly bind mount. The separate serving Source copy is
owner-1001 mode-readonly (0555 directories and non-writable file modes); its owner
can chmod it. This does not claim kernel immutability for that copy. Original
tracked file bytes are compared after build and after serving.

Actual before/end finite OS/tool input maps cover `/usr`, `/opt`, APT metadata,
public TLS roots/OpenSSL configuration, loader configuration/cache, NSS identity
files, dpkg status, and the selected Caddy tool directory. They record bytes,
SHA256, modes, uid/gid, links, nlink, and mtime; selected inputs must be root-owned
and not writable by the unprivileged worker. This includes the actual Node/npm,
Python interpreter/stdlib, curl, OpenSSL, ss, and fuser files. The fresh App venv
has its own full before/end map. A dpkg version TSV alone is not this proof.
This is a finite map, **not** every OS file or a kernel/physical-host certificate.

The host admits and follows only its canonical CID plus exact commit label,
init PID/birth, and corresponding cgroup. HTTPS begins only after the controller
disconnects the bridge and observes no container networks. Normal completion,
actual exit, non-OOM, init absence, empty cgroup, and original inner closure are
all required. Forced stop/cancellation remains unqualified; no automatic retry.

## Budgets And Public Tools

The new controller is bounded by 4500 seconds plus bounded 15-second stop grace;
the workflow allows 80 minutes for setup/upload overhead. Provisioning is 1200s,
original Python5 300s, original Build5 1200s (npmci 300s; four checks 180s each),
and original HTTPS 900s/client alarm 800s. Existing component limits are unchanged.
Docker limits are 4GiB RAM, memory+swap total 4GiB (no extra swap), 2 CPUs, 256
PIDs, and no Docker log stream. Existing build/provision outputs are 128MiB and
HTTPS file cap 512MiB. Initial/admission free floor is 5GiB; original HTTPS starts
at 3GiB. The unchanged Build5 actor also has its own ongoing bounds checks.
The 16GiB storage admission is measured at a phase boundary, not a hard quota or
a claim of continuously enforced container disk usage.

Ubuntu amd64 manifest is pinned to
`sha256:a2d43bffc46670d7108bb3c0468c67c5557c4c92e83e1e34cbff1322ad1b94dc`.
Node 24.22.0 uses the previously authenticated official archive SHA256
`cc2f601cee82d9a5a233302fe307abc600727035fd7d2c3a3571755989e95008`;
this is reuse of its admitted provenance, not a new local signature verification.
The exact Node/npm executable hashes are checked by provisioning and mapped BE.

The public Caddy wrapper `main.go`, `go.mod`, and `go.sum` are unchanged inputs
from the accepted 2.11.7 build. The recipe uses pinned Go 1.26.9, `go mod verify`,
then offline module compilation with the original tags/flags. Its resulting
Caddy ELF must equal `e8d6545c8485f7bd723fc3a6a2fb5662e89a235ae0d32ccde3f43d81577b0db0`.
No local runtime binary or private evidence is copied into CI.

Curl remains exactly Ubuntu `8.5.0-2ubuntu10.16` plus the original ELF SHA256
`1ccbd3dae948374ba8eef1ebda26c64b783ede50b463196e53666e0880bdac60`.
[Ubuntu USN-8932-1](https://ubuntu.com/security/notices/USN-8932-1) lists `.16`
for noble. This metadata is not signed APT or ELF execution proof: the future
guest must pass normal authenticated APT admission and the original binary pin.
Missing version or wrong binary is a STOP, never a waived H2/negative check.

## Outputs

Only `provisioning.json` and `lifecycle.json` are uploaded. They use closed typed
schemas with finite enums, counts, booleans, exit vectors, and SHA256 digests.
Unknown fields/raw exception text are rejected. Credentials, request/game bodies,
stdout/stderr, DBs, environments, private snapshots, and detailed control maps are
not artifacts and are never printed by the controller. Failed/cancelled runs stay
unqualified even when a preceding stage completed.
