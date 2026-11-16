# Firefox current-source acceptance plan — not an acceptance result

Reviewed main: `51d75a3f`. Owner: Claude/project maintainer; implementation/run
assignment requires approval after these prerequisites. This document changes
no driver, fixture, source pin or workflow and starts no browser/server.

## Current facts

- `/usr/bin/firefox --version` returned **Mozilla Firefox 160.0** here on
  2026-11-16. The executable exists, but this is only a version probe: no profile,
  BiDi session, application request, rendered episode or sandbox qualification.
- `.github/workflows/native-browser.yml` declares Chrome and Brave, **not Firefox**.
  Green main/default browser CI is not evidence of Firefox acceptance.
- `frontend/tests/run-browser-ci.sh` is a Chromium/CDP launcher. Do not point
  `MTG_CHROME` at Firefox, silently substitute Chromium, or claim its program
  declarations are Firefox runs.
- Firefox transport/driver, native-input, bootstrap, response-cache and owned
  launcher components exist. The release-owned launcher requires explicit owned
  layout/executable pins and still contains historical/private runtime defaults;
  it is not a copy-paste current clean-checkout entrypoint.
- The historical Firefox 158 application-50 run completed its declared episodes
  on its old source but retained a separate outer identity-observation hold.
  Neither the app result nor later component fixes certify Firefox 160/current
  main or remove that historical hold. See [the historical scope](firefox-native-application50.md).

## Before writing or running a new adapter

1. Select the final measured commit after intended launcher/dependency fixes.
   Create a fresh owned source/DB/profile and install locked app dependencies
   (Node 24.22.0, the complete Python hash lock). No developer DB/art/cache/profile
   reuse. Record source/lock identities and actual runtime versions.
2. Admit an actual Firefox binary on a network/listener-capable ordinary-user
   host: full version, resolved executable, file hash and vendor/package signature
   provenance. A version string alone does not authenticate a build. Keep default
   browser sandbox settings; do not disable protections to make startup pass.
3. Review the current transport's command coverage against **every** configured
   browser program, including programs launching independent services/pages and
   the new Battle/payment cohort. Enumerate unsupported operations explicitly.
   The async-readiness `data:` navigation and the older BO3 enrollment contract
   are known integration work; a skipped program or changed assertion is not a
   transport fix. Any pinned runner/fixture change needs its reviewed layered
   delta before execution, leaving old pins and natural BO3 inputs untouched.
4. Implement a distinct, explicitly selected Firefox launcher/transport path
   with owned startup/readiness and response-cache lifecycle. Use the real
   Firefox BiDi session, fresh profile and actual child handles. Missing startup
   evidence, unknown child identity, failed close, unsupported wire command or
   unavailable required response body must invalidate the run, never become a
   gameplay pass. Use committed current source, not a historical private archive.
5. Add adapter-specific bootstrap/command/closure controls and host-run the
   complete component checks. This is preparatory evidence, not game acceptance:

   ```sh
   npm --prefix frontend run test:unit:firefox
   (cd backend && python -m unittest discover -s tests -p test_firefox_response_cache.py -v)
   ```

No ready-to-run **full current-source Firefox command** is asserted here: the
adapter integration in steps 3–4 must land first. The run handoff must then name
its exact command, commit, browser and all prerequisites. The existing legacy
release-owned command's fixed layout/private defaults must not be guessed or
reused to manufacture an apparent current pass.

## Required native run, once the adapter is ready

Run the **entire configured cohort**, with a predeclared inventory and exact
per-program/episode results, not a successful subset called full coverage. Keep
all existing assertions and original natural BO3 cohort; add these current cases:

- Both-seat Battle and deferred-upkeep-payment episodes in human/human and
  human/AI modes. Label those **declared canonical midgame**; exercise real App
  controls/HTTP/rules/SQLite, Siege combat/transform, Pact pay and decline, and
  reload while the payment choice is pending.
- Unknown-control warning cases for both seats. Run the unmodified warning-only
  baseline, then a disposable warning-node-removal mutation. RED must fail at the
  explicit missing-warning assertion after its panel renders, not at startup or
  a missing transport method. Revert the mutation; it never enters main.
- Existing paid actions, response windows, combat/targets/order/payment choices,
  native input/focus, unavailable-art fallback and game results. Preserve tests
  that use native input rather than substituting JS clicks to hide a driver gap.
- Existing natural HH and both-human-seat AI BO3, mulligans/bottoms/sideboards and
  play/draw transitions; refresh, lost accepted response, idempotent reconciliation
  and backend restart. Record whether each loss is ASGI, browser transport or
  actual TCP; one is not evidence of all three.
- The one-command built-frontend launcher, once merged: real UI/API/media on one
  loopback origin, owned DB, graceful stop and saved restoration. This local HTTP
  smoke does **not** qualify trusted HTTPS or a remote LAN client.

On failure, retain the first failing program, assertion/error class, stage,
revision and sanitized diagnostics, plus actual owned-child exit/closure status.
Do not retry until a test turns green or combine different attempts into one
result. Missing report, bootstrap timeout or partial run is incomplete, not a
rules loss, browser pass or original-cohort qualification.

## Exit criteria and report

Required: all declared programs/episodes completed with original assertions,
warning mutation RED discriminates, no unhandled browser/runtime error, no
unsupported transport operation, and all owned services/profile users closed.
Separately record input/output privacy and browser sandbox/provenance limits.
The report must identify commit, browser/runtime versions, exact command,
program inventory, actual PASS/FAIL/SKIP counts, duration, failure ledger, and
current-source changes/checks. No summed historical counts or strength percentage.

Even a passing loopback Firefox run leaves assigned-device LAN routing,
certificate trust, long-session soak/accessibility and full RC sign-off separate.
This plan itself adds **zero** Firefox gameplay evidence and no CI execution.

Protocol reference for the adapter review: [Mozilla Remote Protocols](https://firefox-source-docs.mozilla.org/remote/index.html) and [Remote Agent security](https://firefox-source-docs.mozilla.org/remote/Security.html). These references do not constitute a native run.
