# Resolution-time linked discard

## Scope

Shared complete-instruction recognition handles self-discarding any number of
cards followed by a bounded basic-land search, and whole-hand discard followed
by drawing the actual discarded count or a fixed printed number. Canonical Rites
of Spring, Tolarian Winds and Dangerous Wager are real fixture cards, not name-
dispatched handlers or invented decks. These are resolution effects, not prices.

The existing discard handler uses exact or zero-to-hand-size owned choices.
`followup_effect` carries the actual selected count into the existing search/draw
handlers. Zero discard does not turn a zero-limit search into an unlimited one;
the search still shuffles once. Qualified searches permit failing to find, reveal
found basic lands and preserve the advertised restriction. Copies recount the
current hand when each resolves; countered spells discard nothing. Whole-hand
instructions exclude the already-cast spell. Shared discard events and graveyard
replacements retain discarded-count meaning even when cards go to exile.

Self-discard recipients are resolved from the current effect controller, rather
than captured from the original caster. Opposing-controller spell and activated
ability copies discard their own hands; explicitly targeted recipients remain
unchanged. This shared repair also covers ordinary draw-then-discard effects.

Choices and follow-up continuations survive snapshots and SQLite restoration.
Nested dredge/draw choices retain the original resolving spell and finish it once.
Both human seats use the existing choice controls, including valid zero-card
optional selections. Frontend choice-kind unions now include ordinary and
simultaneous discard instead of silently relying on cast response types.
Unrecognized linked-discard instructions produce coverage warnings and no cast
options; Change of Fortune's per-turn discard history is not faked as a fixed draw.

## AI boundary

All difficulties compare bounded land-search gains with retained hand value and
known mana development, preferring fewer discards on equal-valued trades. The
search only considers its controller's own possible matching cards, not opposing
hidden zones or unknown future draws. Fully developed mana does not justify an
unnecessary whole-hand dump. Whole-hand draw casts reuse public-count draw forecasts
for supported replacements/caps; exercised valuable-hand loss and doubled-draw
exhaustion are rejected. Expected unknown draw value remains a heuristic, not a
trained distribution, graveyard-combo plan or optimal card-quality forecast.

## Checklist

- [x] Canonical normal casts and actual linked discard/search/draw resolution.
- [x] Both seats, zero/empty resources, fail-to-find and illegal-choice atomicity.
- [x] Copies, counters, exile replacement and nested draw/dredge continuation.
- [x] SQLite restoration through the production recovery function and HTTP actions.
- [x] All-difficulty optional-search and hand-retention/draw-exhaustion checks.
- [x] Frontend lint/contracts and production build.
- [x] Complete Chromium, including six normal casts and two opposing-copy cases.
- [x] Twelve repeated seat-balanced replay samples across Dimir Control, Tempo,
  Tokens and Ramp, with no reported anomaly, timeout or determinism failure.
- [x] Full isolated backend suite against the final source: 4,582 passed, 408
  deprecation warnings, 719.74 seconds; no failures.
- [x] Verified RCHFiles evidence archive, AST-only Graphify refresh and milestone docs.

Current focused acceptance: 80 linked-discard/copy tests and a 247-test combined
AI/draw regression selection pass. Frontend lint, contract/mutation checks and
TypeScript/Vite production build pass. The final targeted replay completed in
339.815 seconds. Each of its twelve logical BO1 samples ran twice for repeatability;
this is a smoke matrix, not a sample establishing balance or expert play.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/linked-discard/20261003T162553Z/`.
Retained artifacts include canonical responses and field-parity checks, initial
failures, source-epoch-specific reruns, final suite/frontend/browser/replay logs,
isolated databases, source hashes and the separately preserved pre-existing user
plan. Closed browser artifacts are archived independently. Archives are verified
by tar content comparison and SHA-256 before local disposable copies are removed.
Graphify's final code refresh reports 9,423 nodes and 24,167 edges, with zero API
tokens. A successful milestone does not complete the project's broad release gates.

Initial findings/failures are retained with acceptance evidence. The library-search
fixture first lacked canonically hydrated basic lands; correcting the fixture did
not relax search eligibility. The API restore fixture initially assumed GET would
reload an evicted active match; it now exercises actual lifespan recovery code.
One AI tie needed rounding before minimum-payment tie-breaking. Two test commands
referenced nonexistent files and ran no tests; successful checks are recorded
separately. The frontend build exposed an omitted existing discard choice type.
Opposing-controller copy probes initially failed for both seats, exposing the
captured-recipient bug. The first full backend run also caught a new AI check
reading Oracle text directly from a minimal test card without that attribute;
the check now uses the existing safe Oracle-text helper. One Chromium rerun timed
out in an older kicker scenario before reaching the new cases. These failed runs
are retained and are not substituted for successful final acceptance.

## Known Limitations and Next Upgrades

Arbitrary linked counts, discard history this turn, random/opponent/simultaneous
variable discards, chained modes and other conditional clauses remain incomplete.
Unrecognized complete sequences are rejected rather than approximated. General
replacement ordering, madness/optional graveyard choices and long-term discard
payoff planning need further acceptance. AI draw forecasts omit downstream trigger
chains, optional dredge and hidden draws; costs/opponent responses can invalidate
an apparent plan. These fixtures are not whole-card, full-corpus, expert-AI or
match-balance certification. Installed dependencies are reused; UI redesign and
packaged release gates remain separate work.
