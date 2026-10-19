# Officer Origin And Private Browser Diagnostics

## Observed Failure

The completed `d89e18a3` browser job passes Officer's eight human/AI HTTP and
privacy checks, then the mounted App reports `BACKEND OFFLINE` / `Failed to
fetch` while waiting for the private inspection panel. Officer uses frontend
origin `http://127.0.0.1:15237`; its launcher did not configure that origin.
The unchanged backend defaults trust only ports 5173, 4173 and 9999. Node's
direct requests have no browser Origin header and do not prove CORS admission.

The launcher now exports `MTG_TRUSTED_ORIGINS="$MTG_FRONTEND_ORIGIN"` before
either backend process starts. Production defaults, mutation-origin rejection,
native ownership, original browser actions, assertions and deadlines are
unchanged. Three whole pure policy modules first report 104 passes/four new
regression failures, then 108 passes (0.26s). The new cases exercise the actual
launcher configuration through the real GET/POST/OPTIONS middleware and reject
both the ordinary harness origin and a foreign origin. SQL, sockets and child
launches are denied before imports; these checks are not a native browser pass.

The subsequent isolated native run executes both original Officer phases once:
all eight HTTP/privacy checks and four mounted browser scenarios pass, exit0
(2026-10-10 16:08:06-16:08:25 UTC). Both seats exercise no-hit acknowledgement
and qualifying selection, an actual backend process restart, reload, bottoming
and opposing reveal privacy. All 1988 backend/frontend source hashes match
before/end; ten audited SQL connections remain owned. Original closed-runtime
integrity/tar comparison passes, the three ports are empty, and scoped process
and existing-path fuser checks show no remaining owned writer.

A separate unchanged whole Officer run with the observer UNSET also passes all
eight HTTP and four browser checks, exit0 (16:13:18 UTC start). This checks the
default CI driver path, not a summed 24-case cohort or a retry after failure.
Source hashes and scoped owned resource closure pass again.

## Opt-In Observer

`MTG_PASSIVE_CDP_EVIDENCE` opts the existing browser driver into private CDP
diagnostics within its exact local `MTG_BROWSER_SQL_OWNER` directory. With the
variable absent, removing only the enumerated opt-in seams reconstructs the
original driver byte-for-byte. The original package/cohort, selectors, command
replies, retries and clocks are not changed.

Opt-in startup opens a blank page, installs listeners and awaits Network/Runtime
domains before navigating to the original URL. It observes existing events;
it does not issue additional game API requests or intercept/rewrite traffic.
Only bounded own-match metadata is stored: status, route/frame correlation,
revision, controller and pending-kind/count summaries. Raw bodies, headers,
cookies, hidden card arrays and arbitrary console/exception text are excluded;
allowed diagnostic text is represented only by hashes.

Reused request IDs discard previous admission before any new route is examined.
Redirect-hop status is retained, while missing status, scope changes and lost
transport mark coverage incomplete. Coverage completeness is never a gameplay
pass. Output is owner-private, exclusive-created and local; NFS execution is
rejected. The initial packet and red correction ledgers remain immutable.

The corrected whole synthetic protocol module passes 31 cases in the worker
and independent parent (108.77ms). Both original navigation checks pass. The
boundary is fake CDP, not Chrome or a native timing/resource certificate.

The later native Officer run produces four real recorder closures: one complete
and three explicitly incomplete, including outstanding requests and two
body-projection failures. These coverage limits remain in the private evidence;
the observer does not convert the four gameplay passes into a completeness
claim or suppress the incomplete records.

Private evidence is archived under `diagnostics/ci/` and
`diagnostics/parent-integration/` on the MTG NFS share, never published as a
public fixture. Full current browser/backend CI, measured AI quality,
clean-machine/operator/soak and all original release requirements remain open.
