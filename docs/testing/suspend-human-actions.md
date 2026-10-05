# Bounded Human Suspend Actions

Parent integration qualifies the actual engine, UI and AI together: ten
actual-App cases and ten real-HTTP AI cases pass, alongside 892 backend checks
and frontend lint/build/unit/wire gates. Use `npm run test:unit:suspend` with
the declared backend Python environment, or `npm run test:browser:suspend`
for the self-isolating ten-case browser gate. The default shared browser scope
is not expanded silently. The original UI-only qualification below is historical.

Qualified source baseline: isolated tracked main `e645456` plus frozen backend
delta SHA256 `f703d1c580f1396a638e11e433e35a74b8f8c2b33ccae9449c35aa80a7d58856`.
This delta changes only Battlefield, shared frontend types, the actual contract
parser `frontend/src/api/match-contract.ts` (there is no `api/contracts.ts`), new
Suspend tests/fixture runner, and this document. App, API-client methods,
Controls, shared browser drivers/CI/Cathar, dependencies, backend sources, and
root documents are untouched.

## Human Contract

The hand action is shown only when the backend supplies legal move type
`suspend` for that card. Its label displays the authoritative fixed mana cost
and time-counter count. The action sends only type/card ID, not targets or an
invented alternative cost. This works independently of card names.

The final-counter ability requires a decision, not a mandatory cast. An explicit
choice-owner/human-gated panel explains cast-or-decline. Existing permitted-exile
spell controls supply ordinary casting costs and targets. Decline sends the
backend's declared `choose_mechanic` choice. When no cast is legal, the notice
explains that declining leaves the card in exile without time counters. Stale
other-seat or AI-owned Suspend choices expose no human cast/decline controls.

Battlefield omits only hand Suspend moves it actually renders from the generic
PermanentActions missing-control audit; other unimplemented actions still raise
that audit. No normal game control or backend admission rule is bypassed.

The public `suspended` flag is typed/validated. Suspend moves must have a positive
integer time count, card ID and supported printed mana-cost form. The optional
cast-choice wire contract requires the responding choice owner, count one, and
the declared decline option. Existing targets/costs use existing contracts.

## Reproducible Gate

From a normal Git checkout containing the backend delta and this UI delta:

```sh
MTG_TEST_PYTHON=/path/to/external/python \
MTG_FRONTEND_DEPS=/path/to/frontend/node_modules \
  node frontend/tests/browser-suspend.mjs
```

On this machine, external dependencies are main's backend `.venv/bin/python`
and frontend `node_modules`; no installation, migration or shared DB is needed.
`MTG_FRONTEND_DEPS` denotes the **node_modules directory**, not its parent.

The standalone gate freezes regular source files and canonical fixtures into a
new disposable local runtime. SQLite stays local. It allocates unique loopback
backend/App/CDP ports, starts the real App/API, reuses the existing CDP driver
without edits, and closes browser windows/owned processes before archival.
Only test-local dependency links are created; Vite caches stay local, not in
external dependencies. The source manifest pins every copied file hash.

Local evidence requires a mounted writable NFS project archive and fails closed
without it. Default root is
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/suspend-browser/`.
Hosted runs require `GITHUB_ACTIONS=true`, `RUNNER_TEMP`, and explicit
`MTG_SUSPEND_ARCHIVE` strictly inside RUNNER_TEMP; there is no NFS requirement
on hosted GitHub. No hosted execution or shared CI wiring is claimed here.
Unknown arguments fail before runtime creation; declared scope is always ten.

Ten cases, five per human seat:

- Canonical Rift Bolt: paid hand Suspend, separate upkeep and final-counter
  triggers, restored cast choice, explicit opposing player target, real cast
  and damage/graveyard resolution. P2 also restarts the actual backend process
  while the cast decision is pending; full snapshot hash survives unchanged.
- Canonical Errant Ephemeron: printed `{1}{U}` payment, all four time counters
  removed on distinct owner upkeeps, real no-target creature cast, battlefield
  entry, and visible granted haste after restoration.
- Canonical Rift Bolt with opposing/own Ivory Masks: suspension remains legal
  without available targets; final decision exposes no cast and explains decline.
- Canonical Rift Bolt: voluntary decline while a valid cast is available;
  reload/restore leaves it counterless in exile with no new cast permission.
- Canonical Rift Bolt without payable mana: no Suspend control or game mutation,
  including after restore/reload.

Rift Bolt/Errant Ephemeron/Ivory Mask reuse the backend's unmodified canonical
records and provenance hashes. Fixture transitions to each owner upkeep are
explicit source-grounded manual test setup, not played intervening turns or a
natural saved-game history. Every Suspend, pass, cast/target and decline is
performed through visible App controls, never directly POSTed by the runner.
Fixture-only routes create positions, audit, restore, or enter an owner upkeep;
they cannot fake a game action. Guards refuse import beside a normal Git checkout
before SQLite startup, enforce owned loopback tokens, and reject invalid zones.
No user games, private opponent hands, or hidden library policy inputs are used.

Screenshots, synthetic snapshots, HTTP action/status records, stopped test DB,
process/port audit, results and frozen source manifest are archived privately.
Each archived regular file is byte-verified before successful runtime removal;
failed runtime/logs are retained. Never execute archived SQLite on NFS.

## Focused Companion Checks

```sh
MTG_TEST_PYTHON=/path/to/external/python \
  node --experimental-strip-types frontend/tests/suspend-human-actions.mjs
node --experimental-strip-types frontend/tests/match-contract.mjs
frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json
PYTHONDONTWRITEBYTECODE=1 /path/to/external/python -m pytest -q \
  frontend/tests/test_suspend_fixture_guards.py
```

The new companion check renders ten canonical backend-generated states,
asserts both-seat human controls, foreign-seat/AI-owner isolation, unavailable
targets/payment, and malformed wire payload rejection. It uses installed
React/esbuild in memory without changing App methods. Type checking and existing
contract tests check adjacent compatibility. No full suite is required per file.

## Qualification Boundary

These bounded **human** actions and snapshot continuations are closed by the
ten-case actual-browser gate. There was no missing backend App integration hook:
existing onCardAction, legal-player selection and snapshot restoration sufficed.
AI Suspend planning/choice policy remains open and untouched. Variable-X,
nonmana/hybrid/granted/multiple/complex-face Suspend, additional card-specific
effects, every time-counter-removal spell, arbitrary taxes/additional-cost UI,
and blanket 109-card/corpus certification are not claimed. The companion backend
document retains the backend-specific limits; no historical repair is made.
