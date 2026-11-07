# Targeted Draw AI: Live Delivery

The preview backend now runs application commit
`97f9c3096c9f90a587e3384bacbe8a04d4afb39b`, including the selected-modal-target
and retained-blocker corrections. Its verified update is described below.

## Initial Ordinary Draw Delivery

The first update used `ecda33bdf2740d4bd4af14542d10bffea4f10e08`.
Delivery was verified on 2026-11-05.
Only the backend working-directory override changed; the existing Python
runtime, frontend, persistent database path and image cache were retained.
No native-engine replacement or new model weights were activated.

## Initial Verification

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

## Current Modal And Blocking Delivery

The next combined update from `7bfbfad4` to `97f9c309` passed 1,230 tests and
six subtests across 38 whole modules before switching. All 2,651 backend input
hashes remained equal and the pre-import native I/O guard recorded no denials.

The installed 4,328 regular files were attested against the exact Git blobs.
Only a new backend working-directory drop-in changed. The existing runtime,
environment, database path and frontend process were verified unchanged. The
closed 367,837,184-byte database passed quick-check and was backed up privately
to mounted NFS, with byte verification before startup. It was never replaced
or restored. All 148 image-cache files were copied with equal bytes.

Health passed on the actual new PID/cwd. All 1,254 saved match IDs remained;
two historical match GET responses and two cached-image samples matched.
Those are sampled restore checks, not exhaustive replay of every saved match.
No experimental learned weights or native engine were activated.

The first attempt stopped before service mutation because systemd omitted an
empty EnvironmentFiles property. Its original scripts and failed log remain
archived. A separate one-line operational correction handles that omitted
empty value while continuing to reject changed nonempty configuration. The
subsequent switch and verification returned zero; no application source or
test expectations were changed for this harness error.

## Remaining Work

This fixes ordinary targeted-draw recipient selection, not every modal route or
overall AI strength. Broad current full-game quality, decision time, BO3 strategy
and useful learned-policy generalization remain open. The native-engine save
diagnostic does not authorize moving existing saved matches to its loader.
