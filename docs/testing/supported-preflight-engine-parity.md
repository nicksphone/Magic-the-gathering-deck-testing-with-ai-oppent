# Supported preflight / engine parity audit

## Frozen Source And Scope

Source: `07305a18801e884ff3e4f8a3393a7132c436e990`, immutable numeric-legacy archive
SHA256 `d9bd64251f0e651832f995cc7dc70ed6af062a2a891b5241266793d304396716`.
NEW tests only: `backend/tests/test_supported_preflight_engine_parity.py`.
No classifier repair, warning removal, database, HTTP, frontend, or game-strength claim.

## Actual Terminal Ledger

NEW20: **16 PASS / 4 ordinary FAIL**, 5.58 seconds, pytest exit 1, bound 300 seconds.
Six precollection probes deny SQLite public/native constructors and native socket creation.
The runner installs an audit hook before dependency imports and denies every socket audit event.
All preexisting backend Python/JSON/JSONL hashes match after execution.

Four production preflight-body checks pass using real `DeckPairInput(sandbox=True)`.
The exact three production function bodies are AST-extracted without decorators, not
reimplemented. Their public hydration/classifier calls use a read-only in-memory
canonical cache adapter. This is **not** live HTTP, repository, or lifespan qualification.

Eight both-seat paid Mage/Salve replacement cases pass: Lightning Bolt and Unholy Heat,
affected-player conversion-first and prevention-first, genuine prevention receipts,
explicit offered choices, wrong-actor/unoffered rejection, zero damage events, exact
counters/remaining shield/life, and snapshot roundtrip. Mage, Salve, and damage spells
are actually paid and resolved; the explicit rules fixture supplies starting resources.
Two paid Salve gain-life mode controls pass without changing canonical mode text.

## Four Desired Failures / Two Causes

1. Both seats: canonical Mage conversion is classified as an unsupported **counter
   modifier**. `coverage.known_unsupported_mechanics` routes any `If ... counters ...
   instead` line through `counter_replacements.counter_modifier`; the dedicated
   `replacement._noncombat_damage_counter_candidates` family is different. The tests
   require only removal of this wrong-family claim, not blanket card certification.
2. Two diagnostic-only Salve prevention suffixes: the closed instruction compiler
   returns `noop` plus `__unsupported_instruction`, while the preflight inventory
   returns no diagnostic. Fault-injection strings are not invented card fixtures or
   paid supported episodes. This is inventory false-negative evidence, not evidence
   that the engine executes those unsupported tails. Conversion-tail controls retain
   warnings; they do not qualify altered conversion runtime admission.

Future remedy proposals must be generic, source-grounded family classification and
closed-body diagnostic parity, preserving unsupported clauses. No name allowlist or
warning clearance is authorized. Full Mage semantics, arbitrary any-target Battle
gameplay, hidden-information policy, HTTP deployment, and whole MTG remain uncertified.

## Canonical Intake And Dependencies

Mage is the committed complete printed seed record in
`tests/fixtures/soulscar_consumer_audit/cards.json`, with its existing provenance;
it is not represented as a newly fetched full Scryfall raw response. Salve is the
committed full raw `tests/fixtures/soulscar_protection_boundaries/healing-salve.json`;
the actual sync normalizer creates cache metadata. Full Oracle, cost and type text
remain equal after production hydration. No network intake or shortened Oracle.

The new module reuses unchanged `test_soulscar_protection_boundaries` and its inherited
paid/order helpers already present at the pinned source. Frozen integration adds only
this new test and this document; no duplicate fixture/helper/product adds.

## Readiness Map Increment

Original readiness report SHA `4fd644cb51dcbe822f965ec5ea1d69914bf7b7e069bc7833878768de51f29271`
remains immutable and describes an older source. Its numeric shield priority is
superseded by parent current 48-module/1766-pass evidence and this narrow paid-order
receipt, not by a reexecution of that whole cohort here. Current next bounded work is
preflight family routing and unsupported closed-tail diagnostics. Same-source HTTP,
deployment/restart, BO3/persistence, clean install/security exposure and unsupported
mechanics remain separate release gates; this pure audit does not close them.

## Preserved Setup Ledgers

Initial NEW20: 12/8, 5.96s, four invalid empty-opponent deck inputs.
Second NEW20: 12/8, 5.52s, four one-card decks omitted explicit sandbox flag.
Both setup-failure ledgers are preserved. Only NEW input setup was corrected; all
desired diagnostic, canonical paid action, privacy and root assertions stayed intact.

## Reproduction

Use the archived `evidence/run-pure.py` with the pinned external Python:

```sh
MTG_PREFLIGHT_PARITY_RECEIPTS="$ROOT/evidence/terminal-receipts.jsonl" \
timeout 300 /home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python \
  "$ROOT/evidence/run-pure.py" tests/test_supported_preflight_engine_parity.py \
  -q --tb=short -p no:cacheprovider --junitxml="$ROOT/evidence/terminal20.xml"
```

Runner expects `$ROOT/source/backend`. Expected exit 1 retains four ordinary desired
failures; no xfail, skip, assertion weakening, or exclusion.
