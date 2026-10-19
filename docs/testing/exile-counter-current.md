# Current Exile Time-Counter Bodies

## Product

The bounded printed instruction that triggers when a time counter is removed
from an exiled card now executes independently of the Suspend cast permission.
Supported complete bodies draw a fixed number of cards or destroy a targeted
land, including a nonbasic-land restriction. Canonical Aeon and Detritivore
episodes retain normal trigger ordering, public target choices, counterability,
snapshot restoration and stale-object rejection.

The three production paths are `rules_engine/suspend.py`, `events.py` and
`oracle_effects.py`. The target-reference condition preserves the newer
`cast_from_graveyard` behavior. The already-integrated basic/nonbasic graveyard
selector was not reapplied. Unknown bodies/layouts and multiple-counter removal
remain explicit limitations; no full-card coverage warning was cleared.

## Independent Parent Acceptance

The parent composed the worker's surgical patch over application source
`d13a8afdc5d91bb48383274441c68160f711a669` in an isolated source-only checkout.
One combined gate passed **403 cases in 35.18 seconds** across 17 whole modules:
the same 15-module 339-case suite, the 60-case current graveyard-reference module
and four unchanged full-body goldens. JUnit records no failures, errors or skips.

The guard installed before project imports. Six native/public SQL and socket
denial controls passed; unexpected I/O was empty. Source hashes before and after
the gate remained equal. No SQLite, HTTP server, browser or external network
qualification is claimed. Parent AST-only graph refresh completed separately.

The exact approved nine Aeon test rows now resolve the independently retained
printed draw trigger through normal priority before their existing final
assertions. All other 80 original rows remain unchanged. Earlier immutable
failure ledgers and preimages are preserved; no skip or expected-failure marker
was added.

## Provenance And Limits

Worker current-source evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/holding-spells/variable-suspend-intake/exile-counter-body-current-ff9-qualified/`.
The parent independently verified its full manifest and retained all later
current-source hunks when applying the patch.

Parent evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/exile-counter-current-20261007/`.
It includes the original canonical inputs, exact module declaration, JUnit,
isolation receipts, source checks and graph log.

This is bounded rules acceptance, not general Suspend, arbitrary counter-removal
multiplicity, Ghostly support, a protection-land game, complete human gameplay,
AI strength or release readiness. No live source, database or service was changed.
