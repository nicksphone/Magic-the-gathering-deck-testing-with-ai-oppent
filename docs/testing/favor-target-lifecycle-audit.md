# Favor Target Lifecycle Audit

Immutable source: 55ebc8c6cba982300f85289bdbe3d114fa29b2e5. TESTS ONLY.
Family ownership: Fertilid's Favor here; Fertilid assigned separately to Lagrange.
Only new Favor-prefixed support/worker/tests, canonical intake fixtures, and this
report. No original test, production, UI, schema or action-contract changes.

## Terminal Evidence

New two-module gate: 42 cases, 30 PASS / 12 ordinary FAIL, 34 warnings, 39.75s.
Core: 26 cases (18 PASS / 8 FAIL); ASGI HTTP: 16 cases (12 PASS / 4 FAIL).
No skip/xfail/deselection, outcome monkeypatch, injected StackItem or fake event.
Unchanged producer compiler, resolver-contract and runtime-dependency neighbors:
three WHOLE modules, 61 PASS, 2 warnings, 9.05s. This is not another whole release
certificate, and no general targeted-search or blink support claim follows.

Eight strict Favor failures: four direct both-seat find/fail rows plus four
memory/file ASGI rows. The optional creature target gains hexproof from a real
paid Snakeskin Veil before Favor resolves. Its player target remains legal.
Search, private choice, tapped entry/shuffle and completion proceed, but Favor
incorrectly changes the creature from one +1/+1 counter to three. File-backed
rows reproduce this after an actual cold-process HTTP restore and choice POST.

Four independent strict response failures: actual paid Cloudshift compiles as
exile-only and leaves Grizzly Bears exiled instead of immediately returning it.
No post-blink Favor/source-incarnation conclusion is claimed from those rows.
Full printed response text, paid stack and resolved state are preserved; this
is false partial admission, not a fabricated blink workaround.

## Observed Causal Seams / Proposals Only

In both captured hexproof states, authoritative
validate_hexproof_shroud_targets says the creature target is illegal. Existing
clause_target_assignments returns None because the two parts emitted by
oracle_effects._infer_targeted_search_effect lack clause_text. Consequently the
existing nonmodal multi-target effect_sequence resolution branch cannot bind
and prune the illegal counter instruction. add_counters only tests battlefield
zone, so it later adds the two counters to the still-present hexproof creature.
Nonmutating read probes preserved full root equality. Minimal follow-up proposal:
compiler-owner review of complete per-instruction clause/target metadata using
the existing clause binding/resolution seam; no card-name exceptions, blanket
friendly-target rules, new effect_controller field or action schema is needed.
No such product edits are authorized or applied by this audit.

Cloudshift's actual paid descriptor has key exile with no return instruction.
Its complete exile-then-return text is being partially consumed by existing
Oracle inference. A separate compiler/handler completeness review is needed;
this audit does not implement or certify generic blinking. Jason need not infer
a shuffle/source-incarnation defect: reached Favor shuffles retained the real
spell source, original caster and stack ID correctly.

## Scope and Positive Controls

Canonical Favor paid four mana, responses paid one, and all priority passes and
choices were real checked engine/API actions. Initial board/library/resources
are explicit canonical retained fixtures, not a historical reconstruction.
Full raw Favor/provenance is reused unchanged from committed targeted_search;
new full raw Grizzly Bears, Unsummon, Lightning Bolt, Snakeskin Veil and Cloudshift
responses have intact source URLs, oracle IDs, retrieval timestamp and SHA256.
No shortened Oracle or invented stats/cards. Provenance was verified before
runtime, then the runtime stayed offline.

Both-seat legal counter-target controls and deliberate zero optional counter
choices pass. Genuine Unsummon returns the target to hand; genuine Lightning
Bolt kills it before Favor resolution; both reached search/completion without
illegal counter application. Deliberate [] fail-to-find and no-eligible-library
cases still shuffle. The caster's library is unchanged; selected basic lands
enter tapped under the affected player's ownership/control. Original caster
remains continuation controller and genuine shuffle cause controller.

Private legal options remain affected-seat only; public pending packets contain
only prompt keys. Decision views mask never-observed opponent cards and all
opponent libraries. An actually public creature returned to hand may retain
its recorded authorized identity; that is not a leak or a hidden-state peek.
Wrong actors, foreign IDs, duplicate selections, actions during resolution,
stale cast actions and raw effect_payload injection reject with root/controller/
SQL unchanged. File SQLite cases restore the exact paused root/controller/SQL
in a new process, query both seats, reject wrong actor, POST the explicit choice,
and read back exactly the child's persisted state.

HTTP means actual FastAPI ASGI routing via TestClient, NOT TCP sockets/browser.
Eight independent file-backed cold workers executed real choice POSTs, including
two rows whose later desired assertion exposes the hexproof defect. Workers
forbid network connections/startup and constrain SQLite/path access to the own
local root. Memory rows use persisted same-process restore, not cold DB claims.
No live/main/parent service or SQLite access.

Favor's filter is basic_land: a nonbasic shockland cannot legitimately create
an entry-choice pause for this spell. No qualifying basic-land entry-choice
fixture was established; no nonbasic/filter override was used. Ordinary real
entry/counter preparation and delayed suffix completion are exercised, but
shock-entry pauses and successful actual target blink remain explicit limits.

## Rule Basis and Reproduction

Official CR effective September 25, 2026: 608.2b requires illegal targets not be
affected while other legal targets allow resolution; 608.2c preserves instruction
order. 701.23b permits failure to find the stated quality in a hidden zone.
Source: https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt
Official complete rules and Favor rulings intake are archived as evidence.

From source-only Git checkout (including tracked assets), use external qualified
Python and an own local basetemp:

```sh
export MTG_ISOLATED_TEST_ROOT="$(pwd)"
cd backend
PYTHONPATH=. /home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python -m pytest \
  tests/test_favor_target_lifecycle.py tests/test_favor_target_lifecycle_http.py \
  --basetemp="$MTG_ISOLATED_TEST_ROOT/.favor-audit-runtime/reproduction" -vv
```

On this immutable baseline the twelve failures must remain ordinary failures.
Do not remove assertions/rows or reinterpret them as support. The historical
first gate (14PASS/12FAIL) is preserved: four new privacy assertions wrongly
required a publicly bounced creature to be unknown; four passed CardInstance
instead of card ID to effective_keywords; four are the unchanged actual
Cloudshift return gap. Correcting those two test mistakes retained every desired
mechanical outcome and all original repository assertions.
