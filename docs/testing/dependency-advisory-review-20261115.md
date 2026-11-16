# Dependency advisory review

No application dependency was installed, upgraded, removed or automatically
fixed. Package manifests and lockfiles remain unchanged. This is not a clean
security result. Completed host scans and proposed dispositions are recorded below; Gate 3 #4 remains open pending decisions and CI.

## Inputs and actual local results

Source: `main-e51` (`e51ddb82`) plus the audit command, 2026-11-15. Scope: frontend
package-lock (214 package entries) including build/test tools, a separate
production-only frontend query, and all 28 entries of the Python 3.12/Linux hash
lock. The nine direct Python requirements alone would miss the transitive lock.

| Input | SHA256 |
| --- | --- |
| frontend/package.json | 5bbcd5abba2330afe64286a322bdaaf000d22e2acb90922dd8a00e11055c376c |
| frontend/package-lock.json | 8a7ac6872d818c3d860500602f2147aa6b932b6b74eaeba11654779b3196923f |
| backend/requirements.txt | 7aa9f2b409551322171d8fdc0fcdde02fc5f38aedacdb9c904d6e47966c95b97 |
| backend/requirements-py312-linux.lock | c6a9c3a0416ee55b8d17c1470ccbe1745e62b80ba473ec83379811d212488beb |

Actual command:

```sh
MTG_AUDIT_PYTHON=/absolute/path/to/python3.12 bash scripts/review-dependency-advisories.sh
```

| Attempt | Observed result |
| --- | --- |
| npm audit, full lock | Exit 1, `ENOTFOUND registry.npmjs.org`, no vulnerability metadata returned |
| npm audit, production only | Exit 1, same DNS failure, no vulnerability metadata returned |
| Isolated pip-audit bootstrap | venv creation exit 1: ensurepip/python3.12-venv unavailable |
| pip-audit vulnerability query | **Not executed**; no results/counts |

Local Node is 26.8.1, npm 11.19.0. The script's overall exit was 1. Both npm
queries ran against copies with their own cache, with no node_modules install;
application inputs were unchanged. Zero vulnerabilities must not be inferred
from an endpoint failure, an absent report, or an unavailable scanner.

## Reproduce on supported host/CI

Run the command on a network-enabled host with venv support. It creates an owned
output directory and records revision, input hashes, scanner versions, raw JSON,
stderr and exits. npm uses the public registry advisory API, with separate full
and `--omit=dev` queries. A fresh isolated scanner venv installs **pip-audit
2.10.1**, not application dependencies, then queries every entry of the complete
hash lock using `--disable-pip --no-deps`. No `npm audit fix` or pip-audit `--fix`
is used. See [pip-audit usage](https://github.com/pypa/pip-audit#usage).

After merging, dispatch **Dependency Advisory Review** on the desired main
revision. The manual Ubuntu workflow provisions Python 3.12.3 and Node 24.22.0,
runs this script, and uploads the reports even on failure. It does not create a
PR or edit a lock. No workflow dispatch or hosted scan has run from this sandbox.
The wrapper exits nonzero on findings, malformed/partial results or query errors;
inspect the reports to distinguish those cases. pip-audit must report all 28
packages without skips. npm's exit 1 alone does not identify vulnerabilities.

## Review required after a successful query

For each advisory, record package and exact version, direct/transitive path,
production/build/test exposure, advisory ID/link, affected/fixed range, severity,
and whether the affected API is reachable here. Treat absence of a known
advisory as database coverage, not proof of security. Compare the full and
production npm reports; dev-only issues still matter for CI/build execution.
Separate OS/browser/Node/Python-runtime advisories from these package scans.

Send findings and proposed minimal upgrades to Claude **before changing any
application dependency or lock**. Any accepted exception needs explicit scope,
reason, owner and review date. Rerun both scans and relevant tests after an
approved upgrade. Until a completed scan and disposition exist, the advisory
review remains open; there is no accepted risk or upgrade decision in this PR.

## Completed host scans — 2026-11-15, approximately 23:3x

Claude supplied the full JSON reports from the committed PR #61 frontend lock
on Node 24.22.0 and from pip-audit 2.10.1 against the 28-entry backend hash lock.
I read the reports directly; these completed scans supersede the local query
failures above. The frontend dependency files match the inputs listed above.
The host npm version was not supplied. These are dated database observations,
not permanent assurances; there were no upgrades or auto-fixes.

| Completed scan | Result |
| --- | --- |
| npm audit, all 214 lock entries | 10 moderate package entries; 0 low/high/critical |
| npm audit, `--omit=dev` | 0 vulnerabilities |
| pip-audit `--disable-pip --no-deps --require-hashes` | 28 dependencies, 1 affected package/advisory; 27 without reported advisories |

Report SHA256s: npm-all `840311a4add09d382be36284ad610b2601cf782499f15cbd326fe55b0931d431`;
npm-production `bafc863409e129d17894a6ca81b8943a49b4e0d535a84668f255666c128c10e5`;
pip-audit `846e16b4b8a8d4684d3b45f610b5c1e05db4c6e16f96250ebedb3ea6f7154c3c`.
The npm ten are **two distinct advisories**, not ten independent defects:

| Affected locked packages | Advisory identity | Proposed disposition (Claude to decide) |
| --- | --- | --- |
| minimatch 10.2.6 | [GHSA-g3hv-75wg-m249 / CVE-2026-118764](https://github.com/advisories/GHSA-g3hv-75wg-m249), npm source **1244623** | Dev/CI glob processing; investigate compatible parent updates, otherwise a narrowly scoped, dated dev-tool exception pending a tested fix |
| eslint 10.11.0; @eslint/config-array 0.23.5; typescript-eslint 8.70.1; @typescript-eslint/eslint-plugin, parser, type-utils, typescript-estree and utils, each 8.70.1 | Same minimatch advisory, propagated through eight dependent package entries; no additional GHSA in their `via` chains | Same disposition; do not count these as independent advisories or blindly apply npm's suggested forced resolution |
| vite 6.4.4 | [GHSA-8g5g-mxqh-grgj / CVE-2026-118662](https://github.com/vitejs/vite/security/advisories/GHSA-8g5g-mxqh-grgj), npm source **1243858** | Recommend a separate approved 6.4.x patch update; advisory minimum 6.4.5, npm report proposes 6.4.6 |
| opentelemetry-api 1.45.1 | [CVE-2026-126360 / GHSA-mf5v-w3w3-f6cg](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-mf5v-w3w3-f6cg) | Recommend a separate approved patch to 1.45.2 with a new wheel hash and full locked-runtime validation |

### Reachability and remediation review

**Vite — actionable developer-server exposure.** The advisory concerns denied
file reads through crafted queries when a dev server is network-exposed and a
sensitive denied file lies within its allowed tree. The built static bundle is
not that server. This repo nevertheless enables the relevant network exposure:
`frontend/vite.config.ts` binds `0.0.0.0`, and README's dev command repeats
`--host 0.0.0.0`. Thus “devDependency” is not sufficient dismissal. The presence
of sensitive files and an exploitable request was not tested. In contrast,
`ops/caddy/run.py` starts Uvicorn and serves a prebuilt dist through the operator
proxy; it does not launch Vite. Recommendation: approve the patch update first;
until then keep dev servers loopback-only/trusted and keep secrets out of the
served workspace. This is a recommendation, not a configuration change here.
Revalidate Vite dev/proxy behavior, lint/typecheck/build, the full browser runner
and clean-checkout acceptance after any approved update.

**Minimatch/eslint chain — build/lint exposure, not shipped gameplay.** The
advisory's amplification requires attacker-supplied glob patterns with
`optimizationLevel >= 2`. The locked paths are eslint → minimatch,
eslint → @eslint/config-array → minimatch, and typescript-eslint → parser/
typescript-estree → minimatch. All flagged nodes have `dev: true`; none is a
React runtime dependency. `npm run lint` executes `eslint src`; the committed
`frontend/eslint.config.mjs` uses fixed `src/**/*.{ts,tsx}` and `dist/**` patterns.
Static inspection of matching installed package versions found `{dot: true}`
options in eslint/config-array and typescript-estree's inspected call site;
minimatch defaults to optimization level 1. Exploitation is therefore **not
established in these inspected paths**, not proved impossible in all tooling.
Untrusted PRs can change config/patterns and execute tooling in CI, so trust and
resource bounds still matter; no remote app-input-to-glob path was found.

The upstream fix starts at minimatch 11.0.1, outside these parents' declared
`^10.2.x` ranges. npm reports a semver-major/force-style proposed change to
typescript-eslint 8.36.0 despite our locked 8.70.1; that is not evidence of a safe
upgrade. Prefer compatible parent releases that adopt the fix. If unavailable,
Claude can choose a time-bounded trusted-config/CI-only exception or approve a
separate targeted minimatch-major override experiment. Such an override needs
API/Node-engine compatibility review, lint/TypeScript rule parity and full
frontend checks; do not use `npm audit fix --force` indiscriminately. No exception
is accepted by this document.

**OpenTelemetry — transitive production import, conditional vulnerable path.**
FastAPI 0.142.2 metadata requires `opentelemetry-api>=1.44.0`; FastAPI's
`applications.py` imports its telemetry modules, which import OpenTelemetry.
It is not an unused random lock entry. The vulnerability is ReDoS in
`TraceContextTextMapPropagator.extract()` for an untrusted carrier preserving
embedded newlines. Ordinary conforming HTTP headers cannot contain them;
JSON-carrier integrations need separate assessment.

`backend/main.py` creates `FastAPI(...)` without telemetry providers or middleware
instrumentation. No direct OpenTelemetry/traceparent extraction, provider setup
or MCP JSON carrier was found in application/operator source. The complete lock
contains no OpenTelemetry SDK/exporter/instrumentation package. FastAPI's
telemetry **configuration defaults to tracing true**, but `NativeTelemetry.enabled()`
checks that a real provider is configured; the default deferred providers do not
activate it. Its enabled tracing path calls `propagate.extract()` on ASGI headers,
not arbitrary request JSON. This supports **no demonstrated reachable vulnerable
carrier in the default checked deployment**, not unconditional immunity if an
operator adds instrumentation/providers or another integration.

A fresh constructor-only probe corroborated enabled=false with no OTEL settings
or providers, without importing main or starting services. That local interpreter
already has opentelemetry-api **1.45.2** (not changed by this work), so the probe is
not execution evidence for the locked vulnerable 1.45.1. The reachability judgment
rests on source/configuration and the closed lock, not that patched probe.

Prefer the small 1.45.2 patch despite the limited demonstrated exposure. It
satisfies FastAPI's lower bound. Changing only the version without its exact wheel
SHA256 breaks `--require-hashes` installation. Regenerate the approved Linux/
CPython wheel pin, verify all 28 resolved versions and `pip check`, rerun the
advisory query and backend/frontend/browser checks. Update the synthetic expected
version in `.github/scripts/tests/test_ci_backend_shards.py` in that upgrade PR
while preserving the runtime's strict lock equality; do not weaken metadata
checks. No telemetry disabling or HTTP validation workaround is implemented here.

### Decision status

All three advisory dispositions are **recommendations awaiting Claude**. Gate 3
#4 remains OPEN until risks/exceptions are decided and any chosen upgrades pass
CI and fresh scans. The zero-production npm result excludes dev tooling; it does
not negate the exposed Vite dev server. No application dependency, lock, CI
expected-version fixture or production source was edited in this review.

## Maintainer decisions — 2026-11-15

- **Minimatch/eslint temporary exception ACCEPTED by Claude**, project maintainer
  and exception owner. Scope: the dev-only lint/config chain for
  GHSA-g3hv-75wg-m249, including its propagated npm entries. Rationale: production
  dependency scan is clear; committed globs are fixed; the inspected calls use
  the non-amplifying default optimization level; no application-input exploit
  path was demonstrated. This does not declare minimatch generally safe or
  authorize arbitrary untrusted glob inputs. Keep CI resource limits and review
  changes to lint configuration. **Revisit when a compatible typescript-eslint/
  eslint release carries minimatch >=11.0.1**, or sooner if glob inputs/options,
  tooling exposure or exploit evidence change. Owner should review again by
  2026-12-15 if the upstream trigger has not occurred. No force override and no
  downgrade are approved.
- **Vite remediation handled by Claude in PR #64**, to 6.4.6. Host lint, build and
  1,047 frontend tests passed; the host rescan cleared the Vite advisory. This is
  a PR/host result, not a claim that its main-branch CI has already passed.
- **OpenTelemetry patch APPROVED**, 1.45.1 → 1.45.2, as a separate coordinated
  hash-lock/wheel-inventory/runtime-expectation change. It is not applied by this
  advisory-document branch. Validate the approved patch and rescan before
  closing its disposition.

These decisions supersede the earlier awaiting-decision wording. Gate 3 #4
remains OPEN until the selected remediation branches pass CI and the final
composed dependency scans/dispositions are confirmed.

## Applied patch status — 2026-11-16

Reviewed main `51d75a3f` already contains PR #66 (`c9a2f0c5`, patch commit
`8c9cdb99`). OpenTelemetry API **1.45.2 is applied**, not merely proposed:
`backend/requirements-py312-linux.lock` selects wheel SHA256
`2cbd737377e710ee740d261c94e93fa0f08e6d037c18f17513cc0a2d94479a34`.
The hosted-clean wheel/metadata inventory and synthetic runtime expectation are
aligned. All 28 application lock rows remain consistent; the installer is a
separate 29th inventory row. No second bump is needed.

This supersedes the earlier pending-integration wording. Vite 6.4.6 and the
accepted temporary minimatch exception remain as recorded. The **final composed
scan is still pending**: a permitted repository user must dispatch **Dependency
Advisory Review** on the intended main revision and retain its run ID/reports.
A changed lock is not by itself a successful scan or fresh-install/CI result.
Gate 3 #4 stays OPEN until that run and the maintainer dispositions are confirmed.
This follow-up changes only this document; no dependency pin is changed again.
