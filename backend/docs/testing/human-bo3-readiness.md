# Human BO3 Readiness

Qualified application base: `441201cee29dd527ba394b086e80accbf43bfc43`.

Before game N+1 starts, every controller marked `human` must have submitted the existing sideboard endpoint for game N. An empty `cards_out`/`cards_in` pair is an explicit no-swaps confirmation, including seats with an empty sideboard. AI seats do not acquire an extra confirmation requirement. Existing loser play/draw choice validation is unchanged. The readiness rejection is HTTP409 `sideboarding_not_ready` with public unfinished `players`; the existing controller transaction prevents state, inventory, revision, receipts, or SQLite mutation on rejection.

The UI consumes existing `sideboarding[seat].applied`: no new schema or public metadata. Each human can confirm no swaps; next-game controls remain disabled until all human seats are ready. This is deliberately a small Controls change, not a browser redesign or manual-browser certificate.

## Acceptance Harness

Run in a marked, source-only isolated checkout without `.git`, dependencies, cached/live databases, or NFS SQLite. Use the archived `gate.py`, `.private` exact-root marker, shared read-only Python, explicit `MTG_ISOLATED_TEST_ROOT`, and fresh `MTG_HUMAN_BO3_EVIDENCE` directories. The gate installs native audit checks before app/pytest imports; only owned-local SQLite/memory are allowed in the parent, and the fixed cold child is limited to the same owned DB using an explicit read-only URI. All sockets/binds are denied. No server port is used.

`test_human_bo3_readiness.py` contains 15 controlled contract cases. Its explicit finished-state fixture is NOT a native game-over witness. Legacy test adapters submit real no-swaps requests only; all original assertion ASTs remain unchanged.

The explicit long acceptance driver `test_human_bo3_interactive.py` is bounded to 6000 checked actions/1200s: seed1972639901, two human controllers, supported canonical Burn/Aggro variants, existing public-information testpilot, normal checked HTTP actions and native game-over. It requires `evidence/selected-preflight.json` from the archived pure preflight and inherited full official Shock fixture `tests/fixtures/human_transform_audit/canonical.json`; Shock is loaded through the actual repository, not a hydration override. The API still labels coverage exploratory; this is a concrete episode certificate, not all-card/rules/AI-strength proof.

`test_human_bo3_terminal_restore.py` is an explicit dependent acceptance check requiring the driver's actual completed artifact and persisted owned DB. It verifies a read-only cold child and a parent cold GET of the completed series, then atomic rejection of advancing it. It is not a standalone fixture or a fabricated native outcome. Keep the driver and dependent check serial; neither is a reason to run SQLite on NFS or against live state.

Frontend qualification includes actual Controls renders, typecheck, lint, configured tests with pure backend fixture children, and isolated build. It does not claim browser interaction. The shared dependency directory is read-only; build/cache outputs are local.

## Actual Current441 Acceptance

One authorized serial run completed at 09:16:55 UTC on 2026-10-07. Eleven
whole backend modules yielded 100 ordinary passes: 95 contract cases, the
canonical native human series, terminal cold restore, genuine different-card
swaps and both unchanged original live-series cases. JUnit has no failures,
errors or skips. The canonical series finished three games through 1,044
checked actions with score 2-1; no winner, life total or third game was forced.
The swap episode conserved mainboard/sideboard inventory across the native
series; it does not establish that the incoming singleton was cast.

Controls readiness SSR/callback checks, typechecks, lint, the full configured
frontend tests and React-enabled Vite API build all passed. Shared dependencies
were reused read-only, not freshly installed. Manual browser interaction,
all-card correctness and AI strength remain unqualified.

All 2,248 enumerated source inputs matched before and after execution.
Runtime-generated media and test/build outputs are inventoried separately;
this is not full-tree equality. Twelve gate/cold-child closure receipts and
independent database fuser checks established quiet owned resources and SQL
slot release at 09:18:22 UTC. Closed SQLite bytes were archived, never run on NFS.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/training-groundwork/human-bo3-current-441-actual-w8HjPk/`.
Parent independently checked the full manifest, all 2,643 regular tar members
against local originals, and the five JUnit files totaling 100 passes. All
twelve applied patch files matched the tested tree before documentation updates.
