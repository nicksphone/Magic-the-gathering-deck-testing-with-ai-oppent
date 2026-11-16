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


## Partial, blocked and player routing (test-only extension)

Six additional declared canonical midgame, human-vs-human episodes cover both
seats in three cases. Each really casts and resolves Invasion of Zendikar, makes
its search choice, selects one creature and explicitly chooses its defender in
the UI. Draft edits must leave the revision unchanged. Accepted attacks and
blocks are checked against the authoritative state before combat damage:

- Partial Siege attack: defense falls from three to one; both lives stay 20.
- Player attack with a Siege present: the defender loses two life; defense stays
  three. The UI must route the attack to the selected player.
- Blocked Siege attack: an opposing Grizzly Bears is a declared birth input;
  both Bears trade, defense stays three, and neither player loses life.

None defeats or transforms the Siege. The tests require its protector and visible
defense to remain correct and no defeat trigger or cast choice to appear. Run the
focused browser command above; this branch expects twelve PASS lines (six old,
six routing). This is code awaiting host/browser execution, not a browser result.
Other staged payment extensions add their own counts only after composition.

Backend checks passed locally: **15 passed, 0 failed** (nine existing fixture
checks plus six routing cases, two existing dependency deprecation warnings).
The selected runner byte-inverse test passed; no browser run is claimed.
Reproduce the backend checks separately:

```bash
cd backend
python -B -m pytest -q tests/test_battle_payment_browser_fixture.py tests/test_battle_browser_routing.py
```

The existing fixture and pinned runner remain unchanged. Simultaneous-debt
continuation and pending-Pact backend restart have separate branches/evidence.
