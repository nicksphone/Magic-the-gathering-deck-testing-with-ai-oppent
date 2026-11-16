# Battle and deferred-payment browser acceptance

This cohort uses **declared canonical midgame** positions, not natural opening
hands or played history. The existing natural BO3 cohort is unchanged.

`browser-battle-payments.mjs` drives the mounted App through real HTTP/rules/SQLite
after fixture birth. It declares four episodes: both seats in human-vs-human and
human-vs-AI modes. Each casts Invasion of Zendikar, searches for Forests, attacks
the Siege, casts Awakened Skyclave, pays one Summoner's Pact upkeep obligation,
then declines another to reach a game result. It reloads the page while payment
is pending. Two additional UI negatives require an explicit warning and no
fabricated choice button for `diagnostic_unknown`.

The extended program adds **two further human-vs-human episodes**, one per
seat, for an unaffordable Pact. Its new declared-midgame variant moves the
initial Forests back into the library at fixture birth, preserving the canonical
objects and deck stock. Real zero-cost Pact casting, its library search and
native turn progression create the upkeep debt; no pending choice or delayed
trigger is injected. The existing fixture helper and original natural BO3
programs remain unchanged.

For those episodes, the actual API must offer exactly `['decline']`. The
actor-bound App panel must have exactly one enabled “Decline payment; lose the
game” button, no Pay button and no unsupported-control warning. A completed
page reload must preserve the entire public match response, including the
choice, options, resources and revision. One real decline must increment the
revision exactly once and render the other player's win. The default program
therefore declares **eight** episodes: the original four funded flows, two new
unaffordable flows and the original two warning negatives. Warning-only mode
still runs only the original two negatives. These are declared episodes, not
new execution results.

## Run

Install the locked app dependencies and frontend dependencies as for the existing
browser CI. From a checkout containing this stack:

```bash
MTG_TEST_PYTHON=/absolute/path/to/python \
MTG_CHROME=/absolute/path/to/google-chrome \
bash frontend/tests/run-browser-ci.sh browser-battle-payments.mjs
```

The existing runner builds a fresh source copy and excludes databases, image
caches, diagnostics, training outputs and developer caches. A focused command is
not the full browser gate. The default CI command also runs this program and
retains all existing browser programs.

## Warning-removal negative

Run this only in an independent disposable checkout. First run the warning-only
baseline with `MTG_BATTLE_WARNING_ONLY=1` and the same command above. Then remove
only the unsupported warning branch, keeping the choice panel and supported
controls intact:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('frontend/src/components/Controls.tsx')
text = p.read_text()
marker = '{!supportedMechanicControls.has(mechanicMove.kind ?? "") ? '
assert text.count(marker) == 1
start = text.index(marker) + len(marker)
end = text.index('</p>', start) + len('</p>')
assert text[start:end].startswith('<p role="alert">')
assert 'Unsupported mechanic choice:' in text[start:end]
p.write_text(text[:start] + 'null' + text[end:])
PY
```

Repeat the warning-only command. It must fail at the explicit warning assertion
after the actor-bound choice panel has rendered; a bootstrap failure is not this
RED result. Restore the disposable file afterwards. No warning-removal mutation
belongs in the PR.

## Evidence and limits

- Fixture checks: **9 passed, 0 failed** locally, including a fresh-process import
  without pytest's path setup. The import regression failed before the fixture
  stopped depending on pytest-only audit imports.
- Restore regression: both seat checks failed before initializing the fixture's
  total mana pool with zero entries for all six colors. The original serialized
  response failed the actual frontend parser with `Invalid match response:
  player 1 snow mana pool`; all six episode/negative fixture responses pass that
  parser after the correction. This is fixture evidence, not a browser pass.
- The local fresh-copy Vite development build completed. Local browser execution
  was blocked by socket/listen/crashpad permission errors; that local attempt executed no browser episode. Host results are recorded
  below.
- Frontend lint and production build passed on the copied source using the
  existing dependency cache. This is not a fresh locked-dependency installation.
- The focused host browser counts and warning-removal RED are recorded below;
  final combined-source/full-workflow results remain separate.
  Fresh dependency installation, real TCP response loss, the complete browser
  cohort and the wider Gate 1/RC requirements remain separate acceptance work.

## Host result recorded 2026-11-15

Claude ran branch commit `bf347e3f` on a clean clone with npm ci, venv Python
and Chrome: **six PASS episodes, exit 0** (four canonical-midgame flows and two
warning negatives). Warning-only baseline passed both seats. Removing only the
warning node in a disposable clone failed at `Missing explicit unsupported-control
warning for seat 1`; the mutation was reverted. This is the intended warning RED,
not a bootstrap failure. The later Vite patch and final full clean-checkout
composition still require their own acceptance run; see
[current status](current-release-status-20261116.md).

## Extended fixture checks and remaining gaps

The new whole `test_battle_payment_browser_unaffordable.py` module passes six
local pure-engine cases. It checks canonical stock and an initially absent
choice/debt; genuine Pact cast/search/opponent-upkeep/next-own-upkeep progression;
the actual decline-only legal offer; snapshot round-trip; atomic rejection of an
unoffered Pay; and the real losing decline for both seats. This is not HTTP,
browser or a new natural-game result. Run from `backend/`:

```sh
python -B -m pytest -q tests/test_battle_payment_browser_unaffordable.py
```

Claude host-verified PR #82 with eight browser PASS lines (six predecessor
episodes plus both unaffordable cases). Its browser CI job in run `43893763013`
also passed. Those results precede the later composed program. No runner, driver, source pin or original fixture/helper is
changed; the existing wrapper adds a test-only unaffordable-birth endpoint.

The additional simultaneous and routing cases below close those specific
source-branch gaps, subject to a composed host run. ASGI/SQLite pending-Pact
restart has separate four-case host evidence in PR #87; that does not establish
an uninterrupted browser across restart. Final-source full-cohort, native
vendor, clean-checkout and broader Gate 1/RC acceptance remain separate.


## Simultaneous-debt extension

Two additional declared canonical midgame human-vs-human episodes cover both
seats with eight Forests and two genuine Pact casts/searches. No debt or prompt
is injected. The player selects a real simultaneous-trigger order, pays first
while the second remains owed in the same upkeep, refreshes at the second prompt
without changing public state/revision, and pays again. Each payment commits
once and taps four Forests; drawing starts only after both debts resolve.

Claude host-ran the original isolated branch `654d78c1`: 15 Python tests and
eight browser PASS lines (six predecessor episodes plus these two). That is
source-specific evidence, not a composed-program result. The merged #82 base
already has eight episodes; the intermediate simultaneous-only commit
`7643cdb1` expected ten. The final composition below adds six routing episodes
and requires a new host run.


## Composed routing and payment cohort

This branch starts from merged main
`ec26f6f5ef68003d731a85648b2f40c282a4d449` and unions the test-only load
variants, fixture endpoints and episode calls. It retains all host-tested funded,
unaffordable, simultaneous and routing episode bodies. It changes no production,
original fixture, natural BO3 program, browser driver or pinned runner.

The final focused program expects **16 PASS lines**:

| Episodes | Count |
| --- | ---: |
| Original funded Battle/Pact flows: two seats × human/human and human/AI | 4 |
| Original explicit unsupported-control warning negatives | 2 |
| Unaffordable Pact, both seats | 2 |
| Simultaneous Pact debts and first-choice continuation, both seats | 2 |
| Partial Siege, player defender, blocked Siege: both seats | 6 |

Each routing case really casts/searches the Battle and selects one attacker and
its explicit defender through the UI. Draft edits must not change the revision.
The partial Siege ends at defense one and both lives 20; a player attack leaves
defense three and deals two to that player; a blocked Siege attack trades both
Bears while defense remains three and both lives stay 20. The opponent's Bear
is a birth input only. No defeat trigger or back-face cast choice may appear.
The public view must retain the correct protector, and the UI must display the
retained defense.

Claude host-ran isolated routing commit `bbfd43d3`: 15 Python tests and 12 browser
PASS lines (six predecessor episodes plus six routing). Together with the source-
specific simultaneous result above, these are **not** a new 16-episode result.
A new host run on the exact composed commit is required with the command above;
its result is pending here. Warning-only mode still runs just the original two
negative cases, and their warning-removal RED remains separate.

The full local fixture/lifecycle selection is:

```sh
cd backend
python -B -m pytest -q \
  tests/test_battle_payment_browser_fixture.py \
  tests/test_battle_payment_browser_unaffordable.py \
  tests/test_battle_payment_simultaneous.py \
  tests/test_battle_browser_routing.py
```

On the exact merged-main composition, these four whole modules completed
**27 passed, 0 failed**, with two existing dependency deprecation warnings. The
selected runner byte-inverse contract passed one test, and JavaScript/Python
syntax checks passed. This used the existing local dependency cache, not a fresh
hash-locked install. No counts from separate runs should be added into a claimed
full-suite result.
The source-specific four-test cold restart result and limitations are recorded
in PR #87's `pact-cold-restart-20261116.md`; that file is not part of this browser
branch yet.
