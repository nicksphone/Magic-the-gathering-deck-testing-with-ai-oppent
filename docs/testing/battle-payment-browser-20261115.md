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

- Fixture checks: **7 passed, 0 failed** locally, including a fresh-process import
  without pytest's path setup. The import regression failed before the fixture
  stopped depending on pytest-only audit imports.
- The local fresh-copy Vite development build completed. Local browser execution
  was blocked by socket/listen/crashpad permission errors; **no browser episode
  or warning-removal RED is claimed yet**.
- Frontend lint and production build passed on the copied source using the
  existing dependency cache. This is not a fresh locked-dependency installation.
- Host/CI browser counts and the warning-removal RED remain to be recorded.
  Fresh dependency installation, real TCP response loss, the complete browser
  cohort and the wider Gate 1/RC requirements remain separate acceptance work.
