# MTG Deck Testing Lab Finish Plan

## Current Execution Order

1. Finish preserved selection/ranking and combat latency validation; extend
   Suspend and choice-dependent mana families without card-name exceptions.
2. Apply the verified corpus safely, materialize bounded mechanic metadata and
   expand complete training choices/features. Preserve private observations,
   qualified snapshots and expert-data provenance; do not force matchup win rates.
3. Continue the original rules/AI/release gates below: conditional/compound
   semantics, affordable multi-action planning, restart behavior, network posture
   and competitive-quality evidence remain unfinished.

Parallel knowledge work audits all-card provenance and conservative mechanic
descriptors in isolated copies. [Learned-policy groundwork](docs/plans/learned-policy-groundwork.md)
tracks environment, data and evaluation prerequisites; no neural policy is trained
or deployed, and regression runs are not training.

Completed bounded work:
- [x] Training mana choice safeguards: 304 composed tests pass. Unsupported
  resource/hybrid/X selections are reported and rejected rather than silently
  dropped; ambiguous legacy ability selection and stack-route bypasses reject.
  Actual chosen-payment execution remains unfinished. See
  [scope](docs/testing/training-mana-choice-coverage.md).
- [x] Offline knowledge-to-engine report: 49 checks pass; a current-source
  read-only run over all 38,690 qualified profiles is byte-identical to the
  independent worker report. Known gaps, unknown surfaces and missing metadata
  are separate; no affirmative support is inferred. See
  [scope](docs/testing/knowledge-engine-coverage.md).
- [x] Integrated paid-selection consumers and checked legacy batch/replay actions:
  1,055 composed tests pass, including actual production decisions, privacy and
  unknown-inventory regressions. Two seeded Burn/Aggro games finish in both seat
  assignments with repeated replay equality. Opaque selection projections are
  qualified, but retained Tempo cast-versus-pass ranking remains unfinished.
  See [scope](docs/testing/selection-policy-integration.md).
- [x] Complete training-choice prompts and explicit payload validation: 172
  composed checks pass for both-seat canonical modal/inspection/trigger/ward/
  replacement cases. Resource/hybrid mana encoding and broader choice coverage
  remain unfinished. See [scope](docs/testing/training-choice-coverage.md).
- [x] Bounded offline corpus index application: 100 importer/recovery checks
  pass. All 38,690 profiles qualify against a parent backup with nine other
  tables and 1,264 snapshots preserved. Live import and nested metadata
  materialization remain outstanding. See [scope](docs/testing/corpus-readiness.md).
- [x] Immutable combat query batches: 799 composed tests pass; a retained Master
  decision preserves complete action/state/projection parity and all search work,
  reducing measured time from 116.0 to 92.5 seconds. Interactive latency remains
  unfinished; this one-position result is not a general performance bound. See
  [scope](docs/testing/combat-query-batches.md).
- [x] Checked live autoplay and complete heuristic intent conversion: 259 composed
  tests pass, including four seeded Strong match smoke cases and actual cast
  exports for both seats. Rejected requests preserve whole state and storage.
  Legacy analytics/replay checked action acceptance is now integrated above;
  broader hydration/transition parity, interactive support warnings and strategic
  quality remain outstanding. See [scope](docs/testing/autoplay-action-safety.md).
- [x] Opt-in Cathar target-lifecycle browser sidecar: ten combined cases pass
  on parent-composed e645456 source, with 84 actual App HTTP actions and three
  backend restarts. The default six-case shared CI scope remains unchanged.
  This is focused lifecycle evidence, not whole-app or broad rules certification.
- [x] Recovery-safe offline corpus tooling and versioned trajectory export:
  composed knowledge/dataset/training/metadata/mana gate passes 245 checks,
  including teacher-source hash coverage. All 38,690 card/ruling patches remain
  staged, not live imported; datasets use a generic heuristic, not expert labels.
  See [corpus](docs/testing/corpus-readiness.md) and [dataset](docs/testing/training-dataset.md).
- [x] Full shared browser gate exits zero with 484 PASS lines, including all
  three BO3 control modes and independent Officer/Cathar epilogues. Its frozen
  source precedes fixed-mana promotion; it is not full post-mana certification.
- [x] Shared fixed additional triggered mana: complete colored output bundles,
  distinct snow/restriction provenance and actual activation/payment parity.
  Composed gates pass 1,865 affected checks plus a separate 300-check integration
  gate; retained Ramp position can legally pay for Ugin in both seats. Choice-
  dependent and produced-type variants remain open. See [scope](docs/testing/additive-triggered-mana.md).
- [x] Dedicated canonical Cathar actual-App browser acceptance: six cases across
  both seats, source departure/blink, day/night transitions, pending choices,
  reload and two real backend restarts. Parent composed run also passes all six;
  broader transform families remain open. See [scope](docs/testing/cathar-browser.md).
- [x] Wire self-isolating private-inspection restart/reload checks into browser
  CI. Normal-checkout run passes eight HTTP and four browser cases; five harness
  regression groups cover occupied ports, missing NFS and caller preservation.
- [x] Add deterministic training-environment groundwork and versioned canonical
  mechanic metadata. Composed gates pass 323 and 161 checks respectively. Complete
  neural action encoding, datasets, learned policies, custom-deck training and
  broad strategic acceptance remain open; this is not a trained model.
- [x] Composed acceptance: 595 delta checks and complete browser gate, exit 0,
  466 PASS lines including restart, sideboard and all three BO3 control modes.
  These are bounded correctness/flow checks, not expert strategic validation.
  Follow-up inspection CI isolation and dedicated Cathar browser now pass their
  separate bounded gates. Shared Cathar CI wiring now passes six lightweight
  isolation/ordering checks plus the existing Officer wrapper checks; an actual
  hosted GitHub full-gate execution remains separate acceptance.
- [x] Repair supported unknown-library deployment valuation. Exact retained
  Master Ramp-versus-Tokens configuration casts the payable spell without peeking
  at library order. Live-code and composed gates each pass 536 affected checks;
  canonical mana-value correction passes 188. Natural decision quality remains
  under evaluation. See [scope](docs/testing/ai-topdeck-deployment.md).
- [x] Repair shared day/night entry and incarnation-linked exile using canonical
  Cathar fixtures; both-seat rules and HTTP restoration pass. Night entry uses
  Moonrage Brute without the front face's trigger. Dedicated browser acceptance
  now passes; broader transformation semantics remain open. See
  [evidence](docs/testing/cathar-day-night.md).
- [x] Provide server-gated, read-only AI hand debugging. Normal redaction and AI
  information inputs remain unchanged; real ended-match reveal/read/hide passes
  without game writes. See [scope](docs/testing/ai-hand-debug.md).
- [x] Stop human-game automatic ticks and stale actions after an authoritative
  winner, with a visible result/series banner. Preserve manual between-game
  choices and AI-series continuation; mocked actual-App browser, lint/build and
  frontend tests pass. Do not infer losses solely from a life counter.
- [x] Qualify affinity, effective type consumers, sacrifice mana/self-death,
  private inspections and bounded resolution conditions: 9,464 backend tests
  across 374 modules; independent databases and explicit stale-test correction.
  Combined inspection HTTP/browser restart checks and frontend unit/lint/build
  pass. The complete combined browser gate now passes; broader live-game racing
  quality remains under review.
  See [evidence and limits](docs/testing/backend-rule-batch-2026-10-05.md).
- [x] Human Attack All declares ordinary eligible attacks directly; separate
  Select all preserves selection-only behavior. Costs, alternate defenders and
  bands require deliberate review/confirmation. Fifteen isolated browser cases
  and captured-payload engine replay cover both seats and duplicate clicks;
  frontend lint/build/tests pass. Live-game AI racing remains under review.
- [x] Correct autoplay's thirty-second client deadline mismatch: ten-minute
  bounded ceiling, unchanged ordinary deadlines/write coordination; actual-client
  test, frontend unit/lint/build pass. Reject a more complex score-key encoder
  after its full-decision gain proved marginal. Planning latency and background
  job/cancellation acceptance remain open.
  See [scope](docs/testing/autoplay-request-deadline.md).
- [x] Continuous source ordering/activity reuse: 3,545 affected checks across 85
  files pass; source departure, timestamp/control changes and defensive views
  have explicit tests. Retained full action/state parity: 30.00 seconds versus
  archived 37.55; nested forecasting and interactive latency remain open.
  See [scope](docs/testing/continuous-source-reuse.md).
- [x] Lethal-check query ordering: 2,422 affected checks across 58 files pass;
  undamaged/nonlethally damaged creatures avoid indestructible queries, while
  zero toughness and deathtouch semantics remain covered. Retained full decision
  parity: 37.55 seconds versus archived 51.48; latency remains unfinished.
  See [scope](docs/testing/lethal-query-order.md).
- [x] Deferred unused forecast scores: 1,107 affected checks across 18 files;
  eager-reference, both-seat and snapshot parity. Retained decision 51.48 seconds
  versus archived 55.64 seconds; interactive latency remains unfinished.
  See [scope](docs/testing/deferred-forecast-scores.md).
- [x] Review completed timing and ordinary-graveyard natural runs: six unique
  seeded games per increment, repeated twice; all twelve reconstructions match
  and no reported determinism failures/anomalies. Timing changes Tempo/Control
  seat two at decision 524; tactical optimality remains unverified. Limited
  graveyard runs also completed: six logical seat-balanced games, twelve repeat
  executions; identical replay results/logs and no reported anomalies. These
  narrow runs do not establish tactical optimality or matchup balance.
- [x] Shared suppression/static-subject query reuse: 3,436 affected checks across
  82 files pass; retained complete action/state parity, 66.62 to 55.64 seconds
  for one position. Remaining nested forecasting/latency stays the priority.
  See [scope](docs/testing/layer-query-reuse.md).
- [x] Decision-local exact score reuse and read-only scan scopes: 1,087 affected
  AI checks pass; retained full action/state parity, 80.95 to 65.77 seconds for
  one position. This is not a general latency or professional-play guarantee.
  See [scope](docs/testing/ai-exact-score-reuse.md).
- [x] Qualified resource payments/events and AI opportunity milestone on main.
- [x] Consolidated timing/graveyard/announced-method/color-cost runtime on main.
  Frozen `91b5dff`: 8,878 backend tests, 359 recursive files exactly once,
  738 source hashes in four initially DB-free copies; complete browser suite and
  frontend unit/lint/build pass. Initial failed gate is preserved, not counted.
- [x] Copied-database recovery: eight matches restore, saved deck rows unchanged.
  Live backend automatically reloads and health passes; user data is preserved.
- [ ] Original broader rules, expert AI and release requirements remain open.

See [integration evidence](docs/testing/backend-consolidation.md) and
[engineering workflow](docs/engineering-workflow.md). Historical qualification
notes below do not require repeating unchanged predecessor gates.

## Earlier Backend Work And Remaining Family Limits

- [x] Add shared affinity cost determination for supported permanent selectors
  and unconditional spell grants. Both-seat engine, HTTP/snapshot and actual AI
  acceptance tests cover canonical cards; see [scope](docs/testing/affinity.md).
  Conditional/next-spell grants and broader layer semantics remain unfinished.

- [x] Consolidate implemented cost, graveyard and timing work into an integration
  milestone. The combined gate is complete and integrated into main. Fixed color/type modifiers, actual prototype color, both-seat
  HTTP/restart and browser flows pass. Broader unknown semantics stay explicit;
  do not require a new small-sample natural matrix for every independent clause.
  See [scope](docs/testing/announced-spell-costs.md).

- [x] Qualify announced casting-method permissions and strategic source/type
  selection. Prototype/bestow use chosen characteristics; AI preserves scarce
  allowances for known own-graveyard follow-ups. 194 backend checks, four focused
  browser flows and frontend unit/lint/build pass. Frozen full/browser gates and
  consolidated main integration are complete; broader affordable multi-action
  plans and announcement ordering remain open. See
  [scope](docs/testing/graveyard-cast-methods.md).

- [x] Qualify shared graveyard casting/land permission and admission families:
  ordinary self/subtype grants, source/timing/cost limits, modal land faces,
  suppression, global prohibitions and real departure events. Both-seat unit and
  HTTP checks and exact-source full/browser/natural gates pass; integrated into
  the consolidated main runtime. Broader permission families remain open. See
  [scope](docs/testing/graveyard-play-permissions.md).
- [x] Qualify durable limited graveyard permission ledgers and source/type choices.
  Shared Lurrus/Muldrotha/Gisa-style restrictions, actual X limits, land allowances,
  snapshot isolation and stale-choice rejection are integrated into main;
  six focused browser flows, 8,824 full backend tests and the complete browser
  suite pass. Seeded review and integration qualification are complete;
  duration, subtype layers and casting-announcement ordering remain open. See
  [scope](docs/testing/limited-graveyard-permissions.md).

- [ ] Qualify tactical casting-resource choices: twenty-three canonical cases and 342 earlier
  overlapping checks pass. Preserve engine fallback, bounded legal projections,
  blocker/mana/graveyard opportunity costs and hidden-information invariants.
  The 8,650-test full gate, complete browser gate and twelve repeated seeded
  reconstructions pass; this milestone is integrated into main. Broaden
  colored/compound payment alternatives and decision-quality samples. See
  [scope](docs/testing/ai-resource-opportunity.md).
- [x] Investigate natural Tempo/Control seat-two decision 524: control cashes
  a seven-mana graveyard card-selection spell in opponent upkeep while holding
  two counters, instead of waiting for an appropriate later window. Scope the
  fix to general interaction reservation/instant timing, not a card-name rule.
  The corrected natural trace passes at 524 and counters Expressive Iteration
  at 530 using reserved mana. Both repeats reconstruct; this verifies the
  observed sequence, not all counter timing or broader competitive strength.

- [ ] Qualify resource-event follow-up: real-tap paths, pre-move graveyard watcher
  capture, batch/APNAP semantics and original-action stack ordering. 175
  overlapping checks and eight HTTP/SQLite cases pass. Frozen full backend
  (8,627 tests/348 files) and complete browser gates pass; wider
  trigger semantics and natural tactical evaluation remain open. See
  [acceptance](docs/testing/resource-event-fidelity.md).

- [ ] Qualify the casting-resource candidate: shared ordinary delve/convoke/
  improvise witnesses, strict API, deliberate both-seat UI, 439 expanded checks
  and six new browser flows pass. Frozen full backend (8,603 tests/345 files)
  and complete browser gates pass. Event-aware tapping and
  graveyard departure, ordered compound costs, granted keyword/color fidelity
  and tactical AI choices remain open. See
  [acceptance](docs/testing/cast-resource-payments.md).

- [ ] Qualify the offline private decision comparator and integrate it into
  natural replay review. Twenty targeted cases pass; preserve unequal-length
  prefix analysis, strict provenance, private output and explicit exceptions.
  See [scope](docs/testing/decision-view-comparison.md).

- [ ] Qualify selective hand acquisition and masked count planning. Canonical
  fixed-count/mana-spent families, durable bottom ordering, both seats and
  guarded strategic projections pass 528 focused checks plus eight HTTP/SQLite
  cases. Frozen qualification passes 8,516 backend tests across all 342 files
  with 670 matching source hashes, the existing full browser suite, and eight
  new both-seat selection/reload scenarios. Combined natural acceptance remains
  open; the completed predecessor matrix is not this runtime's acceptance.
  See [contract](docs/testing/opaque-selection-horizon.md).
- [ ] Implement casting-resource mechanics (delve, convoke and improvise),
  including deliberate human/AI resources, generic-only substitution, legal
  combinations with other costs, no double-spend and durable atomic rejection.
  The isolated candidate now implements ordinary payment paths; full acceptance
  remains open and main has not changed. Fully paid Dig Through Time resolution
  alone is not evidence of delve payment.

- [ ] Qualify the measured mana-multiplier query prefilter. Canonical selections
  and one recorded decision's action/state parity pass. Complete frozen gates
  pass (8,396 backend tests, full browser, frontend test/lint/build);
  representative natural decision review remains open. See
  [candidate contract](docs/testing/mana-multiplier-prefilter.md).

- [ ] Qualify the combined strategic draw-count/root-score reuse and private
  replay-view candidate. Frozen full gates and final canonical exports pass;
  retain strict hidden-information boundaries and finish the fresh paired-seat
  comparisons before rollout. See
  [candidate contract](docs/testing/strategic-draw-counts.md).

- [x] Add direct battlefield attack/block drafts for both human seats, with
  engine-supplied legal targets/capacity, legal drag-to-band and confirmation.
  Detailed payment/defender controls remain. See
  [scope and validation](docs/testing/direct-combat.md).

- [x] Replace empty human-versus-AI phase clicks with authoritative automatic
  priority progression. Preserve actual plays, choices and end-step instant
  opportunities; keep hotseat/manual pause behavior. See
  [scope and validation](docs/testing/human-auto-progress.md).

- [x] Qualify [pending strategic announcements](docs/testing/strategic-pending-announcements.md)
  together with private decision timings. Separate AI/metrics selections pass
  468/73 checks, combined selection 541; frozen `b8f59fb` passes 8,294 backend
  tests in all 334 files/653 matching hashes and the complete browser gate.
  Actual seat-one trace now casts on turn 9 but still refuses a body later;
  this is not complete strategic play. Keep timing fields out of replay state.
- [x] Qualify shared stack-response deltas: seven reproduced failures repaired;
  129 selected checks and nine expanded contracts pass (overlapping). The
  exact frozen full gate passes 8,303 tests across 335 files/656 matching hashes
  and the full browser harness in all three BO3 modes.
- [ ] Finish paired-seat and cross-archetype natural trace review, keeping
  unchanged canonical inputs and sample accounting. The completed forward sample
  develops four creatures rather than one; no desired deck winner is forced.
- [ ] Optimize measured strategic/query hotspots with unchanged legality and
  decision-parity evidence. Baseline profiling finds many repeated ability-
  suppression queries in deep stack search; no optimization is qualified yet.

- [x] Qualify [catalog identity and successful trace export](docs/testing/catalog-and-replay-traces.md).
  Separate red/green catalog and runner candidates are combined without changing
  gameplay source. Exact runtime passes 8,219 tests across all 332 files with
  649 matching hashes and the full browser gate in all three BO3 modes.
- [ ] Continue actual-game trace review and strategic horizon repair. Corrected
  template traces reproduce legal creature deployment being declined by the
  complex-board planner. An independent shared valuation repair and decision
  timing candidate are under targeted validation; no expert-play claim is made.

- [x] Qualify [joint mana/resource activation planning](docs/testing/joint-activation-payment.md).
  Exact runtime passes 8,159 tests in all 330 files with 644 matching backend
  hashes and the complete browser gate in all three BO3 modes. Preserve selected
  resources, allow tap-only use and choose feasible automatic/AI alternatives.
- [x] Qualify [nested mana life budgets](docs/testing/nested-mana-life-budget.md).
  Canonical four-failure reproduction is repaired by shared source-selection
  budgets and protected outer life. Latest selection passes 505 checks, four
  new HTTP recovery cases and six focused browser cases. Exact runtime passes
  8,209 tests in all 332 files with 649 matching hashes and the full browser
  harness in all three BO3 modes.
- [ ] Extend real-game timing and decision evidence. A paired-seed Drain/Tribal
  replay is running on pinned canonical inputs; successful decision-trace export
  and stable catalog refresh are separate candidates under targeted validation.

- [x] Qualify [deliberate activated payments](docs/testing/activation-payment-choices.md).
  Shared ordinary activation resource selection, strict HTTP validation, both
  human seats, mandatory source costs, ownership and resource-aware AI pass
  targeted checks. Exact source passes 8,133 tests in all 328 recursive files
  with 639 verified source/fixture hashes and the full browser harness across
  all three BO3 modes. Selected-resource ordering is repaired by the separately
  qualified joint and life-budget planners; other action families remain open.

- [x] Qualify [contextual costs and source sacrifice](docs/testing/contextual-cost-prohibitions.md).
  Batch casting/activation life and sacrifice prohibitions, effective-source
  suppression, Phyrexian payment branches, exhaustive/mixed costs and supported
  symbol-free activations. Repair actual payment when a generic sacrifice can
  consume the ability source. Initial selection: 495 checks; the subsequent full
  gate exposes a default-selection regression. Preserve other-creature preference
  without forbidding legal self-sacrifice; latest source passes 292 selected
  checks, including six HTTP/SQLite cases. Exact-source qualification then passes
  8,053 tests in all 326 files/634 verified hashes and the full browser gate in
  all three BO3 controller modes. Conditional costs, deliberate activation
  resource choices and optimal resource strategy remain open.

- [x] Qualify [life conversion and beneficiary planning](docs/testing/life-conversion-planning.md).
  Batch shared static replacement admission/resolution, affected-player ordering,
  durable continuations, loss-protection checks and original/copy AI decisions.
  Canonical failures are repaired. The exact timing runtime passes 7,944 tests
  in all 321 files with 617 matching source/fixture hashes. Eight HTTP cases,
  full browser acceptance and four new choice/reload browser cases pass.
  Both enchantment and creature matrices strictly reconstruct eight executions
  each. Three actual creature casts, zero creature conversions: targeted tests
  establish conversion timing, not those natural games or expert-level AI.

- [x] Qualify effective printed life restrictions after ability suppression.
  The isolated runtime passes 7,964 tests in all 322 files/618 matching hashes.
  Expanded canonical tests reproduce 34 failures/four passes before repair;
  322 overlapping checks, two HTTP payment/recovery cases and four browser cases
  pass. The combined source passes 7,988 tests and the full browser harness,
  preserving published scenarios. A later query prefilter passes 207 overlapping
  checks, then 7,991 tests across all 324 files/624 verified source hashes and
  the complete browser gate, including all three BO3 controller modes.
  Relevant-source suppression remains covered. Broader conditional restrictions
  remain open.

- [x] Qualify supported complete fixed damage/caster-gain instructions and
  semantic beneficiary targeting. Latest frozen gate: 7,829 tests in 318 files,
  606 matching backend source/fixture files; full browser and integration frontend
  test/lint/build pass. Four fresh Boros/Dimir capability games have 3,414 logical
  decisions, eight matching repeats/strict reconstructions and 22 checked caster
  gain resolutions. Complex qualified/variable clauses remain unsupported.
  [Scope and evidence](docs/testing/beneficiary-polarity.md).

- [x] Verify beneficial original-spell targeting with identical seed/seat inputs.
  Four logical games per stage reduce harmful beneficiary choices from eight to
  zero; all sixteen before/after executions strictly reconstruct. The subsequent
  latest full gate includes these repairs. This is not expert-player evidence.

- [x] Publish the qualified landfall/copy/beneficiary integration (`4b9903d`).
  Live reload-enabled services respond to HTTP checks and retain all-interface
  bindings. Test evidence, browser artifacts, committed source and an integrity-
  checked pre-publication SQLite backup are verified on mounted NFS. This is not
  a cross-device browser, expert-player or universal rules certificate.

- [ ] Validate cross-device and long-session live behavior; continue broader
  beneficiary planning, complete targeting dependencies and qualified/variable
  damage/life instructions beyond the tested structural family.

- [ ] Finish [linked conditional damage](docs/testing/linked-controller-targets.md).
  Complete-pair admission, exclusive damage amounts, captured recipients and
  bounded AI pair selection pass focused gates. Current frozen backend passes
  7,688 tests in 313 discovered files, with 594 source/fixture files equal to the
  candidate. Typed human controls pass eight Chromium cases for both seats and
  primary types, including paid casting, wrong-controller rejection and reload.
  The pre-copy full browser gate also passes natural BO3 in all three controller
  modes. Paired-copy choices and simultaneous same-object damage are now
  implemented: 306 overlapping backend checks and twelve focused browser cases
  pass. The frozen full backend gate passes 7,736 tests in all 316 recursive files;
  its full browser gate passed. Departed planeswalker
  LKI, broader protection corners and latest-source match acceptance remain open.

- [ ] Complete conditional-copy acceptance after repairing stale branch recipients
  and branch-aware AI targeting. Twenty-four new canonical cases fail before and
  an overlapping 188-check selection passes after correction. Latest conditional
  edits pass a subsequent 7,760-test full gate in all 317 recursive files, with
  602 backend source/fixture files identical across candidate and four shards.
  Eight paid human browser cases pass both seats and ordinary/enhanced branches,
  including deliberate retarget, reload, untouched original and copy resolution.
  Retained natural copy games now complete with matching strict reconstruction;
  before/after beneficiary analysis is linked above. Latest exact-source gates
  include these repairs; broader copy strategy remains open.
  The earlier four-game matrix has 2,217 logical decisions, eight matching strict
  reconstructions and actual casts of all four landfall families; it is not
  evidence of these subsequent copy repairs or competitive balance.

- [ ] Validate and integrate the independent [land-entry history and alternatives](docs/testing/land-entry-history.md)
  candidate. Shared events record real entries independently of land-play limits;
  complete pump/life/draw landfall forms choose one branch at resolution. The
  isolated 354-check selection and latest 7,688-test full backend gate pass;
  broader HTTP/browser and fresh-match acceptance remain outstanding. Remaining
  linked damage semantics, AI forecasts and unknown-legacy
  recovery are not closed by this increment. The live root remains unchanged.

- [ ] Complete [coupled and independent target fidelity](docs/plans/coupled-target-fidelity.md)
  after the current AI acceptance gates. Ordered modifier selection and copied
  target continuations are published after 7,569 tests, full browser acceptance
  and four capability games/eight strictly reconstructed executions. Linked
  damage/landfall is qualified for the documented bounded families; publication
  and live deployment remain separate steps. Share target
  instances, controller dependencies and partial-resolution validation across
  rules, API, AI and human actions; do not add card-name-only exceptions.

- [x] Complete bounded [strategic waiting and public stack threat](docs/testing/ai-strategic-wait.md)
  acceptance. Preserve best-scoring passes, include legal waits in the bounded
  root and descendant shortlists, and value counterable threats from their actual
  public outcomes. Candidate two passes 7,425 backend tests but fails the natural
  AI BO3 browser budget. Candidate three repairs the exposed planning/targeting
  defects and passes 256 focused checks. Its browser state then finishes legally
  seven actions beyond the original total BO3 budget. Candidate four also fixes
  ability-counter forecast dispatch/protection, passing 121 focused checks; its
  complete 7,467-test backend suite, frontend checks and adjusted-budget full
  browser gate pass. Its six-style matrix completes 30 games/60 repetitions with
  identical full packets and no reported drift or timeouts. Strict review matches
  29 games and rejects one Searing Blaze cast; coupled-target admission remains
  an explicit rules blocker, not a balanced-win-rate tuning task.
  Candidate two's complete 30-sample/60-execution matrix remains separate evidence.
  Do not force deck win rates.

- [x] Publish [offline action reconstruction](docs/testing/action-reconstruction.md)
  while retaining its failures as rules evidence. Twenty-one unit/CLI checks
  and a complete retained game pass; strict reconstruction matches 26 samples
  and rejects four illegal target announcements. Repair single-alternative and
  controller-linked multi-target casting without weakening rejection. Keep
  reports with hand/log data private.

- [x] Complete the supported [casting/trigger repair batch](docs/testing/casting-trigger-repairs.md).
  All six reproduced failures are repaired. The final isolated 7,310-test
  backend gate, complete rules-only browser harness and eight repeated
  seed/seat-balanced samples pass. The report defines bounded support, not
  arbitrary casting costs, grants or full-card certification.

- [x] Implement and validate decision-local AI projection reuse from the
  completed performance diagnostic; preserve decisions, legality, privacy and
  mutable-state isolation. Do not weaken search or force matchup win rates.
  The [implemented scope and acceptance](docs/testing/ai-destruction-reuse.md)
  cover 42 new invariants, 7,354 final combined backend tests, eight-state pinned
  benchmarks and a six-style, thirty-sample matrix repeated twice. The two late
  control hotspots improve 67-78%; other slow decisions and strategic quality
  remain separate work, not solved by preserving decisions.

- [x] Complete the broader browser gate for human land-play guidance and explicit
  Next Step progression. Backend and frontend checks, real physical land clicks
  and exhausted-allowance probes pass. The first broad run exposed the async
  readiness helper's truthy-Promise bug; its regression and the complete final-source
  harness now pass, including both human BO3 flows and restart recovery.
  See [current evidence](docs/testing/human-land-progress.md).

- [x] Integrate offline backup/restore verification and dry-run retention tools.
  The combined 128-test storage/recovery gate and cold offline 119-name probe
  pass. These tools do not close the operational release gate: online cache
  coordination, idempotency expiry, quotas and deployment policy remain open.

- [x] Integrate the reviewed battlefield-first UI into the live frontend.
  Unit checks, lint/build and five isolated browser suites pass against the
  repaired backend. The full integrated browser harness also passes, including
  natural AI/human BO3 and restart recovery. Its stale collapsed-log selector
  was corrected without weakening authoritative state assertions. The second
  visual pass is now integrated: the complete combined browser harness passes,
  including dense-board checks and retained ordered-target controls. See
  [v2 evidence and limits](docs/ui-redesign-v2.md); this is not a long-session soak.

Work follows [the capability-batch protocol](docs/development/batch-workflow.md).
Group connected rules/AI work; retain fast per-change checks and broader batch
gates. Do not substitute parser coverage, smoke wins or unchanged buggy decisions
for correctness or seasoned-player acceptance.

- [x] Finish the cross-family rules regression repair batch: integrate the
  canonical agent handoff, preserve compound counter/graveyard instructions,
  implement bounded global damage doubling and undying with durable object
  references. The independently reproduced 14 failures are repaired, with 195
  integration checks and 24 new edges passing. The final isolated 7,189-case
  backend gate and scoped frontend/browser gates pass. All ten pinned samples
  repeat without timeout or drift, but reversed Blue Control/Ramp remains a
  slow-planning investigation. The new UI's complete harness is separately
  delegated. See [scope and open boundaries](docs/testing/rules-regression-repairs.md).

- [x] Finish the current search/provenance batch: correct recursive reply actors,
  continue already executed selected prefixes without reducing search breadth,
  pin resolved replay manifests, and validate both seats across multiple styles.
  Full backend/frontend/browser gates and reference/repeat replay comparisons
  pass, with the final manifest validation covered by affected follow-up checks.
  Six snapshot medians improve 14-30% against an actor-correct replaying reference;
  two remain over one second. See [scope and evidence](docs/testing/ai-search-prefix.md).
- [x] Finish the AI observation/public-utility batch: exclude unexposed card
  metadata from all agent decision paths, preserve owned inspection continuations,
  persist private submitted-deck composition for linked land-search planning,
  conserve pure removal without banning profitable friendly death-trigger lines,
  and rank announced public trigger targets/optional acceptance. The captured
  Ramp self-destruction decision is repaired. All 7,021 backend tests across 289
  isolated test files pass, with frontend lint/contracts/build and the complete
  41-script browser harness. See [scope and evidence](docs/testing/ai-information.md).
- [x] Complete the bounded revealed-hand memory/copy batch: retain authorized
  identities through supported reveals/public returns and restart, exclude stale
  hidden-library/face-down observation records, and avoid copying private metadata
  before masking. Known land inventory counts owned stolen lands but not land
  tokens. All 7,053 backend tests, frontend gates and 41 browser scripts pass;
  ten pinned seed/seat samples repeat twice on each tested stage without timeout
  or matching cast/payment errors. See [scope and evidence](docs/testing/ai-memory.md).
- [ ] Continue durable public-card memory and uncertainty-aware
  future-resource planning, including authorized observations surviving zone
  changes and restart. Integrate known-list priors without reconstructing hidden
  shuffled identities; compare actual decisions across proactive and reactive
  styles. Profile the private observation boundary and complex trigger/search
  continuations before extending depth or claiming information-set/expert play.
  The [known-composition draw/rummage checkpoint](docs/testing/ai-resource-priors.md)
  adds reconciled own-list land/spell expectations, shared curve/role utility,
  unknown fallbacks and public resolving-source visibility. The 7,135-test broader
  gate, 468-check fixture follow-up, frontend gates, two-seat HTTP/SQLite probes
  and ten repeated/final-compared seed/seat samples pass. Ordered knowledge, color
  feasibility, opponent beliefs and multi-turn resource planning remain open.

- [x] Finish shared basic-land subtype layers: global, controller-only
  and Aura additions/replacements, source-existence dependencies, intrinsic mana,
  entry, counted subtypes, landwalk, AI resource reads and public/snapshot parity.
  Seventeen canonical fixtures and 74 new regressions cover shared subtype and
  per-ability spending/payment paths. All 5,724 backend tests across isolated
  shards and the complete final-source Chromium harness (eight new scenarios)
  pass. Twenty-four cross-archetype seat-balanced samples, repeated twice,
  finish with zero timeout, anomaly or drift. See
  [current checklist and boundaries](docs/testing/land-type-layers.md).
- [x] Extend AI valuation for public resource changes from type-changing
  effects, including own fixing and opponent disruption. Use shared projections
  and known information, not hidden opposing hands or forced matchup win rates;
  verify actual before/after decisions across archetypes and difficulties.
  Shared projections, dynamic retention, Aura targets and comparable ordinary
  land alternatives pass focused checks, including HTTP/SQLite paths. Canonical
  quoted token abilities, next-turn draw scheduling and attached-creature
  recipient references are repaired alongside this batch. Missing Oracle metadata
  no longer crashes the new heuristic; focused compatibility checks pass.
  All 6,134 isolated backend tests and final-source browser/frontend gates pass.
  Sixty six-archetype seat-balanced samples, repeated twice, resolve with zero
  timeout, anomaly or determinism failure; see
  [scope and checklist](docs/testing/ai-public-mana-changes.md).
- [x] For that valuation batch, first reproduce both useful fixing and harmful
  self-disruption using canonical additions/replacements. Compare legal spell
  access and retained resources through checked projected actions, including
  source/controller changes, restricted abilities and entry costs. Test both
  seats and multiple archetypes before running the repeated replay matrix.
- [x] Implement bounded printed Foretell actions, later-turn alternative costs,
  saved cast/look permissions, live cost/grant modifiers and both-seat controls.
  Self-buff rewards use the stack; all AI styles share conservative idle-mana
  banking. Canonical keyword tests do not certify all card effects. See
  [scope and remaining acceptance](docs/testing/foretell.md).
  Validation: 6,359 isolated backend checks, frontend gates and final-source
  Chromium pass. Six seat-balanced samples repeated twice show no reported
  timeout, anomaly or drift. The 855-second Control/Ramp integration shard
  confirms the wider latency work below remains open.
- [x] Add bounded conditional Foretold token/scry effects, selected-cost X
  contracts, both-seat later-turn browser casting and durable game-end reveals.
  Preserve unknown-clause warnings. Shared AI action construction now uses the
  selected alternative cost rather than the printed cost when sizing X.
  Validation: 6,482 isolated backend checks, frontend gates and complete
  final-source Chromium flows pass. Six seat-balanced offline-data samples,
  repeated twice, resolve without reported timeout, anomaly or drift; these
  are repeatability checks, not expert-play or matchup-balance certification.
- [x] Add bounded effect-created Foretell permissions through ordinary draw/hand
  and damage/self-exile triggers. Preserve owner access, countering, prevention,
  copied-object identity, replacement-aware draws, saved choices and selected-face
  costs; share AI hand selection across styles and difficulties. Fix absent versus
  zero mana costs in shared casting, preserving explicit free/alternative costs.
  Validation: 6,630 checks across 282 isolated test files, all 41 Chromium scripts
  and frontend gates pass. Four seat-balanced mechanic samples reproduce exactly
  on rerun with no timeout or invalid-action messages; these are not balance data.
  The slowest integration shard takes 1,112.66 seconds, keeping latency work open.
  See [acceptance evidence and remaining boundaries](docs/testing/foretell.md).
- [ ] Complete other Foretold conditional effects and effect-created clause families,
  broader exile rewards, browser restart/countering and strategic/X-cost planning.
- [ ] Measure and bound wide-state tactical planning latency without silently
  skipping legal actions or losing deterministic decision behavior. The seeded
  live Control/Ramp BO3 restart regression passes but remains an expensive gate.
- [x] Profile fixed real-game decisions and reduce repeated pure-query and clone
  work without changing search horizons, candidate limits or chosen actions.
  Query scopes isolate root/branch/thread contexts and discard results before
  authoritative mutation; mutable return containers and card aliases stay safe.
  See [measurements and remaining latency work](docs/testing/ai-query-latency.md).
  Validation: 6,685 isolated tests, 283 assigned files, frontend gates and all
  41 Chromium scripts pass. Six fixed-snapshot medians improve 19-46%; six
  seat-balanced samples preserve complete baseline traces on both optimized
  repeats. Hardest sampled decisions still exceed one second; the latency
  requirement above remains open rather than becoming a smaller completion goal.
- [x] Export/import hash-verified resolved matrix deck manifests with preserved
  roster order and source/selected corpus provenance. Imported runs bypass mutable
  cache/bootstrap state and validate all inputs before simulation; final CLI
  repeatability and no-database runtime checks pass.
- [ ] Verify canonical corpus/initial cache provenance beyond input consistency for
  paired before/after reports. Separate databases used by tests from replay
  databases; bootstrap/metadata history can change the selected representative
  roster. Internal repeated execution is not fixed-corpus cross-run validation.

- [x] Finish shared mana-ability acceptance: live devotion and counted outputs,
  paid activations, pure multipliers and resource-preserving spell payments.
  All 5,650 isolated backend tests, frontend gates, complete Chromium and 24
  seat-balanced samples repeated twice pass. Forty-one new regressions and
  84 cross-archetype decisions cover the bounded payment path. See
  [checklist and limits](docs/testing/mana-abilities.md).

- [x] Finish shared conditional-type acceptance: effective battlefield types,
  live devotion thresholds, animation/ability-loss ordering, combat removal,
  band persistence, counted life loss and entry/control tenure. All 102 new
  checks plus nine existing banding checks pass. All 5,609 isolated backend
  tests, frontend gates and complete Chromium pass; 24 seat-balanced samples
  repeated twice report no anomalies, timeouts or drift. See
  [scope, evidence and checklist](docs/testing/conditional-creature-types.md).
  Keep arbitrary type/dependency/copy layers explicitly open; bounded devotion
  mana is covered by the subsequent batch above.
- [ ] Extend non-tap/mixed-output/triggered mana and conditional/global type effects with
  canonical fixtures, layer/dependency tests and both-seat live/simulator parity;
  do not infer complete-card support from a recognized type clause.

- [x] Finish bounded shared post-block tactical forecasting: forty-four canonical regression/HTTP checks and 5,405 isolated backend tests pass; twenty-eight actual Master decisions improve from zero to twenty-eight checked wins across fixed/live-variable pumps, both seats and six archetypes. Frontend gates, complete Chromium and two repeated seat-balanced matrices (24 samples/48 executions) pass. See [scope and checklist](docs/testing/ai-combat-responses.md); unanswered winning forecasts are not adversarial/expert-AI certification.
- [x] Finish bounded defensive/announced-stack/between-strike acceptance: 103 new checks, expanded 380-check selection, 5,508 isolated backend tests, fifty-two actual before/after outcomes (0 to 52), frontend gates and Chromium with four new casts pass. Twelve seat-balanced replay samples repeated twice report no anomaly, timeout or drift. See [scope and checklist](docs/testing/ai-defensive-responses.md); future-turn/adversarial planning and heuristic calibration remain open.
- [ ] Expand adversarial response likelihoods, end-step deferral/future-turn resources, public choice branching and larger/multiaction/multitarget boards. Calibrate life/hand weights across deck styles; never inspect hidden hands or force matchup percentages.

- [x] Finish shared live devotion payoff acceptance and front-characteristic/proxy boundaries. Seventy-nine new checks, 5,361 isolated backend tests, frontend gates, complete Chromium with fourteen new casting cases and repeated seat-balanced replay samples pass. The conditional-type batch subsequently implements bounded God type changes; the mana batch adds bounded devotion sources, with broader mana families still open. This is not expert-AI certification. See [scope and checklist](docs/testing/devotion.md).

- [x] Finish bounded shared crew/indefinite land-animation effect lifecycles and copiable-type boundaries. Validation: 48 new both-seat lifecycle/HTTP/trigger checks, 5,282 isolated backend tests, frontend gates, complete Chromium and twelve repeated seat-balanced replay samples pass. Conditional/global type changes, dependency ordering and full copy layers remain open. See [scope and acceptance](docs/testing/type-effect-lifecycle.md).

- [x] Finish bounded conditional self/team static preflight admission and shared opponent-graveyard/low-life predicates. Validation: 5,234 isolated backend tests, frontend gates, complete Chromium and two repeated seat-balanced matrices (24 samples/48 executions) pass. Arbitrary composed clauses, attachment coverage, devotion and type-changing/layer fidelity remain open. See [scope and acceptance checklist](docs/testing/static-admission.md).

- [x] Finish supported conditional static resource-effects acceptance: shared Threshold/Metalcraft/Delirium/Hellbent, life/color/basic-land predicates; keyword provenance, Ward layer costs and coordinated combat clauses. Fix the request-session leak exposed by browser acceptance. Validation: 5,215 isolated backend tests, frontend gates, complete Chromium, five fresh six-case browser repetitions and two explicit repeated seat-balanced matrices pass. See [scope and remaining gaps](docs/testing/conditional-static.md).

- [x] Batch supported hand/graveyard/type/resource creature definitions, battlefield-only self modifiers, printed-expression persistence, copy/face propagation, effective damage and shared AI entry valuation. See [scope and acceptance evidence](docs/testing/characteristic-stats.md).
- [ ] Extend unsupported/composed conditional clauses and their preflight admission diagnostics; expand unusual characteristic/type-changing definitions, devotion and full layer/zone-change fidelity. Add cost/entry-aware and adversarial AI projections before claiming arbitrary-deck expert play.

The user deferred alpha-UI fixes and the redesign on 2026-10-01. The unpublished
layout patch and browser evidence are preserved on RCHFiles under
`diagnostics/deferred-ui-20261001/`; the tracked UI remains the published version.
Do not treat passing fixture tests as proof that the current UI is ergonomic.
Finish backend rules, supported-corpus correctness and simulation/AI evidence
before returning to the redesign. Broad release gates below remain open.

- [x] Batch fixed surveil, supported surveil/cast/draw payoffs and recipient-preserving mill. Private ordered choices, player-level first-surveil history, original-object payoffs, all-difficulty known-resource decisions and HTTP/SQLite/App restoration are covered. Repair effect-authorized casting through ordinary target/cost/event admission, recognized exile departures, singular discard-or-sacrifice costs, X token counts and actual mana-spent provenance. See [bounded scope](docs/testing/surveil-mill.md); this does not certify complete cards or expert AI.
- [x] Add durable effect-authorized graveyard cast/decline choices for both human seats, reusing ordinary target/cost controls and checked announcements. Announce supported graveyard trigger targets before resolution, preserve both choice stages in snapshots, and prefer usable AI spell targets over uncastable counters or zero-mana-spent draw. See [bounded scope](docs/testing/effect-cast-choices.md); this is not broader optimal tactical planning.
- [ ] Extend surveil modifiers/replacements and conditional payoffs; optimal nonland/graveyard curation, broader optional/additional costs and payment continuations. Validate graveyard-permission target selection's tactical value beyond avoiding illegal or ineffective announcements.
- [x] Add explicit normal/free spell discard and sacrifice cost-card selections, checked against owned eligible zones before payment. Reuse shared discard/sacrifice operations so supported leave/dies triggers and replacements also apply to costs. All AI difficulties choose known lower-loss payment cards and compare singular either-cost branches. See [bounded contract](docs/testing/cast-payment-selections.md).
- [x] Replace whole-text spell cost inference with a bounded shared additional-cost clause reader: exact discard/sacrifice counts, typed unions, mixed components, fixed-life alternatives, explicit unsupported-clause rejection and stable alternative-method identity. Both-seat canonical and HTTP checks cover counted payments and land costs; AI compares grouped payment losses. See [scope and remaining gaps](docs/testing/spell-cost-clauses.md).
- [x] Implement bounded single-mana instant/sorcery kicker payment and conditional instruction surfaces together. Ordinary and free casts, branch-specific targets, copies, known-resource AI choices, both human seats and snapshot recovery share the casting path. See [scope and acceptance evidence](docs/testing/kicker.md); this is not complete kicker support.
- [x] Add bounded permanent kicker: shared entry counters/replacements, conditional ETBs, durable original-object casting history, copied permanent spells and noncreature-permanent removal. Full isolated suite (3,958 tests), focused 226 tests, frontend checks, complete browser suite (16 new cases) and two-sample repeated replay smoke pass. See [scope and evidence](docs/testing/permanent-kicker.md); broader clauses and expert AI remain unfinished.
- [x] Batch recognized kicked-cast payoffs, first-kicked discounts, fixed token ETBs and AI payoff guards. Acceptance: 4,013 backend tests; frontend lint/contracts/build; full browser suite with sixteen new cases; twelve seat-balanced replay samples repeated twice, no reported anomaly or drift. See [checklist, corpus inventory and remaining limits](docs/testing/kicked-cast-payoffs.md). Draw replacement forecasting, other kicker families and actual knowledge-consuming AI remain open.
- [x] Batch replacement-aware optional draw forecasting: canonical doublers, first-draw exceptions, caps and both-seat AI choices; 189 focused checks, 4,081 backend tests, frontend gates and full browser pass. Twelve seat-balanced replay samples repeated twice have no reported anomaly or drift. Actual before/after decisions reduce six unsafe kicked draws to zero while retaining six safe choices. See [scope and checklist](docs/testing/ai-draw-forecast.md); dredge, arbitrary replacements, draw-trigger chains and expert planning remain open.
- [x] Batch fixed nonmana kicker: shared life/typed-sacrifice costs, conditional discard counts, copies, checked payments and payment-aware AI; repair controller-scoped self-or-other death triggers. Acceptance: 421 focused checks, 4,156 backend tests, frontend gates, full browser with twelve new cases, twelve seat-balanced replay samples repeated twice without reported anomaly/drift, and 24 checked AI decision traces. See [scope and checklist](docs/testing/nonmana-kicker.md); classification does not certify whole cards, compounds or expert decisions.
- [x] Finish bounded acceptance for five [canonical kicker goldens](docs/testing/kicker-goldens.md): four artifact-or-creature sacrifice negative-stat spells plus Hypnotic Cloud's mana kicker and conditional discard. Shared lethal-state targeting, payment, copies, snapshots, 204 focused checks, full browser with twenty new cases, frontend gates and 4,340-test backend suite pass; twelve seat-balanced samples repeated twice have no reported anomaly/drift. The twenty HTTP cases added during the full run pass separately. Constructed legal-move materialization improves 0/24 to 24/24 productive kills, not autonomous timing, whole-card or expert-play certification.
- [x] Finish bounded acceptance for the [qualified subtype/color cost batch](docs/testing/qualified-spell-costs.md): four canonical spells, actual green-creature search and referenced-controller damage; 84 focused checks, 374 initial regressions, 4,430-test full suite, frontend gates, full browser with eight new cases and twelve repeated seat-balanced replay samples pass. Fourteen late borrowed-resource/token checks pass separately. Preserve whole-card, autonomous timing and general layer-fidelity limits.
- [ ] Extend broader qualified filters, exile/reveal/return/tap and variable-count costs with exact eligibility; model different-type mandatory components and general payment order. Finish activated-cost selections and interrupted continuations. Extend broader permanent/ETB and cast-trigger kicker families, multiple/nonmana/X costs, multikicker, arbitrary conditional instructions and face-specific acceptance; retain coverage warnings for unmodeled forms.
- [x] Finish bounded [exhaustive and announced-X payment acceptance](docs/testing/variable-spell-costs.md): shared costs, actual canonical effects, public-state AI checks, both-seat controls and HTTP atomicity; 58 focused checks, 4,502 backend tests, frontend gates, complete browser and twelve repeated seat-balanced samples pass. Twelve autonomous public-state sequences reach tested finishes against scripted passing. Retain explicit blocks for random payments and X recipient cardinality. Bounded linked-discard resolution is covered by the subsequent milestone; general payment order remains unfinished.
- [x] Finish [resolution-time linked discard acceptance](docs/testing/linked-discard.md): canonical variable basic-land search and whole-hand fixed/count-linked draw, owned choices, replacements, current-controller spell/ability copies, nested draws, HTTP/SQLite recovery and bounded AI resource checks. Verification: 80 new checks, 4,582 isolated backend tests, frontend gates, complete Chromium and twelve repeated seat-balanced replay samples without reported anomaly/timeout/drift. General linked instructions and expert discard strategy remain open.
- [x] Finish [bounded rummaging and discard-history acceptance](docs/testing/discard-history.md): complete printed-limit self-discard/draw and per-turn counted whole-hand draw, normal modal/loyalty paths, shared cost/cleanup/event history, copies/counters, API/SQLite recovery and bounded AI choices. Verification: 92 new checks, 4,674 isolated backend tests, frontend gates, complete Chromium with six new cases and twelve repeated seat-balanced replay samples without reported anomaly/timeout/drift. Broader linked effects and expert discard strategy remain open.
- [x] Finish [simultaneous wheel and hand-defined characteristic acceptance](docs/testing/wheel-draw.md): fixed/actual/largest/minus-one draws, shared discard events, active-first owned draw continuations, star-creature lethal checks, signed metadata and bounded public-count AI evaluation. Verification: 114 new checks, final 386-check selection, 4,770-test isolated full suite (18 late tests pass separately), frontend gates, complete Chromium with twelve new cases and two twelve-sample repeated seat-balanced matrices without reported anomaly/timeout/drift. Whole-card, arbitrary characteristic and expert-strategy certification remain open.
- [ ] Extend opponent/random variable discards, linked conditional clauses, wider mode combinations and discard-characteristic history. Preserve actual count, event staging, owned continuations and explicit unsupported-sequence admission; validate graveyard payoff and card-quality planning rather than equating parser coverage with strong AI.

Historical cost-parser evidence: a fresh canonical Scryfall probe on 2026-10-03
reproduced Cathartic Reunion priced as one discard rather than two and Raze priced
as a creature rather than land sacrifice. The shared clause reader above fixes
those counts/types and rejects exercised unsupported clauses, without named-card
exceptions. This does not establish that every card cost/effect is supported.
Original source payloads, Oracle IDs and the isolated failing probe remain under
`diagnostics/cast-payment-selections/20261003T091348Z/canonical-cost-probes/`.
- [ ] Investigate the optional Python 3.12.3 timed traceback diagnostic crash with a minimal reproducer. Preserve its failed run separately from normal BO3/full-suite outcomes; do not attribute it to an upstream issue without proving the cause. See [evidence boundary](docs/testing/surveil-mill.md).
- [x] Batch the five canonical legendary Channel lands using shared legendary-creature discounts, target unions, owned optional basic-type land searches, post-mill creature/planeswalker choices and temporary token haste. HTTP/SQLite/App continuations and Master public-board winning hand-ability retention are covered. See [bounded scope](docs/testing/legendary-channels.md); whole-card certification, arbitrary mill/replacement clauses and long-term strategic retention remain open.
- [x] Batch source-bound hand activations with spell/ability counter-payment ownership. Canonical damage, bounce, graveyard-card return, basic-land search and counter fixtures share costs, targets, activated stack identity and restoration. Noncreature graveyard hints reach both human seats and AI; human Pay/Decline choices survive reload. See [bounded scope](docs/testing/hand-activations.md); arbitrary zone permissions, unusual hand costs/reducers and wider strategic search remain open.
- [x] Batch capacity-aware blocker intent search, shared legality/payment filtering, multi-block fallback, direct-versus-band-expanded declaration provenance, explicit combat-damage projection and planeswalker defense. See [scope and validation](docs/testing/combat-intents.md). Wide-board optimality, hidden-choice projections and deeper adversarial planning remain open.
- [x] Bind supported fixed attack/block costs to shared self/attachment/global recipients; keep unrelated creatures free and price a multi-blocker once. Parse alternative self/attachment all-block recipients, with canonical AI/HTTP/SQLite/App checks. See [scope](docs/testing/recipient-combat.md); this does not certify complete cards.
- [x] Share supported numeric activation increases/reductions, one-mana floors, source/recipient scope and mana exceptions across legality/payment/hints. Cover reserved tap/sacrifice/crew resources, zero printed cost, cycling/ninjutsu/loyalty/equip, announced AI X, checked HTTP and SQLite restore. See [scope](docs/testing/activation-modifiers.md); this does not certify every ability or whole card.
- [x] Implement bounded mana-symbol bestow casting, effective spell/Aura characteristics, target-dependent payment, legal/illegal target resolution, unattachment, copies/retargeting and HTTP/restart. Both-seat browser mode/target/cast controls and actual payable AI decisions are covered. See [scope](docs/testing/bestow.md); this is not whole-card or expert-AI certification.
- [x] Batch source-power activation discounts with controller-turn opponent spell/ability taxes. Shared effective power, source/controller scope, floors, suppression and mana exceptions reach legality/payment and HTTP/SQLite recovery; unsupported ability-specific forms remain visible gaps. See [implemented scope](docs/testing/activation-modifiers.md); this does not certify whole cards or expert AI.
- [x] Bind supported count/condition discounts to the selected regular ability across legality/payment/hints/AI. Canonical artifact, graveyard-creature, creature-counter, controlled-creature and controller-turn fixtures cover real payment, resolution, unrelated-ability isolation and HTTP/SQLite recovery. Cost determination is locked before a counted Treasure is consumed; source-excluding tap targets use shared inference/admission. See [bounded scope](docs/testing/activation-modifiers.md); keyword/mana/other-zone abilities and arbitrary conditions remain open.
- [ ] Extend bestow phasing/type-layer fidelity and arbitrary zone permissions; ability-specific activation discounts, arbitrary conditional/dynamic expressions, copied-name references, explicit reduction/payment-source ordering and costed-mana conversion planning. Keep unrecognized clauses flagged before claiming full Noble Quarry/Oppressive Rays support.
- [x] Prevent creature-first proactive AI heuristics from overriding supported winning setup modes. Shared Master combat projections cover bestow, Auras, Equipment, pumps and blocker removal; already-winning boards preserve cards. See [scope and evidence](docs/testing/combat-setup.md): 3,267 isolated backend tests, complete Chromium and 30 repeated seat-balanced samples pass. Expanded canonical decision probes improve from 116 to 140 winning fixture continuations across fourteen archetype labels, not tournament win rates.
- [ ] Extend setup planning to wider boards, multiple setup actions, exhaustive target alternatives and adversarial instant responses without hidden-card peeking. Establish Strong/Casual adoption and broader unsupported-effect detection rather than claiming arbitrary-deck expert play.

- [x] Add optional flushed JSON/sample progress, measured ETA and an atomic non-resumable progress file to the replay CLI. Thirty-three runner/protocol/sampling checks, a real two-sample repeated seat-balanced run and 3,274 isolated backend tests pass. Default output remains unchanged. A progress file is not a live-process check, completed validation proof or resumable game snapshot; source-local databases stay off NFS.
- [ ] Add deliberate replay checkpoint/resume and periodic within-sample heartbeats with crash/restart and duplicate-execution acceptance tests; expose the distinction from completed-rule/strength validation.

- [x] Batch numeric attack payments with target-specific Lure-style blocking requirements: shared locked payments, optional-payment-aware requirements, exact capacity-aware blocker scoring, all-difficulty AI finalization, actual-use traces, canonical fixtures and atomic HTTP/SQLite/browser checks. Fix declaration priority/pass bypasses and sacrifice-during-payment ghost attackers. See [scope and remaining forms](docs/testing/combat-payments-requirements.md).
- [x] Extend attack mana costs to colored/colorless/snow/hybrid/Phyrexian symbols, explicit human branch announcements, shared AI branch provenance and zero-cost optionality. Add static self/Aura/Equipment minimum blocking requirements with saturated scoring, small exhaustive comparisons and wide mixed-board bounds. See [scope and acceptance](docs/testing/combat-branches-minimums.md); no complete-card or expert-AI claim follows.
- [x] Batch controller-relative domain attack taxes with resolution-created global attack/block mana taxes: announced X, cleanup lifetime, source independence, snapshot/HTTP recovery, per-distinct-blocker payment, optional paid requirements and bounded public-board AI activation planning. See [scope](docs/testing/combat-domain-temporary-costs.md). This does not implement all domain cards, conditional/static block taxes or arbitrary cost events.
- [x] Batch supported source/controller-conditional attack taxes with static global/controller/opponent block mana costs: shared source-status/self-reference predicates, live suppression, locked payment, optional requirements, all-difficulty actual AI choices and both-seat HTTP/SQLite/browser checks. See [scope](docs/testing/conditional-combat-costs.md); qualified subsets and arbitrary conditions remain unsupported.
- [ ] Complete arbitrary conditional/qualified block taxes, nonmana/optional additional costs, individual mana-source choices and interrupted cost continuations; extend targeted requirements to qualified blockers, temporary/granted nonkeyword requirements and specific defenders. Finish pre-declaration priority/timing acceptance and arbitrary cost/requirement composition rather than treating bounded mana batches as completion.

- [x] Enforce unconditional numeric attack/block declaration limits, player-only attack caps, and maximum recognized each-combat requirements across checked human actions, internal completion and all AI difficulties. Expose active limits in legal hints/live diagnostics. See [scope and regression contracts](docs/testing/declaration-limits.md). Remaining paid cost forms, conditional limits, broader target requirements and attacker-chosen blocking remain open.

- [x] Share bounded condition-aware static combat clauses across self, attachment and global sources, with source suppression, effective-power limits, cumulative extra blockers and unresolved-clause engine traces. See [scope and remaining gaps](docs/testing/conditional-combat.md). Broader predicates, other paid cost forms and dedicated in-match visual diagnostics remain open.
- [x] Reuse supported static predicates for known-gap coverage and live evaluation; expose card/face-specific combat gaps in completeness, simulator preflight/results and a locked public-battlefield diagnostics API. Verify canonical warning admission through the real browser flow. See [scope](docs/testing/combat-coverage-diagnostics.md). Numeric payments are now handled by the subsequent shared payment reader; coverage still does not certify arbitrary cards.

- [x] Route supported opening-hand permanent entries through shared off-zone counter preparation, affected-player replacement ordering and guarded once-only commitment. Keep mandatory exile instructions resumable; do not consume cast-only entry records.
- [x] Implement bounded proliferation instructions, all-kinds non-targeting selection, resumable atomic counter vectors, canonical triggers/spell continuation, both-seat controls and shared AI choices. See [scope and remaining gaps](docs/testing/proliferation.md).
- [ ] Complete generalized pre-entry characteristics, remaining multi-kind entry/damage/cost events, proliferation-event replacements, conditional instructions, counter movement/spending and arbitrary replacement clauses.
- [x] Persist permanent-counter timestamps and merge keyword-counter grants with supported layer-6 removals, including global keyword suppression and explicit can't-have overrides. Existing keyword consumers/public views read them; proliferation AI treats redundant and restored keywords differently.
- [x] Route turn, spell and animated-land untaps through the shared stun-counter replacement, including already-untapped and self-restricted untap-step cases; preserve state through snapshots.
- [x] Resolve bounded unconditional named-counter instructions and fixed-number scry clauses without dropping later effects. Both-seat private scry partition/top ordering and AI decisions use durable choices. Remove name-based fabricated effects and reject missing spell Oracle metadata. See [counter/untap scope](docs/testing/named-counters.md).
- [x] Implement shield damage/effect-destruction consequences, shared bulk indestructible checks, simultaneous multi-block combat boundaries and durable affected-seat scalar damage ordering. Preserve unpreventable damage and free reduction semantics; add HTTP/SQLite restore and AI resource-choice regressions. See [scope](docs/testing/shield-counters.md).
- [x] Implement Decayed/Exalted intrinsic stack triggers, supported independent instance counts, non-targeted original-object references and durable end-of-combat sacrifice. Validate both seats through HTTP/SQLite restore and bounded AI combat projections. See [scope](docs/testing/combat-keyword-triggers.md).
- [x] Apply source-aware supported printed color/type hexproof variants and counters to target hints, checked actions and resolution. Separate durable object-bound grants from printed metadata/physical counters; cover both seats, SQLite restore and actual planeswalker hint identity. See [scope](docs/testing/hexproof-variants.md).
- [x] Persist resolution-created keyword grant/removal timestamps, duration, incarnation and source provenance separately from physical counters. Cover targeted gain/loss sequences, cleanup, legacy migration, HTTP/SQLite resume and bounded public-board AI target projection. Preserve actual control-change/untap/haste instructions and report unsupported optional tap/untap choices. See [scope](docs/testing/keyword-effect-timestamps.md).
- [x] Connect supported all-ability loss to printed mana capacity, activated/loyalty/equip/crew legality and printed trigger collection. Preserve pre-death suppression in last-known snapshots and already-stacked abilities; verify both seats through HTTP/SQLite restore. See [scope](docs/testing/printed-ability-suppression.md).
- [x] Extend supported suppression to continuous bonuses/keyword sources, recognized counter/token/life replacements, draw limits, land/library permissions, cost modifiers and static timing/mana readers. Preserve the bounded combined loss/base-stat effect across layers, not independent abilities; validate shields and AI reward valuation. See [scope](docs/testing/static-ability-suppression.md).
- [x] Implement bounded temporary targeted/player-wide all-ability loss and base-stat setters with shared resolution timestamps, snapshot/zone/cleanup lifecycle, ETB tap-then-loss target continuation, public-board AI projection and split-second timing. See [scope](docs/testing/temporary-ability-loss.md); this does not close general layers or expert AI.
- [x] Apply supported suppression to recognized printed combat restrictions/capacity, player immunity and battlefield counter protection. Replace immediate Bushido/Rampage/Flanking changes with counterable APNAP triggers, numeric instances, response-time blocker counting and original-object references; include shared AI combat projection and HTTP recovery. See [scope](docs/testing/combat-ability-provenance.md).
- [ ] Integrate remaining direct Oracle static/replacement/prevention/permission readers with effective ability provenance, dependency ordering and cross-layer continuation. Complete arbitrary gained non-keyword abilities, general combat-reference incarnation tracking and simultaneous departure/reentry LKI acceptance; the increments above do not close full suppression.
- [ ] Complete affected-player ordering across simultaneous combat, protection/amount-based prevention, counter-conversion and competing destruction replacements. Finish arbitrary keyword grant composition, variants, other untap restrictions and competing replacements. Complete full non-keyword ability suppression and broader timestamp/dependency fidelity; validate tactical choices against those actual rules.
- [ ] Expand tactical decision-quality and corpus-wide latency evidence, then replay/restart matrices and operational backend gates.
- [x] Separate external card/image/ruling sync from latency-sensitive match creation. Admission now reads local cache, verified canonical knowledge and the shipped seed without network calls or database writes; missing faces/stats return structured sync-first errors. The existing completeness report exposes local readiness and image status. Cold browser recovery no longer needs fixture cache priming. See [offline admission scope](docs/testing/offline-match-hydration.md).
- [ ] Add bounded asynchronous card-sync progress/cancellation and request quotas; explicit card/ruling/image sync is still synchronous. Metadata readiness is not a semantic rules certificate.
- [ ] Redesign the alpha UI after backend milestones; use real pointer/viewport tests as well as fixture action tests.

Opening-route evidence is documented in [opening-hand scope](docs/testing/opening-hand-actions.md).
The final isolated backend suite passed 2,453 tests; focused tests passed 111,
and the final-source full Chromium harness passed. These close this bounded
opening-entry increment only, not the larger rules or release gates.

Damage-counter increment: supported infect/wither/toxic and noncombat
damage-to-counter results now use scalar replacement events with source-controller
attribution, combat aggregation, durable choices and deferred SBA/lifelink.
176 focused checks, frontend lint/build/unit and isolated human/AI HTTP probes
pass; the complete isolated backend suite passes 2,324 tests. Eight seat-paired
games reproduce complete results/logs across sixteen executions without timeout
or detected cost/target/action rejection. Full Chromium now passes after fixing
simulator-fixture storage leakage. Disk capacity and the live backend are
recovered; completed evidence is archived on RCHFiles. Successful browser runs
clean their scratch checkouts/profiles automatically.
[Scope and current evidence](docs/testing/damage-counter-replacements.md).

- [x] Implement and focused-test damage counter routing, effect-only provenance, simultaneous supported combat packets and repeated choice recovery.
- [x] Recover disk capacity and the LAN-bound backend, pass full Chromium, preserve evidence on RCHFiles and enable automatic successful-run scratch cleanup. Broader rules/release completion is not implied.
- [x] Publish the verified increment after documentation/Graphify checks: `92e6771` is confirmed on GitHub `main`.
- [ ] Complete remaining entry/cost counter variants, simultaneous noncombat/prevention fidelity, proliferation-event replacements and broader resource valuation. Supported entry routes and basic multi-kind proliferation have separate completed increments above; this item is not a claim that those features are absent.

Counter-effect replacement increment: 2,308 isolated backend tests, 257 focused
counter/AI checks, frontend lint/build/unit and full Chromium pass. A real HTTP
autoplay probe resolves a seat-two counter trigger; eight seat-paired smoke games
repeat complete reported results/logs across sixteen executions without timeout
or detected cast/target/cost rejection. Canonical doubling, halving and plus-one
clauses now modify registered counter effects with placer/recipient scope,
per-ability usage and affected-player choices. Resumption preserves effect
sequence/batch continuations and actual triggered stack items across snapshots.
Shared AI evaluates resulting amounts; the browser tests actual seat-two ordering.
[Scope and verification](docs/testing/counter-replacements.md).

- [x] Add bounded scalar replacement parsing, affected-player ordering, per-ability usage and durable continuations for registered counter effects; connect shared AI and human controls.
- [x] Route positive loyalty activation costs through scalar counter replacements with non-effect provenance, once-only payment, snapshot continuation and deferred ward triggers. Negative loyalty costs remain removal. See [bounded scope and checks](docs/testing/loyalty-counter-costs.md).
- [x] Route supported Saga turn-based lore and registered lore effects through crossed-threshold chapter events; support grouped symbols, human order/targets, ward, durable batches and pending original-chapter lifetime. Expose lore in UI/API and add bounded AI token/team-buff dependencies. Verified 2,360 backend tests, 199 focused checks and full Chromium. See [scope](docs/testing/saga-counter-events.md).
- [x] Add off-battlefield normal permanent-spell entry counter packets: supported loyalty/lore/creature amounts, affected-player replacement choices, snapshot recovery and human Read Ahead choice with exact entry-turn chapter restriction. See [scope](docs/testing/permanent-spell-entry.md).
- [x] Make compleated reductions orderable against shared scalar modifiers; commit checked entry amounts without retroactive incoming global counter bans. Extend AI amount ordering to reductions and verify canonical cards through snapshot and seat-two UI paths. See [scope](docs/testing/entry-replacement-order.md).
- [x] Share counter preparation across supported created-token batches, permanent-spell copies, graveyard returns, library selections and green-creature hand placement. Keep candidates/off-zone cards uncommitted through choices; separate creation doublers from entry counters. Stage complete stack resolution and preserve original continuation ownership. See [scope](docs/testing/entry-routes.md).
- [x] Extend supported linked-exile returns to durable owner-aware counter/chapter and land-entry choices before atomic group commit; pause SBA around those choices. See [scope and remaining entry families](docs/testing/linked-entry-counters.md).
- [x] Prepare supported exile-return-transformed entries against durable back-face projections, distinguish entry loyalty from in-place counters and retain front-face restoration metadata. See [scope](docs/testing/transformed-entry.md).
- [ ] Extend the now-shared supported opening-entry pipeline to remaining special entry families and general projected pre-entry characteristics; complete simultaneous multi-kind ordering, conditional/non-doubling token replacements and cast-linked one-shot semantics. Complete arbitrary chapter effects, optional/multiple targets, phasing and gained/suppressed chapter abilities; improve AI Read Ahead planning.
- [ ] Expand AI simultaneous-trigger planning beyond the verified friendly token/team-buff dependency; evaluate mixed effects and board-state interactions with before/after decision traces.
- [ ] Route entry/damage/activation costs through the same replacement event model with correct pre-entry characteristics, no premature SBA/triggers and resumable simultaneous batches. Complete multi-kind packets, counter movement/spending and proliferation. Existing route-fidelity warnings remain intentional.

Counter-prohibition increment: 2,264 isolated backend tests and 118 focused
checks pass, including 44 new regressions. Frontend lint/build/unit and full Chromium pass; eight
seeded seat-paired games reproduce their complete reported results/logs across
sixteen executions without timeout or detected cast/target/cost rejection.
Shared physical placement now enforces supported
unconditional player/type/self bans across effects, damage consequences,
Soul-Scar-style replacement, tokens, supported spell entries and Saga lore.
Existing counters and internal damage/buff markers remain distinct. General
loyalty-counter effects use the authoritative loyalty field; blocked positive
loyalty costs are rejected and filtered from ordinary legal moves.
[Scope and validation](docs/testing/counter-prohibitions.md).

- [x] Implement bounded unconditional counter prohibitions through shared application-code placement, with canonical fixtures and explicit unsupported-clause diagnostics.
- [ ] Finish doubling/halving/additive replacements across entry, damage and costs with correct attribution and resumable simultaneous/combat continuations. Registered counter-effect ordering landed above; general route coverage remains open.
- [ ] Finish all entry/cost/return/copy placement routes, proliferation, removal/spending and variable-resource AI. Initial planeswalker loyalty and arbitrary permanent-entry rules require further integration; do not claim whole-card correctness.

Player-counter milestone: 2,220 isolated backend tests, 181 focused checks,
frontend lint/build/unit and full Chromium pass. Fourteen canonical rows and
68 new regressions cover supported counter gains, scaling and ward X. Eight
seat-paired games repeat across sixteen executions without timeout or rejected
cast/target. [Scope, evidence and remaining gaps](docs/testing/player-counters.md).

- [x] Add persisted named player counters, poison compatibility and both-seat validated views. Connect supported cast/entry/death/end-step gain triggers, turn-scoped departure facts, self/global/CDA stats and named-counter ward X to shared application rules and human/AI payments.
- [ ] Implement remaining player-counter replacements/prohibitions and competing choices, proliferation/removal/spending, arbitrary counter-dependent clauses and variable resource strategy. Bounded unconditional bans landed above. Complete Meren/Daxos/Ezuri/Kelsien/Katara/Zuko/Toph follow-up abilities before claiming those whole cards work.
- [ ] Use the [cached experience inventory](docs/testing/player-counter-corpus.json) to prioritize actual unsupported clauses across all styles: 19 payloads, eight recognized gain clauses, fifteen with known gaps. Empty warning lists and recognized clauses are not whole-card or AI certification.

Ward-form milestone: 2,152 independent backend tests, 53 focused ward checks,
frontend lint/build/unit and full Chromium pass. Eight seeded seat-paired games
repeat identical reported results/logs across sixteen executions without timeout
or rejected cast/target; one optional Spell Pierce payment fails normally.
[Scope, evidence and remaining gaps](docs/testing/ward-forms.md).

- [x] Recognize supported printed keyword-list ward and named self-grants with tapped/untapped conditions; retain triggered payments after the conditional grant ends. Detect unsupported inline/granted costs and preserve human Oracle labels. [Scope](docs/testing/ward-forms.md).
- [ ] Extend arbitrary ward conditions/grants and remaining X definitions, complete suppression/dependency layers and multi-ward strategic payment planning. Named player-counter X/gains/scaling landed above; replacements and arbitrary counter-dependent semantics remain open. A known-gap warning is not implemented card semantics.

Hot-path/keyword milestone: 2,133 standard backend tests and 259 focused checks,
frontend gates and full Chromium pass. Shared optimizations preserve the captured
decision/reasoning and eight parent smoke-game logs. Composed keyword prohibitions
are corrected across all five Archetypes. [Evidence and open diagnostic risk](docs/testing/ai-hotpaths.md).

Ward milestone verified: 2,096 independent final-source backend tests, 246 focused
checks, frontend lint/build/unit and full Chromium pass. Eight seeded seat-paired
games repeat across sixteen executions without timeout or cast/target rejection.
See [scope, source hashes and remaining gaps](docs/testing/ward-resolution.md).

- [x] Replace the ward casting-tax approximation with supported triggered response/payment windows across spells, abilities and copies; provide durable human choices and bounded shared AI payment planning. See [ward scope and evidence](docs/testing/ward-resolution.md).
- [ ] Extend ward to generic resolution-time X definitions, arbitrary temporary/conditional grants, full ability-layer suppression and cost-prevention/replacement ordering. Improve pre-cast multi-ward and response/opportunity planning; certify supported whole-card clauses rather than infer correctness from keyword recognition.
- [x] Profile control/ramp decisions and reduce measured shared clone/static-parser work without changing tactical search depth or candidate limits. Add paired ablations, mutation/alias safety tests, canonical dynamic-state checks and composed keyword-prohibition fixes. See [hot-path evidence](docs/testing/ai-hotpaths.md).
- [ ] Bound worst-case per-decision and aggregated autoplay request latency without dropping relevant legal lines. Profile additional complex positions and master-plus search, improve reusable ranking/projection work and distinguish CPU contention from stalls. One optional timed diagnostic run crashed natively while printing a stack dump; standard suite and isolated/GDB BO3 reruns pass, but its root cause remains unverified. Preserve that investigation before stronger release claims.

Aura-cost milestone: 2,062 isolated final-source backend tests, 178 focused
checks, frontend lint/build/unit and the complete final Chromium harness pass.
Eight seeded seat-paired games repeat unchanged reported results/logs across
sixteen executions without timeout or cast/target rejection. Supported Aura
mechanics are verified by canonical and UI/API tests, not this smoke matrix.
See [scope and remaining gaps](docs/testing/aura-costs.md).

- [x] Implement supported target-aware Aura casting discounts and shared per-target cost-option compatibility across normal, permitted exile and escape casting. Separate enchant targeting from later abilities; share supported enchant constraints with attachment checks. Verify real human controls and attachment projections across styles. See [scope](docs/testing/aura-costs.md).
- [ ] Extend enchant constraints to subtype/status/numeric/compound predicates and player Auras; add deeper attachment exposure/resource planning, variable Aura X optimization, granted abilities, competing replacement choices and full type/ability/dependency layers. Do not certify a whole card from one working clause.

Equipment-context milestone: 2,020 isolated backend tests, 157 focused checks,
frontend lint/build/unit and the complete Chromium harness pass. Human seat two
can activate the supported target-discounted equip with no mana. See
[scope and remaining limitations](docs/testing/equip-context.md).

- [x] Implement bounded target-aware ordinary equip discounts, effective-power reductions, payable-target filtering and shared AI equip selection. Scope attached base-stat setters correctly; separate attachment layer timestamps from persisted battlefield identity. See [scope and verification](docs/testing/equip-context.md).
- [ ] Extend arbitrary Aura spell cost predicates, equip timing overrides/multiple costs, deeper equip transfer/response and resource-opportunity planning, reconfigure/fortify, and full ability/type/dependency layers. Supported Aura target-aware reductions landed above; partial-card warnings remain mandatory.

Attached-predicate milestone: 1,999 isolated production-source backend tests, 102 focused checks, frontend lint/build/unit and the full final-code Chromium harness pass. Eight seeded seat-paired games reproduce identical reported objects/logs across sixteen executions, unchanged from the parent with no timeout or cast/target rejection. Targeted canonical and real land/cast UI/API scenarios cover the new mechanics. See [scope](docs/testing/attached-predicates.md).

- [x] Implement supported attached condition/otherwise branches and domain, target-color and attachment-count scaling using shared public-state evaluators. Cover source-control ownership, threshold/counter/subtype predicates, snapshot purity and corrected shared AI value. Package a provenance-backed offline subtype registry; do not interpret unknown status words as false subtype tests. See [scope](docs/testing/attached-predicates.md).
- [ ] Extend compound/negated/composed predicates, arbitrary attached cast/activation cost predicates, otherwise prevention, source-named counters and granted activated abilities. Maintain explicit partial-card warnings and broad unsupported-mechanic preflight until whole families are actually covered.

Attached-scaling milestone: 1,974 isolated production-source backend tests, 77 final focused checks, frontend lint/build/unit and full Chromium pass. Eight seeded seat-paired games reproduce identical complete reported objects/logs across sixteen executions, unchanged from the parent and without timeout or cast/target rejection. Targeted canonical tests and the real UI/API removal scenario verify the new mechanics; the smoke matrix alone does not. See [scope](docs/testing/attached-scaling.md).

- [x] Replace flat-prefix attached modifier inference with supported current-controller battlefield-type/land-subtype counts and source-counter scaling. Preserve independent known effects and expose detected unknown attached clauses in public views, layer traces and both-seat controls. See [scope](docs/testing/attached-scaling.md).
- [ ] Extend remaining attached compound/negated predicates, arbitrary targeted cost predicates, otherwise prevention, source-named counters, granted activated abilities, source ability suppression and full type/dependency layers. Supported condition/domain/attachment-count/target-color forms landed above; arbitrary forms remain open. Reconfigure needs both attach/detach actions plus creature-type restoration; permitting attachment alone is not completion.

Restricted-mana/attachment milestone: 1,943 isolated backend tests, 196 focused checks, frontend lint/build/unit and full Chromium pass. New real seat-two UI/API coverage verifies restricted pools, actual equip stack/priority and attached effective stats. The [scope report](docs/testing/restricted-mana-equipment.md) distinguishes this supported increment from arbitrary spending/attachment semantics and expert-play certification.

- [x] Persist supported type-restricted mana units and respect casting/activation permission through ready/floated/snow/partial payment, source departure and snapshots; expose validated purposes in human views. Verify both seats and style-independent real-cost decisions.
- [x] Fix ordinary equip target admission, stack/priority/responses, source/target/control revalidation and paid-cost preservation. Connect supported attached static P/T and keyword grants to shared characteristics and layer traces.
- [ ] Extend spending predicates to selected mana abilities, multiple/granted/conditional/color/subtype restrictions, spending bonuses/triggers and restricted-resource future utility without hidden-hand peeking.
- [ ] Implement special/multiple equip costs/targets, reconfigure and fortify, arbitrary attached/granted effects and dependency/ability-suppression fidelity. Explicitly exercise the creature-Equipment reconfigure exception rather than claiming blanket attachment completeness.

Variable-resource increment: 1,897 isolated final production-source backend tests, frontend lint/build/unit, the complete final-code Chromium rerun and an eight-game/sixteen-execution repeated seeded matrix pass. Scaling quantities reach actual payment and public views; two Tribal/Burn traces contain real two-to-seven-green Archdruid payments. The initial browser failure prompted canonical offline sideboard fixture caching; production network latency is not declared fixed. This is not calibrated expert play or balance evidence. See [scope](docs/testing/variable-mana.md).

- [x] Share supported state-aware battlefield-count, source-counter and effective-power nonland outputs across automatic/manual payment, views, AI resource valuation and postcombat reservation. Verify canonical rows, both seats, snapshot purity and style-independent decisions.
- [x] Remove incidental live card synchronization from the sideboard browser fixture by caching canonical basics; validate zero network-sync calls through the real HTTP route without mocking production hydration.
- [ ] Complete mixed/color-dependent output, restricted/granted/multiple mana abilities, conditional costs, paid untap engines, and full type/layer dependency semantics. Add product-level missing-card sync latency/recovery tests; fixture determinism is not a production network fix.

Latest postcombat/layer increment: 1,875 isolated backend tests, frontend lint/build/unit and the complete Chromium harness pass. Six continuous-effect regressions fail on the parent and pass here; eight seed/seat-paired games repeat their complete reported game traces across sixteen executions without timeout or rejected cast/target. One optional Spell Pierce payment fails normally; the smoke traces are unchanged from the parent. This is bounded regression evidence, not expert-play or arbitrary-card certification. See [scope and evidence](docs/testing/ai-postcombat-mana.md).

- [x] Compare supported unblocked mana-source attacks with actual fixed-cost postcombat hand opportunities; preserve vigilance and release redundant sources, using the engine's payment rules and no carried floating mana. Validate both seats, ten style labels, colors, taxes and snapshot purity.
- [x] Correct qualified token/color/type continuous subjects and noncreature keyword protection; keep unactivated/triggered effect bodies out of static layers. Validate canonical protection/targeting/destruction, effective views and restore.
- [ ] Expand attack-versus-activation planning to blocked combat, multiple spells, opposing responses, variable/conditional/costed mana and untap engines. Add real conditional static and layer-5/dependency semantics rather than unconditional text inference.

Latest resource milestone verification: 1,835 isolated backend tests and frontend lint/build/unit pass, as does the complete final-code Chromium harness. Eight seed/seat-paired games repeat with identical full results across sixteen executions without timeout or logged cost/target rejection. Three traces changed from the prior milestone; stronger play is not established by trace changes. See [resource scope and evidence](docs/testing/ai-mana-resources.md). Both LAN services respond. The earlier intermittent sideboard timeout and timeout-diagnostic interpreter crash remain unverified.

- [x] Separate supported repeatable printed nonland mana capacity from readiness and share bounded public-board resource value across board/sacrifice and creature cast/threat evaluation. Canonical colored/colorless/flexible/multi-mana and excluded-source fixtures cover the boundary. See [scope](docs/testing/ai-mana-resources.md).
- [ ] Extend the bounded unblocked fixed-cost hand forecast to broader attack/block-versus-activation opportunity cost, restricted/conditional/variable sources and costed untap engines. The public land-count valuation remains an uncalibrated heuristic.

Recurring-payoff milestone validation: 1,811 isolated backend tests and frontend lint/build/unit gates pass. The complete Chromium rerun passes; an initial sideboard pending-operation timeout remains unverified. Eight seat-paired games repeat with identical full results across sixteen executions without timeout or logged cost/target rejection. [Scope and evidence](docs/testing/ai-recurring-payoffs.md) distinguish tactical fixture improvement from broader strategy and balance claims.

- [x] Share supported recurring payoff valuation across creature ranking, threat and sacrifice scoring; suppress unsupported public death opportunities under applicable exile replacements without mutating state. Validate canonical multi-archetype fixtures and snapshot restoration.
- [x] Preserve a safe answer-before-wipe sequence when a fixed-cost mass-destruction projection proves an opposing public death-trigger loss. Keep uncertain choices and human legal actions available. See [bounded implementation](docs/testing/ai-recurring-payoffs.md).
- [ ] Expand resource/activated/static payoff valuation, variable and compound removal sequencing, and adversarial opponent-response planning. This milestone does not certify these broader lines or seasoned-player strength.

Updated: 2026-09-30 UTC. Original audited implementation: `6b95fab0875f4cc35cb9648f8a598be5b13b2c80`, branch `main`. Current milestone evidence is recorded inline below.

Current pregame milestone: unconditional entries and the printed nonstarting-player entry/counter/hand-exile family have durable human/AI choices and HTTP/SQLite restoration. Counter-dependent land mana outputs are shared by payment, manual actions, AI battlefield estimates and views; land piles expose actual choices and amounts. Full arbitrary pregame semantics, entry choices/reveal/mulligan-time effects, restricted/dynamic land mana and strategic entry/exile planning remain open. See [coverage](docs/testing/opening-hand-actions.md).

Latest performance/repeatability verification: 1,757 isolated backend tests, frontend lint/build/contracts and full Chromium pass. Eight seeded, seat-paired BO1 games have identical complete optimization-enabled/disabled traces, no timeout and no logged cost/target rejection. Three Ramp/Tokens repeats retain identical token identities. The prior pregame milestone's six-series/13-game replay remains historical evidence. These samples are not AI-strength or balance certification. See [scope, benchmark and drift fix](docs/testing/ai-projection-performance.md).

Card-copy latency follow-up: profiling 1,108 decisions in two seed-111 Control/Ramp games identified card reconstruction as the dominant remaining planning-copy cost. Exact-card scalar fast copying still deep-copies every mutable field and preserves aliases/cycles. Five slow snapshots have identical full decisions and 17.3–34.2% shorter paired medians. The CLI supports copy-only ablation and opponent-archetype provenance; a new private-data-free match profiler reports percentile timings and configurable diagnostic exceedances without a gameplay time cutoff. Verification: 1,765 isolated backend tests, frontend lint/build/unit and full Chromium pass; eight archetype game results and two profiled Control/Ramp hashes match baseline. See [measurement scope](docs/testing/ai-card-copy-latency.md).

- [x] Profile repeated announced-stack projections, reuse immutable root results within one decision and omit historical diagnostics from planning copies. Preserve full action/reasoning and gameplay-state equality in ablations; do not shorten search or matches. The measured dense removal fixture is approximately 29.5% faster, not a worst-case latency guarantee.
- [x] Fix reproduced seeded token-identity drift: persist a shared gameplay-object sequence independent of shuffle RNG and retain those identities in replay comparisons. Old random-ID snapshot executions cannot recover their previous historical tie ordering.
- [ ] Investigate the separate timeout-diagnostic interpreter crash. One diagnostics-enabled full run segfaulted while dumping a timeout stack; fresh uninstrumented suites pass, but neither this optimization nor the stable-ID fix establishes its cause.
- [x] Profile representative Control/Ramp decisions, compare full snapshots/actions under copy-only ablation, and introduce an explicit one-second diagnostic decision target without reducing search quality. Current samples are not a release-wide responsiveness guarantee.
- [ ] Extend latency samples across more seeds/complex states, define a corpus-wide release budget, and measure end-to-end API/serialization and long-session tails.
- [x] Remove name-derived role shortcuts from ranking, rollout, counter recognition, opening-hand, closure/threat evaluation, burn estimates and deck classification. Canonical fixtures and all eleven built-in label-change analyses cover the bounded invariants; flat/nested faces share analysis and land-only faces do not create acceleration packages. Historical per-card priors and display/tie identity remain intentional. See [scope](docs/testing/ai-oracle-semantics.md).
- [ ] Expand equivalent-card/face decision-quality fixtures and measure archetype-profile accuracy on verified custom/tournament decks. Relative heuristic confidence, mixed strategies and broad conditional/variable mechanics are not certified by the name-shortcut cleanup.

Oracle-grounded AI verification: 1,787 isolated backend tests, frontend lint/build/unit and the final full Chromium rerun pass. Eight seat-paired logical games repeat across sixteen executions with identical complete identity-sensitive results, no timeout and no logged cost/target rejection. Both LAN services respond. All eleven built-in deck analyses are label-invariant in tests; role-density weights and mixed/custom-deck strategy remain heuristics, not calibrated expertise. See [scope and evidence](docs/testing/ai-oracle-semantics.md).

Counter-resource AI follow-up: a sole opposing creature spell with low stack-threat score no longer automatically consumes a pure counterspell, and the AI does not double-counter a spell while its own counter is already the top stack item. Another uncovered opposing spell remains answerable, as do a high-threat planeswalker and an opposing counter response. Focused legal-state tests cover these lines; a Blue Control/Ramp seed no longer countered Arboreal Grazer or stacked two counters on Go for the Throat. Verification: 1,519 isolated backend tests, frontend lint/build/unit, a three-game BO3 replay with zero determinism failures or anomaly labels, and a full Chromium rerun. One preceding Chromium attempt intermittently lost a fetch during match-start recovery, then passed unchanged on retry; browser harness stability remains worth monitoring. The seed still lost to an established Nissa board; further work is needed on context-dependent counter timing, removal prioritization and planner horizon before claiming seasoned control play.

X-sweeper AI follow-up: variable all-creature debuffs now score X against effective toughness and creature threat rather than raw mana availability. Casts with no opposing creature removable at the affordable X are withheld even when anti-stall conversion would force another proactive action. Focused tests cover spell-tax payment, holding against an unaffordable large threat, casting efficiently at X=6 once affordable, and repeated passes; a Blue Control/Ramp seed that previously cast into an empty board waited for an opposing creature. Verification: 1,517 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a three-game BO3 replay with zero determinism failures. The seed still lost, so this fixes a specific decision error rather than establishing strong control play. Remaining AI work includes sweep timing against mixed boards, opponent counterplay, persisted knowledge-score consumers, and seed/seat-balanced strategic evaluation.

Offline tactical-tag backfill: the bulk-knowledge CLI now has `--backfill-tags`, deriving tags from each row's stored canonical payload without downloading Scryfall data. It preserves rulings/provenance and existing tactical scores, skips rows lacking canonical data, reports changed/unchanged counts, and rejects a nonexistent `--database` path rather than creating an empty file. The summary has a separate default output. Verification: 1,515 isolated backend tests and frontend lint/build/unit passed; an isolated full-database rehearsal and the backed-up live migration each updated all 38,690 rows, while a repeat updated zero. The live database has 3,214 per-face tag arrays, retained 87 verified-rulings flags and 112 gameplay-cache rows, and passes SQLite integrity. The ignored backup is `backend/knowledge/data/pre-tag-backfill-20260930-031904.sqlite3`. This closes the local data migration, not persisted-profile AI consumption or strategic quality.

Tactical-tag follow-up: AI role tagging now derives from printed Oracle text and card types, not names. The same pure derivation populates tags in per-card and bulk Scryfall knowledge profiles, with per-face tags for multiface cards and offline backfill for old verified cached rows. Canonical real-card regressions cover burn, ramp including Nissa, sweep, Memory Deluge card selection and face-specific removal, while an empty-Oracle card named Lightning Bolt no longer scores as burn. Verification: 1,513 isolated backend tests, frontend lint/build/unit, full Chromium harness, two seeded Blue Control/Ramp games (one win each, no timeout or invalid-action log), and one three-game BO3 replay with no determinism drift. The local Scryfall bulk file populated tactical tags for 38,690 Oracle rows and per-face tags for 3,214 multiface rows in an isolated SQLite database; a repeat import left all 38,690 unchanged, with rulings correctly pending. Memory Deluge was absent from Blue's hand in the first traced game and cast in the second; this is not a strategic-quality verdict. AI still does not consume persisted play-value/threat scores; decision-trace A/B testing and verified profile consumers remain open.

Library-search entry follow-up: search effects that put multiple selected cards directly onto the battlefield now move the complete selected group before collecting their entry triggers. A grouped "one or more" Zombie entry test previously produced two triggers and now produces one, while an individual-entry watcher still produces two. Split battlefield/hand search stays a single-entry path. Verification: 1,510 isolated backend tests, frontend lint/build/unit, the full Chromium harness including the library-search UI path and natural BO3 flows, and a seeded two-game BO3 replay with no timeout or determinism drift passed. This smoke sample does not establish broad AI quality or rules fidelity. Other simultaneous movement sources and affected-player entry-replacement ordering remain open.

Simultaneous-entry follow-up: multi-token creation and both supported topdeck multi-permanent placement handlers now place the whole group before collecting entry triggers. Supported "one or more" entry clauses produce one trigger for the group; ordinary per-entrant clauses still produce one per qualifying entrant. Human choices of attacking-token defenders are collected before any member of the token group enters and survive snapshot restore. Focused regressions cover both trigger kinds, both topdeck paths and separate attack targets. Verification: 1,509 isolated backend tests, frontend lint/build/unit, the full Chromium harness including natural AI/human BO3 flows, and a seeded two-game BO3 replay with no timeout or determinism drift passed. Two games do not establish matchup balance. Other effects that put several objects onto the battlefield, entry replacements and arbitrary grouped-trigger wording remain open.

Tribal entry-and-activation milestone: generic "one or more other [subtype] you control enter" wording now matches qualifying entrants, including both common Oracle clause orders. Once-per-turn bookkeeping records an actual trigger rather than any observed event, remains spent if the stack object is countered, survives snapshots, and resets with the turn or a new battlefield incarnation. Inferred creature tokens retain subtype metadata; supported activated subtype-wide P/T and keyword bonuses apply to the matching creatures controlled at resolution, not later arrivals. Static subtype anthems use the same plural-to-singular matching. Real Elvish Warmaster and synthetic Zombie regressions cover these boundaries. Verification: 1,505 isolated backend tests, frontend lint/build/unit, full Chromium harness, three Tribal/Midrange and three Tribal/Ramp seeded games without timeout or logged rule errors, and a two-game BO3 replay with no determinism drift. Warmaster triggered three times and AI paid its subtype bonus once in the Tribal/Ramp set; these small samples do not establish matchup balance or strong strategy. The earlier milestone left simultaneous-entry batching open; the bounded token/topdeck follow-up above addresses those paths only. Changed creature types, other subtype grammars and arbitrary trigger clauses remain open; [Kaldheim release notes](https://magic.wizards.com/en/news/feature/kaldheim-release-notes-2021-01-22) document the specific Warmaster rulings.

End-step attack-reward milestone: the supported Oracle clause pattern adding counters, choosing a draw versus a creature token based on the number of creatures actually declared as attackers that turn, and transforming on a counter threshold now uses a responseable trigger and shared draw/token/transform handlers. Per-player declaration history survives snapshots and resets each turn. Real Wedding Announcement regressions cover attackers leaving, tokens entering attacking, no-attack token production, delayed transform and source re-entry. Verification: 1,496 isolated backend tests, frontend lint/build/unit, full Chromium harness, a seeded two-game BO3 replay with zero drift, and one White Weenie/Blue Control AI game in which the end-step trigger drew a card. One game does not establish AI skill or matchup balance; arbitrary conditional end-step clauses remain open.

Live-route follow-up: a bundled-corpus Wedding Announcement deck starts by names and quantities through HTTP; two creatures attack through the action API, the match is persisted and restored from SQLite, and two priority passes resolve the end-step draw with its invitation counter visible in the public card view. A fresh isolated backend suite passes 1,497 tests. This closes that card's specific live/diagnostic parity gap, not the unchecked shared-fixtures gate for the full supported corpus.

Attacking-token defender milestone: the supported tapped-and-attacking token effect now pauses for each token when player/planeswalker defenders are available, validates the chosen defender, and resumes across snapshots. AI selects a vulnerable planeswalker over nonlethal face damage. Adeline, stale-choice, multi-token and frozen-count regressions cover this bounded path. Verification: 1,490 isolated backend tests, frontend lint/build/unit, full browser harness including the human defender control, a seeded nine-turn White Weenie/Blue Control AI game and a two-game replay with zero determinism drift. The first browser run hit a preflight-only failure in the older lost-response test; warming the preflight with a rejected action made the complete rerun pass. Full AI combat targeting and arbitrary attack-token Oracle wording remain open.

Attack-group milestone: supported "whenever you attack" triggers now fire once per declared group; tapped-and-attacking tokens enter combat without declaration triggers, and creature-count power follows battlefield changes. Real Adeline regressions cover two attackers, non-attacking source, empty attack, snapshot, token entry and combat damage. Verification: 1,485 isolated backend tests, frontend lint/build/unit, full browser harness and a seeded two-game BO3 replay with zero determinism failures or drift labels. A recovery-fixture failure was traced to response-stage interception using `Fetch.continueRequest`; switching to `Fetch.continueResponse` made the full rerun pass. The UI/engine still defaults tokens to the defending player when a planeswalker choice exists; that human/AI target selection and other attack-group Oracle forms remain open.

Training milestone: Hopeful Initiate's keyword now checks the simultaneously declared attacking group, stacks one +1/+1 counter trigger, and retains the source incarnation across snapshot/resolution. Equal-power, solo-attacker and leave/re-entry cases have focused regressions. Verification: 1,482 isolated backend tests, frontend lint/build/unit, full browser harness and a seeded two-game replay with no determinism drift. Other keyword triggers and arbitrary Oracle attack clauses remain open.

Latest strict AI simulation increment: speculative search and ranking rollouts request the engine's rejecting mode on cloned states, so supported invalid cost and target branches are not scored as successful actions. A real unpayable Counterspell fixture fails on the prior planner and passes here. Verification: 1,467 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded two-game replay with zero determinism failures or drift labels. The engine still has some silent early-return paths, so this does not prove complete invalid-action detection or optimal decision-making.

Latest AI reply-shortlist correction: the six-reply strategic beam and eight-reply ranking rollout now use shallow move scoring before capping, instead of the first moves in lexicographic order. A guard prevents the shallow pass from recursively launching another rollout. Verification: 1,466 isolated backend tests, frontend lint/build/unit, full solo Chromium harness, and seeded two-game replay with zero determinism failures or drift labels. A paired Blue Control/Ramp API BO3 took 139 seconds with the shortlist versus 135 seconds on the prior planner; one run does not establish stable throughput. The ranking still uses heuristic archetype preferences, can omit the actual best reply, and does not model hidden information fairly; Gate 2 decision-quality acceptance remains open.

Latest AI ranking-rollout correction: both candidate and opponent-reply branches materialize targets before simulation, instead of silently scoring targeted moves as no-ops. Focused regressions pass. Verification: 1,463 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded BO3 replay with zero determinism failures or drift labels. The capped reply list and hidden-information estimates remain open, so this does not establish optimal or fair opponent modeling.

Latest AI tactical-search correction: the bounded lookahead now picks the minimizing opponent reply after sorting, rather than an optimistic reply, and materializes targets before simulating each reply. Deterministic own-turn/opponent-turn and targeted-action regressions pass. Verification: 1,461 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded BO3 replay with zero determinism failures or drift labels. The six-action beam remains ordered by deterministic move key, not exhaustive opponent strategy, so this does not establish seasoned-player play or close Gate 2 AI measurement.

Latest sacrifice team-counter increment: supported "Whenever a player sacrifices another permanent, put a +1/+1 counter on each creature you control" now triggers for either player, excludes the source's own sacrifice, and counts creatures controlled when the trigger resolves. Real Mazirek fixtures cover a departed watcher in a simultaneous sacrifice, snapshot restore and a changing battlefield. The reusable effect handler is not card-name-specific. [Wizards' rules update](https://magic.wizards.com/en/news/announcements/secrets-of-strixhaven-update-bulletin) explicitly cites Mazirek as a sacrifice look-back case. Verification: 1,458 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded BO3 replay with zero determinism failures or drift labels. Broader counter clauses, affected-player choices and arbitrary Oracle interpretation remain open.

Latest targeted sacrifice-drain increment: supported "Whenever you sacrifice a permanent, target opponent loses N life and you gain M life" now resolves both life changes as one targeted trigger. The target selector restricts opponents, filters hexproof/shroud, pauses for a human choice, and fizzles both changes if the target becomes illegal. Real Popular Egotist, Llanowar Elves and Leyline of Sanctity fixtures cover ordinary and self-sacrifice, snapshot restore and late hexproof. This is generic clause handling for supported sacrifice events, not a card-name exception. Verification: 1,453 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and a seeded BO3 replay with zero determinism failures or drift labels. Other sacrifice effects, multiple-player targets and wider Oracle semantics remain open.

Latest sacrifice look-back increment: `sacrifice` events now inspect departed watchers using the same last-battlefield snapshot path as creature/permanent death events. Real Mayhem Devil and Rest in Peace fixtures cover the sacrificed watcher triggering from graveyard or replacement exile, human target selection after snapshot restore, and one trigger per simultaneous Annihilator sacrifice. This follows [Comprehensive Rules 603.10a](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). Verification: 1,448 isolated backend tests, frontend lint/build/unit, a full solo Chromium harness and seeded BO3 replay with zero determinism failures or drift labels. A concurrent browser/full-suite run timed out during match creation recovery, while a no-competing-load rerun passed; load behavior remains unverified. Remaining: wider sacrifice trigger wording, affected-player replacement choices, and arbitrary-card certification.

Latest simultaneous-death trigger increment: `creature_dies` batches now inspect all departing sources through their last-known battlefield state, including sources that die alongside other creatures. The prior isolated self-death path was folded into the shared watcher scan to prevent duplicate triggers while retaining effective last-known power. Generic "another nontoken creature dies" matching excludes self and tokens. Blood Artist, Pitiless Plunderer, Harvester of Souls, Rest in Peace, wipe, state-based lethal, APNAP, and snapshot regressions cover this bounded 603.10a behavior. Verification: 1,444 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a seeded BO3 replay with zero determinism failures or drift labels. Remaining: broader leaves/sacrifice look-back cases, competing replacements, and arbitrary Oracle clauses.

Previous named-self death-trigger increment: supported "[printed name] or another creature dies" clauses recognize the dying source or a separate creature. Targeted player-life drain uses a legal stack-entry choice, AI opponent preference, snapshot-safe human selection and resolution-time target recheck, so an illegal target prevents both life changes. Real Blood Artist, Llanowar Elves and Leyline of Sanctity fixtures cover these paths. Verification: 1,437 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded BO3 replay with zero determinism failures or drift labels. Other named-reference wording and broader target/replacement interactions remain open.

Latest activated-cost event increment: sacrificed permanents now emit staged leave, sacrifice and actual-graveyard death events, preserving triggered-ability ordering above the activation and suppressing death triggers after replacement exile. A generic supported creature-death drain clause now applies both life changes. Real Fanatical Firebrand, Mayhem Devil, Bastion of Remembrance and Rest in Peace fixtures cover stack order, human ordering, life totals and snapshot restoration. Verification: 1,432 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded BO3 replay with zero determinism failures or drift labels. Remaining: broader sacrifice-cost selection, multiple competing replacements, trigger wording and arbitrary-card certification.

Previous damage-source last-known-information increment: departure snapshots now retain effective keywords, colors and controller on pending abilities. Supported damage and single-target activated-ability rechecks use them for lifelink, infect, wither and protection even after the card returns as a new object; self-sacrifice costs capture before removal. Real Prodigal Pyromancer, Fanatical Firebrand and Crypt Rats tests cover departure, live keyword changes, controller/color changes, snapshots and batch life gain. Verification: 1,429 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded BO3 replay with zero determinism failures or drift labels. Source-dependent replacement/prevention wording beyond the tested keywords and general last-known-information rules remain open.

Latest divided-damage increment: Pyrotechnics-style allocated damage now reuses the all-recipient batch resolver. The printed allocation stays fixed when a target becomes illegal; damage retains its source, defers lethal checks across targets, aggregates one post-prevention lifelink gain, and carries a human replacement choice through snapshots. Focused real-card regressions cover these boundaries. Verification: 1,421 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded BO3 replay with zero determinism failures or drift labels. Wider damage-event ordering, unusual prevention combinations and source last-known information remain open.

Latest noncombat-lifelink increment: single-target noncombat damage uses post-prevention damage for the source's life gain. The supported Crypt Rats-style all-recipient event aggregates one gain per source, carries its total through human replacement choices and snapshots, and applies gain replacements before lethal state-based actions. Focused real-card regressions cover prevention, one gain trigger, self-lethal survival and gain-replacement continuation. Verification: 1,418 isolated backend tests, frontend lint/build/unit, full Chromium harness, and one seeded BO3 replay with zero determinism failures or drift labels. Distributed-damage and arbitrary all-recipient effects, last-known source characteristics, and wider simultaneous replacement ordering remain open.

Latest restricted-X payment and simultaneous-damage increment: the shared mana planner enforces printed "spend only [color] mana on X" for activated costs without restricting fixed generic mana. Crypt Rats-style X damage snapshots every creature and player, defers lethal state-based actions until the batch ends, and preserves human damage-replacement choices through serialized continuations. AI X materialization uses the payable color and declines self-lethal or nonpositive nonlethal activations. Focused tests cover mixed pool/source payments, wrong-color HTTP rejection, simultaneous double loss, protection, snapshot replacement order, and tactical choices. Verification: 1,413 isolated backend tests, frontend lint/build/unit, full Chromium harness and three best-of-three replay matches (six games) with zero timeouts or determinism failures. Other all-recipient wording, granted noncombat lifelink and unusual replacement combinations are not certified.

Prior variable-activation and linked-copy increment: unrestricted activated {X} mana costs now use the same announced value for generation, checked legality, payment, stack effects, AI materialization and user controls. Supported "choose a creature card exiled with this permanent with mana value X ... becomes a copy" wording offers a resolution-time choice, applies printed front-face characteristics, keeps the source's battlefield identity and restores its printed values on departure. Real Valki/Elvish Mystic tests cover unaffordable/missing X, AI matching a linked card's mana value, stacked activations, stale exile, snapshot persistence and browser UI/API activation. Unsupported/no-op activations are withheld before costs; self +1/+1 counter clauses resolve, and move enumeration cannot log failed Oracle inference. At that milestone, printed color-restricted X payment was withheld using a real Crypt Rats regression rather than paid with arbitrary colored mana; the newer increment above implements this bounded payment rule. Verification at the prior milestone: 1,406 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift. Full copy-layer/dependency, characteristic-defining and cross-effect interaction certification remains open.

Prior linked-hand-exile increment: the shared 610.3 link records the exiled object's previous zone. Supported two-player reveal-and-exile-from-hand ETB wording now offers the existing human/AI choice and returns the chosen creature card to its owner's hand when that source incarnation leaves. If it left before resolution, the hand is revealed but no card moves. Real Valki front-face, snapshot, old-incarnation, AI and HTTP tests cover the bounded trigger. Verification at that milestone: 1,399 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift or anomalies. Broader linked-exile wording and hidden-zone identity remain open.

Latest type-line follow-up: modal face selection and the shipped-corpus auditor now use one front-face printed-card-type parser, including Battle and Kindred and excluding supertypes, subtypes and back-face types. Scryfall-backed Kindred Sorcery and Sorcery // Land type-line fixtures pass; the empty-cache corpus report still covers 112 names with zero parser-fallback/missing-Oracle classifications. Verification: 1,392 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift or anomalies. This alignment does not certify the report's structured-effect classifications.

Latest linked-exile increment: Temporary Lockdown-style ETB wording now creates a persisted source-incarnation link to exiled nontokens, returns them under their owners when the source leaves, and does not exile when the source leaves before trigger resolution. Focused tests cover normal casting, snapshot restore, bounce/reentry, state-based death, simultaneous sources and between-clause return. The distinct-type reveal matcher now includes the current Kindred card type. An empty-cache shipped-corpus report finds 112 names and zero missing-Oracle/parser-fallback classifications. Verification: 1,391 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift or timeout. Other linked-exile wordings, object-identity paths, replacement interactions and structured-but-wrong effects remain open; parser classification is not rules certification.

Prior distinct-type reveal increment: an Atraxa-style ETB now reveals at resolution, pauses for a human/AI up-to-one-per-card-type selection, validates a distinct type assignment for multi-type cards, and bottoms the rest in persisted random order. Zero selections still resolve the mandatory reveal; abbreviated legendary self-entry names trigger only for their own entry.

Latest topdeck-land increment: printed "look at the top N ... put up to M land cards ... onto the battlefield tapped" now uses the existing human/AI resolution-time choice, land-entry and persisted random-bottom machinery. A shipped Cartographer's Survey fixture covers land filtering, selected tapped entries, snapshot continuation and AI choice. The empty-cache report still has five parser-fallback copies from Atraxa and Temporary Lockdown; neither their semantics nor broad card correctness is closed.

Latest bounded rules increment: ETB clauses matching "creatures you control get N/M and gain a supported keyword until end of turn" now resolve as snapshot team effects instead of parser fallbacks, and static anthem detection excludes triggered/temporary clauses. A shipped Imodane's Recruiter fixture covers resolution, snapshot restore, opposing creatures, late entrants and cleanup. The empty-cache report still flags six copies across Atraxa, Temporary Lockdown and Cartographer's Survey. This does not establish complete Adventure, layer or arbitrary duration semantics; those fallbacks and other semantic gaps stay open.

Latest implementation reconciliation: validation `01a0235`, recovery `a17712f`, subsequent BO3 browser work, and the permanent-spell context milestone described below. The [two-stage Jev review](docs/audits/2026-09-27-jev-two-stage-review.md) evaluates the older `f760c98` snapshot, not this latest implementation. Its typed judgments evaluate supplied evidence and proposed remedies; they are not application fixes or current release certification. The separate bounded [validation review](docs/audits/2026-09-27-api-validation-jev.md) records one authorized current-source call; no further calls were needed for the spell-context repair.

Latest AI/rules sequencing check: untap now auto-advances to upkeep without a priority window, while pending choices remain available. AI defers optional cycling in its own empty-stack upkeep/draw so it can use main-phase land drops and sorceries first. A fixed-seed Tokens/Ramp replay observed Ramp cast The Meathook Massacre for X=2 at turn eight rather than cycle away its black mana. Verification: 1,370 isolated backend tests, frontend lint/build/unit, full Chromium harness, a two-game deterministic replay with zero reported drift, and four seeded Tokens/Ramp games from both seat orders finished without timeout or obvious cost/target errors. Tokens won all four; this is too small and one-sided a sample to establish balance. Broader sweep timing, planning and matchup calibration remain open.

Offline shipped-corpus follow-up: the tracked canonical seed now contains 119 cards, covering all 112 distinct shipped deck names and existing extras without a developer-only cache. The read-only exporter uses validated local Scryfall bulk records for uncached cards and retains Adventure faces. An empty-cache corpus report has zero missing Oracle records, but seven copies across Atraxa, Grand Unifier; Temporary Lockdown; Cartographer's Survey; and Imodane's Recruiter remain parser fallbacks. Verification: 1,372 isolated backend tests, frontend lint/build/unit, full Chromium harness and a two-game replay with zero reported drift pass. This is metadata completeness, not supported-corpus rules certification; those printed effects and other structured-but-incorrect classifications still need golden acceptance.

Follow-up rules check from the same trace: the real Meathook ETB had been misread as an unrelated life-gain line. The shared parser now handles “each creature gets -X/-X,” isolates one printed entering ability, and evaluates own/opponent creature-death clauses independently. A real-card cast/snapshot fixture checks X, state-based deaths and both life triggers; a repeated seed now logs the debuff and small-creature deaths. Verification: 1,371 isolated backend tests, frontend lint/build/unit, full Chromium harness, a two-game deterministic replay with zero reported drift, and four seeded Tokens/Ramp games without timeout or obvious target/cost errors. Tokens won all four, which is not a balance verdict. Broader multi-line trigger, layer and replacement fidelity remains open.

## Review reconciliation and next execution order

- **Draw/cleanup: core paths repaired.** Turn draws use the shared replacement-aware handler. Cleanup now has persisted human discard choices, ownership-correct shared discard events, discard-before-expiration ordering, deferred APNAP triggers, state-based checks and repeated cleanup. The GUI exposes draw/sacrifice/cleanup choices. Multiple interacting replacements, discard-replacement families and full browser/process-restart acceptance remain open.
- **Knowledge/AI: partially addressed.** `babef27` implements canonical all-card/corpus ingestion and rulings verification. Typed production AI consumers, offline supported-corpus certification and decision-quality evidence remain open.
- **Offline bulk-to-gameplay bridge added.** Exact canonical names from the local Scryfall bulk knowledge table now feed deck parsing, import metadata and live match hydration through lazy materialization of missing cache records. Existing cached printings are retained. Face data and front-face colors are retained without a per-card network fetch. This does not certify Oracle behavior, verified rulings, or local image availability; those remain corpus gates.
- **Documentation: maintained, not reopened.** The finish-plan rewrite was already completed. Keep new evidence and limitations linked without presenting documentation as gameplay acceptance.
- **Local-beta repairs underway:** tracked offline fallback, shared live face hydration, effective public views, acting-seat controls and strict request validation are implemented with regressions. Focused Chromium action paths and scripted human-vs-AI/human-vs-human BO3s pass against a noncompetitive opponent; broader human-game acceptance remains separate. Conventional permanent spells no longer execute later abilities. Modal face costs/timing, land-face plays, Adventure exile permissions, supported ETB/self-cast target choices and divided-damage recipient legality have bounded coverage. Textual multi-mode effects compile each selected clause separately. Cryptic Command counter/draw and counter/return have cast-and-resolution coverage; the latter supports partial resolution when a distinct stack or permanent target becomes illegal, including after snapshot restore. Kolaghan's Command destroy/damage now covers two same-kind permanent targets, and its graveyard return uses the announced own-card target. The UI and AI select per-mode targets. Multiple targets within one mode, broader non-damage multi-target resolution, broader face semantics and full face-specific restart acceptance remain open. Interactive BO3 now has bounded seed/play-draw tests and narrow AI sideboarding; broader matchup plans remain open.
- **Recovery implemented with bounded acceptance:** saved-match restore, serialized/versioned/idempotent guarded mutations, refresh, lost-response reconciliation and test-backend process restart have regression/browser coverage. Match creation now has durable same-key recovery, including lost-success-response retry and reload coverage. Extended soak remains open. A local self-signed HTTPS proxy smoke covers same-origin and configured cross-origin built artifacts in Chromium; a real LAN/trusted-certificate deployment remains untested. Access/origin controls, bounded jobs and multiworker coordination are still network release gates. Refresh advisories before choosing dependency upgrades.
- **Simulator strength remains unverified.** The latest two-game BO3 smoke shows repeatability only; it does not measure broad balance or seasoned-player quality.
- **Both advertised human BO3 modes are browser-covered against one bounded opponent.** Scripted humans use production controls to complete Mono Red Aggro versus 60-Island AI and human-seat series, including mulligan, land, cast, combat, priority, trigger order and between-game transition. This opponent is intentionally noncompetitive; the tests do not close sideboarding strategy or broad matchup quality.
- **Combat phase handoff, first-strike windows and ordinary multi-combatant damage choices repaired in supported cases.** Human controllers now assign numeric damage to multiple blockers or attackers before it is dealt; choices are persisted and exposed through HTTP/UI. Trample validation includes another attacker's simultaneous assignment, with restart and AI support. Ordinary banding damage-choice ownership, attacking-band declaration, snapshot persistence and block propagation are supported; "bands with other" and simultaneous replacement interactions remain open.

First-strike timing follows [Wizards' Comprehensive Rules 510.4](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). Local verification for this increment: 951 backend tests pass in an isolated source/database copy; frontend lint, build and unit checks pass; the complete Chromium harness passes, including first/regular damage UI windows and both human BO3 modes. Hosted CI is pending.
- **Simple alternative targets and Oracle ordering repaired.** Single player-or-permanent target clauses admit one legal candidate, the human UI offers one combined selector, planeswalker damage reduces loyalty, and turn restrictions execute in printed clause order. More complex target grammars and replacement/layer interactions remain open.
- **Token-art network stall removed from game actions.** Token creation reads a persisted local art index or immediately uses shipped fallback art. An explicit CLI sync fetches and stores art for later games; unsynced tokens remain generic, and art-cache lifecycle/automated prefetch is still an operational follow-up.
- **Import analysis corrected:** curve buckets now come from cached mana costs (including front-face modal costs), with separate land/unknown counts; spell-color counts come from cached colors, and archetype analysis sees resolved metadata. These are not mana-source quality or AI-strength metrics. Full-deck strategy and mana-base validation remain open.
- **AI hand exposure closed for local play:** public match responses redact AI-controlled hands but preserve counts, and legal-move queries cannot expose AI card views. Human-vs-human remains a shared-device sandbox without per-seat authorization; separate-client hidden-information privacy is not implemented.
- **Land classification tightened:** game-state inference, rules legality, AI hand evaluation and deck-analysis land counts now use explicit front-face land types/type lines, with exact basic-name fallback for missing metadata. Mana production, Oracle text mentioning lands and land-name substrings cannot turn a nonland into a land. AI land priority selects only offered legal moves; missing nonbasic type metadata is a hydration/data issue, not permission to fabricate a play. Regression fixtures cover mana creatures, nonland card names containing a basic-land word, modal back-face lands, exact basics and malformed AI card IDs.
- **Deck-shape estimates aligned with layout:** cached modal/transform cards use front-face cost and creature type for archetype priors rather than treating every `//` name as split; back-face Land does not remove a cheap front spell. Canonical Valki, Delver and Bala Ged fixtures cover this boundary. Mana-base quality and strategic archetype inference remain open.
- **Replay attribution tightened:** a BO3 timeout is now classified from the timed-out game's log, not resolved games' errors. One fixed-seed Tempo/Dimir game reached turn 44 at the smoke test's 1,200-tick cap, but resolved on turn 65 at 1,836 ticks with a 3,000-tick cap. Its lone own-main pass with an actionable spell was not evidence of a stall. Repeated missed legal land drops across distinct turns remain a conservative `likely_stall` signal; statistical and full-game AI quality work stays open.

Verification for the land/diagnostics increment: 929 backend tests passed in an isolated source/database copy, including replacement of the obsolete fabricated-land and name-overrides-type expectations. The production-route browser harness passed all existing action, recovery and sideboard paths. A seeded Tempo/Dimir BO3 had zero replay drift; its 1,200-tick timeout was reported as `timeout_long_game` with one counted anomaly, while the timed-out first game resolved at 1,836 ticks under a 3,000-tick cap. This is not a broad matchup-strength or arbitrary-card rules certificate.
- **Live-game rules evidence:** a local-Oracle Ramp versus White Weenie scripted-human/AI API best-of-three completed through 200 HTTP calls (0-2, seed 19) with no rejected actions after the diagnostic translated display hints into typed requests. Its saved log has zero `not inferred` or missing-handler lines after the Recruitment Officer fix. This is not a browser game or balance estimate.

Next: broaden target legality beyond simple alternatives and divided damage, then competitive-opponent/full-game coverage, deeper sideboard strategy and frontend contracts, maintaining draw/replacement acceptance alongside changes. Keep network release gates mandatory before wider exposure; continue supported-corpus AI work after local correctness. All acceptance checkboxes below remain evidence-based.

Latest divided-damage checks: 871 backend tests pass in a fresh isolated source/database copy (103.37 seconds, 798 deprecation warnings); frontend production build and unit checks pass. A seeded Mono Red Aggro/Dimir Control BO3 completes two games in 36 turns with no timeout, anomaly label or determinism drift. The previous cast-trigger milestone passed thirteen human-action browser scenarios; this backend-only increment did not rerun those paths. These are bounded regression checks, not balance or expert-AI certification. Earlier full-App recovery checks cover refresh, lost response and test-backend process restart, not a complete game or production deployment.

## Release scope and status

First finish a reliable local desktop application for an explicitly supported card corpus. Arbitrary-card rules completeness and seasoned-player AI across every deck require additional acceptance criteria and remain longer-term goals.

The frontend compiles and the backend has substantial regression coverage. Human playtesting is not release-ready: general trigger target/mode windows, non-damage multi-target resolution, broader conditional entry and competitive-opponent BO3 acceptance remain unfinished. Scripted human-vs-AI and human-vs-human browser BO3s now complete against an all-Island opponent. Bounded ETB/self-cast target windows, divided-damage legality and interactive BO3 seed/play-draw policy are implemented. Acting-seat controls, checked requests, canonical modal spell/land choices, Adventure exile permissions, responseable crew activation and saved-match recovery are implemented. Live hydration shares the face-aware helper, public views carry effective stats/faces, and hover shows base stats, damage, keywords and counters. Turn draws and cleanup discards share event-aware paths; cleanup choices are exposed in the GUI.

This plan supersedes the July status paragraphs and patch history previously stored here. Historical changes remain in `CHANGELOG.md`. The September audit is stored in [docs/audits/2026-09-27-app-audit.md](docs/audits/2026-09-27-app-audit.md). Its detailed evidence and reproduction artifacts are local at `/home/nick/.hermes/cache/scratch/mtg-audit-6b95fab/`; those artifacts are not portable repository fixtures.

## Evidence baseline

These are results reported by the supplied September audit, not checks rerun by the documentation update:

- Frontend `npm run build`: passed, including the configured TypeScript gate. TypeScript strict mode is already enabled.
- Tracked-source disposable checkout: backend suite had **718 passed, 2 failed**, 154 warnings. Both failures required an ignored generic token SVG. Copying the developer asset into scratch made the two focused tests pass; the full suite was not rerun after that copy.
- The pinned Python venv passed `pip check`. The obsolete TestClient incompatibility/stall did not reproduce. API tests must no longer be excluded on that historical basis.
- Frontend lint and test commands are absent. No tracked frontend CI workflow was found.
- Registry audit reported 7 vulnerable frontend packages: 4 high, 2 moderate, 1 low. Review current advisories before choosing upgrades; these counts do not establish shipped-bundle exploitability.
- One seeded Mono Red Aggro vs Dimir Control BO3 completed two logical games, 2-0, 30 total turns, without timeout or deterministic drift. This does not establish balance or optimal decisions.
- Runtime probes reproduced lost faces, base/effective stat disagreement, draw/cleanup event inconsistencies, malformed-request 500s, and the game-two starting-player issue. Render probes reproduced missing human-seat/action controls; browser E2E was not performed.
- No fresh dependency install, live LAN/HTTPS deployment, large matchup matrix, concurrency stress test, full Scryfall sync, or long-session browser test was performed.

Past zero-parser-fallback counts describe parser classification only. They are not current cache facts or proof that every effect clause is implemented correctly. Knowledge storage exists, but AI consumption and the broader knowledge plan remain unfinished.

## Working rules

- Keep rules, effects, legality, timing and AI in application code. SQL stores data only.
- Use canonical card data with provenance. Do not invent cards, text or stats to improve a matchup.
- Fix reusable mechanics and integration boundaries rather than one named-card exception.
- Read Graphify before source navigation; refresh it after code changes. Check graph freshness against the implementation revision.
- Preserve unrelated local files, databases and cache. Run database-writing release tests in a disposable tracked-source checkout, not merely a different working directory.
- Each completed task needs focused regression evidence, relevant integration coverage, documentation updates and a recorded revision. Leave checkboxes open until acceptance is demonstrated.
- Win rates are observations, not fixed targets. Never force all matchups into 65-70% bounds; report sample size, seats, seeds and confidence intervals.
- The token-compression experiment is not a dependency or a planned feature.

## Gate 1: Reliable local human-playtesting beta

Complete these steps in order. Steps 1-5 close the highest-impact reproduced failures before deeper AI work.

### 1. Make clean checkout assets reproducible (P1)

- [x] Ship or deterministically generate the generic token fallback outside the disposable image cache.
- [x] Serve offline card/token placeholders through the intended media contract.
- [x] Test release-candidate source with empty database/cache and declared dependencies; do not copy ignored developer assets.

Evidence: 758 backend tests pass after installing `requirements.txt` into a new venv and copying source without databases/image cache (159.21 seconds, 173 deprecation warnings). Generic-art HTTP and empty-cache/offline resolver tests pass using the tracked asset. Frontend production build passes. The final Git-archive/CI gate remains to be established under step 9; this test did not borrow ignored image files or the developer database.

Acceptance: full backend suite passes in a clean checkout; generic token media returns 200 without a pre-existing cache.

### 2. Unify live and diagnostic hydration (P1)

- [x] Use one hydration contract for live start, sideboarding, analytics and replay; transfer cached face data.
- [x] Expose necessary face metadata in public card views and preserve it through snapshots/restart.
- [x] Add HTTP regressions using a real modal/transform card and names/quantities-only decks.

Evidence: `test_release_card_contracts.py` checks HTTP names/quantities start, transformed views, snapshot resume and live/diagnostic parity. The HTTP fixture mocks persistence; it does not prove process-restart or browser face-choice workflows. Those remain Gate 1 acceptance requirements.

Cache-name increment: repository bulk lookups now prefer exact Oracle names and only scan face aliases when needed; art-series `Card` records do not supply playable-face aliases. A canonical `Mountain // Mountain` art-series regression checks that a requested basic Mountain hydrates and enters the game as a Land, independent of cache insertion order. Import and match-start admission now reject known art-series, token and emblem objects while retaining valid transform cards. Broader legalities and format-specific deck validation remain Gate 2 work.

Admission validation: 880 backend tests pass in a fresh isolated source/database copy (114.96 seconds, 826 deprecation warnings); frontend TypeScript/Vite build and unit checks pass. The backend-only increment did not rerun the browser harness.

Validation: 878 backend tests pass in a fresh isolated source/database copy (103.65 seconds, 814 deprecation warnings), and frontend TypeScript/Vite build and unit checks pass. The browser harness was not rerun for this backend-only cache change.

Acceptance: both faces survive HTTP start and restart; legal face selection and transformation work through UI controls with correct types and stats.

### 3. Expose truthful effective card views (P1)

- [x] Serialize printed/base and effective power/toughness separately, with counters, damage and effective keywords.
- [x] Display effective battlefield/hover stats consistently with combat resolution.
- [x] Cover counters, anthems, temporary pumps, characteristic-defined stats and cleanup expiration.

Evidence: view regressions cover counters, anthems, temporary-bonus/damage clearing, characteristic-defined and unknown stats, including snapshot reload. The frontend compiles with shared card types and the updated hover renderer. Browser visual verification and full cleanup timing remain open; helper expiration coverage is not a cleanup-order certificate.

Acceptance: UI and engine agree before and after reload for each fixture.

### 4. Share draw/discard event paths and choices (P1)

- [x] Route turn draws, spell draws and cycling through replacement-aware shared operations.
- [x] Route cleanup discards through event-aware, ownership-correct operations.
- [x] Let humans choose cleanup discards and resume pending choices after snapshots.
- [x] Discard before damage removal/end-of-turn expiration, perform simultaneous cleanup, then handle state-based actions, triggers, priority and repeated cleanup.
- [x] Test cleanup repetition where resulting triggers require another priority window.
- [ ] Expand interacting draw/discard replacement and APNAP/replacement-order fixtures; complete process-restart and browser interaction acceptance.

Evidence: `test_cleanup_choices.py` covers seat-2 ownership, rejected choices leaving snapshots unchanged, choice reload, damage/pump clearing without an intervening SBA, shared discard ownership and trigger-driven repeated cleanup. A React server-render probe confirms all three mechanic-choice controls render for seat 2 and block priority advancement; it is not browser E2E. The deterministic replay runner now initializes its database before querying decks and runs independently of prior API/tests.

Draw-path evidence: turn draws call `draw_cards`; spell draws and cycling reach the same handler. Canonical Thought Reflection fixtures cover one/two unconditional draw-doubling sources, per-original-draw choices, draw-step/HTTP choices, nested dredge pauses, snapshot resume and later effect clauses. Canonical Teferi's Ageless Insight/Alhammarret's Archive wording now excludes only the first actual draw in the affected player's own draw step; the successful-draw count survives snapshots, and Archive's life-gain clause applies independently of its draw clause. Existing cycling replacement tests also pass. Other conditional replacement families, alternative win/empty-library replacements, APNAP combinations and a complete browser/restart flow remain open under the second unchecked item.
Static draw-limit follow-up: Spirit of the Labyrinth/Narset-style one-draw-per-turn limits now count only successful draws across both players' turns, including draws before a limiting permanent enters. Prohibited draws bypass replacement and dredge choice generation and do not cause empty-library loss. The count survives snapshots and resets with each turn. A browser fixture casts canonical Divination under Spirit and sees one draw. This closes neither optional multi-draw rules nor other static draw prohibitions, simultaneous replacements, and process-restart acceptance.

Each-player draw increment: exact Vision Skeins/Prosperity-style clauses now resolve all active-player draws before the other player's draws, including X and paused human dredge choices. A stack-resolution regression verifies both empty libraries produce a game draw at the next state-based-action check. This follows [Comprehensive Rules 121.2c and 704.5b](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). Other compound or optional draw wording and interacting replacements remain open.

Latest draw-replacement validation: 914 backend tests pass in an isolated source/database copy; a seeded two-game replay reports no timeout or determinism drift. Frontend build and unit checks pass. The loopback-only browser harness passes 19 paths, including a human choosing Thought Reflection over Stinkweed Imp and then choosing both nested draws. This is not a complete-game/browser-restart certificate.

Conditional draw/life replacement validation: 918 backend tests pass in an isolated source/database copy; frontend build and unit checks pass; all 19 loopback-only browser action paths pass. A seeded two-game BO3 resolves in 36 turns without timeout or determinism drift. This is focused rules and repeatability evidence, not broad conditional-replacement, full-game or balance certification.

Validation: full existing suite 762 passed after the final engine change; the five cleanup fixtures also pass, including the subsequently added cascading-SBA case. Frontend build passes. Clean standalone seeded BO3 (Aetherdrift Aggro/Karlov Manor Control) completes without timeout or drift. No arbitrary-card or balance certification is inferred.

Acceptance: equivalent draw/discard sources invoke the same applicable replacements/triggers; cleanup choices and restart resume are correct.

### 5. Render legal actions for the acting seat (P1)

- [x] Replace battlefield player-1 assumptions with explicit acting-seat ownership and human controller checks.
- [x] Drive controls from legal moves, including generic activation, crew, loyalty, cycling, equipment and permitted exile/top-library play.
- [ ] Provide target, mode, face, X-value, mulligan and cleanup choices needed by supported actions.
- [x] Implement starting-player-first mulligan declarations and round-batched reshuffles/redraws through shared resumable engine state. Live, replay, batch and debug loops use the same pregame actor; snapshot/HTTP restoration and out-of-order rejection have focused fixtures. This does not complete all mulligan semantics.
- [x] Resolve mandatory ordered bottom-card choices after each mulligan redraw before another declaration round. Durable choice queues cover both players, AI/human decisions and no double-bottom on Keep; legacy snapshots preserve unresolved Keep-time choices rather than silently dropping cards.
- [x] Offer supported unconditional opening-hand battlefield entries in starting-player order, with multiple entries/decline, AI/human controls, canonical fixtures and HTTP/SQLite restoration. See [bounded coverage](docs/testing/opening-hand-actions.md).
- [x] Add the printed nonstarting-player entry/counter/hand-exile family with mandatory resumable selection and empty-hand handling. Share counter-dependent mana outputs across human/AI payment and views, and expose actual color choices for land piles. Other conditions, costs, quantities, restrictions and entry choices remain open.
- [ ] Support opening-hand and mulligan-time effects before claiming complete pregame fidelity under [Comprehensive Rules 103.5b-103.6](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt). Complete explicit legacy migration and broader restart/hidden-information certification.
- [ ] Verify permanent cast effects cannot execute later activated/triggered text prematurely; select targeted ETB/cast-trigger choices in their actual ability window, not as spell targets.
- [x] Separate conventional permanent spell compilation from activated/triggered text, preserving Aura attachment and supported entry choices.
- [x] Add snapshot-safe human target selection for supported single-target ETB triggers after APNAP ordering, with resolution-time legality checks and no-target fallback; add separate resolution-time accept/decline for supported optional triggers. Other trigger families and multi-target work remain open.
- [x] Extend the same choice window to supported self-cast single-target triggers: target the ability after casting, resolve it before the spell and retain it if that spell is countered. Cast-only triggers no longer fire for a copy; modal/multi-target and other cast-trigger clauses remain open.
- [x] Recheck each recipient of supported divided-damage spells at resolution, preserve announced allocations for legal recipients, fail when all are illegal, and include distribution recipients in protection checks. Canonical Pyrotechnics tests cover zone changes, protection, hexproof, player targets and snapshot restore; other multi-target effect families remain open.
- [x] Pay crew tap costs at activation and resolve Vehicle animation through a counterable stack ability; preserve costs if crew creatures leave and track the same battlefield object across control changes. Vehicle-specific crew triggers/copy layers remain open.
- [x] Preserve canonical layout, selected modal spell characteristics and printed-identity restoration through stack resolution and snapshot codecs; verify differing costs/types and planeswalker stats.
- [x] Normalize both battlefield transform paths through the shared face adapter; canonical Kumano/Delver tests cover numeric stats, keywords and AI threat assessment. A real-card Mono Red Aggro/Burn interactive autoplay BO3 now completes after this crash fix; one 2-0 series is not matchup evidence.

Transform increment evidence: 877 backend tests pass in a fresh isolated source/database copy (103.11 seconds, 812 deprecation warnings); frontend TypeScript/Vite build and unit checks pass. The canonical-card interactive BO3 completed two games without a stall. Its first attempt used an erroneous ad-hoc face-first diagnostic loader and is excluded from gameplay conclusions; the corrected loader prefers exact Oracle names before face aliases. Neither run certifies AI quality.
- [x] Implement bounded modal land-face plays and Adventure resolve/exile/normal-face permissions with persistent snapshots, single-target failure checks, actor ownership separation, AI payload and human browser coverage.
- [x] Implement Aftermath graveyard permission, printed costs/timing and owner-correct exile for resolution, countering and failed targets; preserve copy/draw choices and snapshots with canonical engine, actual AI-decision and human browser fixtures. See [Aftermath acceptance](docs/testing/aftermath-boundary.md).
- [x] Correct combined versus selected-half split colors, preserve absent Scryfall color metadata and refresh legacy split cache rows from canonical data; verify protection legality and idempotent offline cache repair.
- [x] Share saved spell-copy characteristics across targeting, ordinary/taxed counters, resolution and AI threat scoring after the physical original leaves the stack. Canonical Adventure/split/modal fixtures verify snapshot persistence, exact/minimum mana-value target bounds, rejected writes, AI choices and human Negate controls; see [stack-copy acceptance](docs/testing/stack-copy-characteristics.md).
- [x] Separate intrinsic spell counterability from supported standalone battlefield color/type protection. Ordinary/taxed counters check current scope without making protected spells illegal targets; source spell text does not protect stacked activated abilities. Canonical cast, copy, controller, snapshot and human Stifle regressions cover this [bounded repair](docs/testing/counterability-scope.md). Conditional/granted protection and ability-removal dependencies remain open.
- [ ] Complete other conditional entry families and competing replacements, compound multi-target Adventure effects, Fuse and broader face-specific process-restart/browser acceptance. Split cards with canonical faces now cast one half at its own timing/cost, Fire // Ice has engine and human browser paths, and incomplete layout or legacy split-color rows are refreshed from verified local knowledge where available; see [split-card boundary](docs/testing/split-card-boundary.md). Aftermath graveyard casts, owner-correct exile, counter/failed-target departure and snapshot/draw-choice continuation now have canonical rules and human browser fixtures; arbitrary half effects remain open, as detailed in [the Aftermath boundary](docs/testing/aftermath-boundary.md). Simple separate-clause target failure and partial resolution have a canonical Meager Meal engine/snapshot/browser fixture; supported copies choose each announced clause target separately across snapshots without changing the original or gaining a creature-cast permission. A focused AI choice regression redirects beneficial copy clauses to friendly recipients; this does not establish broad copy tactics. The prior Adventure-copy revision passed 1,528 isolated backend tests, frontend lint/build/unit, full Chromium harness and a three-game deterministic BO3 replay. The pay-2-life/tapped land family has focused engine, browser and seeded replay coverage.

Land/Adventure evidence: [boundary fixtures and open cases](docs/testing/land-adventure-boundary.md) use canonical Bala Ged Recovery, Riverglide Pathway, Bonecrusher Giant and Brazen Borrower faces. The UI scenarios play a tapped land face and follow Stomp into exile and Bonecrusher Giant onto the battlefield. No entire-card Oracle or broad matchup-strength claim follows from these boundary checks.

Modal spell evidence: [boundary tests](docs/testing/modal-spell-faces.md) use actual Wandering Archaic / Explore the Vastlands, Valki / Tibalt and Delver Oracle metadata. Human browser scenarios cover the affordable back-face default and a deliberate switch with distinct cost. AI payload materialization and cast bias respect the offered spell face. Known transform-only backs are not direct cast choices. These do not certify full Oracle semantics or every face/permission family.

Spell-context evidence: canonical Oracle fixtures reproduce premature effects before the repair and pass afterward. Modern entry wording routes through supported ETB matching; ETB draw/destruction remains on a separate stack object. Supported single-target ETB and self-cast triggers now expose a human target choice after ordering and optional human accept/decline at resolution, with snapshot and browser coverage. Ulamog's cast trigger resolves before its creature spell and survives that spell being countered. Unattended choices remain deterministic; other trigger/ability semantics remain open. See [bounded contract](docs/testing/targeted-trigger-choices.md).
- [x] Show an explicit warning for any legal action kind without an implemented control.

Evidence: [browser harness and reproduction](docs/testing/human-actions-browser.md) exercises the actual Battlefield component and production API action handlers in an isolated database: seat-2 land, targeted permanent activation, crew selection and response window, exile spell and top-library creature. This is not a full App onboarding/game/recovery E2E. Generic abilities expose advanced JSON for less common choice contracts; polished multi-choice/mulligan/face coverage remains open. Shared extraction now retains adjacent mana symbols, targets validate before costs and unsupported variable activated costs are excluded. [Crew timing tests](docs/testing/crew-stack-timing.md) cover the core stack boundary, not every Vehicle-specific trigger or layer interaction.

Validation: 768 backend regressions pass in a tracked-source copy with initially empty database/cache and existing pinned dependencies; the TypeScript/Vite build also checks the browser harness. Five Chromium action scenarios pass. No fresh dependency install, full browser game or network deployment is claimed.

The [seeded Aggro/Dimir BO3 smoke replay](docs/plans/baselines/2026-09-27-human-actions-replay.json) completes two games without timeout or deterministic drift. This is repeatability evidence, not a matchup-balance or expert-AI measurement.

Acceptance: complete human-vs-human and human-vs-AI flows through UI; seat 2 can act, crew a Vehicle, activate an ordinary ability and play a permitted exile card. No silent legal-action omissions.

### 6. Validate API requests before mutation (P2)

- [x] Define bounded typed deck entries and discriminated action/choice contracts.
- [x] Reject malformed quantities, missing fields, invalid player/card IDs and unsupported actions with structured 4xx responses.
- [x] Define explicit sandbox deck-size policy separately from malformed-input validation.
- [x] Verify rejected external actions leave authoritative game state and persisted snapshots unchanged through copy-on-write execution.
- [x] Commit accepted match mutations, history and snapshots together and roll back memory on persistence failure; retain durable revision/idempotency metadata for the versioned UI write path.

Evidence: 806 backend tests pass in an isolated source/database copy (120.05 seconds, 548 deprecation warnings). Malformed HTTP payloads, invalid actor/source/face/cost/target choices, failed loyalty payments, duplicate concurrent land requests, combat restrictions, and deliberate London mulligan bottoms have regression coverage. Normal mainboards require 60-250 cards; explicit sandbox permits 1-250, never empty. The 250 cap is an application resource limit, not a Magic maximum. Live and batch admission resolve name/quantity entries through cached/canonical metadata. See [input contracts](docs/api/input-contracts.md).

Frontend production build, seven error-message assertions and six Chromium component/HTTP paths pass. A seeded Mono Red Aggro/Dimir Control BO3 finishes two games without timeout or drift ([replay](docs/plans/baselines/2026-09-27-api-validation-replay.json)). Human seat 2 can explicitly select ordered London bottoms; mulligans may continue to a zero-card opening hand. This does not establish full-game browser acceptance, arbitrary-card target semantics, fresh dependency installation or expert AI.

One fresh, authorized Jev request judged the scoped rejection, storage/topology/target limits and next-work direction against current working-source excerpts. [Review provenance and limits](docs/audits/2026-09-27-api-validation-jev.md). No database contents were supplied; the credential was used only in the authorization header, not evidence or archives.

Acceptance: missing/negative/oversized inputs and stale IDs cannot cause internal 500s or invalid games. Fuzz meaningful action families.

### 7. Restore matches and coordinate UI mutations (P2)

- [x] Add saved active-match discovery/resume and persisted frontend selection.
- [x] Add visible errors, bounded request timeouts and revision-checked state/legal-move reads.
- [x] Serialize manual/autoplay/response-window mutations and guard duplicate clicks.
- [x] Reconcile authoritative state before retrying when a write result is lost; persist revision and bounded idempotency receipts.
- [x] Make match creation idempotent with a durable receipt and same-key frontend retry/reload recovery.
- [ ] Validate remaining successful response contracts, test extended disconnect/reconnect and rapid multi-window transitions, and enforce deployment-specific authorization/topology under steps 9/14.

Evidence: 822 backend tests pass (161.21 seconds, 798 warnings), including concurrent identical retries, stale/conflicting writes, restored revision/receipts and injected snapshot/commit failures with unchanged full game/database snapshots. HTTP match mutation history and snapshots commit together; memory rolls back on exceptions. `GET /matches` discovers incomplete restored matches. The UI stores only its selected ID, resumes authoritative state, pauses automatic play on restore/error, and uses one non-queuing mutation gate plus versioned write keys generated with HTTP-LAN-compatible `getRandomValues`.

The production build and frontend unit scripts pass. Chromium passes the human-action paths plus full-App refresh/double-click, discarded-success-response reconciliation and actual backend-process-restart checks. These use an isolated fixture/database with production routes, not a complete human game. Mutation retry receipts retain the latest 100 keys; matching retries return current authoritative state. Legacy headerless callers remain supported without stale-version protection. Network/multiworker deployment remains open.

Creation-retry increment: `POST /matches/start` now persists a bounded start key and request fingerprint atomically with the new match snapshot. Concurrent same-key requests return one match; changed payloads conflict, and retry after losing the in-memory controller restores only that match. The frontend retains the pending key/payload until a match and its legal moves load, retries ambiguous responses, and recovers after reload. HTTP and Chromium regressions cover both lost-response paths. This is local single-process durability, not multiworker coordination or long-session certification.

Repeated Start clicks after an ambiguous failure reuse the pending request rather than creating a new key; the browser harness verifies this path. Simultaneous fresh starts from separate windows are still outside this local single-process acceptance.

Verification: 922 backend tests passed in an isolated source/database copy; the final recovery-file rerun passed 14 tests after adding a database rollback assertion. Frontend build, lint and unit checks passed. The loopback browser harness passed its 19 action paths, three existing recovery paths and two new ambiguous-start paths. One seeded BO3 replay completed two games with zero determinism failures. These checks do not certify full-game UI play, balance or multiworker safety.

Cast admission also distinguishes permanent spells from their later target-bearing abilities, preserves Aura attachment requirements and covers artifact/enchantment/land/general-permanent target availability. Unqualified land targets include both players' lands; supported controller qualifiers remain explicit. The modal-parser fixture now has its intended Sorcery type rather than retaining a setup Island's Land type. These checks do not certify ETB/effect timing. The post-change seeded BO3 has zero timeout/drift ([replay](docs/plans/baselines/2026-09-27-recovery-replay.json)).

Acceptance: refresh, backend restart, disconnect, double-click and autoplay/manual overlap do not lose a match or apply an action twice.

### 8. Share BO3 transitions and seed provenance (P2)

- [x] Preserve root/per-game seeds for newly started interactive matches and restored controller snapshots; next game uses `root_seed + game_number`, matching the diagnostic runner's seed schedule. Keep seeds out of active public responses so library order stays hidden. Legacy saved matches without a root seed remain explicitly unseeded.
- [x] Let the previous game's human loser choose play or draw; AI losers choose play by default. Validate the chooser before transition and expose both human choices in the GUI.
- [ ] Broaden AI sideboarding beyond the bounded public-type heuristic and validate more complete series; add explicit legacy-seed migration tests and certify other simultaneous-loss paths. Drawn-game score/chooser policy has engine, HTTP, replay and browser regressions.

Draw policy increment: simultaneous life/poison and empty-library draw failures are collected at the next state-based-action check, so concurrent losses produce a game draw. Failed-draw flags survive snapshots and multi-card effects stop logging further draws. A drawn BO3 game awards no point and retains the prior chooser across SQLite restore and rendered next-game controls. Diagnostic series allow extra drawn games but cap them and distinguish the cap from a tick timeout. This does not certify every simultaneous multi-player draw effect, broader AI sideboard strategy or tournament time-limit procedures.

Bounded sideboard transition: the API shows current mainboard/sideboard quantities for human-controlled seats only between games, rejects completed-match and AI-seat manual swaps, and preserves an applied swap through restore into game two. The UI displays that inventory, limits manual selection to human seats and disables duplicate submission. An HTTP regression checks exact next-game card counts and rejected writes against memory/database snapshots; a loopback browser path submits a real basic-land swap, reloads and verifies game two. AI seats now have the limited public-type swap heuristic documented under Gate 2; the combined checkbox remains open for broader strategy and legacy-seed coverage.

A seeded HTTP regression completes natural AI-vs-AI BO3 matches for both Mono Red Aggro/Burn and Blue Control/Ramp, restoring each controller from SQLite between games. A browser path restores an Aggro/Burn series, advances it through the rendered `AI Step x30` control, and verifies match completion. Scripted-human browser paths play Mono Red Aggro through natural BO3s against a 60-Island AI or human seat, exercising mulligan, land, cast, attack, pass, trigger-order and next-game controls without forcing wins. The human-vs-human path exposed and now guards the missing combat-damage step action. Drawn-game policy and narrow AI sideboarding have since gained bounded tests; competitive-opponent play and broader strategy remain open.

Current local verification: 946 backend tests pass in an isolated source/database copy; frontend lint, build and unit checks pass; the Chromium harness passes its action, recovery, sideboard, natural AI BO3, scripted human-vs-AI BO3 and scripted human-vs-human BO3 paths. The target-selector browser path also casts canonical Lava Spike at a planeswalker. Hosted CI for the previous target/art milestone passed all jobs in run `36379142377`; hosted CI for this combat increment is pending.

Verification: 932 backend tests passed in an isolated tracked-source/database copy, including both seeded live-series pairs; frontend lint, production build and unit checks passed; the browser harness passed its existing action/recovery/sideboard scenarios plus the complete natural Aggro/Burn BO3. Hosted CI runs `36375696141` and `36376066903` each passed backend, browser and frontend jobs.

Verification: 923 backend tests passed in an isolated source/database copy. Frontend build, lint and unit checks passed. The loopback browser harness passed its existing action/recovery paths plus the new sideboard transition and seat-switch draft-clearing checks. Hosted CI run `36372772663` passed all three jobs.

BO3 increment evidence: 875 backend tests pass in a fresh isolated source/database copy (102.62 seconds, 812 deprecation warnings), including helper and HTTP choice/restore tests. Frontend TypeScript/Vite build and unit checks pass; fifteen isolated Chromium paths pass, including both play/draw buttons against the API. A two-game seeded Mono Red Aggro/Dimir Control diagnostic replay has no timeout, anomaly label or determinism drift; it does not exercise an entire interactive series or sideboard strategy.

Acceptance: repeated seeded interactive series and restarts agree when actions agree; game-two starts follow the documented policy and sideboards remain legal.

### 9. Add contract and frontend release gates (P2)

The frontend now checks live match responses for core fields, both player views, required card-view fields and list-valued block assignments. Unit regressions reject malformed payloads, and a backend-serialized match passed the validator. This is partial boundary coverage, not generated OpenAPI types or full response validation.
Legal-move responses now also validate the acting seat, nonnegative revision, move discriminator and optional card-view/choice-list shapes. Unit tests reject malformed examples, and the loopback browser harness accepts production API responses across its action/recovery paths. Other successful API responses still need boundary contracts.
Saved-match discovery now checks IDs, modes, turns, game numbers, revisions and two player names; malformed summaries fail before recovery selection. Unit cases and the production-route browser recovery fixture pass. Deck import and the rest of the API still need generated/shared contracts and selective runtime validation.
The Testing Simulator job-status boundary also validates progress and completed summary metrics, and its `any` result cast is removed. Diagnostic run payloads and other API responses still need generated/shared contracts and selective runtime validation.

A clean-checkout GitHub Actions baseline installs declared Python and locked npm dependencies, then runs the backend suite, frontend build, lint and frontend unit checks. Browser-flow gates were added later and are described below. The final frontend `any` casts for Vite environment access and start-mode selection were removed; `ImportMeta` now uses Vite's client declaration. A disposable frontend copy passed `npm ci`, build and unit checks locally; a separate fresh Python venv passed seven API smoke tests.

ESLint checks TypeScript and React hooks in `src`, with the shared autoplay, response-pass, deck-refresh and legal-move dependencies corrected rather than suppressed. A fresh `npm ci` copy passes lint, build and unit checks; the local browser harness passes 19 action paths plus App refresh, ambiguous-write recovery and backend-process restart. The updated hosted gates are verified below.

A separate browser CI job uses the existing production Controls/API and App recovery fixtures against a temporary backend copy, including an actual process restart. Hosted run `36370371065` passed 918 backend tests, frontend build/lint/unit checks, all 19 browser action paths and three recovery checks. Chrome is used on the hosted runner because its Chromium binary did not expose the CDP port. This is not a complete human game or BO3.

- [ ] Generate/share OpenAPI types and validate response payloads at runtime where needed.
- [x] Correct block assignments to list-valued mappings and remove broad simulator/action `any` types.
- [x] Configure ESLint with React-hooks checks and production-component browser smoke tests.
- [x] Add clean-checkout CI for backend tests, frontend build/lint/tests and an HTTP/UI flow.

Acceptance: malformed block/card-view payloads fail contract tests; regressions cover steps 1-8. Do not add a redundant task to enable existing TypeScript strict mode.

Gate 1 exit: empty cache/database setup can import a supported deck, play both advertised human modes, choose mulligans/targets/responses/cleanup, complete combat and a BO3, sideboard, reload/restart and resume. All configured gates pass without developer-only assets; bad inputs return 4xx.

## Gate 2: Trustworthy supported-corpus simulator

September 27 engine increment: dedicated core handlers for Infect/Wither/Toxic, Ninjutsu, Annihilator, Escape, Prototype and optional Dredge; persisted mechanic choices and spell continuations; draw-step replacement routing; ability-versus-spell cast events. This does not complete corpus certification. Next: expose new actions/choices to humans, unify canonical live hydration, validate interacting replacements and first-strike windows, then implement Morph/Manifest, Suspend, Discover, Battle protectors/defense, Mutate, Craft and Banding in separately tested increments. Contracts and remaining limits: [docs/rules/expanded-keywords.md](docs/rules/expanded-keywords.md).

September 29 snow-spend increment: fixed-output payment records snow-produced mana spent on spells, copied spells record zero, and Search for Glory resolves its eligible search followed by the corresponding life gain. Human library-search choices resume subsequent effect clauses, including chained choices after snapshot restore. Cast actions cannot replace the printed search filter, count or mana limit. Dynamic snow supertypes, other snow-spend-dependent Oracle wordings and full corpus certification remain open.
Copy timing follow-up: supported copies now create independent stack objects, can be countered without moving the source, and preserve copied spell characteristics after the original leaves the stack. Permanent-spell copies become tokens at resolution; Search for Glory and Memory Deluge copies count zero mana spent to cast. Focused tests cover response timing, priority passing, target rechecks, counters, snapshots, Magecraft ordering, an HTTP action and Twincast's Oracle target pattern. Later increments add optional new-target selection for single-target spell and ability copies, including real Lithoform activation, snapshot and HTTP regressions. Bounded divided-damage and single-target-per-mode modal copies (explicit or unambiguous shared announcements) are implemented; other multi-target and modal forms, linked-ability/last-known-information, copy-layer/face edge cases and permanent-entry replacement interactions remain open before treating copies as rules-complete.
Copy UI follow-up: the isolated Chromium harness also selects a new target through the rendered human Controls and resolves both copied and original Bolt to their distinct players. This validates the supported choice path end to end, not arbitrary copy effects.
Permanent-spell targeting follow-up: the shared Oracle parser now recognizes "copy target permanent spell you control" and restricts candidates by controller and permanent type. A real Lithoform third-ability regression rejects an instant, copies a creature spell as a token and preserves the original stack object. Battle entry, Aura attachment, linked abilities and complex copy layers still require separate validation.
Divided-damage copy follow-up: supported `deal_damage_multi` stack copies now pause for each announced target, preserve that target's damage share and the target count, reject duplicate/newly illegal replacements, and allow an illegal original target to remain unchanged. Focused Pyrotechnics/Twincast tests cover snapshot continuation and copying-spell timing; the Chromium fixture chooses two targets through Controls. Modal copies make one optional choice per supported single-target mode. Unambiguous shared top-level announcements are normalized on the copy only, including two modes that initially target the same permanent. Kolaghan's Command and Cryptic Command regressions cover separate destroy/damage and counter/bounce targets, snapshot continuation, an HTTP choice path, and AI avoidance of self-targeting; Chromium drives explicit per-mode human choices. Ambiguous or multi-target-per-mode clauses, non-damage distribution and other multi-target patterns still need explicit implementations and tests.

### 10. Verify corpus and finish knowledge consumers

- September 27 ingestion milestone: reusable all-Oracle bulk import, exact-name/search rulings verification and a knowledge gap report are implemented. The first local import contains 38,690 unique Oracle records and 6,433 faces; bulk records explicitly await rulings verification. Data remains local and is rebuildable from the official source. Tactical profiles, AI consumers, verified offline seeds and full rules coverage remain open.
- Corpus verification now covers 88 requested names with zero missing metadata or pending rulings (87 canonical records). The full bulk reimport leaves all 38,690 records unchanged. See `docs/plans/baselines/2026-09-27-card-knowledge.json` for the evidence summary.
- Bulk-only cards now appear in read-only completeness and typo-suggestion endpoints without being misreported as absent or forced into the gameplay cache. The query-string list accepted by `/cards/completeness` is explicitly bound as query data, and verified-empty rulings are counted as available. This improves metadata diagnostics, not rules certification.
- Simulation preflight now uses the same known-gap summary as completed batch results, before any job is queued. The UI requires explicit `Run Anyway` acknowledgement for detected unsupported mechanics; a browser fixture covers both the warning and ordinary first-click start. The detector remains conservative, so the broader unsupported/ambiguous-semantics gate stays open. Batch `Master+` input now matches the existing AI/UI option.

- [ ] Freeze and publish the supported corpus and per-mechanic coverage limits.
- [ ] Sync canonical data/rulings with provenance; use verified offline seeds and report incomplete metadata honestly.
- [ ] Replace expansion-labeled archetype copies with source-backed era/format-legal tournament lists, including provenance and an explicit legality policy.
  - Partial: OTJ now contains a sourced 2024 Pro Tour Domain Ramp 60+15 list with player/event/finish/format provenance. The other 51 entries are explicitly labeled archetype templates, not historical or format-legal decks. Current-format legality and per-card rules fidelity remain unverified; source-backed replacements for the other entries are still required.
  - Repeated catalog imports now reuse saved IDs. Legacy duplicate rows are deliberately retained while referenced by match history; a reference-aware cleanup/migration is still needed.
- [ ] Reconcile [the knowledge implementation plan](docs/plans/2026-09-09-ai-knowledge-base.md) with current code before carrying forward its historical cache counts.
- [ ] Implement tactical profiles, AI consumers and measured matchup priors; storage alone does not complete knowledge integration.
- [ ] Surface unsupported/ambiguous semantics before simulation instead of silently approximating them.
Partial coverage: deck completeness distinguishes known unsupported from not certified across mainboard and sideboard. Persisted batch results and the Testing Simulator label win rates exploratory and list detected unsupported cards; 986 isolated backend tests and frontend lint/build/unit pass. This does not classify every unimplemented effect, publish a certified corpus or block unreliable simulations yet.
Follow-up: the shared detector also flags Morph, Manifest, Suspend, Mutate, Craft and Discover from root/face Oracle text. Verification: 989 isolated backend tests plus frontend lint/build/unit checks pass. It is intentionally conservative, still lacks a certified supported corpus, and does not make those mechanics playable.
OTJ corpus follow-up: the shared detector flags kicker, multikicker, Domain and Incubate. Herd Migration's supported Domain token-count wording counts distinct basic land subtypes at resolution, and spell casting does not borrow the card's separate discard/search ability. Leyline Binding's printed Domain generic discount uses the same subtype count in legality, AI affordability and payment while leaving mana value unchanged. Bounded Incubate paths cover fixed-number triggers, land-count "incubate X twice," Sunfall and Chrome Host Seedshark with transforming tokens. Unknown X sources do not silently create zero-counter tokens. Other Domain effects, kicker outcomes, Incubate variants and transform-related triggers remain open. Warnings do not prove complete detection; preflight still cannot certify a deck as rules-accurate. This increment passed 1,358 backend tests in an isolated tracked-source copy and frontend lint/build/unit checks; browser play and broader matchup acceptance were not rerun.

Transform follow-up: battlefield face changes now emit a shared event. Supported "transforms into a [subtype], put a +1/+1 counter on it" text triggers from the resulting subtype and controller, as tested with Norn's Inquisitor and Incubator. Other optional once-per-turn transform wordings, unusual entering-transformed effects, and additional trigger effects remain open. Counter resolution now requires its permanent to remain on the battlefield. Verification: 1,361 backend tests in an isolated tracked-source copy plus frontend lint/build/unit checks pass; browser play and matchup replay were not rerun.

Optional transform draw follow-up: Corruption of Towashi's exact Oracle pattern now uses the shared optional trigger window. Declining does not consume its once-per-turn allowance; accepting does, including across snapshots, and the allowance resets next turn. Transforming permanents that enter back-face-up count; modal double-faced land backs do not. The ETB Incubate sentence is compiled without the separate draw sentence. Verification: 1,363 isolated backend tests and frontend lint/build/unit pass; a final accepted-choice snapshot assertion passed separately. Other once-per-turn optional wordings and unusual entering-transformed effects remain open.

Day/night ordering follow-up: upkeep start stages the day/night change, resulting daybound/nightbound face changes and ordinary upkeep triggers together. All faces change before transform triggers are collected, and both players can order the combined triggers by APNAP; the pending order survives a snapshot. This is tested with Corruption of Towashi, multiple Brutal Cathar copies on both sides and Phyrexian Arena. Verification: 1,364 isolated backend tests and frontend lint/build/unit pass. Browser play and matchup replay were not rerun. Simultaneous transform causes outside day/night and broader triggered-effect fidelity remain open.

Transforming Saga follow-up: the supported final-chapter wording now exiles the Saga and returns its back face as a new permanent rather than transforming in place. Fable of the Mirror-Breaker coverage verifies reset lore/other counters, creature entry and summoning sickness, enter-transformed rather than transform triggers, snapshots and nonowner control. Verification: 1,365 isolated backend tests and frontend lint/build/unit pass; browser play and matchup replay were not rerun. Wider re-entry replacement interactions and other Saga wordings remain unverified.

Live Saga route follow-up: a names-and-quantities HTTP deck hydrates Fable's two faces, its final chapter persists through SQLite restore, and public priority-pass actions return the back-face card view with its printed types and stats. Verification: 1,366 isolated backend tests, frontend lint/build/unit and the full isolated Chromium harness pass. The test prepares the chapter-ready battlefield after starting the match; the browser harness does not specifically play Fable. Broader live-route and diagnostic parity remains open.

Acceptance: corpus completeness and AI profile consumption are reproducible, including offline mode. Do not require nonempty rulings when the authoritative card legitimately has no rulings.

### 11. Validate semantics across rule families

- [x] Enforce bounded printed combat restrictions for a blocker requiring a named keyword on the attacker and for attack/block permissions gated by controlling N lands. Real Brazen Borrower and Topiary Stomper fixtures cover both sides of the condition and snapshots. Other conditional combat clauses and loss-of-abilities interactions remain open.
- [x] Prevent one blocker of multiple attackers from dealing its full power to each; Palace Guard now has one shared damage budget per step.
- [x] Expose controller-chosen numeric combat damage division for multi-attacker blockers and attackers with multiple blockers under current no-assignment-order rules. Focused tests cover ordinary assignment, trample, first/double strike, snapshot, HTTP and UI; the remaining exceptions below stay open.
- [x] Count another attacker's simultaneous assignment, including deathtouch, toward a shared blocker's trample-lethal requirement. Reject an illegal final attacker split without mutation and permit a pre-damage restart; focused snapshot/AI and browser paths cover the supported case.
Shared-trample milestone validation: 968 backend tests pass in an isolated source/database copy; frontend lint, build and unit checks and the full loopback browser harness pass, including a restart before the defending blocker's own choice. A seeded two-game BO3 replay resolves in 40 turns with no timeout, anomaly label or deterministic drift. This does not measure broad matchup quality.
- [x] Route ordinary banding damage-assignment controller overrides to the defending or active player as appropriate; human seat ownership and AI defensive choice have focused fixtures.
Banding choice-owner validation: 972 backend tests pass in a fresh isolated source/database copy, including a mixed-controller restart that retains the other player's assignment. Frontend lint/build/unit and the full browser harness pass, including Player B assigning Player A's damage. A seeded two-game BO3 replay resolves in 40 turns without timeout, anomaly label or determinism drift. This does not cover attacking-band declarations or "bands with other."
- [x] Add ordinary attacking-band declarations and blocking propagation with human controls, strict admission and snapshot coverage.
Attacking-band verification: 980 backend tests pass in an isolated source/database copy. Frontend lint/build/unit and the full Chromium harness pass, including deliberate attacker selection, band submission and a defending blocker propagating to a flying band member. A seeded 1,200-tick Tempo/Dimir BO3 had no replay drift but one long-game timeout, so it is not a quality/balance claim.
Live-deck follow-up: ordinary Banding was missing from Oracle keyword inference despite passing manually constructed combat fixtures. The factory now distinguishes it from "bands with other" wording; focused real-card regressions cover both cases, and 981 isolated backend tests pass. The latter mechanic is still unsupported rather than treated as ordinary banding.
- [ ] Add "bands with other" variants; certify replacement/prevention interactions and full-step trigger ordering. Follow the [combat assignment audit](docs/rules/combat-damage-assignment-audit.md); the deterministic low-level fallback is not full rules support. Teach AI strategic band formation after rules coverage.
Combat-choice milestone validation: 964 backend tests pass in a disposable tracked-source copy with the new fixtures overlaid; frontend lint, build and unit checks pass; the loopback Chromium harness passes its damage-choice path and existing recovery/BO3 paths. A seeded two-game BO3 replay resolves without timeout or deterministic drift. This is bounded regression evidence, not full simultaneous-damage certification.
- Recruitment Officer's canonical mana-value-limited top-four reveal and Militia Bugler's power-limited variant share a resolution-time handler. A human may select a qualifying creature or reveal none after snapshot restore; HTTP legal-move/action coverage reaches the same choice. Live/replay AI now uses the pending choice with contextual ranking; direct effect calls retain deterministic fallback. Remaining cards go to the library bottom in RNG-backed random order where Oracle text says so. The earlier Recruitment Officer test used altered card text and has been corrected. Other top-library families remain to audit.
- Supported creature/permanent topdeck battlefield effects no longer peek at hidden candidate cards during cast/legal-move generation. Human and AI selection occurs after resolution inspects the then-current library; human choices permit zero through the printed up-to count, survive snapshots and complete the paused stack item. AI ranks free battlefield value rather than taking the first eligible card; one focused regression checks this, not broader strategic quality. Focused canonical Collected Company/Storm the Festival fixtures cover changed library order, choice bounds and random-order bottom placement using persisted RNG; a Thought-Knot Seer boundary verifies `{C}` in creature mana value. Supported "any order" clauses now pause for a second ordered human bottom choice, preserve zone consistency, and finish the stack item only after that choice; focused and browser tests cover Collected Company. Broader clauses remain open.
- Expressive Iteration-style hand/exile/bottom placement inspects cards only at resolution. Human ordered choice pauses and resumes the stack across snapshots; live/replay AI chooses a ranked hand card and exile card through the same legal move. The exile-play expiry uses the resolution turn. Focused tests cover hidden cast hints, duplicate rejection, changed library order, HTTP actions and a production Controls browser path.
- Supported library-search effects now expose candidate cards at resolution, not during cast. The human chooser survives snapshot/stack continuation, supports failing to find a restricted hidden-zone card, and is exercised through the Controls/API browser path. Live and batch AI controllers now use the same pending choice and rank needed mana colors and near-term card value; a snapshot regression checks the choice, but broad tutor decision quality remains open. Inferred one-card tutors no longer take every matching card. A corrected canonical Cultivate fixture verifies ordered split placement (first land tapped on battlefield, second into hand) rather than the earlier altered hand-only text. Other search wordings and full clause fidelity remain open.
- Tutor-choice validation: 902 backend tests passed in an isolated source/database copy before the legacy-snapshot migration edit; 24 focused recovery/search tests passed after it. Frontend build/unit checks passed. A seeded two-game replay completed without timeout or determinism drift. These checks establish regression stability, not optimal tutor strategy.
- Generalized library-choice validation: 905 backend tests passed in an isolated source/database copy, followed by 27 focused library-choice tests after adding the old-snapshot-key compatibility assertion. A seeded two-game replay completed without timeout or determinism drift. No complete browser game or broad AI decision-quality matrix was run for this change.
- AI mechanic-choice audit found that the generic sacrifice ordering could discard lands before tokens and that unattended cleanup discarded the first hand cards. Sacrifice now ranks token/board loss and protects mana sources; cleanup uses a persisted AI choice and a hand-retention heuristic. Focused regressions cover both. These are bounded tactical heuristics, not optimal play or broad discard-synergy coverage.
- Mechanic-choice validation: 907 backend tests passed in an isolated source/database copy; a seeded two-game replay resolved in 40 turns with no timeout or determinism drift. Frontend code was unchanged for this increment; no browser full-game run was performed.
- The September inventory in `docs/plans/baselines/2026-09-27-mechanics-inventory.json` identifies additional gap candidates: Morph (153 cards), Suspend (74), Infect (49), Ninjutsu (37), Mutate (34), Discover (33), Escape (33), Banding (26), Craft (24), Prototype (21), Dredge (14), Manifest (68) and Annihilator (15). Battle metadata covers 39 cards; protector/defense behavior still needs implementation. These are data inventory counts and code-audit candidates, not exhaustive coverage certification. Supplemental, digital and novelty cards are also present in bulk data and require explicit format/scope handling.

- [ ] Add golden fixtures for full clauses, costs, modes, targets, attachments and zone permissions.
- [ ] Complete the [battlefield-entry choice boundary](docs/audits/2026-09-28-battlefield-entry-choice.md). Supported pay-2-life/tapped wording uses shared pre-entry handling for plays and land-capable effect paths. Effect-driven multi-entry now stages payment and ETB triggers until all land choices finish, including snapshot continuation and human trigger order. Still verify competing replacements, other entry wordings and broader replay coverage before claiming general support.
- [ ] Complete the [life-total-lock boundary](docs/audits/2026-09-28-life-total-lock.md). Platinum Emperion-style wording blocks gain/loss and nonzero life costs while damage and opponent lifelink still apply. Combat gains use the shared replacement handler. [Font of Agonies-style life-payment triggers](docs/audits/2026-09-28-life-payment-triggers.md) receive separate amount-bearing events from activated, additional and land-entry payments with post-action staging; effect-driven multi-entry ordering is covered. Cross-event replacement ordering, alternate lock/payment wording and multi-part cost atomicity remain open.
- [x] Repair the bounded [variable additional life-cost and name-fallback boundary](docs/audits/2026-09-29-variable-life-cost-and-name-fallback.md). Announced X is checked against life and mana before payment; the shared pay-life event and a reusable all-creatures temporary modifier resolve the supported wording. Name guesses cannot override present Oracle text. Focused engine, snapshot, HTTP and AI-choice regressions replace the three strict xfails. Other variable cost grammars and layer ordering remain open.
- [ ] Complete the zone-change object reset audit against the [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt), especially 122.2, 400.7 and 603.10. Battlefield re-entry clears old counters, damage and end-of-turn P/T modifiers before supported Escape/entry counters. Direct, batch and replacement-to-exile paths reset old counters after supported leave-trigger collection; single and batch graveyard death paths reset after supported death-trigger collection. Stack-to-graveyard and sacrifice-only paths reset their new objects. Printed persistence wording retains real counters outside hand/library, while those two destinations clear them. Lethal spell damage emits the shared leave event; battlefield exits also reset transformed faces, attachments and temporary control durations. Supported death triggers now use persisted pre-exit power, type, controller and transformed-face data, with mass exits captured before any permanent moves. Still validate copied characteristics, other last-known-information consumers, unusual persistence wording and nonbattlefield-zone views before closing this gate.
- [x] Add bounded artifact-to-graveyard trigger support for the printed Marionette Master clause across destruction, sacrifice, replacement-to-exile and simultaneous creature wipes. The event collector now considers only sources that departed in the current death batch, using saved last-known source power. Canonical Marionette Master, Everflowing Chalice, Memnite and Rest in Peace fixtures cover positive and negative cases. Optional-payment variants (Urza's Miter, Tablet of Epityr), other artifact-death effects, and general cross-event trigger ordering remain open.
- [x] Group supported triggers generated by one sacrifice for a shared human/APNAP ordering choice without flushing an outer staging context. Canonical Merchant of Venom and Marionette Master fixtures cover order selection, snapshot restore, opponent sacrifice and Rest in Peace exile. The bounded printed one-damage "any target" sacrifice clause now has human player/creature/planeswalker choice, snapshot and browser coverage. Other targeted sacrifice clauses, Battles, modal/multi-target choices and complete trigger timing remain open; do not treat generic sacrifice wording as complete support.
- [x] Move unattended sacrifice-damage target preference into the AI layer. Its legal-option scorer prefers lethal opponent damage, then a killable opposing creature or planeswalker when worth more than nonlethal player damage; otherwise it targets the opponent. Printed Mayhem Devil and Havoc Jester fixtures guard the generic path. Response planning, optional payment and broader trigger modes remain open.
- [x] Apply bounded player hexproof/shroud target legality to spell hints, announcement, trigger choices and resolution rechecks. Unconditional battlefield Oracle clauses are supported; conditional/temporary grants, player protection and broader targeting families remain open.
- [x] Keep single player-or-permanent GUI target selection mutually exclusive, including selected modal faces; retain separate fields for genuine multi-target actions. An isolated HTTP regression and loopback browser fixture verify hexproof filtering and creature fallback.
- [x] Make AI target materialization respect legal player candidates after static player immunity filters them. Filter battlefield target hints through shared hexproof, shroud and protection checks, then hold pure direct-damage spells with no opposing legal recipient while preserving creature removal; Shock and Lightning Bolt use one wording-based rule. Evaluate modal/multi-effect self-damage synergies and deeper response planning separately.
- [x] Evaluate mandatory target availability per textual spell mode before offering `Choose one`/`Choose two` casts; expose legal modes to UI and AI, revalidate announced modes, and resolve them in printed order. Real Cryptic Command, Izzet Charm and Drown in the Loch fixtures cover targetless mode availability, unavailable target modes, generic tap-all resolution and untargeted draw/discard. Cryptic Command stack/permanent and Kolaghan's Command artifact/creature target pairs have independent announcements and resolution-time checks. Kolaghan's Command return mode now honors the selected creature in your graveyard. Repeated modes, multiple targets within one mode and broader Oracle effects remain open.
Modal-target verification: 1,203 isolated backend tests, a final 33-test focused rerun including AI and snapshot choices, frontend lint/build/unit, full loopback Chromium harness and a three-game seeded BO3 replay (60 turns, no timeout, anomaly or drift). This is bounded cast/resolution evidence, not a general Oracle or AI-strength certificate.
UI follow-up: Kolaghan's Command's return-from-your-graveyard/destroy-artifact pair has a loopback human cast-and-resolution case. It checks that an opponent-owned graveyard card is not offered and the selected creature enters the caster's hand. Both public graveyards now serialize card views and have compact inspectable UI lists; count/view consistency, AI-hand privacy and browser inspection are regression-covered. Exile remains count-only until face-down visibility is modeled.
Public-zone verification: 1,205 isolated backend tests, frontend lint/build/unit and the full loopback Chromium harness pass. A seeded three-game BO3 replay resolved in 60 turns without timeout, anomaly or drift. Browser checks open both graveyard trays and preview a card; visual layout on a dense long-session board still needs human review.
Spell-discard follow-up: supported discard effects now pause for the affected seat to select cards from its hand, following the default in [Comprehensive Rules 701.9b](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). Kolaghan's Command verifies opponent-seat choice, snapshot continuation and a later destruction mode; Izzet Charm verifies that newly drawn cards are eligible for the subsequent discard. AI chooses from the pending hand with its retention score, and random discard uses seeded RNG without a choice. The public API redacts AI-owned pending hand options, with HTTP and browser regressions. Another-player chooser wording, simultaneous choices and competing replacement/trigger ordering remain open.
Spell-discard verification: 1,210 isolated backend tests, frontend lint/build/unit and the full loopback Chromium harness pass. A seeded three-game BO3 replay finished in 60 turns with no timeout, anomaly or drift. This determinism smoke is not proof of broad discard or AI decision quality.
Simultaneous-discard follow-up: supported "each player discards N cards" effects now collect private choices in active-player order, preserve them across snapshots, and move all selected cards in one discard event batch. Delirium Skeins engine and two-seat browser fixtures cover this bounded path; AI chooses from its own hand. Another-player chooser wording, replacement-choice ordering and broader discard clauses remain open.
Simultaneous-discard verification: 1,213 backend tests passed in a disposable tracked-source checkout; frontend lint/build/unit and the full loopback Chromium harness passed. A seeded three-game BO3 replay resolved in 60 turns without timeout, anomaly label or drift. This does not certify arbitrary discard text or all simultaneous replacement interactions.
Revealed-hand discard follow-up: the supported Coercion wording now requires an opponent target and lets the caster choose a card from that opponent's revealed hand at resolution, including AI choice and snapshot continuation. The HTTP legal move presents revealed options while the ordinary AI hand remains hidden; the loopback browser casts and resolves Coercion through a labeled player-target control. Other reveal/chooser grammars and shared-device seat isolation remain open.
Revealed-hand verification: 1,216 isolated backend tests, frontend lint/build/unit and the full loopback Chromium harness pass. A seeded three-game BO3 replay resolved in 60 turns without timeout, anomaly label or drift. This is bounded Coercion-wording coverage, not general hand-reveal or multiuser secrecy certification.
Selective revealed-hand follow-up: the shared reveal chooser now filters hand cards by supported nonland and noncreature/nonland wording, while the public log records the entire revealed hand, including in the no-eligible-card case. Effect-sequence continuation applies Thoughtseize's life loss after a human choice or immediately when no card qualifies; the sole target becoming illegal prevents the whole effect. Thoughtseize and Duress fixtures use printed Oracle text; browser controls expose only eligible options. General reveal selection, alternate characteristics and competitive discard strategy remain open.
Diagnostic-AI follow-up: verbose head-to-head games now enable mechanic-choice windows, matching replay/live AI instead of using the engine's unattended fallback. Live start, restore and both batch-analytics paths also supply the opponent archetype; focused integration assertions cover live/restore/batch construction. Revealed-hand discard ranks cards from that player's perspective when known. This is a bounded hand-value heuristic; deeper matchup-specific discard planning remains open.
Selective-discard verification: 1,223 backend tests passed in a fresh isolated tracked-source checkout, including live/restore/batch AI profile assertions, full-hand reveal, filtered selections, snapshot continuation and sole-target illegality. Frontend lint/build/unit and the full loopback Chromium harness passed. A seeded three-game BO3 replay resolved in 60 turns without timeout, anomaly label or drift. The diagnostic Midrange vs Dimir Control seed 111 game exercised Thoughtseize with and without an eligible target and finished without a timeout. These small samples cannot establish strategic quality.
Additional reveal-filter follow-up: Inquisition of Kozilek's nonland mana-value ceiling and Despise's creature-or-planeswalker choice use the same reveal/selection path. Exact canonical wording, option filtering, snapshot continuation and browser controls are covered. Verification: 1,225 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded three-game BO3 replay (60 turns, no timeout, anomaly or determinism failure). Other hand-inspection restrictions, comparisons and strategically optimal discard choices remain open.
Reveal-to-exile follow-up: Appetite for Brains uses the same eligible-card choice with a printed mana-value minimum, but moves the chosen card from the revealed hand to exile without a discard event. Snapshot, AI, no-eligible-card, illegal-target and browser paths cover the distinct destination; a positive-control Liliana's Caress fixture checks that a real discard trigger still fires separately. Verification: 1,229 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). The chosen card is named in the public log; the separate exile-view follow-up below adds persistent face-up inspection.
Exile-view follow-up: public match responses include face-up exile card views and a total count, while an explicitly flagged face-down exile is count-only; its visibility survives snapshots and is cleared when that card leaves exile, including supported land/spell plays from exile. Both battlefield trays expose visible cards to hover/focus preview. Verification: 1,231 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). Face-down exile mechanics themselves remain unsupported, so this is a safe view boundary rather than full exile-rules certification.
- [x] Preserve mandatory plural-target admission for divided damage after mode-aware targeting changes. Pyrotechnics is not offered when both players have shroud and no damageable permanents remain; legal player recipients still retain their announced share if another target leaves before resolution.
- [ ] Complete [combat lifelink gain resolution](docs/audits/2026-09-28-lifelink-events.md). The strict Archive expected failure now passes: per-source gains use supported replacement handlers, multiple human choices resume through snapshots, and death state-based actions wait for those choices. Focused Nefarious Lich/Boon Reflection and double-strike fixtures now cover gain-to-draw continuation and separate damage windows. Cross-event ordering, nested draw-replacement choices and unsupported gain wording still need certification before checking off the full rule gate.
- [ ] Expand continuous layer/dependency, replacement/prevention ordering and can't-override fidelity.
- [ ] Cover simultaneous state-based actions, APNAP trigger choices and resumable nested effects.
Combat-trigger follow-up: trample-to-defender and blocker-to-attacker damage now emit combat-damage events, while self-damage triggers reject another source. Verification: 993 isolated backend tests, frontend lint/build/unit checks and a two-game seeded replay without drift or anomaly labels pass. Collecting all combat-damage triggers simultaneously and ordering them after applicable state-based actions remains open.
Damage-step batching follow-up: combat-damage events now enter the shared trigger-order path as one batch, with a two-hit human-choice and snapshot-resume regression. The 994-test isolated backend suite passed before the final test-only assertion, which passed separately; a two-game replay had no drift or anomaly labels. Combining combat-trigger stack insertion with death/state-based-action triggers at the complete Magic timing boundary remains open.
Audited next gate: [combat trigger timing audit](docs/audits/2026-09-28-combat-trigger-timing.md) reproduces a missing shared order choice between Ohran Frostfang damage and Grim Haruspex death triggers. A strict expected-failure test keeps the gap visible until durable cross-event staging, replacement-choice continuation and APNAP ordering are implemented. Validation: 994 isolated backend tests passed with exactly 1 expected failure.
Staging follow-up: the strict expected failure has been removed; persisted staging now groups that damage/death pair and focused APNAP and snapshot tests pass. A real-card human replacement-choice pause/resume, repeated SBA waves and browser continuation remain open, so the broader rule gate is not checked off.
Own-death follow-up: the shared collector now retains supported "when this creature dies" triggers after the source leaves the battlefield. A real Doomed Traveler combat regression resolves its printed flying Spirit token; generic token parsing separates its white color from its name and preserves color in snapshots/public views. Verification: 999 isolated backend tests, frontend lint/build/unit, full Chromium harness and a two-game replay without drift or anomaly labels pass. Named self-death variants and uncommon token clauses remain open.
Color metadata follow-up: live cache hydration now preserves card colors, including face-specific colors; hybrid mana symbols are parsed when canonical color data is missing, while Devoid remains colorless. Figure of Destiny, Ruination Guide and Valki/Tibalt regressions cover the boundary. Continuous color changes and broader face interactions remain open.
SBA-wave follow-up: ordinary state-based action checks now repeat after battlefield changes and stage generated triggers until stable. Elvish Clancaller/Llanowar Elves and Grim Haruspex fixtures cover cascading lethal toughness and a shared, snapshot-restored trigger-order choice. Human replacement choices across simultaneous deaths and a browser continuation still need certification.
Replacement audit: [death-replacement boundary](docs/audits/2026-09-28-death-replacement-boundary.md) identifies the separate sequential combat-death path, missing canonical Rest in Peace graveyard replacement semantics, and tests that assign altered text to real card names. Converge the paths and replace those fixtures before certifying simultaneous human replacement choices.
Replacement follow-up: combat lethal checks now delegate to shared SBA, and simultaneous default destinations are chosen before any source leaves. Canonical Lorcan/Warlock and non-Warlock cases test the general subtype clause and batch timing. The old `combat_die` resume branch remains for saved snapshots; human multi-choice batches remain open. Non-death graveyard moves and altered Rest in Peace fixtures were addressed in the later follow-up below.
Rest in Peace gate: two strict real-card expected failures reproduce graveyard replacement missing for battlefield death and hand discard. Do not treat the existing altered-text fixtures as certification. Unify destination evaluation across stack resolution, discard, costs, milling/dredge, cycling and effects before removing the expected failures.
Rest in Peace follow-up: the shared destination path now covers the identified direct non-death graveyard writes, death destinations see global "from anywhere" replacement before source removal, and the entry trigger exiles existing graveyards through the stack. The two strict expected failures were removed after passing; focused fixtures cover death, hand discard, cost discard, cycling, dredge milling, stack resolution/countering, 0 loyalty and simultaneous enchantment destruction. Five older Rest in Peace fixtures were corrected to canonical text. Broader replacement ordering and other synthetic fixtures remain open.
Live-route replacement evidence: HTTP action and SQLite-restore tests now cover Lightning Bolt exiling Doomed Traveler without its dies-trigger Spirit, and casting Rest in Peace with both graveyards occupied, including the ETB stack trigger. This closes the bounded live HTTP restart-parity check for these interactions, not simultaneous human replacement choice or every graveyard replacement family.
Opponent-card replacement follow-up: Leyline of the Void's verified Oracle clause now uses card ownership (not battlefield control), excludes tokens, and applies to supported discard, resolved-spell and death paths; a simultaneous enchantment destruction fixture preserves source visibility until destinations are chosen. An HTTP action/SQLite-restore case covers an opponent-owned spell. Simple Leyline opening-hand permission is now supported; conditional/reveal pregame families, competing replacement ordering and broader family certification remain open.
Token-lifecycle follow-up: generated tokens now leave non-battlefield player zones on the next SBA check and retain only an internal ceased/source record; ordinary death, exile replacement, snapshot and Bastion dies-trigger fixtures pass. Effects that attempt another zone move before the next SBA check and token-copy edge cases are not yet certified.
Token-transfer follow-up: a shared token predicate now guards supported graveyard returns, recasts, dredge, escape payments, mass graveyard exile and hand discard before SBA. Card instances and snapshots preserve immutable token identity even when type-changing effects remove the legacy `Token` marker; nontoken trigger and public-view regressions cover this case. Same-resolution library/exile transfers and token-copy edge cases still need a shared transfer audit.
Token-hand follow-up: activated/additional discard costs, Ninjutsu, legal move generation, exile play permission and supported hand-to-battlefield effects now reject departed tokens before SBA. A generated land-token fixture proves the former discard-cost admission failure and checks that no land action or effect can replay the token. Direct library/exile transfers remain distributed across handlers and require a transfer-level design audit.
Transfer audit: [token zone-transfer boundary](docs/audits/2026-09-28-token-transfer-boundary.md) inventories the remaining direct mutation paths and defines the event-ordering and snapshot acceptance gate. Only hand/graveyard second-move failures have been reproduced; library/exile paths are unverified, not labeled confirmed bugs.
Search-destination follow-up: canonical Entomb and Buried Alive patterns exposed a distinct parser gap: unrestricted card searches had no eligible cards, and creature searches to graveyard moved them to hand. The search filter now admits any card for the unrestricted wording and routes selected cards through the shared graveyard destination helper, including Rest in Peace replacement. Human selection survives a snapshot; an HTTP action regression covers the Entomb choice. Other library-search destination grammars and full clause fidelity remain open.
Search-quantity follow-up: rule 701.23d requires finding an available card when an unrestricted search says "a card"; Entomb's HTTP choice now rejects zero cards and the UI disables that selection. Buried Alive's "up to" flag survives inference and lets AI choose zero under Rest in Peace rather than exiling three creatures. The search parser anchors optionality and destination to the sentence containing the search. Qualified hidden-zone searches may still fail to find; broader quantity/destination grammars and simultaneous replacement choices remain open.
Hidden-information follow-up: unrevealed hand searches no longer disclose found names in the public log (Demonic Tutor fixture), while reveal/public-zone searches retain their public names. Expressive Iteration-style top-card choice logs likewise omit the unrevealed hand and bottom cards while naming the publicly exiled card; an isolated HTTP regression reproduced and then verified the repair. AI-owned pending mechanic choices redact options, effect payload and library order from public match responses; the internal AI choice remains intact. Human-vs-human still lacks per-seat authorization and earlier saved logs are not retroactively sanitized.
Loyalty/X and land-animation follow-up: a seeded Dimir/Ramp trace exposed Ramp passing with a legal fixed-cost planeswalker because AI cast materialization borrowed X from later loyalty text. It also exposed Unicode `−X`/`−10` being parsed as positive loyalty costs, an unimplemented colored-permanent X mass exile, and a real `target noncreature land` clause missing the existing animation parser. Shared cast-cost, loyalty-sign, color/mana-value and target-pattern paths now handle these bounded cases. Canonical Ugin, Nissa and colored/token fixtures cover them; two seeded games finish 1-1 without parser-fallback, invalid-target, timeout or decision-quality flags. This small replay does not prove optimal loyalty choices: the AI still needs board-aware scoring for X sweeps versus +loyalty lines, and other Oracle wordings remain uncertified.
- [ ] Test live HTTP and diagnostics against shared fixtures; parser classification alone cannot satisfy this task.

Acceptance: expected zones, choices, stats, timing, triggers and outcomes match fixtures and replay/restart state.

### 12. Measure and improve decisions across archetypes

- [ ] Establish per-archetype before/after decision metrics using full hand/board/legal-action traces.
- [x] Use the shared counterability check to conserve supported pure counters, prefer counterable opposing targets and reduce ineffective pure counter-mode scores without removing legal human targets. Canonical repeated decisions, tax counters, compound mode preservation and four full-state baseline comparisons cover this [bounded increment](docs/testing/ai-counterability.md).
- [ ] Plan removal of a battlefield protector before countering and value arbitrary secondary effects. Expand conditional/granted protection and ability-removal fidelity before claiming broader counter intelligence.
- [x] Fix bounded generic pending-removal conservation using announced-stack rules projection, not card-name exceptions. Prefer uncovered threats or pass while removal is sufficient, and preserve backup against a known counter/pump response. Add `redundant_removal_casts` with unavailable legacy/malformed/unknown-choice evidence. The original Dimir/Tempo seed 711 burst is reproduced by the baseline agent and corrected by the updated agent; see [acceptance and limits](docs/testing/ai-pending-removal.md). Arbitrary secondary effects and broader prevention/protection planning remain open.
- [x] Extend per-decision traces with stack objects and their saved spell-copy characteristics, announced targets, source last-known information and engine-detected counterability. Shared producer/consumer and surviving-copy regressions cover this increment; complete semantic coverage and every counter timing decision remain unverified.
- [x] Avoid unproductive pure single-target destruction against indestructible or friendly permanents even without pending removal, across spell, selected-mode, activated and loyalty target materialization. Verify remaining selected-mode candidates instead of stale mode metadata. Canonical Naturalize, Doom Blade, Abrade, Thrashing Brontodon and Vraska fixtures establish this [bounded increment](docs/testing/ai-destruction-targets.md); Slice in Twain preserves its secondary draw against a legal indestructible target.
- [x] Recognize supported unanswered winning self-removal lines using legal action admission, actual costs, stack, death triggers and replacements. Resolve only own choices with an isolated configured AI policy; stop at undeclared opposing choices and hidden-zone movement. Canonical Murder/Bastion, Blood Artist choices, Thrashing Brontodon sacrifice costs and Vraska loyalty fixtures establish this [bounded increment](docs/testing/ai-self-removal.md). Preserve recurring sacrifice payoffs separately from spent entry rewards.
- [ ] Expand removal conservation to arbitrary compound/modal clauses, profitable secondary effects and nonterminal self-removal. Add opponent response search and deeper combo planning; certify further prevention, protection and replacement responses without treating unknown projections as certain outcomes.
- Counter-target trace follow-up: two seeded Tempo/Blue Control games exposed Tempo countering its own Lightning Bolt with Spell Pierce twice because the target chooser returned a friendly stack object when it was the only legal option. Shared ordinary/modal AI counter materialization now requires an opposing target unless printed text explicitly requires one it controls. Real Spell Pierce and Counterspell tests cover holding the counter with only a friendly spell and countering an opposing spell when both are available. The same seeds finished with zero self-counter tax-loss lines, invalid-target lines or timeout; both winners remained Blue Control. Verification: 1,367 isolated backend tests, frontend lint/build/unit and the full isolated Chromium harness pass. This is a bounded decision correction, not matchup balance evidence.
- Shared-draw tactical follow-up: Master AI previously forced Vision Skeins into an empty opposing hand and into its own empty library. Exact each-player draw casts now pass a hand/library-state screen before forced end-step and stall-conversion heuristics; regressions cover five archetypes and Prosperity's X draw while retaining an opponent-decking line. This is a local decision correction, not the unchecked cross-archetype trace matrix or an expert-AI certificate.
- Source-density follow-up: a color-source count of all 11 built-ins found Dimir Control with 4 black lands for 18 black spell copies and Tempo with 4 red lands for 16 red copies; Blue Control, Burn and three-color Midrange also had avoidably strained mana. Three additional Scryfall-verified original duals and redistributed basics raise access without adding unsupported conditional-entry rules. The catalog invariant now requires at least half as many land sources as spell copies of a color (minimum four); this is a screening heuristic, not a probability model. Same-seed two-game Tempo/Dimir shifted from 2-0 to 1-1, and two games each of Midrange/Drain and Burn/Blue Control played the added sources without timeout. Larger seed/seat-balanced decision analysis remains open.
- Built-in mana-base audit: catalog-wide seed/cost/source inspection found Ramp had no blue source for Growth Spiral/Hydroid Krasis, Drain had no red source, Tokens had no green source, and Tribal had no black source. Five verified original dual lands now provide those colors without an unsupported conditional-entry approximation; an invariant covers all 11 built-ins. Saved built-in and expansion templates refresh changed mainboards in place and preserve deck IDs, with user-deck isolation and expansion idempotence tests. Two-seed Ramp/Tokens after the change cast Growth Spiral and March of the Multitudes and finished 1-1, while two-seed Drain/Tribal cast Claim the Firstborn, Dreadhorde Butcher and Shaman of the Pack without timeout. These small samples do not prove deck balance or optimal AI. Format-specific legality and conditional shock-land choices remain open.
- X-loyalty follow-up: the Ramp/Dimir trace showed an artificial X=3 cap that stranded a legal colored-permanent sweep against mana-value-6 and mana-value-4 threats. For the supported mass-exile effect family, AI now simulates only meaningful X breakpoints, evaluates the resolved board after loyalty payment and friendly losses, and forces a sweep only above a bounded gain threshold. Real-card tests cover a profitable X=6 line and a low-value no-force line; two same-seed games use X=6 and X=4 with zero timeout, invalid-target or parser-fallback lines. The sample shifted from 1-1 to 2-0, which is not balance evidence. Other X-loyalty abilities and opponent-response-aware valuation remain open.
- Single-target damage follow-up: two seeded Dimir/Ramp games showed Ugin's +2 AI activation announcing both a player and creature; the resolver silently used the creature, marking 3 nonlethal damage on a 5/6 each turn. Shared external admission now rejects dual declarations for a single "any target" clause, and AI materialization selects only one. For fixed damage, it prefers an opposing creature when the hit is lethal and a player otherwise. Real Lightning Bolt fixtures check both choices and admission; the same two games still finish 1-1 with zero invalid-target/parser-fallback lines. This is bounded targeting evidence, not a general removal or race planner.
- [ ] Evaluate land drops, mana sequencing, lethal opportunities, bad attacks/blocks, engine protection and interaction windows.
Partial blocking evidence: a five-attacker banded-board regression found that large-board AI fallback assigned a ground blocker to a flyer; legality filtering and band-aware prevented-damage scoring now pass 983 isolated backend tests. A seeded two-game Burn/Dimir Control BO3 has zero timeout, anomaly label or determinism drift. This does not close broader archetype decision-quality measurement.
Further blocker restriction coverage: small-board search and large-board fallback now use the engine's numeric minimum-blocker count, with real Guile three-blocker and unblocked-choice fixtures. Verification: 985 isolated backend tests and a seeded two-game Burn/Dimir Control replay without timeout, anomaly or deterministic drift. This remains a bounded AI legality repair, not proof of optimal combat.
Graveyard-tutor decision follow-up: a real-card Reanimate/Griselbrand fixture reproduces the AI choosing Swamp for a graveyard search. Destination-aware ranking now selects a reanimation target instead of applying hand mana-fixing scores; with Rest in Peace present, it avoids exiling that premium target. Midrange and Reanimator decisions, plus snapshot restore, are covered. Verification: 1,031 isolated backend tests; a seeded Tempo/Dimir Control BO3 resolves without drift at 3,000 ticks, while a 1,200-tick cap truncates one long game. Other graveyard synergies and broader matchup quality remain unmeasured.
Land-target crash follow-up: a three-deck replay exposed an unassigned variable in AI land-only target materialization. A Nissa-style loyalty regression fails before the repair and passes afterward; 1,035 isolated backend tests pass. Tempo/Dimir Control/Ramp replay covers three seeded pairs with zero crashes or determinism drift. Tempo/Dimir reaches the 1,600-tick cap at turn 57 but resolves at turn 65 under 3,000 ticks, again without drift. Broader long-game behavior and decision quality remain open.
Decision-trace follow-up: `debug_head_to_head.py` now uses the shared authoritative trace builder rather than an incomplete duplicate, so its card-play analyzer can assess all five decision metrics when evidence is valid. Rich board traces include effective keywords and marked damage. One original random Tempo/Dimir game reported a bad block but lacked a saved seed/state; two subsequent random games showed zero bad blocks, so the original is not classified as an AI error or analyzer false positive. A reproducible `--seed` option records per-game seeds; two 600-tick runs matched card/action sequence but not raw generated stack IDs. Verification: 1,037 isolated backend tests and two complete traced games. Next: capture anomalous-state snapshots and inspect repeatable bad-block cases before tuning combat AI.
Seeded stack-target follow-up: a five-game Tempo/Dimir run at seeds 100-104 reproduced one bad-block warning. Seed 100 showed a graveyard Sheoldred still listed on the battlefield after Counterspell targeted its draw trigger; the ghost then entered AI blocking analysis. Counterspell now targets only spells, and Stifle-style activated/triggered ability counters target abilities without moving their source. Focused legal-move, rejected-cast and direct-handler tests pass; 1,039 isolated backend tests pass. The same five seeds all resolve, max one Sheoldred is reported on the battlefield, and bad blocks fall from one to zero. This validates the reproduced failure only; optional copy retargeting, arbitrary ability families and independent combat quality remain open. The later copy-stack increment in Gate 2 addresses basic copy timing separately.
Negate follow-up: canonical Negate's noncreature counter text previously inferred a no-op despite presenting stack targets. It now maps to a guarded counter effect; direct ordinary and conditional handlers reject creature spells. Focused parser, hint and handler regressions plus 1,040 isolated backend tests pass. Other conditional counter clauses and unusual target grammars remain open.
Drown/corpus follow-up: canonical Drown in the Loch had a structured counter mode but did not filter stack targets by mana value versus the targeted spell controller's graveyard count. Selected-mode restrictions now apply to stack targets, including announced X, and are rechecked at resolution; a direct counter handler call also honors the restriction. Verification: 1,043 isolated backend tests; five seeded Tempo/Dimir games using a disposable backup of the canonical local cache all resolved (2-3), with four Drown casts and no invalid-target/missing-inference logs. One earlier seed-100 game resolved but never cast Drown and is not rules evidence. A local read-only corpus comparison found 61 of 81 handwritten fallback Oracle texts differ from local canonical cache (some may be formatting-only). The fallback Drown entry is materially simplified, so empty-cache simulation remains untrustworthy until verified canonical offline data replaces approximations. Next: ship a provenance-backed built-in corpus, remove invented fallback text from gameplay, and compare empty-cache versus synced match behavior.
Offline corpus follow-up: a bundled 87-card Scryfall-ID-backed seed now replaces the handwritten fallback entries and covers all 81 distinct built-in deck cards plus six extras. The exporter is read-only and reproduces the tracked JSON byte-for-byte from the local synced cache. Four planeswalker loyalty values were verified against Scryfall's exact-name API because CardCache omits loyalty. Face image URIs are omitted from the offline seed; gameplay fields match cache-backed hydration across all 87 locally, while explicit cached zero stats retain precedence. An initial seed-100 Tempo/Dimir offline/cache replay diverged because `debug_head_to_head.py` duplicated and truncated cache hydration; after switching it to the shared live hydrator, both runs match winner, turn/tick count, life and normalized action sequence. Verification: 1,044 backend tests pass in an empty-cache tracked-source copy. This repairs the known invented-fallback-text path but does not certify every Oracle effect clause or arbitrary custom cards; broader seed/seat parity and unsupported-mechanic audits stay open.
Canonical-effect follow-up: the corpus classifier reported Memory Deluge as structured even though it resolved as one draw. A reusable mana-spent top-card-to-hand effect now handles its normal and printed Flashback costs, persisted human/AI choice, non-draw movement and random-bottom order. The cost system now admits printed Flashback from graveyard and exiles such spells on resolution or countering. Focused tests and a two-game seeded Dimir Control vs Ramp replay pass, including normal and Flashback selections; unusual mana-spent changes, other Flashback clauses and broad AI-quality impact remain open.
Reminder-text follow-up: quoted token abilities and parenthetical explanations could be parsed as executable effects or activated abilities on the source card. Effect inference, target hints, trigger discovery and activated-ability extraction now exclude reminder text; the unsupported-trigger placeholder is an explicit no-op. Bloodtithe Harvester and Witch's Oven regressions establish the boundary, not full card support. The named artifact-token gap found here is addressed in the bounded follow-up below; player sacrifice choices remain open.
Activation-timing follow-up: printed "Activate only as a sorcery" clauses now gate both legal moves and direct actions before costs, while unrestricted abilities retain instant-speed activation. Generic turn/step/stack tests pass; once-per-turn and other specialized activation restrictions remain open.
Named artifact-token follow-up: executable reminder text remains excluded from the creator card, while a printed artifact-token definition can now supply the created token's own ability. Food and Blood creation, payment, activation, snapshot restore, token ceasing and Witch's Oven's effective-toughness threshold have focused regressions. Two seeded Drain vs Midrange games finished without stalls and used Food, but are not balance evidence. Open: named tokens without source definition, player choice of sacrificed permanent, and Cauldron Familiar's Food graveyard activation. Reflection's copy-token effect and Fable's Goblin attack ability were gaps found here and are addressed in the bounded follow-ups below. These are distinct token semantics, not evidence that Food/Blood support covers all tokens.
Creature-copy follow-up: Reflection of Kiki-Jiki-style activated text now offers only other nonlegendary friendly creature targets, rejects illegal or stale targets, copies base card characteristics without counters, adds haste as printed, and sacrifices the copy at the next end step even on the opponent's turn. Two same-seed Drain vs Midrange replays completed (seeds 61 and 62) with zero previous Reflection inference misses; outcomes are not balance or optimality evidence. Open: full copy/layer interactions and unsupported copy targets outside this printed family. Fable's Goblin attack trigger is addressed in the token follow-up below.
Printed-token follow-up: a checked-in Scryfall-ID-backed seed supplies exact Food, Blood and Treasure definitions without inventing Oracle text. Created creature tokens retain quoted abilities, so Fable's chapter-I Goblin attack trigger creates Treasure. Shared nonland mana payment recognizes any-color Treasure and pays its printed self-sacrifice cost. A direct chapter-to-attack-to-colored-payment regression passes; three seeded Midrange vs Drain games completed with Treasure creation and zero inference misses, but are not balance evidence. Manual activation now uses the same supported source/cost eligibility as automatic payment: humans can select a produced color on ready mana creatures or Treasure, with checked seat/color admission and HTTP/browser regressions. Open: token definitions beyond the three verified entries, multiple distinct mana abilities on one source, activation mana costs, variable mana quantities, and precise ordering of triggers caused during mana-cost payment.
Fixed-output follow-up: Sol Ring's `{C}{C}` and Llanowar Tribe's `{G}{G}{G}` now produce their printed amounts in manual activation and automatic cost payment, with leftovers retained in the pool. Public card views expose the amount and the human control labels it; a browser fixture exercises Sol Ring. This does not handle mixed/variable outputs or multiple abilities on one permanent. The flexible-source affordability gap found here is addressed in the next follow-up.
Source-allocation follow-up: affordability removes each physical source when used, so one Treasure cannot count toward both `{R}` and `{G}`. A later shared allocation search now drives both precheck and actual payment for supported fixed-output sources. Hallowed Fountain plus Marble Diamond can pay `{W}{U}` despite land-first greedy order, and Gilded Lotus surplus pays generic cost. Legal-move, precheck, payment and failed-payment regressions pass. Verification at that step: 1,260 isolated backend tests, frontend lint/build/unit, complete Chromium harness and one seeded three-game replay without reported timeout/anomaly/drift. Later hybrid and Phyrexian follow-ups below extend the planner; mixed or variable outputs, multiple abilities per source and exact mana-trigger ordering remain open. This is not all-mana-rules certification.

Hybrid-cost follow-up: payment planning enumerates supported two-part hybrid choices (`W/U`, `2/W`, `C/W` forms) and applies generic modifiers after choosing each branch. Mana value uses the largest hybrid component under [Wizards' Comprehensive Rules 107.4e and 202.3f](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). Tracked Spectral Procession fixtures cover three-white and six-generic routes, legal-move exposure, two-color alternatives and a reduced monocolored-hybrid branch. A later human cast control exposes each printed branch; explicit choices are validated against the selected cost option and affordability before payment, while AI/older clients retain automatic payment. Shared cost-option views extend this to permitted graveyard, exile and top-library casts. Payment source selection remains automatic. A later Phyrexian follow-up supports colored-mana or two-life branches for ordinary and hybrid Phyrexian symbols in the shared planner; human cast and activated-ability controls can announce the life branch. Additional life costs are reserved together, life-paid triggers from casting are staged above the spell, and low-life checks reject unaffordable branches. Human choice for Phyrexian cycling, other loyalty-entry replacement interactions, snow-source provenance and other alternative-cost interactions remain open.

Phyrexian verification: 1,271 isolated backend tests, frontend lint/build/unit, complete Chromium harness and one seeded three-game replay without reported anomaly or determinism drift. A browser regression found that target selections from a previous match could leak into a new match's cast form; per-card draft choices now reset on match change. These checks establish the supported cost paths, not universal Phyrexian-card semantics.

Activated-payment follow-up: legal moves, checked actions, payment and human controls now carry explicit hybrid/Phyrexian branches for supported activated abilities. A real Pestilent Souleater fixture verifies black-mana and two-life choices, rejection without mutation, and browser/API submission. Its self-granted infect now uses a reusable temporary single-keyword effect, persists through snapshots, expires at cleanup and does not apply if the source leaves play before resolution. Verification: 1,272 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded three-game replay without reported anomaly or determinism drift. No fabricated Phyrexian cycling card was added; cycling remains automatic, and other activated-effect families still require verification.
Any-one-color quantity follow-up: verified Gilded Lotus text now supplies three of the chosen color through the shared nonland output model; the same amount appears in manual controls, affordability, and automatic payment. A browser fixture exercises its three-red-mana activation. Variable amounts, any-combination output, mana-costed activation, and multiple different abilities on one permanent remain open.
Compleated follow-up: the cast payment planner records how many Phyrexian symbols used life, carries that count on the spell stack payload through snapshots, and applies two fewer entry loyalty counters per such symbol to a compleated planeswalker, matching [Wizards' rule 702.150a](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). A printed Tamiyo, Compleated Sage fixture checks the life and mana branches, countering, resolution and printed-loyalty restoration after leaving play. The browser harness also casts both branches through the API and asserts the displayed loyalty; its launcher now selects the backend venv explicitly. Verification: 1,273 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded two-game replay without reported anomaly or determinism drift. Other interacting entry replacement effects remain open.
Snow-mana follow-up: fixed-output mana from snow sources keeps its color and source provenance in a per-player subset pool. `{S}` is a snow-source requirement, not generic mana; the shared planner reserves it before paying colored and generic costs, while leaving ordinary mana to pay other costs first. Manual land/nonland taps, effect mana, automatic payments, snapshots, step clearing and the public pool view now carry that distinction. Snow-Covered Forest, Boreal Druid and Icehide Golem fixtures check legal and illegal payment through engine and browser/API paths. This follows [rule 107.4h](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). Verification: 1,278 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded two-game replay without reported anomaly or determinism drift. Snow-spend-dependent effects, dynamic source types and unusual mana abilities remain open.
- [ ] Extend bounded multi-turn planning, hidden-information estimates and sideboard plans using demonstrated mistakes.
- [ ] Cover control, tempo, aggro, ramp, tokens, tribal, midrange, drain and combo-style decks rather than tuning one archetype alone.

Bounded AI sideboarding increment: AI seats with supplied sideboards now make at most four swaps from hydrated Oracle text and a conservative mana-source check. Against a human, the plan uses only opposing public battlefield, graveyard and face-up exile types, not hidden hand or internal archetype. Full AI testing may use its known matchup archetype. Next-game HTTP, autoplay transition and SQLite restore regressions pass. Verification: 1,257 isolated backend tests, frontend lint/build/unit, complete Chromium harness, and one seeded three-game replay with no reported timeout/anomaly/drift. No built-in sideboard templates were added; card-name-free text scoring is limited to common removal, counters and sweepers and is not a measured strategic improvement. The planning checkbox stays open.

Observation-memory follow-up: each persisted action and each autoplay tick records opposing types seen in public battlefield, graveyard, face-up exile or stack. The type-only record survives SQLite restore and lets game-two AI respond to a publicly seen card that later returned to hidden hand, without reading a never-revealed hand card. Verification: 1,258 isolated backend tests, frontend lint/build/unit, complete Chromium harness and one seeded three-game replay without reported timeout/anomaly/drift. This is still a coarse type signal, not per-card tracking or expert sideboard planning.

AI color follow-up: opening-hand checks count only mandatory colored pips for supported hybrid and Phyrexian costs; a hand with Islands and `{W/U}` or `{B/P}` spells is not rejected solely for missing white or black, while fixed-white spells still require white. Land-selection demand distributes optional hybrid colors. Earlier two-part-hybrid verification passed 1,265 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded three-game replay without reported timeout/anomaly/drift; Phyrexian handling is covered by the later regression gate. Broader mana-base optimization, life budgeting and strategic payment-branch choice remain open.

Acceptance: each AI change has concrete decision evidence and regressions; no strength claim based only on completing games or winning a small sample.

### 13. Run seeded matrices and replay/restart gates

- [x] Make replay matrices seat-balanced by default with explicit seeded workload, timeout denominator, per-game provenance and anomaly traces. Repeated determinism executions are not independent samples. Live and diagnostic series now share loser/draw chooser and seed policies, record starters and stop replay at an unresolved timeout. Diagnostic sideboarding, strategic play/draw selection, mulligan-round ordering, broader live-transition parity and statistical certification remain open. See [the protocol](docs/testing/seat-balanced-replay.md).
- [x] Distinguish legal conditional-counter nonpayment from repeated recent cost failures in timeout labels; one early Spell Pierce counter no longer converts a late tick-cap timeout into `timeout_rules_issue`.
- [x] Remove automatic combat-damage shortcuts from live and diagnostic turn loops; focused live/replay tests preserve first-strike and regular-damage priority windows. A seeded Tempo/Dimir BO3 finishes without drift or anomalies at 3,000 ticks; this is not a broad matrix or AI-quality result.
- [ ] Predefine sample sizes, seed schedule, seat balancing and long-game timeout policy.
- [ ] Run representative then full supported-corpus BO3 matrices, retaining detailed anomalous-game traces.
- [ ] Report confidence intervals, rules/cost/target errors, illegal attempts and explained timeouts.
- [ ] Validate deterministic replay and snapshot restart equivalence, with first-divergence drilldown.

Gate 2 exit: no unexplained supported-corpus rules/cost/target stalls; reproducible replay/restart; measured decision improvements and transparent uncertainty. Small deterministic smoke results remain smoke evidence.

## Gate 3: Packaged release and operational hardening

### 14. Test production API and media routing

- [x] Default production routing to same-origin `/api`; keep an explicit backend-origin override.
- [x] Align card-media routing and remove implicit HTTPS-to-HTTP mixed-content behavior from the default.
- [x] Test the built artifact under a local HTTPS proxy for `/api` and `/card-images`, then rebuild for a separately configured HTTPS backend origin.

Evidence: `frontend/tests/production_proxy_smoke.py --browser --cross-origin` passed in a disposable backend checkout with empty initial SQLite/cache and a temporary self-signed certificate. Both modes passed Chromium `Backend online`/deck loading and HTTPS health, import, match start/action and media requests. Frontend build/unit checks pass. The script restores the default build. This does not prove a real trusted-certificate LAN deployment, multiuser security or long-session behavior.

Acceptance: health/import/start/action/media work under both documented deployment modes; Vite development proxy success alone is insufficient.

### 15. Bound jobs and concurrent mutations

Single-process batch admission now shares one slot across synchronous and background-job routes. A second request gets structured 429, and failure paths release the slot. Background jobs now support cooperative cancel at the next AI action, preserve completed-match progress, and release the slot on worker exit; no partial results are published. This does not provide a queue, durable retention, multiworker coordination or network authorization; the larger job-control checkbox remains open.
The in-memory simulator history is capped at 20 terminal jobs while old result lookups fall back to SQLite. Startup loads only recent rows plus unfinished jobs, which are marked failed after restart. New background starts now have a 10,000-row persisted quota, after durable start-key replay/conflict checks; existing rows are not deleted. Offline retention tooling exists, but automatic retention, byte quotas and measured load guarantees remain open. See [job quota](docs/testing/simulation-job-quota.md).

- [ ] Define single-process local topology and network exposure policy explicitly.
- [x] Add cooperative cancellation and restore active simulator polling after a browser refresh.
- [x] Recover ambiguous simulator starts with durable idempotency-key replay and reject conflicting reuse.
- [ ] Add bounded job queues/quotas, database retention and documented crash/restart behavior.
- [x] Add single-process per-match locking/versioning and stale-write checks; simultaneous retry, storage rollback, receipt restoration and detached-read regressions cover the implemented coordinator. Legacy clients may omit write headers; this is not distributed locking, authorization or multiworker certification.
- [ ] Add authentication/authorization and restricted origins before supporting network access beyond a trusted single-user setup.
- [ ] Upgrade vulnerable dependencies deliberately against current advisories; retest without blind forced upgrades.

Acceptance: mutations cannot corrupt concurrent state; job floods remain within measured limits; network authorization/origin policy matches the documented deployment. Keep development servers private during this work.

### 16. Verify installation and long-session operation

- [ ] Test clean-machine dependency install, offline fallback and backup/restore.
- [ ] Test backend restart recovery and supported worker topology.
- [ ] Run browser soak tests, accessibility/error-boundary checks and replay inspection flows.
- [x] Bound saved-match and diagnostic-run history previews to three rows with incremental expansion, collapse and scrolling; verify both controls through the browser. This does not replace long-session/soak acceptance.
- [ ] Reconcile README features/limitations, changelog and Graphify with final verified behavior.

Gate 3 exit: reproducible install, HTTPS/API/media smoke, bounded jobs, restart/data recovery, long-session usability and dependency/security review all pass.

## Completion and reporting

Work remains open until its acceptance evidence is recorded. A milestone report must include changed files, checks and artifacts, remaining risks and manual-review needs. This documentation update does not close any implementation checkbox.

The scoped release is finished only after all three gates pass. Any remaining unsupported mechanics must be explicitly visible and documented. Full Magic rules completeness and arbitrary-deck expert AI are not implied by that scoped release.

## Known Limitations and Next Upgrades

Current priority is backend rules, supported-corpus simulation and measured AI decisions. The competitive table v2 is integrated; functional human choices and priority controls retain regression coverage. Long-session UI, accessibility, broader rules fidelity, knowledge-driven AI, statistical validation and operational release checks remain open, alongside unfinished human-release acceptance gates.
