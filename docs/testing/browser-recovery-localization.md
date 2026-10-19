# Focused Browser Recovery Localization

This separate hosted workflow runs two existing whole programs through the
unchanged focused-scenario entry point in `run-browser-ci.sh`:

- The four-mode CORS transport diagnostic: baseline, request interception,
  response interception and dual-stage interception, with distinct fixtures.
- The original match-start recovery program, including its original response
  dropping, durable intent, reload and explicit recovery assertions.

It uses the same setup actions, dependency declarations, ordinary hosted Chrome
and no-sandbox mode as the full CI browser job. Observed runtime versions are
recorded rather than assumed equal to earlier runs. No private trace, protected
backend input, provider credential or local developer database is supplied.

The existing launcher still builds its development frontend, checks the real
development proof, creates owned services and shuts down its own process groups.
The unchanged focused entry point uses a 300-second process bound per program,
not the ordinary full-suite 45/180-second bounds. Original in-program waits
remain unchanged. The additional aggregate bound is 720 seconds with 15 seconds
TERM grace. Nonzero results are preserved, and service ports must be absent
afterward; a failed port query also fails closed. This port check is
not a whole-host process or file-descriptor confinement certificate.

Two stdlib workflow tests cover the explicit origins and six mocked shell
outcomes, including a failing port query and retention of an earlier timeout.
These controls do not launch a browser, server or SQL connection.

This job is localization evidence, not the full UI/browser suite or native
Chrome, Brave, Firefox, release or Phase 1 acceptance. An earlier program failure
can prevent the later program from executing and must not be called its pass.
The ordinary full CI workflow is not edited or narrowed. No retry, recovery
workaround, application change or protocol-method substitution is introduced.
