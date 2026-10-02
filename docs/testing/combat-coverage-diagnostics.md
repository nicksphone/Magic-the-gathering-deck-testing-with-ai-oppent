# Static combat coverage and live diagnostics

## Implemented

Supported static conditions now use one immutable-text parser and one live-state
evaluator for combat and attachment readers. Coverage checks reuse that parser
rather than guessing a board state. Runtime truth can be false while the predicate
is supported; an unrecognized predicate remains unknown, not false.

Known unsupported combat bodies, subjects, conditions and payment clauses reach:

- Card completeness: `unsupported_mechanics`, `combat_clause_gaps`, and existing
  `rules_coverage: known_unsupported` labels.
- `/simulate/batch/preflight`: deck/card/face-specific clause details and reason
  tags. The existing simulator UI requires explicit exploratory review.
- Batch results: the same shared `rules_coverage` report.
- `GET /matches/{match_id}/rules-diagnostics`: locked, read-only public battlefield
  inspection with revision, source provenance, active/unresolved combat constraints,
  printed coverage gaps and supported printed-ability-suppression status.

The live endpoint deliberately does not enumerate hand, library, graveyard or
exile cards. Printed coverage gaps are separate from current active constraints:
a suppressed source may retain a printed semantic gap without applying a rule.
The endpoint is not an authorization system or a network-release certificate.

Canonical fixtures cover Propaganda, Ghostly Prison, Sphere of Safety and Archon
of Absolution's supported numeric payments; Norn's Annex's now-supported
Phyrexian payment; Collective Restraint's unsupported domain-dependent tax;
Stormtide Leviathan's unimplemented
qualified subject; Silent Arbiter's declaration limits; and Goblin War Drums'
already-supported keyword grant/reminder. Fetch provenance is retained in
the combat coverage/payment/minimum fixture files. No card-name gameplay dispatch or
fabricated competitive deck additions were introduced.

Known supported clauses from the previous nine-card conditional-combat fixture
remain unflagged. Triggered text and quoted granted abilities are not mistaken
for a source's unconditional static restrictions. Face diagnostics preserve
actual face names/indices, while reason tags are deduplicated.

## Validation

`tests/test_combat_coverage_diagnostics.py` checks coverage/runtime recognition
parity, canonical positives/negatives, root/face provenance, both-seat HTTP
privacy/read-only behavior, SQLite restoration, real preflight routing and
cached completeness without external sync. Tests run in isolated source copies,
not against the live database.

`frontend/tests/browser-combat-coverage.mjs` uses the actual App and production
preflight route with a canonical cached Collective Restraint fixture. It checks that the
warning and exploratory-review button appear without creating a simulator job.
The fixture routes exist only in the guarded, copied browser fixture server.

Verified 2026-10-02: 2,860 full backend tests passed (310 deprecation warnings),
127 focused coverage/condition/cache checks passed, and frontend lint/unit/build
passed. The full Chromium harness passed including the new canonical admission
check, recovery and natural AI/human BO3 flows. Twelve logical seat-balanced games
each repeated twice produced zero determinism failures, drift labels or reported
anomalies. These checks are not fresh-install, visual or broad AI-strength proof.
Evidence, including the earlier missing-import and DOM-serialization test
failures, is archived under RCHFiles
`diagnostics/combat-coverage/20261002T065310Z`; only final passing runs count here.

## Known Limitations and Next Upgrades

- Attack/block taxes were reported, not implemented by this milestone. Subsequent
  [declaration work](declaration-limits.md) implements unconditional numeric limits;
  conditional limits and broader costs remain unsupported. Subsequent
  [payment/target work](combat-payments-requirements.md) handles numeric attack taxes.
  Exploratory simulation can still produce inaccurate
  results for those cards; direct API clients must inspect coverage themselves.
- This classifier detects known static grammar gaps, not all missing clauses,
  replacement interactions, arbitrary gained abilities or complete Magic rules.
  An empty report remains `exploratory`/`not_certified`.
- Full compound predicates, dependency/type/color layers, targeted requirements,
  combat payment choices and strategic AI remain open. Recognized each-combat
  requirements now use the subsequent declaration solver.
- The dedicated in-match visual diagnostics interface belongs to the deferred
  UI work. Existing preflight warnings are functional coverage, not a redesign.
