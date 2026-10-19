# Focused Browser Recovery Localization

This separate hosted workflow runs two existing whole programs through the
unchanged focused-scenario entry point in `run-browser-ci.sh`:

- The four-mode CORS transport diagnostic: baseline, request interception,
  response interception and dual-stage interception, with distinct fixtures.
- The original match-start recovery program, including its original response
  dropping, durable intent, reload and explicit recovery assertions.

It uses the same setup actions, ordinary hosted Chrome and no-sandbox mode as
the full CI browser job. No private trace, protected backend input, provider
credential or local developer database is supplied.

## Runtime Parity

The initial `a99a569a` focused run passes all four transport modes and four
start-recovery flows. Its observed Python is 3.12.15; the backend gate uses
3.12.3. FastAPI and Starlette match the current lock. Three transitive packages
do not: SQLAlchemy 2.0.55 versus 2.0.54, certifi 2026.10.18 versus 2026.7.22,
and pluggy 1.7.0 versus 1.6.0. This is not proof of the cancellation cause.

The frontend fixture, full browser and focused jobs now reuse the existing
backend hash lock, Python 3.12.3 and Ubuntu 24.04 contract. A shared installer
creates a fresh venv, verifies the existing platform and complete 28-package
identity, and publishes its path only after successful admission. Package and
application requirements are not changed. Full CI test declarations remain.
Mocked installer controls cover success, four failures and stale path rejection;
they do not claim a local package installation or actual hosted parity result.

## Separate Cold Component

Before browser execution, the unchanged offline probe runs once from a separate
committed-backend archive. Its configured SQLite file is freshly absent in a
separate runtime directory, outside the extracted source. It exercises shipped
hydration/fallback HTTP responses through TestClient, idempotent match start and
in-process snapshot restoration. It is not process restart, browser rendering
or OS-level network confinement. Its own socket-method observations are bounded
by the existing probe. Probe data/cache are not used by the subsequent browser
launcher; this is not a same-database cold/warm declaration.

The existing launcher still builds its development frontend, checks the real
development proof, creates owned services and shuts down its own process groups.
The unchanged focused entry point uses a 300-second process bound per program,
not the ordinary full-suite 45/180-second bounds. Original in-program waits
remain unchanged. Browser work has an aggregate bound of 720 seconds with 15
seconds TERM grace; the separate cold probe has 300 seconds. The 25-minute job
deadline also includes setup and cleanup, not a promise of remaining time for
each independent maximum. Nonzero results are preserved, and service ports must be absent
afterward; a failed port query also fails closed. This port check is
not a whole-host process or file-descriptor confinement certificate.

Two stdlib workflow tests cover the explicit origins and six mocked shell
outcomes, including a failing port query and retention of an earlier timeout.
These controls do not launch a browser, server or SQL connection.

This job is localization evidence, not the full UI/browser suite or native
Chrome, Brave, Firefox, release or Phase 1 acceptance. An earlier program failure
can prevent the later program from executing and must not be called its pass.
Ordinary CI test/scenario declarations remain unchanged; runtime installation
is updated as described above. No retry, recovery workaround, application
change or protocol-method substitution is introduced.
