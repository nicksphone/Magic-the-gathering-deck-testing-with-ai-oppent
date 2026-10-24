# Built-App Manual Mana Routes

Base: `19fb9923abe7fb08b8a6a1612873ef02765b024b`. Expected scope is SIX
browser cases: both actor seats for `tap_land_for_mana`,
`tap_nonland_for_mana`, and `tap_lands_bulk`. All outcomes are UNRUN here.
These are distinct real built-App controls; this is not compatibility-only
selector/core-CLI coverage, an AI game, or RC completion.

## Implementation Plan

1. Register the new fixture helper from existing `ui_v2_fixture_server.py`.
   Reuse the real fixture app, publisher, persistence, and PR38 cached-body
   ASGI receipt pattern. No parallel server, Fetch interception, request/response
   rewrite, new dependency, direct engine-action call, or fake HTTP response.
2. Use the existing built App/driver and six mandatory fixed cases. Verify one
   accepted exact public body/HTTP 200, one revision increment, real pool/tap
   effects, no stack/spell count, retained position and unchanged opponent.
3. Add exactly one 180-second default program declaration after zone-keyword
   coverage. The CORS source-integrity test requires that declaration once and
   removes only it before ALL original assertions. Its original 73 wrappers,
   `f9004615e9da07bfa624f22be2e6c212b5d06dbaf6666564d51c78283e504933`
   legacy hash, 45 banners, and all prior bounds/programs remain unchanged.

## Genuine Printed Inputs And Trusted Pose

Existing `browser_positive83_canonical.entry` verifies complete RAW source and
object identity, normalizes the full object, then passes it into MatchFactory
BEFORE physical card birth. Island is the existing complete 60-field record in
`knowledge_profiles/seed155-scryfall.jsonl`; Sol Ring is the 65-field
`manual_mana_a227/sol-ring.raw.json`. The existing pinned SOURCES manifest covers
both; no new RAW, fabricated Oracle, projection renamed RAW, or network intake.

Each genuine Factory deck is 59 Islands plus one Sol Ring. After native birth,
the setup returns initial hands to libraries and moves three existing Islands
plus the existing Sol Ring per player into play. It does not create cards,
replace IDs, rewrite printed facts, seed mana, or invoke game actions. This is
explicit trusted test-board setup, NOT a played checkpoint or original-stock
certificate (`capture_original_stock=False`). Both pools start empty and all
sources untapped, at the actor's ordinary precombat main priority window.

- Individual Island: open Individual lands and deliberately select the SECOND
  native Island ID, then click `Tap selected for U`. Exact `card_id`/color/type,
  only that source tapped, U1; other Islands/Ring/opponent unchanged.
- Sol Ring: click its actual `Add 2 C` card button. Exact Ring ID/color/type,
  C2, Ring tapped; all lands/opponent unchanged.
- Bulk: explicitly select count TWO from the three-Island pile, then click
  `Add U`. Exact `land_name=Island`, count2/color/type, U2, first two tapped;
  the third, Ring, and opponent unchanged. Only ONE accepted public POST.

UI selections themselves must leave all engine facts, receipts, and revision
unchanged. Only actual DOM button clicks submit game actions. Read-only fixture
facts expose selected public source coordinates/counts, not private hand contents
or full state/trace dumps. Console output is aggregate case scope only.

## Parent Verification

Existing launcher already copies frontend ui_v2 into backend/tests and starts
`tests.ui_v2_fixture_server:app`; the new helper is an ordinary backend test file.
After reviewing/integrating the candidate, parent-only commands under the existing
ownership/runtime envelope are:

```bash
node --test frontend/tests/browser-cors-transport-diagnostic.test.mjs
bash frontend/tests/run-browser-ci.sh browser-built-app-mana-routes.mjs
```

The focused command includes the existing development-runtime proof, not the
whole browser gate. Default/native CI must prove actual outcomes separately.
Author checks are static Python AST/compile, JavaScript `node --check`, `bash -n`,
canonical input hashes, exact additive inverses and legacy source-hash continuity
only. No app import, SQL, browser, HTTP/native controls, actual test, build,
package install, C access, Git/index/ref write, or operator-install change.
