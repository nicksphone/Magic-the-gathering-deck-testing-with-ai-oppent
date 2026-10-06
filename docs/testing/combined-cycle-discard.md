# Combined cycle/discard triggers

Incremental base: source-only parent candidate
/home/nick/.hermes/cache/scratch/mtg-composed-release-xxWjrw, checksum-pinned in
parent-source.sha256. It already includes worker self-death, parent self-cycling,
and color increments. Do not prepend those patches again. No main/live writes.

Production ownership and touched files:
- backend/rules_engine/events.py: discard/cycle clause routing, combined matcher,
  event-specific instruction extraction only. Self-death and self-cycling source
  materialization are unchanged. Combined conditions fire on discard only.
- backend/rules_engine/oracle_effects.py: bounded fixed signed team-counter body.
- backend/effects/handlers.py: existing add_counters_each_creature recipient scope.
  Other handlers and retained-source consumers are unchanged.

## Contract

The actual cycling cost emits discard and cycle. Recognize structurally bounded
'when/whenever you cycle or discard a/another card' (and reversed verb order) on
discard. Never recognize that same combined clause on cycle. Match controller,
and exclude the source itself for 'another'; never match by card name. Route
individual clauses so a combined clause cannot suppress an independent one.

Compile the instruction after the condition, not the condition's word 'discard'.
Target-resolution metadata is installed only for a targeted instruction: the
untargeted team effect must not open a target prompt or disappear for no target.

Bounded compiler grammar: fixed quantity a/an/one through ten or decimal integer,
literal signed P/T counter, each creature you control or your opponents control.
No X/effective-power quantity or unsupported recipient guesses. Payload carries
counter, amount, recipients='controller'/'opponents'. The existing helper defaults
to controller for compatibility, evaluates recipients on resolution, and retains
existing effective creature queries, counter replacement handling and per-object
incarnation stamps. An unknown explicit recipient mode produces no effect.

Paid optional instruction bodies containing 'you may pay' or 'if you do' are NOT
implemented here. They are queued as an explicit noop with an unsupported marker
and diagnostic, without payment, reward or inferred choice. Canonical Drake Haven
and Faith of the Devoted prove both funded/unfunded behavior. Do not claim full
combined-trigger support for optional payments or other unresolved conditionals.
That is the next consequential related gap, requiring a real payment/continuation
protocol and public choices, not permissive effect inference.

## Baseline and qualification

Old frozen ordering archive is immutable. Its 26 self-cycling reds belonged to
old3ccb, not this candidate. On the composed source, its read-only observer needed
to wrap the engine's imported event emitter as well as the events module;20 initial
failures were instrumentation errors, retained separately, not product failures.
The corrected unchanged127-case audit:117 pass,10 ordinary failures. Every valid
old assertion remains strict, including original self-cycling checks.

Final158-case unchanged parent:128 pass,30 ordinary failures,13.48s,exit1.
These are22 combined-trigger execution/compiler failures and8 missing explicit
unsupported-payment diagnostic assertions, not30 independent product bugs.
Final same158 checks with this patch:158 pass,13.28s,exit0.
No xfails, deselections or weakened canonical assertions in the new checks.

Canonical behavior includes both seats, exile destinations, owner/controller,
creature suppression vs artifact, counters/LKI, real generated token replacement,
ordinary spell discard costs, repeated cycling, same-name separate instances,
opponent cycling exclusion, no-target team effects, actual source sacrifice and
incarnation bookkeeping, API rejection root/controller/SQLite invariance, and
restart/private dredge continuation. Actual Krosan Tusker search-then-draw passes
six HTTP cases on the parent composition (default optional accept), not a new
claim about an explicit private search-choice protocol or optional decline.

16 neighboring modules (neighbors.files):282 pass,15 deprecation warnings,
20.56s,exit0. This includes existing self-cycling/training, dynamic death, counters,
trigger targets, resource events and identity checks. This is not a broad matrix
or live deployment qualification. Test timing is not a performance improvement
claim. Initial family source-sacrifice signature errors and the first draft's
untargeted target-metadata mistake are retained, superseded by full green reruns.

The first generic draft produced free Drake tokens /Faith life gain with no mana
left. paid-before.log retains four ordinary failures. The explicit unsupported
boundary is necessary; current parent did not previously recognize these clauses,
so do not label those draft-only free rewards as a parent regression.

## Reproduction

Source-only checkout without .git, fresh local SQLite, external main interpreter:

```bash
cd "$ROOT/backend"
MTG_ISOLATED_TEST_ROOT="$ROOT" \
MTG_ORDERING_AUDIT_EVIDENCE="$ROOT/evidence/qualified-receipts" \
PYTHONDONTWRITEBYTECODE=1 timeout 90 \
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q \
tests/test_death_cycle_ordering_audit.py \
tests/test_death_cycle_ordering_http_audit.py \
tests/test_cycle_discard_family_execution.py \
tests/test_cycle_discard_paid_limits.py
```

Neighbor command uses the same env with timeout240 and the exact16-module list
in neighbors.files. All SQLite tests run serially, local only. HTTP tests use real
TestClient/main/repository/restart with external sockets forbidden. No liveDB,
external card requests, fabricated card facts, fake decks, balance changes or AI
hidden-information access. Source-only copies exclude DB/cache/dependencies.
19 new raw records (17 immutable old audit rows,2 additional paid-family rows),
plus unchanged existing Tormenting Voice fixture data, are used. JSON provenance
pins offline raw source and payload hashes; unsupported cards are not renamed.

CR702.29c/d underpin destination-zone self cycling and once-only combined costs:
https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt
