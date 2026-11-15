# Dependency advisory review — scans currently blocked

No application dependency was installed, upgraded, removed or automatically
fixed. Package manifests and lockfiles remain unchanged. This is not a clean
security result and does not close Gate 3 #4.

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
