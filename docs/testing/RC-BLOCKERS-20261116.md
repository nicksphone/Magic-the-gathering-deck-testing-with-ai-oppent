# RC blockers and required evidence — 2026-11-16

**RC is not accepted.** Reviewed main:
`8e17fd55a2eb5284977919a95e038370eb48106d`. This is a documentation audit,
not a test run, workflow dispatch, matrix launch or deployment. It reconciles
the original [Gates 1–3 and Completion Checklist](../../plan.md#gate-1-reliable-local-human-playtesting),
the [release completion requirements](release-acceptance-status.md#required-before-completion)
and the [knowledge plan](../plans/2026-09-09-ai-knowledge-base.md).

Use this as one open-work checklist. Preserve historical reports and failed
attempts; do not rewrite them into final-source results. A checked implementation,
merged PR, component pass, zero parser warning or `PILOT-COMPLETE` marker does
not clear the broader gate that depends on it. The long-term all-rules,
arbitrary-deck and seasoned-player objectives remain open too.

## Evidence rules and audit findings

The audit searched `docs/testing` Markdown for gate, acceptance, qualification,
current-status and remaining-work claims, then checked the linked release,
knowledge, browser, storage and operator reports against the commands/workflows
in the reviewed tree. It does not independently authenticate private archives
or re-execute the historical claims. The following dependencies apply wherever
those claims appear, including documents whose title says “current”.

| Claim in the documentation | What it establishes; what still blocks promotion |
| --- | --- |
| “Full CI passed”, including [Phase 1 acceptance](phase1-acceptance-current.md), [release status](release-acceptance-status.md) and [current release status](current-release-status-20261116.md) | Only the named source/run and configured jobs. Obtain completed final-source CI; do not add host/subset counts to its totals or transfer an old green run to a later merge. |
| “833 data cases”, [card-data acceptance](current-card-data-acceptance-20261108.md), [rulings corpus](knowledge-rulings-shipped-corpus.md), [domain admission](knowledge-domain-admission.md), and the November 9 knowledge qualification reports | Real bounded fixture/model/repository evidence on their named source. Not a census of all user decks, every indirect fixture input, live migration, all-card sync or all mechanics. Repeat the declared current-source cohort and reconcile the original Phase 1 requirements. |
| “155 complete/ready names”, [fresh-install knowledge acceptance](current-clean-install-knowledge-acceptance.md), [legacy-copy readiness](phase1-legacy-copy-readiness.md) | The fixture/selected-copy inventory, with verified empty rulings allowed. The default report historically enumerated 149, separately checked 155, and a selected legacy copy enumerated 158; none is a current universal count. The operator must select and report the actual corpus/decks. Data, image availability and semantic support are separate. |
| “Persisted tags affect decisions”, [tag acceptance](ai-knowledge-tags-current-acceptance.md), [consumer audit](ai-knowledge-consumer-audit.md), [repository qualification](ai-knowledge-repository-qualification-20261109.md), [consumer qualification](ai-knowledge-consumer-qualification-20261109.md) | Bounded production dataflow/privacy/choice evidence. It does not establish complete threat/answerability migration, learned matchups, deliberate sideboarding, causal decision improvement or AI strength. Current repository/trace/restart checks and separately judged before/after decisions remain required. |
| “No known unsupported mechanics”, [coverage report](knowledge-engine-coverage.md) and [matrix plan](archetype-matrix-plan-20261115.md) | Admission/classifier output only. No semantic certificate; no bypass of flagged cards. Burn and Mono Red remain explicitly excluded from v2, not repaired or silently substituted. |
| “Natural games/full matrix” in [historical browser50](current-d657-native-browser50.md), [Master matrix](full-master-matrix-20261108.md), and earlier AI reports | Only the stated games/source and actual terminal outcomes. The rejected 110-series prefix cannot be reused. New canonical-midgame browser cases are not natural histories; a head-to-head smoke is not the predeclared matrix or a strength estimate. |
| “Native browser passed” in [Chrome/Brave](current-2d-browser-acceptance.md) and Firefox reports | Vendor/source/transport-specific evidence; see the browser table below. Generic no-sandbox CI, SSR, driver mocks and a focused Chrome smoke do not certify all native vendors or final HTTPS/LAN trust. |
| “Clean install/advisories/storage/operator accepted” in the older component reports | Source/environment/topology-specific evidence. The final fresh-install workflow, composed advisory dispositions, selected deployment, restored real app and manual operator checks remain separate. No archive path grants permission to mutate a live DB or trust store. |

The reviewed [current-status page](current-release-status-20261116.md) still
describes OpenTelemetry 1.45.2 as pending; the later **Applied patch status** in
the [advisory review](dependency-advisory-review-20261115.md#applied-patch-status--2026-11-16)
correctly records it applied. Do not bump it again. The matrix plan's earlier
“no adapter” wording describes its earlier stages; adapter `c8878a65` is code
with a maintainer-reported 75/75 host result, not measured games or a merged
execution result on this reviewed main. Read its final appended section once
integrated, not the superseded eleven-deck instructions.

There is also a **scope conflict to reconcile, not a new user decision**:
the release ledger explicitly records separate-device LAN/manual CA-trust
checks as **user-deferred for RC, not passed**, while November's current-status
page calls them open without repeating that deferral. Preserve the deferral.
Local HTTPS/authentication and Linux Chrome, Brave and Firefox remain required.
The broader LAN objective remains unfinished; do not silently restore it as an
RC blocker or pretend it passed.

## Final-source prerequisite

- [ ] **F0 — Freeze the intended source and complete CI.** Owner: Claude on
  GitHub/CI. Integrate the intended PRs, record the exact main SHA, then require
  every configured job to finish successfully on that composition. At this
  audit's final check, PR72 (`517c203e`) run **43872988162** was still running;
  PR75 (`a389bdad`) run **43862518476** had succeeded in all eight jobs. That
  branch result is not a later main-composition run; per-case counts were not
  inspected by this docs audit. Commands are in **C0**. Preserve exact
  collected/pass/fail/error/skip/xfail and episode counts, not just an exit code.
  A later source change needs scoped revalidation.
- [ ] **F1 — Integrate and confirm the new bounded components.** Owner: Claude,
  then final CI/host. Backup PR75 has a supplied 28-pass host result. Matrix
  adapter `c8878a65` has a supplied 75-pass host result but no pilot. Launcher
  smoke `1b7814bc` has a supplied **3-pass Python result and real Chrome
  create/restore/restart PASS**; it is stacked on PR72, not part of reviewed
  main. These facts advance their named cases, not all Gates 1–3. Use **C4**,
  **C5** and **C7** only after the corresponding files are integrated.

## Open requirements, owners and closure evidence

Every row stays open until its stated evidence exists on the intended release
composition. Commands marked **preparation only** cannot close that row alone.
“No accepted command yet” identifies missing acceptance work rather than an
invented runnable test or an automatic waiver.

| Open item | Exact evidence required | Who / command |
| --- | --- | --- |
| [ ] **G1.1 — Hydration and characteristic parity** | Faces (including Battle defense), effective stats/keywords, counters/damage and knowledge carriers agree through API, sideboard, simulator and replay, including cold restoration. Record exact mismatches and resolved cases; a parser or seed census alone is insufficient. | Host/CI: **C2**, **C3**, **C4**; owner must inventory any remaining cross-surface cases. |
| [ ] **G1.2 — Interacting choices** | Real HTTP/UI draw/discard replacements, cleanup/repeat cleanup, trigger order and human choices, with pending state surviving restart. Add any supported branch absent from the configured cohort; no silent auto-choice. | Host/CI: **C4**. Broader missing cases need new tests, not a claim from these examples. |
| [ ] **G1.3 — Complete supported human play** | Entire configured HH/both-human-seat AI/BO3 browser cohort plus supported-action inventory, Battle/payment cases and discriminating unsupported-warning RED. Record each program/episode and failed/unsupported branch. Canonical midgame and natural games remain separate labels. | Host/CI: **C1**, **C4**; native vendors below. |
| [ ] **G1.4 — Rejection atomicity** | Malformed/stale/wrong-actor/failed-write requests leave complete state/controller/SQLite unchanged across the declared new actions. Battle 64-pass evidence covers its test scope, not all API mutations. | Host/CI: **C4**, final full CI **C0**; expand any uncovered action family. |
| [ ] **G1.5 — Recovery and overlap** | Refresh, actual backend restart, lost accepted response, manual/autoplay overlap and retry reconciliation with original keys/revisions. Classify ASGI response loss separately from browser interception and actual TCP interruption. | Host/CI: **C4**. No single existing command certifies every TCP/disconnect path; missing cases need a declared real-network test. |
| [ ] **G1.6 — BO3/sideboards** | Current-source natural series, mulligans/ordered bottoms, loser play/draw, genuine inventory swaps and restart parity. Deliberate AI sideboard policy must be qualified or explicitly unavailable; a series win is not policy-strength evidence. | Host/CI: full browser **C1**, backend **C4**; strength portion also **G2.6**. |
| [ ] **G1.7 — Fresh-checkout acceptance** | Successful complete `Clean Checkout Acceptance` on final main: fresh locked installs, runtime identity, cold offline assets, API/operator checks, full npm tests/lint/build and unfiltered browser flow. Retain `ACCEPTED.tsv`, all stage exits, JUnit/runtime and episode logs. Missing ensurepip/Node/socket preflight failures prove no downstream pass. | **User with dispatch rights → CI: C1**. Local supported host alternative also **C1**. |
| [ ] **G2.1 — Supported knowledge corpus / original Phase 1** | Current provenance, full faces/rulings/legalities/image/token fields and explicit gaps for the declared corpus and selected stored decks. Reconcile Tasks 1.1–1.4, including hand-authored fallback/fixture scope and indirect constructors. All-card sync completeness, offline image availability and semantics must be reported separately. | Host/CI: fixture cohort **C2**; operator-selected local-copy/live-data follow-up **C8**. No live migration or all-card fetch is authorized by this checklist. |
| [ ] **G2.2 — Rules fidelity** | Canonical paid/action outcomes for supported layers, replacements, continuations, LKI/incarnations and unsupported families. Retain the legacy-unknown seam as open: typed controls pass, untyped historical cleanup has strict xfails; maintainer must decide a provenance/migration policy before a rules change. | Host/CI: **C4**, **C9**, full CI **C0**. Missing rules families require new canonical cases. |
| [ ] **G2.3 — Canonical interaction fixtures** | Current-source corpus/fixture inventory plus actual combat/protection/mana/zone/alternative-win outcomes and durable HTTP/replay parity. Battle goldens are bounded coverage. Neither source pins nor a zero-gap report replace executing these outcomes. | Host/CI: **C2**, **C4**, **C0**. Whole original fixture-inventory sign-off remains a review task. |
| [ ] **G2.4 — Knowledge changes production decisions** | Persisted repository → hydration → actual choice → private usage trace → cold restore, hidden-information controls and causal before/after examples across declared styles. Document fallbacks and unimplemented threat/answerability/learned-matchup paths. | Host/CI: **C3**. Full style-wide causal review has **no accepted complete runner yet**; maintainer must predeclare it. |
| [ ] **G2.5 — Decision quality** | Reviewed current decisions for racing, blocking, reservations, timing, targets, mana, mulligans and multi-turn play. No hidden observations, named-card shortcuts, fixed winners or error-to-pass fallback. | Host/AI reviewer: **C3/C5 are preparation only**. No accepted command presently scores every required quality dimension. |
| [ ] **G2.6 — Benchmarks and A/B** | Frozen hidden-information benchmarks with judged opportunities, legal actions, causal anomalies and comparable before/after conditions. A win rate, reason string or number of stored traces is insufficient. AI-STATUS's unaccepted strength/learned-model limits persist. | Host + maintainer: predeclare benchmark/labels and reviewed A/B analyzer; **no accepted full A/B command yet**. |
| [ ] **G2.7 — Seed/seat matrix and parity** | Approve/run the independent 36-game pilot, inspect every outcome/forecast, then approve a full-matrix controller/run. V2 is 1,440 cells / nine decks, zero crashes/illegal accepted actions/replay/parity divergences and at most 14 resource-limit cells. All cells/traces remain in the denominator; Burn/Mono Red and broader archetypes remain open. Selected direct-handler/SQLite checks do not certify continuously HTTP-played or fresh-app-restart parity. | Host + Claude budget approval: **C5**. Full-matrix batch CLI and remaining parity acceptance are not yet delivered; pilot completion is not RC acceptance. |
| [ ] **G3.1 — Local HTTPS/authentication** | Final built UI/API/media/auth/origin behavior through the pinned local HTTPS proxy, actual certificate verification and each required Linux browser. Earlier 563/617-instance components are not final-source acceptance. Separate-device LAN/manual CA trust stays user-deferred for RC, not passed; it remains necessary before a wider deployment. | Authorized host/user: **C6** plus reviewed browser/TLS protocol. No complete final-source HTTPS acceptance command exists. Remote topology/trust work needs renewed user authorization; it is not an unconditional local-RC blocker. |
| [ ] **G3.2 — Single operator/worker** | Landed enforcement tests remain green; docs match actual launcher and capacity-owner behavior. One BasicAuth identity and same-file local locking must not be presented as tenant/seat authorization or distributed ownership. Broader exposure needs separately reviewed auth/origins/limits. | Host/CI: **C6**. Local launcher smoke is a bounded host PASS, not secure multi-user deployment. |
| [ ] **G3.3 — Jobs/resource lifecycle** | Current-source admission/queue/cancel/retention/crash/restart and stale concurrent mutation evidence, including physical exhaustion/WAL/RSS limits actually claimed. Historical logical-capacity and A/B/C crash components are not a physical containment or distributed-worker certificate. | Host/CI: **C7** component tests; current real-crash/physical-limit protocol still needs maintainer declaration. |
| [ ] **G3.4 — Dependency advisories** | Fresh final-lock full/prod npm and complete 28-package pip reports, query completeness/exits and explicit dispositions. Verify Vite 6.4.6/OpenTelemetry 1.45.2 in composed CI. Retain Claude's dated dev-only minimatch exception, review trigger and owner; findings exit 1 may be expected, but query failures are never clean scans. | **User with dispatch rights → CI: C10**. Claude reviews reports/exception. OS/browser/Go/Caddy/runtime exposure needs its own disposition, not npm/pip extrapolation. |
| [ ] **G3.5 — Clean-machine operation** | Final clean install/offline checks, populated backup/clean restore with exact saved revisions/keys, plus predeclared long-session browser soak, accessibility and actionable-error review. Backup host 28-pass evidence covers reconstruction only. | Host/CI **C1/C7**; user/manual reviewer for soak/accessibility. **No accepted complete soak/accessibility command yet**; choose duration, scenarios and pass criteria before running. |
| [ ] **G3.6 — Reconcile and release** | Final changed-file/source/lock inventory, exact run IDs/counts, known skips/xfails/exclusions, risks and manual sign-off agree across README/plan/AI-STATUS/status pages. Publish/deploy only after appropriate gates pass; record actual running revision/readiness separately from Git pushes. | Claude + user. **C0** identifies source/evidence; no command can substitute for the final requirement review and deployment approval. |

Additional explicit completion/current-batch obligations must not disappear
inside the broad rules rows:

| Open item | Exact evidence required | Who / command |
| --- | --- | --- |
| [ ] **P1 — Pending-source/hand-to-library privacy** | Final-source mixed HTTP/SQLite qualification of pending public stack sources, authorized memory and complete private hand-to-library continuations, including cold restoration and both viewer seats. Public responses must not reveal hidden identities, order, tags or private carriers. Pure decision-view or source-pin checks alone are insufficient. | Host/CI: bounded privacy cohort **C13** plus current continuation inventory and any missing HTTP/restart cases. Links: [pending stack](pending-stack-privacy-current.md), [pending source](pending-source-privacy.md). |
| [ ] **B1 — Graveyard clause/zone/permission inventory** | Complete inventory before relaxing conservative combat leaves; canonical execution and hidden-information controls for missing clauses/layouts. No offered move is not proof of inertness. Existing bounded cases do not establish the full inventory. | Host/maintainer: **C13** is preparation; expand inventory/accepted outcomes. [Current scope](graveyard-combat-current.md). |
| [ ] **B2 — General land animation** | Canonical admission, continuous characteristics, summoning sickness, cleanup and source incarnation across response/reentry; current Flicker/Cloudshift results cover named cases only. | Host/CI: **C13** bounded checks. No complete general-animation acceptance runner exists; inventory remaining families. [Current scope](animation-strategic-current-composition.md). |
| [ ] **B3 — Targeted-search lifecycle** | Source departure/reentry and partial target loss through genuine responses, private choices and cold restart; explicitly account for browser, Ray of Command and dedicated activation paths rather than assuming prior Favor/Act cases cover them. | Host/CI: **C13** bounded tests, then declare missing UI/Ray/activation episodes. [Current scope](announced-target-current-composition.md). |

The seven completion requirements in `release-acceptance-status.md` map to
P1/G1.1/G1.4–5 (privacy/HTTP), G2.1–3/B1–3 (inventory), G1.3/G1.6–7 (built UI/BO3),
G3.1 (HTTPS), G3.3/G3.5 (operations), G2.4–7 (AI) and F0/G3.6 (final audit).
None is dropped merely because it overlaps another row.

## Native browser status — distinct from generic CI

| Browser | Accepted bounded evidence | Still required / exact entrypoint |
| --- | --- | --- |
| **Chrome** | The release ledger records later secure vendor run **39702892051** on the October accessibility composition, after native `ab6e388b` run **39685416759** and `2d106588` run **38713486004**. These have bounded source/vendor/preflight/lifecycle scope. New launcher `1b7814bc` has a supplied host Chrome smoke PASS, without a native-vendor/sandbox qualification claim. | Final-source **Native Linux Browsers** workflow, both current program inventory and preflight/lifecycle; dispatch **C11**. A normal CI/browser job using `--no-sandbox` cannot close this native-protected row. |
| **Brave** | The same later secure runs **39702892051/39685416759** passed Brave separately, as did the older `2d106588` run. Chrome does not stand in for Brave. | Same final-source workflow **C11**, **Brave job must itself pass**. No current-source native pass is asserted here. |
| **Firefox** | The release ledger's October 22 checkpoint records Firefox **158.0.1** on `ab6e388b`: complete original 50 cases, manager exit zero and independent closure. That later pass does not erase the separate outer identity-observation hold in the older [application50 attempt](firefox-native-application50.md). Firefox 160's version probe and unit tests are not current app acceptance. | Follow the [current acceptance plan](firefox-acceptance-plan-20261116.md): qualify distinct current BiDi/bootstrap/response-cache/native-input integration, then whole cohort + warning RED + owned closure. **No ready full-current-source Firefox command/workflow exists. C12 is preparation only.** Never pass Firefox to the Chromium/CDP runner. |

These rows do not settle remote LAN trust, long-session/accessibility or overall
RC. Do not add counts across vendors or call the old 50 episodes the current
configured program count.

## Exact commands and dispatch actions

Commands below are instructions, **not executions performed by this audit**.
Run tests in a clean disposable checkout on a supported host. `PY` means an
absolute Python executable from the intended hash-locked environment; `FINAL_SHA`
means the frozen full Git SHA. Use Node 24.22.0 / CPython 3.12.3 and the supported
Linux runtime where required. Keep private DBs, profiles, traces, credentials and
sealed witness/report values out of logs and public artifacts. Do not delete
owner locks or edit source pins to clear a failure.

For local backend commands C2–C4/C6–C7/C9/C13, first create a **new Git archive**
of the intended source, not a developer DB or an in-place checkout. Some HTTP
fixtures explicitly require no `.git`, a truthful private-root marker and fresh
evidence directories. In Bash from the clean committed checkout:

```sh
CHECK_ROOT=$(mktemp -d /tmp/mtg-rc-check-XXXXXX)
mkdir -m 700 "$CHECK_ROOT/source" "$CHECK_ROOT/evidence"
git archive "$FINAL_SHA" | tar -x -C "$CHECK_ROOT/source"
printf '%s' "$CHECK_ROOT/source" > "$CHECK_ROOT/source/.private"
for variable in ${!MTG_@}; do unset "$variable"; done
unset PYTHONPATH PYTHONHOME PYTEST_ADDOPTS
export PYTHONDONTWRITEBYTECODE=1
export MTG_ISOLATED_TEST_ROOT="$CHECK_ROOT/source"
export MTG_DATABASE_PATH="$CHECK_ROOT/source/backend/mtg_lab.db"
for variable in MTG_PAID_AI_EVIDENCE MTG_PAID_VIEW_EVIDENCE \
  MTG_HUMAN_BO3_EVIDENCE MTG_BOUNDARY_AUDIT_EVIDENCE \
  MTG_BLOCK_AUDIT_EVIDENCE MTG_ATTACK_WITNESS_EVIDENCE \
  MTG_GY_INVENTORY_EVIDENCE MTG_CAUSAL_GY_EVIDENCE \
  MTG_GY_SELF_EVIDENCE MTG_PULL_EVIDENCE MTG_FROG_HTTP_EVIDENCE \
  MTG_BRAINSTORM_MIXED_EVIDENCE MTG_LAND_ANIMATION_EVIDENCE; do
  mkdir -m 700 "$CHECK_ROOT/evidence/$variable"
  export "$variable=$CHECK_ROOT/evidence/$variable"
done
cd "$CHECK_ROOT/source/backend"
```

This is test-owned storage, never the operator's database. Retain private output
on failures. Use a fresh archive/evidence tree for a repeat; some writers refuse
existing paths. These local subsets do not recreate the protected full-CI input
or fake GitHub identity. C0/C1/C5 and the launcher shell smoke instead need the
clean Git checkout described in their commands, not this `.git`-free archive.

### C0 — Final CI and source

```sh
git rev-parse HEAD
git status --porcelain
gh run list --repo nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent --workflow ci.yml --commit "$FINAL_SHA"
gh run view RUN_ID --repo nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent
```

Inspect all configured jobs and the source-bound count/diagnostic artifacts;
public redacted logs alone may not identify failures. Private inputs stay
private. Do not dispatch/rerun an unchanged failing attempt just to obtain green.

### C1 — Fresh checkout, full configured browser

**User action:** Actions → **Clean Checkout Acceptance** → **Run workflow** →
`main`, after intended merges. A dispatch-capable account can equivalently run:

```sh
gh workflow run clean-checkout-acceptance.yml --ref main --repo nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent
```

Record the actual workflow `head_sha` and require it to equal `FINAL_SHA`.
The job calls `bash scripts/accept-clean-checkout.sh "$GITHUB_SHA"`. Local
supported-host alternative from root:

```sh
MTG_ACCEPT_PYTHON="$PY" MTG_CHROME=/absolute/vendor/browser bash scripts/accept-clean-checkout.sh "$FINAL_SHA"
```

For the existing browser cohort alone, after locked runtime/frontend installs:

```sh
MTG_TEST_PYTHON="$PY" MTG_CHROME=/absolute/vendor/browser bash frontend/tests/run-browser-ci.sh
```

That focused invocation is not fresh-install acceptance. The hosted clean
workflow explicitly disables Chrome's sandbox, as documented; no native-sandbox
claim follows. Claude's dispatch token received 403; publishing YAML does not
mean the user dispatched it.

### C2 — Current canonical knowledge/data fixture cohort

From `backend/`, use the **whole original roster**, without assuming its old
833 count still describes today's collection:

```sh
"$PY" -B -m pytest -q --junitxml="$CHECK_ROOT/evidence/current-data.xml" \
  tests/test_knowledge_models.py tests/test_knowledge_domain_boundaries.py \
  tests/test_knowledge_json_boundaries.py tests/test_repository_unicode_names.py \
  tests/test_knowledge_ingest.py tests/test_knowledge_ingest_fixture_fidelity.py \
  tests/test_knowledge_sync_task12.py tests/test_knowledge_cache_recovery.py \
  tests/test_knowledge_rulings_corpus.py tests/test_phase1_stored_deck_corpus_cli.py \
  tests/test_knowledge_gap_report_fields.py tests/test_knowledge_gap_report_cli_corpus.py \
  tests/test_knowledge_gap_report_face_cache.py tests/test_knowledge_gap_report_face_cache_repository.py \
  tests/test_task13_seed_loader_migration.py tests/test_oracle_corpus_report.py \
  tests/test_phase1_final_data_acceptance.py
```

Report actual counts and source; independently reconcile all original Phase 1
requirements and any current-corpus additions. Fixture HTTP replay is not a
new live Scryfall fetch or an arbitrary-data certificate.

### C3 — Knowledge consumer, privacy and trace checks

From `backend/`:

```sh
"$PY" -B -m pytest -q \
  tests/test_ai_knowledge_consumer_audit.py tests/test_ai_knowledge_repository_pipeline.py \
  tests/test_ai_knowledge_profile_consumer.py tests/test_ai_knowledge_snapshot_contract.py \
  tests/test_observation_knowledge_serialization.py tests/test_knowledge_usage_trace_contract.py \
  tests/test_knowledge_profile_repository.py tests/test_card_hydration.py \
  tests/test_ai_knowledge_natural_smoke.py
```

The last case is one seeded Tempo/Control natural smoke with owned fixture-backed
knowledge, not all-archetype or A/B acceptance. Do not replace the actual choices
or private-visibility assertions with mocked pass results.

### C4 — Bounded current HTTP/recovery and built-launcher checks

From `backend/`:

```sh
"$PY" -B -m pytest -q tests/test_battle_http_atomicity.py \
  tests/test_battle_http_recovery.py tests/test_battle_http_goldens.py \
  tests/test_manual_autoplay_collision_http.py tests/test_cleanup_repeat_http.py \
  tests/test_temporary_characteristics_http.py tests/test_private_choice_http_restart.py \
  tests/test_human_bo3_terminal_restore.py
```

After the launcher-smoke branch is integrated, in the backend test archive:

```sh
"$PY" -B -m pytest -q tests/test_launcher_real_app.py
```

Then separately from the **clean committed checkout root**, with free ports
15173/19222 and the selected browser/runtime:

```sh
MTG_TEST_PYTHON="$PY" MTG_CHROME=/absolute/vendor/browser bash frontend/tests/run-launcher-smoke.sh
```

The latter runs the actual built single-origin launcher and restart; its fresh
all-Island opening is not a natural competitive AI game. The full configured
cohort in C1 includes the canonical Battle/payment and warning cases. Preserve
the explicit missing-warning mutation RED; do not infer it from a positive run.

### C5 — Matrix code and pilot, not a full matrix run

After adapter `c8878a65` (or its reviewed successor) is integrated, from backend:

```sh
"$PY" -B -m pytest -q tests/test_archetype_matrix_plan.py \
  tests/test_archetype_matrix_execution.py tests/test_archetype_matrix_game.py \
  tests/test_archetype_matrix_api_check.py tests/test_archetype_matrix_pilot.py \
  tests/test_archetype_matrix_worker.py
"$PY" -B -m scripts.archetype_matrix_plan admission /absolute/private/new-admission.json
"$PY" -B -m scripts.archetype_matrix_pilot plan \
  archetype-pilot-20261116-v2-UNIQUEID /absolute/private/new-pilot-plan.json
# Only after Claude explicitly approves execution and resources:
"$PY" -B -m scripts.archetype_matrix_pilot run \
  /absolute/private/new-pilot-plan.json /absolute/private/new-pilot-output --execute-pilot
```

Two workers, one affinity core each, 2 GiB address-space limit each, shared
game/verifier 120s wall/90 CPU-seconds per cell; host admission needs three
available affinity slots and 5 GiB observed memory headroom. These are not
cgroup reservations. Sleep/crash/source drift invalidates the run; new ID,
no resume/retry/spliced prefix. Pilot seeds never contribute to the matrix.
**No full-matrix batch command exists in this adapter.** Approve its forecast
and deliver/review that controller and remaining parity checks before launch.

### C6 — Operator boundaries and user-selected HTTPS deployment

From backend:

```sh
"$PY" -B -m pytest -q tests/test_single_operator_deployment.py \
  tests/test_operator_learned_startup.py tests/test_capacity_bootstrap_policy.py \
  tests/test_capacity_policy_environment.py
```

After user selection of local configuration, actual private certificates, pinned
proxy and qualified runtime, the existing operator commands from root are:

```sh
MTG_OPERATOR_CONFIG=/absolute/private/operator.json "$PY" ops/caddy/run.py --check
# Listener/deployment requires separate operator authorization:
MTG_OPERATOR_CONFIG=/absolute/private/operator.json "$PY" ops/caddy/run.py
```

See [the operator procedure](../../ops/caddy/README.md). `--check` and startup
alone do not qualify actual TLS/auth/media, client trust, remote routing or
browser gameplay. Do not invent hostnames/certificates or modify global trust.

### C7 — Backup, saved-game reconstruction and resource components

From backend, after PR75's worker/helper are integrated:

```sh
"$PY" -B -m pytest -q tests/test_saved_game_backup_restore.py \
  tests/release_agent/test_restore.py tests/test_storage_backup_deadline.py
"$PY" -B -m pytest -q tests/release_agent/test_retention.py \
  tests/release_agent/test_safety.py tests/test_resource_capacity.py \
  tests/test_simulation_job_quota.py tests/test_capacity_lifecycle_policy.py
```

Follow PR75's operator runbook for an explicitly relocated, closed DB; no live
database replacement or `engine.dispose()` while its owner is active. These
commands do not reproduce the historical live A/B/C SIGKILL scenario, physical
exhaustion, clean-machine soak or accessibility acceptance. Those need a new
current-source run protocol with exact bounds and observed closure.

### C8 — Selected corpus and live-data follow-up

The fixture command C2 is runnable without a live dataset. For an approved
**disposable local copy** selected by the operator, the existing completeness
report command from backend is:

```sh
MTG_DATABASE_PATH=/absolute/private/copied.sqlite3 "$PY" -B -m scripts.knowledge_gap_report \
  --require-rulings --image-cache-dir /absolute/private/images --out /absolute/private/gaps.json
```

It initializes schema if needed: it is not a read-only arbitrary-file audit.
Never point it at an unapproved live/NFS file. Missing/verified-empty rulings,
metadata, images and supported mechanics must remain distinct. Report the
actual requested-name roster; all-card sync and live legacy migration require
separate operator permission, provenance/backup and idempotence checks. There
is no single command certifying arbitrary-card semantics or every indirect
hand-authored test input.

### C9 — Keep the legacy seam visible

From backend:

```sh
"$PY" -B -m pytest -q -rxX tests/test_legacy_unknown_source_recast.py
```

Typed controls must pass. The two historical-frame strict xfails name
`finish_stack_resolution`'s missing source-incarnation proof; they are not
passing rules outcomes or a naturally reachable LIFO exploit. A fix needs a
maintainer policy decision and the usual source-pin delta if applicable.

### C10 — Final dependency advisory workflow

**User action:** Actions → **Dependency Advisory Review** → **Run workflow** →
`main`, after intended dependency merges. CLI equivalent for a permitted user:

```sh
gh workflow run dependency-advisory-review.yml --ref main --repo nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent
```

Supported networked-host alternative from root:

```sh
MTG_AUDIT_PYTHON="$PY" bash scripts/review-dependency-advisories.sh
```

Record actual source, lock hashes, scanner versions, full/prod npm JSON and all
28 pip rows, query exits and dispositions. `ENOTFOUND`, unavailable ensurepip,
skipped packages or malformed reports leave this open. Accepted minimatch risk
may keep the full npm scan nonzero; compare the actual advisory to its documented
scope/owner/revisit trigger, not an imagined zero-finding acceptance threshold.

### C11 — Chrome and Brave native-protected acceptance

**User action:** Actions → **Native Linux Browsers** → **Run workflow** → `main`.
CLI equivalent for a permitted user:

```sh
gh workflow run native-browser.yml --ref main --repo nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent
```

Require both vendor jobs, signed-package/executable preflight, sandbox mode 0,
complete declared suite, zero unexpected runtime errors and successful owned
cgroup lifecycle. Existing `run-native-browser-ci.sh` uses CI identity/systemd;
do not forge those variables to call a random local launch “CI acceptance”.
No bypass/reduced cohort or Firefox substitution is authorized.

### C12 — Firefox preparation only

From root, existing component checks are:

```sh
npm --prefix frontend run test:unit:firefox
(cd backend && "$PY" -B -m unittest discover -s tests -p test_firefox_response_cache.py -v)
```

The [Firefox plan](firefox-acceptance-plan-20261116.md) must first produce a
current-source native launcher/transport command and complete cohort inventory.
Until then no full Firefox acceptance command can honestly be supplied. The
missing adapter, native run, warning RED, identity/closure and trust checks are
open work, not skips counted as successful episodes.

### C13 — Privacy and known current-batch checks, bounded scope

From the fresh backend test archive prepared above:

```sh
"$PY" -B -m pytest -q tests/test_pending_stack_privacy_goldens.py \
  tests/test_pending_source_privacy_goldens.py tests/test_brainstorm_http_ordering_goldens.py
"$PY" -B -m pytest -q tests/test_public_graveyard_inventory.py \
  tests/test_graveyard_inventory_feasibility.py
"$PY" -B -m pytest -q tests/test_canonical_land_animation_audit.py \
  tests/test_canonical_land_animation_mana_controls.py tests/test_land_animation_product.py \
  tests/test_land_animation_pending_reentry.py tests/test_land_animation_cloudshift_composition.py
"$PY" -B -m pytest -q tests/test_targeted_search_lifecycle_audit.py \
  tests/test_targeted_search_resolver_contract.py tests/test_targeted_search_runtime_dependencies.py
```

These commands exercise existing named cases, not the entire pending-source
continuation space, arbitrary graveyard clauses, general animation or complete
browser/Ray/activation search coverage. Inventory gaps and add the missing
canonical/HTTP/UI episodes before claiming the corresponding requirements.

## Closeout record required

For each checked-off row retain: full source SHA and intended scope; exact
command/runtime/vendor; CI run/job or host receipt; actual pass/fail/error/skip/
xfail/episode counts and failed attempts; current dependency/provenance inputs;
owned process/storage closure; reviewer and unresolved limitations. Keep raw
private evidence private. Do not mark a row complete from this checklist, a
planned command, a dispatched but running workflow or a narrower component pass.
