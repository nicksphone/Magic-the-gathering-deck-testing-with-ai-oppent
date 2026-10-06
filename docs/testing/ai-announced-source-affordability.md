# Announced-source affordability qualification

This is isolated-candidate evidence, not a live deployment or general AI-strength
claim. The candidate is based on `d88dbf0` with the composed selected-mana,
spell-consumption, fixed-cost witness and conservative planner-pruning patches.

Two real AI heuristics omitted the identity of the card whose cost they tested:
`mana_resource_policy._can_pay` and `AIAgent._can_deploy_major_threat`. Both now
forward the concrete card and source ID to the existing payment planner. Anonymous
capacity probes remain anonymous. No Oracle text, card costs, search cutoff or
matchup outcomes were changed.

## Evidence

- Before the two-call fix: 64 passed, six failed in the 70-case announced-source
  suite. Canonical Village Rites, Cling to Dust and Skirge Familiar exposed
  self-funding predictions in both seats.
- After: 652 passed, six warnings, 155.72 seconds across announced-source,
  AI mana/resource forecasts, recurring engines, cast resource policy, public
  mana changes, fixed spell cost witnesses and spell-consumption reservations.
  No skips, deselections or expected failures in this gate.
- Separate joint mana/cost gate: 275 passed and two existing escape-fuel expected
  failures, 12.33 seconds. Those expected failures are still open; they are not
  resolved by these two heuristic calls.
- Fresh 63-module whole regression invocation: 2,577 passed, two existing
  Song/type-layer expected failures and 152 warnings in 510.53 seconds, exit 0.
  No module exclusions, deselections or skips. It ran in a source-only local
  checkout with no Git metadata or pre-existing SQLite database. The two Song
  markers are distinct from the escape gaps in the joint-cost gate. This is a
  broad scoped gate, not the entire repository test suite.

Raw before/after logs and the two-file incremental patch are preserved under
`parent-integration/spell-reservations-d88dbf0/` in the project's NFS artifact
store. These gates overlap; their counts are not additive coverage.

## Composed Human And Replay Checks

Frontend lint, build, unit tests, ten Suspend view checks and the five manual-mana
component/wire suites pass with the explicit existing test interpreter. Fourteen
actual-App explicit-mana cases and six shortcut cases pass against the current
backend, covering both seats, chosen resource/output payloads, privacy and restart.
An initial isolated test invocation omitted the Python interpreter setting and
failed with ENOENT; the original log is retained rather than counted as passing.

Seeded Strong replay smoke checks complete in both seat orders with repeated
equality: two expansion aggro templates, then explicitly selected Burn versus
Dimir Control. The core named pair uses hash-pinned hydrated inputs and classifiers
recomputed from those inputs. Burn classifies as Burn and Dimir as Control.
Both core games finish (33 and 14 turns), with zero passes while a land play is
legal and zero invalid-cost messages. Control wins both; this tiny sample does
not establish balance or seasoned play. Full hand/board/action traces and private
stage timings are retained under `current-source-replay/` in the artifact store.

Fresh bootstrap metadata stores Midrange for several named core decks. This is
under separate investigation; the replay agent independently recomputes its style,
so stored metadata alone does not prove the replay used the wrong AI archetype.

## Remaining work

Complete current-source browser integration, broader backend regression and the
separate post-mana escape-fuel witness investigation before promotion. Layer,
face-selection and non-mana intent audits are separate scopes. These checks do
not establish seasoned-player strategy or arbitrary-card MTG correctness.
