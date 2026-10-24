# Canonical zone-keyword browser cases

Base: `09380963373493099f1bdb4b0dc60017b248dfec`, tree
`95b6228bdc6e39be816f3be09bdce81df47bcc0c`. This candidate adds coverage,
not a known production fix, played-game certificate, or RC completion claim.

## Full RAW before native birth

Parent captured the two official full Scryfall responses before offline testing,
2026-10-24 05:17:09-11Z; both HTTP 200/curl exit 0. Exact unchanged bodies and
public provenance are in `backend/tests/fixtures/ui_zone_keyword/`:

| Card | Bytes / fields | SHA256 |
| --- | --- | --- |
| Doomskar | 5716 / 68 | `49ee32b3f03ee7fed84de52f41d74a0c61b3b0f2ffa35b9646644234bdec0f69` |
| Hollow One | 5134 / 67 | `3df32a84d1c5bf470c1d517905017cf0e450fbbe94545b35f8be4921c9e8c456` |

HTTP headers remain private intake evidence, not public fixtures. Ninja uses the
existing complete 62-field `fixtures/ninjutsu_canonical/ninja-of-the-deep-hours.json`
(SHA256 `d5c28c0171ed64bf41b2435a9edcf4ebcef7cc5d121e27996c74b9a1a8f41b0f`)
and its existing adjacent provenance. Island/Bears reuse the existing pinned
`browser_positive83_canonical.entry` reader. The helper hash-checks all three
target RAW files, passes whole objects to the genuine Scryfall normalizer, then
to MatchFactory. No API intake, reduced-row fallback, invented Oracle, or new
normalizer. V1's unresolved input prerequisite is resolved by this parent intake;
V1 remains preserved, not rewritten or retroactively qualified.

## Existing launcher, actual App/API

The tiny test-only import/call in `frontend/tests/ui_v2_fixture_server.py`
automatically registers the new helper. `run-browser-ci.sh:93` copies this module
into `backend/tests`; its :112 service remains `tests.ui_v2_fixture_server:app`.
The new helper uses the existing `tests.browser_fixture_server` app/publisher,
not a parallel service or circular ui_v2 import.

Parent-only focused runtime command, from the reviewed integrated checkout:

```bash
bash frontend/tests/run-browser-ci.sh browser-zone-keyword-actions.mjs
```

This runs the existing development-runtime proof and focused scenario, not the
whole browser gate. The default launcher also includes the same scenario after
human actions and before ordered targets, preserving every original declaration:

```bash
(cd frontend && run_browser_program "browser-zone-keyword-actions.mjs" timeout 300s node tests/browser-zone-keyword-actions.mjs)
```

The native Chrome/Brave workflow now also triggers when this launcher changes.
Its existing complete-suite command, sandbox checks and closure rules are unchanged.

## Six unconditional cases

Each of foretell, cycle_card and ninjutsu runs for both actor seats. Real built-App
DOM clicks submit unmodified public requests. A fixture-scoped middleware records
actual action JSON and status after the unchanged API handles it, without pausing
or replacing responses. It uses the existing Cathar/Suspend cached-body recording
pattern and rejects receipt overflow. Payload/actor/HTTP 200, exact revision and authoritative engine
facts independently verify acceptance and outcome. Missing routes/cards/windows
fail; there is no conditional skip, synthetic HTTP response, or direct game-action
call from the fixture. Fact responses contain targeted counts/coordinates/booleans,
not full private snapshots; console receipts are aggregate case scope only.

Factory-born cards are moved AFTER native birth into declared trusted positions,
not reconstructed checkpoints. Each scene has one target in hand and two untapped
Islands. Foretell/cycling decks are 59 Islands + target. Ninjutsu is 57 Islands +
Ninja + two Bears, both moved to the battlefield nonsummoning-sick. Opponent is 60
Islands. Pose setup does not claim original-stock certification: publisher capture
is explicitly disabled. No floating mana, injected StackItem, or forced winner.

- Foretell Doomskar: pay two real lands, face-down exile, empty stack, retained
  priority, no spell count or printed name in log; real serializer look checks.
- Cycle Hollow One: pay two lands and discard as cost; no premature draw. Two
  actual UI priority passes resolve its real ability, drawing one library card.
- Ninjutsu: attack-all selects BOTH Bears for review without sending an action
  or changing the revision/declared attackers. Submit Attackers then explicitly
  commits both, followed by actual empty blocks.
  Deliberately select the SECOND Bear ID (not the first/default). It returns as
  cost; the first remains on the battlefield and attacking through the subsequent
  passes. Pay the real one-blue-plus-generic cost using two Islands. The Ninja
  remains in hand until real ability resolution, then enters tapped/attacking at
  the opponent, while the selected second Bear stays in hand.

Foretell privacy scope is explicit: real public/opponent/owner serializer
projections and can_look are checked. `main.py:1842` aggregates all human look
seats for its shared hotseat HTTP view; this test does not claim a separately
seat-authenticated HTTP privacy boundary or change that existing behavior.

## Static Verification Only

Author checks: Python AST/compile-only, public RAW byte/hash/identity joins,
ui_v2 inverse proof, and `node --check` syntax-only. No module import, application,
SQL, browser, native C, or browser test execution. All six outcomes and browser
vendor/closure proofs remain UNRUN pending execution. Existing production,
assertions, frontend controls and dependencies are unchanged. Launcher and native
workflow additions only register the new coverage; they are not passing evidence.

The first native run on `611734f7` failed in both vendors. Chrome passed seat-1
foretell/cycling, then stopped because the new test treated selection as submission.
Brave passed seat-1 foretell, then reported `Invalid InterceptionId`; its precise
protocol cause is unproved. Both failures are preserved. The test now uses the
existing two-step attack UI and a server receipt recorder instead of unnecessary
Fetch interception. All gameplay payload/status/count/outcome assertions remain;
no production behavior or time limit is relaxed. Corrected runtime remains unrun.
