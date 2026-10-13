# Linux Private LAN Bind: Scoped Acceptance

Base: immutable `e1dda1bb0fc3c2d10a22f0385e079003e636f838`; its operator
production files matched CF1 before the two LAN production changes. Native
configuration and default-loopback acceptance below bind those candidate bytes;
they do not qualify assigned LAN exposure, browser trust or a clean install.

The existing foreground `ops/caddy/run.py` entry accepts its exact ten keys,
optionally plus one `bind_address`. Absence retains `127.0.0.1`. An explicit
value must be a plain canonical IPv4 string: only that exact loopback address
or RFC1918 `10/8`, `172.16/12`, `192.168/16` is admitted. Public/wildcard,
other loopback, IPv6/link-local/shared space, whitespace, control characters,
non-string values and other extra keys reject. No broad `is_private` rule.

Only Caddy receives the validated `MTG_FRONTEND_BIND`; the Caddyfile has an
explicit `127.0.0.1` default. Backend binding/environment, exact HTTPS origin,
authentication-first, supplied TLS, API/media routing, source/runtime/dist
containment, locks and shutdown remain unchanged. No installer, desktop
framework, global trust/firewall action or listener auto-discovery is added.

Actual NEW34 file-only RED: 25 PASS / 9 FAIL, 0 ERROR, 4.54s. The whole final
pytest scope passes all 49 cases in 6.17s: original eight containment cases,
seven security-configuration cases and all NEW34. The original standalone
inventory program separately exits zero with all 12 declared checks; it is
not counted as twelve pytest cases. Original test bytes/assertions are intact.
Both final receipts record full source equality, seven actual precollection
SQL/native-socket/process/provider denials and no unexpected I/O.

Preserved harness history: one initial precollection bare-socket canary lacked
an alias interception; first whole49 had eight cleanup-policy failures despite
41 passes; first inventory attempt denied `fdopen` on its owned lock. Private
harness-only corrections resolve stdlib FD-relative cleanup and owned file
descriptors. Product/test bodies are not changed to hide those failures.

Tests use actual pinned Caddy file bytes and the real settings function, but
certificate operands are explicit file-shape fixtures, not real TLS material.
No Caddy process, native adaptation, SQL, API, socket, provider or server is
executed by these file-only positive tests. The later native gates are separate:

- Two configuration invocations actually exited zero: unchanged original
  `verify-config.py` with every preparation/lock/inventory/restart assertion,
  followed by a separate real settings/environment/adapt/validate wrapper.
  Its native JSON had exactly `10.23.45.67:18443`; that unassigned address was
  used only for adaptation, never bound by a listener. Both ephemeral secret
  trees were removed and source/package/system/helper pins matched before/end.
  Sanitized evidence: `diagnostics/ci/current-e1d-native-default-private-config-qualified-20261013-3J877y/`.
- The complete unchanged original native operator program then ran once on
  e1d plus only `run.py` c806 and `Caddyfile`82a, with identical CF-built DIST
  from all225 unchanged frontend files. The3214-file source full set/bytes,
  Python2852files+4links and pinned system/helpers matched before/end.
  Actual observed checks: **541, all passed**; shell/driver/client exit0,
  23:26:46.490540 through23:27:38.204249 UTC on2026-10-13. No retry/pruning.
  This was default127.0.0.1 only, with original authentication, certificate
  rejection, strict HTTP/1+HTTP/2, media, incomplete-body and restart assertions.
  All check-label sets match priorCF547; the only multiplicity difference is
  six fewer repetitions of `owned process is its captured group leader`.
  No scheduling/performance cause is inferred and541 is not relabeled547.
  Both production-first shutdowns verified before observer assistance;133known
  PIDs/tasks ended, ownedFD/listeners were empty, pools/owner/jobs/workers closed,
  and all four existing DB/backup/lock fuser checks returned1 with empty output.
  Backend closure non-main-thread observations were[1,1], not invented zero.
  SQL released23:29:50.969884 UTC. Original800/900s+15s,1GiB combined,
  512MiB output and3GiB free bounds were unchanged; resource stop was null.
  Source/closed private SQL and secret-excluded evidence:
  `diagnostics/ci/current-e1d-lan-candidate-native541-default-qualified-20261013-CyV0eY/`.

Evidence directories above are under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`.
Verify their exact SHA manifests before use. Private SQL is archived only after
closure and never executed on NFS. Generated cert/key/auth/operatorJSON, Caddy
storage, environment dumps and credential-bearing native output are excluded.
The successful earlier CF1 run remains its own unchanged-source historical
qualification, not a transferred count or proof of this candidate's LAN exposure.

An admitted private IPv4 is not proof of local assignment or reachability.
Actual server interface/address, canonical hostname/port, matching DNS/IP SAN,
client name resolution and manual trust choice are still required before LAN
issuance. Chrome, Brave and Firefox each need actual trusted-chain and
unknown/wrong-certificate rejection, authentication, UI/action/recovery and
closure on the selected topology; no ignore-certificate fallback or global
trust installation. Linux is first; Windows/macOS and all original Gates1-3,
full AI plan and remaining deployment requirements stay in scope.
