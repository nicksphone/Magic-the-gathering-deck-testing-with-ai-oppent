# Private HTTPS Operator Qualification

The four new `ops/caddy/` files are the exact postimages from the isolated
`0e57baf1f3d48526d3a85e7a0eea45da0b3dee93` runtime qualification. The parent
security entry points (`main.py`, `browser_origin.py`) and frontend source are
unchanged since that baseline. Later compiler/privacy work is not certified by
this operator run; final combined-source/browser acceptance remains required.

One actual invocation passed the complete native loopback corpus:

- Verified private-CA TLS, positive hostname verification, unknown-CA rejection
  and an independent incorrect-hostname validation failure (error 62).
- All 27 missing/wrong/malformed authentication checks returned 401 before
  backend access; built SPA/assets, API prefix and media routing passed.
- Authorization stripping, trusted-origin/native access, legal human setup,
  revision/idempotency handling and concurrent-launch locking passed.
- All 26 hostile-origin requests returned 403 with no body/dependency/action/
  sync/SQL processing and identical complete root/controller/database state.
- The unchanged incomplete-upload request sent zero body bytes: headers arrived
  in 0.091128s and its complete 403 body in 0.091358s, within the original 5s limit.
- Saved match, idempotency receipt and media recovered after a real restart.
  Both original lifespan shutdowns completed, engines disposed, DB descriptors
  and jobs closed; all six owned PIDs/listeners ended and `fuser` was empty.

The actual fix is Caddy's `enable_full_duplex` server option. It allows HTTP/1
responses before consuming the unread request body; native adapted JSON verifies
the option. No authentication/origin check, request body or deadline was weakened.
The four prior failed attempts and the phase-specific header timeout are retained.
The option is experimental; compatibility is proved only for this native corpus,
not every legacy HTTP client.

Verified source/evidence/closed fixture archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/operator-packaging/caddy-0e57-full-duplex-qualified-20261007-wVfKHc/`.
Read `evidence/ACTUAL-QUALIFICATION.md`, `INDEPENDENT-CLOSURE.json`, and
`SURGICAL-INTEGRATION-HANDOFF.md` for exact source, binary and postimage pins.
Private keys, operator configuration, password hashes and Caddy storage were
excluded and removed locally only after verified archival and resource closure.

Scope: Linux private loopback, one user/one backend worker, supplied verified
Caddy 2.11.7 binary, manual certificate and explicit trusted origin. No binary,
global trust, system service or live deployment is installed by this integration.
LAN/public exposure, multi-user authorization, clean-machine/current-browser
acceptance and arbitrary-process OS sandboxing remain unqualified. The original
README's pending-gate wording is preserved as a tested postimage; this record
provides its scoped runtime status rather than rewriting historical evidence.
