# Conditional static admission and opponent resources

## Implemented Scope

Supported `an opponent has N or more cards in their graveyard` and `an opponent
has N or less life` predicates are evaluated from live state relative to the
source's current controller. Graveyard counts exclude tokens. Self stat/keyword
instructions reuse the existing continuous layer, combat keyword consumers and
AI entry projections; predicate values are never cached. Canonical regression
cases are Thieves' Guild Enforcer and Guul Draz Vampire, not name-based handlers.

Conditional self/team static coverage now uses the runtime instruction compiler
and shared predicate parser. Unrecognized predicates and instructions are
reported separately with clause and card-face provenance. The same details reach
simulation preflight/results, local card completeness and public battlefield
diagnostics. The frontend validates the new response fields and offers a native
disclosure before the existing exploratory-run acknowledgment.

Commander-dependent, devotion/type-changing and granted non-keyword ability
examples remain unsupported: Thunderfoot Baloth, Xenagos, God of Revels and
Tyrant's Familiar are warning fixtures, not newly certified playable cards.
Triggered, activated and temporary text is not mislabeled as a static buff.
An empty known-gap report is still not rules certification. This increment does
not implement all attachment coverage, conditional replacements/permissions,
arbitrary composed predicates, devotion or full type/layer dependencies.

## Acceptance Checklist

- [x] Preserve five fresh Scryfall responses and normalized canonical fixtures.
- [x] Reproduce missing resource semantics and preflight warnings before repair.
- [x] Verify both seats, live resource changes, token exclusion, control changes,
  snapshot round trips, read purity and AI entry projections.
- [x] Verify HTTP preflight, public diagnostics and local completeness parity.
- [x] Validate frontend response rejection for malformed static details.
- [x] Complete final isolated backend suite, Chromium flows and repeated,
  seat-balanced explicit archetype matrix.
- [x] Archive evidence on RCHFiles and refresh Graphify for milestone publication.

The initial corrected baseline was nine failures and one pass. Expanded focused
acceptance passes 19 cases. A test-only cache payload initially supplied a raw
list to a string storage column; it was corrected to the repository's explicit
cache contract before final full-suite execution. The first browser attempt used
a button-only test helper for a native summary; the corrected scenario verifies
the disclosure's open state and exact warning text. Failed/interrupted runs are
retained separately from final acceptance evidence.

Final backend acceptance passed 5,234 tests with 464 deprecation warnings in
967.00 seconds. The changed backend files match the tested source copy byte for
byte. Frontend lint, runtime contract tests, script syntax and production build
pass. The complete Chromium harness passes, including the new warning disclosure,
recovery, sideboarding and natural AI/human BO3 scenarios.

An explicitly selected Dimir Control/Tempo/Tokens/Ramp matrix passed 12
seat-balanced BO1 samples, each repeated twice, in 378.259 seconds. The default
selector also completed 12 repeated samples in 581.348 seconds using Aetherdrift
Aggro, Foundations Aggro, Duskmourn Tempo and Bloomburrow Tokens templates. Both
reported zero timeout/anomaly/drift. These 24 samples/48 executions are regression
evidence, not independent balance estimates or proof of optimal play. Normal
matrix traces are hashes; full anomaly traces would be retained if detected.

Canonical responses, source copies, failed/interrupted attempts, final logs and
browser artifacts are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/static-admission/20261003T223532Z/`.
Content comparison and SHA-256 verification precede owned scratch cleanup. The
pre-existing untracked user plan is separately preserved and remains unstaged.

Dependencies are reused and live SQLite data is untouched: backend tests and
matrices use distinct local source copies. This is neither a fresh dependency
install nor a broad AI-strength/balance, LAN security or alpha-UI certification.
