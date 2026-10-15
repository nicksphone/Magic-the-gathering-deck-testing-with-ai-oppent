# Delver Cache Fixture Fidelity

Base: `8083a80e8c1b7c602a6c3537c095a6a3a6a98482`. This bounded Task1.3
test-only migration replaces the incomplete Delver cache row in
`tests/test_fallback_hydration.py`. No production, canonical fixture, dependency,
parent worktree or existing acceptance-document change is included.

## Canonical Facts And Display Overrides

The existing `_official_card` loader supplies a fresh complete Delver of Secrets /
Insectile Aberration object from the pinned official155 snapshot. The existing
`ScryfallSyncService._normalize_payload` produces the complete cache projection,
including both ordered face bodies. Its truthy local display-image argument
avoids placeholder generation while constructing that projection. Only then is
the root image set to `None` and each face image set to the existing local test
image URI. Those display overrides are not canonical Scryfall facts.

The independent existing `archived_card` verifier checks the public-intake
provenance and snapshot SHA256
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.
Neither the official snapshot nor its provenance is changed. The old fixture's
root `Flying` text and two name/image-only faces were not canonical card facts.

All six original test functions and all40 original assertions remain. The
partial/empty-cache Wandering Emperor negative test is byte-exact. Five original
function bodies are byte-exact; the remaining function changes only its fixture
construction, with imports added for that construction. Existing test names,
assertion operands/operators, image-selection checks and diagnostic-hydration
comparison are retained.

## Observed RED And GREEN

The NEW fidelity module captures the actual original nested cache-row builder
before hydration; it does not fail merely because a proposed helper is absent.
It checks the entire normalized row, independently verified RAW/provenance,
fresh official objects, and fresh actual cache rows/face payloads.

The two whole modules collect nine ordinary cases: original6 plus NEW3.
RED:1 failed/8 passed in2.54s, solely the actual cached-row/full-canonical-
projection comparison. GREEN after the fixture-only correction:9 passed in2.54s,
zero failures/errors/skips. There are no selections, deselections or changed
original assertions. Both executions use a300-second TERM/15-second KILL bound,
`--noconftest`, disabled plugin autoload/cache, and owned temporary/evidence paths.

Before collection, seven actual denial canaries cover three SQLite aliases,
two native/public socket constructors, Popen and provider import. Tests record
no unexpected I/O attempts. Importing `main` constructs one unused SQLAlchemy
engine; it is disposed without a connection or database file. Source and2946
read-only-runtime regular files are byte-equal across each test execution.
RED adds five generated media SVGs; GREEN reuses those warm assets and adds no
source paths. Both close with unchanged FDs, no extra threads or children.

Two earlier administrative launches execute zero tests and remain preserved:
an absent-provider `importlib` canary failed before collection; after using
builtin import, pytest's default `/dev/null` logging target hit the strict write
guard. Directing that log to owned evidence resolves the latter without adding
permissions. Neither administrative stop is product RED or a passing gate.

This is fixture fidelity and the complete original six-test regression scope,
not HTTP/TestClient, SQL, match-factory, browser, gameplay or whole-backend
qualification. Repo-wide handwritten positive fixtures, negative/protocol text,
generated token descriptions, original Task1.3 and Phase1 remain open.
