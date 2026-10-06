# Human Flow Audit: Cycling and Death Tokens

This is a tests/report-only sidecar over main `3ccbdf2`, before parent engine
fixes. It constructs explicit small canonical positions, not played games or
historic repairs. No product, fixture-driver, shared-CI or main edits are made.

## Run

```sh
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/path/to/external/frontend/node_modules \
node frontend/tests/browser-human-flow-audit.mjs
```

The 16 flows use the actual App and checked real HTTP, eight scenarios in each
seat: Shark cycling-only/castable, Renewed accept/decline/normal-cast, Hangarback
death, stale cycling after restart, and an independent Grizzly Bears cast.
Only existing legal actions and actual offered choices are used. Missing engine
choices are strict RED, never synthetic buttons or retroactively claimed choices.
The gate exits nonzero on any RED and preserves private evidence on mounted NFS.

Dynamic X is inspected through actual UI controls and actual legal moves.
Selection drafts/read/refresh cannot mutate snapshots. Opponent hand DOM and
actor legal moves must remain private. Unseen library IDs are absent before
draw. Both-human match GETs are not falsely claimed to hide every client hand.
Renewed's optional public effect control is qualified only if the engine offers
it; an absent choice blocks accept/decline coverage rather than proving a UI bug.

Hangarback is really sacrificed to Tower using explicit indexed mana, offered
base vector and selected resource. The queued death stack and generated effective
token views survive real backend process restart and HTTP/reload. Token quantity,
type and LKI semantics are checked separately from UI fidelity to actual views.
The stale test uses a second legitimate HTTP action, then clicks the unchanged
old actual-App cycling control after restart: 409 must preserve the paid state
and reconcile away the stale hand card. No frontend state/choice is forged.

## Bounded Findings on This Baseline

The castable hand branch omits the cycling-X selector even when legal moves
offer X=2. The cycling-only branch supplies it. This is the concrete UI blocker
to propose: share the existing authoritative X selector in both branches, with
valid-current-choice handling. No card-name dispatch or UI redesign is needed.

Unchanged engine failures must not be presented as frontend regressions: self-
cycling payoffs/optional choices do not materialize, Renewed normal cast gains
eight instead of six life, and Hangarback death LKI/count/artifact metadata are
wrong. Existing effective 2/2 flying token views nevertheless match public HTTP
and persist across refresh/restart. Parent engine fixes remain separate and
unapplied; requalify semantic/optional-choice cases after composition.

Eight unchanged raw canonical rows were extracted offline from the hash-pinned
Scryfall bulk already archived by the parent. Provenance pins the complete scan,
compressed input/file hashes and card/Oracle IDs; no network or Oracle changes.
The provenance unit compares existing committed Shark/Hangarback/Tower facts.
This does not certify whole decks, all cycling/death variants, AI decisions or
historical outcomes. Detailed raw evidence and exact source hashes accompany
the archived terminal report; no live/user database is copied.
