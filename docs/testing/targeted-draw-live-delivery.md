# Targeted Draw AI: Live Delivery

The preview backend now runs application commit
`ecda33bdf2740d4bd4af14542d10bffea4f10e08`. Delivery was verified on 2026-11-05.
Only the backend working-directory override changed; the existing Python
runtime, frontend, persistent database path and image cache were retained.
No native-engine replacement or new model weights were activated.

## Verification

- Eight unchanged whole AI modules passed 354 tests in 102.89 seconds on a
  fresh commit archive using the installed application runtime. The guard
  reported no SQL, network or subprocess activity.
- The first fresh-checkout run passed 350 and stopped four cases because the
  no-write guard blocked generation of the shipped generic token SVG. Preparing
  that exact shipped asset fixed the harness setup; no tests or game code changed.
- All 4,270 non-graph Git source files matched the tested and installed commit.
  The test-only source marker was not treated as an application Git artifact.
- The closed saved-game database passed SQLite quick-check and was backed up
  privately with byte verification before switching. It was never restored or
  overwritten. All 148 existing cache files were copied with byte verification.
- The new backend's actual PID and working directory were checked. Health was
  successful, the same 1,254 match IDs remained listed, two historical matches
  restored and two sampled cached images matched their previous bytes. These
  are sampled restore/image checks, not exhaustive replay of every saved game.

An initial deployment verifier incorrectly expected the match ID under a
`state` wrapper. It rolled back to the previous backend code. The corrected
verifier uses the observed root-level `id`; the subsequent switch passed.
Both attempts and their private backups remain archived.

## Remaining Work

This fixes ordinary targeted-draw recipient selection, not every modal route or
overall AI strength. Broad current full-game quality, decision time, BO3 strategy
and useful learned-policy generalization remain open. The native-engine save
diagnostic does not authorize moving existing saved matches to its loader.
