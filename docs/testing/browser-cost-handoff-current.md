# Browser Cost Fixture Handoff

The follow-up over `9ce7e1fc` changes only the cost browser program, its new
actual-script regression and the frontend test entrypoint. It reuses the
existing v2 readiness contract, not a new action retry or a longer timeout.

## Observed Failure

The actual `9ce7e1fc` remote browser job stops at the third cost scenario,
seat two's discard payment, before casting Bone Shards. Its captured view still
belongs to the spent seat-one fixture. The exact callback ordering was not
captured; no engine, card-legality or payment defect is established by this log.

The old driver permits a new fixture publication before the previous action's
rendered view, legal moves and active-match storage have committed. It also
samples a revision before waiting for the previous mutation to become idle.
The correction waits for the existing pending/restoring indicators before
fixture publication and each priority sample. After reload, stored and rendered
match identity and revision must equal the actual fixture response, with the
existing Resume automatic play control present. Each priority action still
waits for its original revision change and then for the mutation to settle.

## Independent Verification

The same eleven actual-source VM regressions reproduce three passes and eight
failures before correction, then eleven passes afterward. Their synthetic
DOM/CDP/API schedules exercise the actual program, not a game engine or Chrome.
The narrow regression denies network and children, with no recorded attempts.

The parent independently executes the complete 46-entrypoint frontend chain,
lint and production build; all exit zero. All 45 original entrypoints remain
the ordered prefix. Removing only the new waits reconstructs the entire old
cost program byte-for-byte; all thirteen assertions and sixteen original
gameplay/evaluate/API calls, selectors and clocks remain unchanged.

All 2,935 declared source files and 5,712 dependency files remain byte-equal.
Dependencies are an owned copy of an existing local cache; this parent build
uses Vite 6.4.3 and is not a new install or current-lock qualification. Generated
SVGs, dist and build metadata are recorded separately. Vite's transient config
cache is inside the owned dependency copy, not a borrowed dependency directory.
The complete frontend chain records two denied Node connect attempts without
attributable stacks. Python records no forbidden-I/O attempts; lint and build
record none. This is not an OS-wide sandbox or a zero-write claim.

## Remaining Acceptance

The original whole remote browser program subsequently passes on `58ab2881`,
including both seats' cost payments, recovery, natural BO3 and later
interactive/Cathar programs. See `browser-58ab-current-acceptance.md` for the
497-checkpoint result and exact coverage limits. This native result is separate
from the VM/frontend checks and does not reconstruct the earlier remote race.
The separate original ten-case Suspend HTTP cohort now passes with verified
cold-restart/closure; see `suspend-native-http-current-acceptance.md`.
Protected backend CI, other unproved native acceptance, measured AI quality and original
release Gates 1--3 remain separate requirements.

Reviewed patch: `087269a1ab7614fc9530101c6fe2dd6b34b13377cc94b67086ea501a13e9685f`.
Cost program: `8c7d2d382b73dc6e1061f4d066957b7eae747e458c91ae7093baa3ccaaa50470`.
New regression: `5ddc9257545704d3036e50dc2d14bdc52de6d30882e01ed9bdfc6b04f358ebbc`.
No private trace, raw CI log, database or dependency cache is published.
