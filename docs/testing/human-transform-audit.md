# Human Transform Audit

NEW tests/report-only gate on the coupled candidate plus Cycling X and token
materialization patches. Input source archive SHA-256:
`55851f786008cad32212dc275762246464a78035adedadb1e1ebc1a7fe335d58`.
No product files, main checkout, live service, or user database are changed.

## Declared Path

Eight flows: both seats, Cathar natural ETB/day-to-night; Delver reveal,
Delver decline, and ineligible top-card control. Each imports a 60-card deck
through actual `/decks/import` with exact source name/quantity (2 source,
1 Grizzly Bears, 1 Shock, 56 Island), then uses production normalization,
repository hydration, and MatchFactory.

The NEW guarded fixture sets an explicit partial position: source in hand,
precombat main on turn 1, exact casting mana, an opposing Grizzly Bears on the
battlefield, a nonempty opposing private Island hand, and an own canonical
controlled top card. No policy consumes this
library order. This setup is not a naturally played history or historical repair.

Everything after setup uses actual App controls and checked HTTP actions:
cast front, pass priority, Cathar ETB target choice, ordinary turn progression,
upkeep trigger resolution. There is NO transform/helper invocation or fixture
transition endpoint. The probe records actual requests, status, revisions,
private snapshots and legal moves, and screenshots. Missing human controls are
RED, never synthesized or replaced by a guessed POST. Restore includes real
backend process replacement, snapshot hash/revision equality and App reload.

## Canonical Evidence

Existing full raw Cathar fixture/provenance are reused unchanged. Delver and
Shock are full raw rows extracted from the parent-authoritative offline bulk,
not projected or invented cards. NEW fixture provenance pins compressed bulk
SHA, exact record scan count, raw-output SHA, IDs and Oracle IDs. There is no
network fallback or changed Oracle text. A focused provenance test pins both
canonical families and checks the optional Delver reveal instruction.

## Strict Limits And Proposed Follow-Up

Delver's canonical reveal is optional. The current trigger materializer emits
`transform_if_top_matches`; that handler automatically publishes the top name
and transforms eligible cards. An automatic back-face result is tested as
materialization only, NOT optional human-choice certification. Decline and
private inspection assertions remain strict RED if no real choice is offered.
Proposed follow-up (not implemented): generic private look/optional reveal
continuation in `events.py::_trigger_from_oracle` and
`effects/handlers.py::transform_if_top_matches`, reusing durable choice ownership
and serialization; consumer work only after an actual public contract exists.

Current day/night machinery has two source-confirmed limits:
`RulesEngine._update_day_night` is called at upkeep rather than untap, and its
`previous == "none"` branch can establish day/night just from spell counts.
The Delver controls assert neither designation remains neither. Cathar natural
night checks at the first public upkeep window do not certify correct internal
untap ordering or simultaneous-transform trigger ordering. Proposed follow-up:
move day/night checking to the canonical untap turn-based window and preserve
neither until a legitimate establishing ability/effect. No global model bypass
is introduced by this gate.

This bounded gate checks linked exile remains held across a natural Cathar
transform and restart. It does not repeat source-departure/return qualification,
night entry, or the two-spell night-to-day direction. No private inspection
or pending reveal-choice restart claim is made where Delver offers no choice;
the real trigger stack and post-resolution state are restarted instead.

Authority: official [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
731.1 and 731.2a-c (designation and untap check). Delver optionality is verified
against the pinned unchanged raw Oracle face. No broad transform/card corpus
certification, meld/flip support, or completion of unsupported choice paths.

## Run

```sh
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/path/to/external/frontend/node_modules \
node frontend/tests/browser-human-transform-audit.mjs
/path/to/external/backend/.venv/bin/python -m pytest -q \
  backend/tests/test_human_transform_fixture_provenance.py
```

A normal Git checkout is inventoried into a fresh local runtime excluding
DB/dependencies/cache. Random owned loopback ports, isolated browser profile,
root/token guards and owned-service cleanup are retained from the qualified
face runner. Local archive fails closed unless NFS is mounted; hosted execution
requires an explicit artifact root under RUNNER_TEMP. Failed runs exit 1 and
preserve private evidence and source, rather than relaxing assertions.

Final observed results and exact archive hashes are supplied in the terminal
report; this document does not predeclare a green qualification.
