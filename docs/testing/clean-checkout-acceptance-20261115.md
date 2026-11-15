# Clean-checkout acceptance

Run on the same supported platform as CI: CPython 3.12.3, Linux x86_64,
glibc 2.39, Node 24.22.0, npm, git, GNU timeout, and installed Chrome/Chromium.
Run as an ordinary user with browser sandbox support and loopback listeners.
Package registries are needed for installation; application offline checks run
separately after installation. This is not an air-gapped dependency installation.

From a checkout containing the script, with the desired revision committed:

```sh
MTG_ACCEPT_PYTHON=/absolute/path/to/python3.12 \
MTG_CHROME=/absolute/path/to/google-chrome \
bash scripts/accept-clean-checkout.sh HEAD
```

The argument is a committed revision, not the caller's working tree. The script
archives it into a newly created workspace, creates an independent virtualenv,
installs the hash-locked backend and npm lock with a fresh npm cache, and checks
installed runtime metadata. No existing venv, node_modules, database, artwork
cache or uncommitted file is copied. App-specific MTG settings and Python import
path overrides are discarded, without printing their values. No caller data is
deleted. The workspace is retained on success and failure.

Stages run serially and stop at the first failure:

1. CI platform and Node version, fresh installs, pip check and runtime identity.
2. Existing cold offline probe, with no initial DB/cache and socket connections
   blocked before app imports: shipped-name hydration, served fallback SVGs,
   idempotent start and persisted restoration. Its JSON reports actual counts.
3. Whole API input, offline hydration and release card contract test modules;
   pytest writes exact pass/fail counts to the log and JUnit XML.
4. The three production operator runtime boundary/inventory/source checks.
5. Full configured npm tests, lint, and production build.
6. Full configured browser runner (no focused selection), with newly installed
   dependencies, another fresh source/database/cache/profile and no developer
   files. The existing UI-v2 offline case asserts `.card-no-art` while retaining
   canonical names/stats. This is a missing-art UI fallback check, not proof
   against every possible external network request.

`results.tsv` contains each attempted stage and exit status; `logs/` retains
output, `api.xml` has backend cases, and `runtime.json` records installed runtime.
`ACCEPTED.tsv` is written only if every configured stage succeeds. Browser
programs report their own episodes; an installation failure is not a test pass.
The configured runner on the accepted revision defines cohort membership. Run
after PR #61 lands to include the Battle/deferred-payment episodes.

## Current evidence

The script has not completed on this sandbox. Its installed Node is 26.8.1,
which intentionally fails the Node preflight (requires 24.22.0). Socket/Chrome
permissions and registry access also prevent claiming host acceptance here.
Host results must include revision, workspace, per-stage exits, pytest totals,
frontend summaries and browser episode output. Do not substitute the earlier
cached-dependency build or focused PR #61 run for this full command.

This run covers the declared Gate 1 #7 checks. Passing it does not establish
complete rules support, AI strength, backup/restore or overall RC readiness.

## Hosted execution

After this branch and PR #61 are merged, dispatch **Clean Checkout Acceptance**
(`.github/workflows/clean-checkout-acceptance.yml`) on main in GitHub Actions.
The job provisions CI's exact Python/Node and current signed Chrome, then runs
the command against `GITHUB_SHA`. It deliberately uses no setup-node npm cache;
the script installs dependencies into its fresh workspace. CI explicitly uses
`MTG_BROWSER_NO_SANDBOX=1`, matching the existing browser CI job; the result does
not certify the Chrome OS sandbox. Local runs default to sandbox enabled.

The artifact includes revision, stage exits, runtime identity, JUnit and stage
logs, including browser episode output, even after failure. It excludes profiles,
DBs and package caches. Record the run ID and exact results after it finishes.
A dispatch that fails provisioning or a stage leaves #7 open. The workflow has
not been dispatched from this sandbox.

The host attempt at `dd8c988a` passed platform and Node checks, then failed venv
creation because that host lacked ensurepip/python3.12-venv. No downstream tests
ran. The hosted setup-python step supplies venv support without requiring host
sudo or reusing an existing environment.
