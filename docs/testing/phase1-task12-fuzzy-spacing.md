# Task 1.2: Fuzzy Requests And Minimum Spacing

This bounded increment implements the original Task 1.2 request and spacing
requirements without changing the corpus, repository schema, learned fields,
offline cache recovery, or ruling-verification semantics.

`KnowledgeIngestor.sync_name` uses only the `fuzzy` request parameter. Before
`sync_payload` or its rulings fetch/writes, the response must match the requested
canonical name or a real face name, case-insensitively. Art-series/Card surfaces
do not supply face aliases. A typo or unrelated fuzzy result raises rather than
creating an alias or falsely satisfying the requested corpus entry. Existing
cache-first and forced-refresh behavior remains.

All requests retain at least 0.25 seconds between the prior completion and the
next request. Named/search endpoints retain their existing 0.5-second minimum;
longer caller intervals and the existing 429 backoff remain. The 0.5-second
value is retained conservative behavior, not a newly verified vendor-policy
claim. The official [Scryfall FAQ](https://scryfall.com/docs/faqs/i-m-having-trouble-accessing-the-scryfall-api-or-i-m-blocked-17)
asks for traffic below ten requests/second. This per-ingestor timing is not a
global cross-process limiter.

## Actual Qualification

Baseline is immutable `60b26ec1ef2218c1ce659727dec2f65ea13b6052`.
The unchanged production baseline runs the whole NEW module: 33 collected,
23 failed, ten passed, zero errors/skips, 2.70 seconds. The failures directly
exercise request identity and the missing all-endpoint spacing floor.

After the two-method correction, nine whole modules pass 231 ordinary cases
in 77.16 seconds, with 2,783 warnings and zero failures/errors/skips. The NEW33
are included, not an additional pass count. The existing recovery/stored-deck
fixtures change exactly four `exact` operands to `fuzzy`; their assertions,
request counts and all other bytes are retained. The old named-endpoint/429
test is unchanged. Official data comes from existing hash-pinned committed
fixtures; malformed variants and clock objects are explicitly protocol controls.

The first attempted baseline ends before collection because invocation from
HOME scans an unavailable backup mount. Its exit4/zero-SQL ledger is preserved,
not called a product RED. The corrected invocation changes only cwd and fresh
output paths. No package, mount, test assertion or guard policy is weakened.

The guard is the existing trusted-cohort recipe, not a child-process sandbox.
All HTTP uses MockTransport or the retained ASGI test client; no real external
HTTP/provider/game/browser is run. The gate disposes 205 engines, closes 89
fixture connections, and records all 149 child commands ended, with no remaining
jobs, threads or denials. All 3,329 pre-gate source files remain byte-equal.
New runtime additions are 152 SVG placeholders and the owned default database,
its actual capacity backup and owner lock. Direct fuser on all 149 existing owned
database files returns one with empty stdout/stderr.

Independent bounded static review is CLEAR on the tested production/test patch.
The natural seeded-game module is not run under the explicit no-game grant:
`test_ai_knowledge_natural_smoke.py::test_original_tempo_control_cli_completes_a_natural_seeded_game`.
This is not a whole-backend or native-game qualification. Phase 1 remains
unsigned; the separate literal synthetic-test-Oracle issue is unresolved.
