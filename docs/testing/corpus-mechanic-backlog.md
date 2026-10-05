# Corpus Mechanic Backlog

Status: independent, offline planning sidecar, 2026-10-05. No engine/AI changes,
live imports, per-card HTTP, or correctness certification. Priorities are work
ordering, not tactical scores or estimates of trained competence.

## Evidence Boundary

Engine/classifier source is frozen at `4334e370`. Parent has advanced separately;
re-evaluate these candidates on the exact promoted revision before starting or
closing a family. These are **known-gap flags**, not measured failing effects.
Absence of a flag means unassessed, never correct. A handler or a passing focused
test does not certify a whole mechanic family.

- Canonical snapshot: `38690` rows;
  `5c91bd9bb925bb4d8932420d27c80d29bfd129cbcf99b3768eb8b87495953cdc`.
- `backend/rules_engine/coverage.py` SHA256:
  `763612db3b9778be0db6ab8555d84f0c3c3ce50e68408f502479ec37f68aa654`.
- `backend/decks/builtin_decks.py` SHA256:
  `236bc11807d9aeea3134c2b1ec9d1fa73a29d9dc366bf0e11a79ed605a14c0b3`.
- Historical official oracle bulk is dated 2026-09-27 and digest-pinned in the
  campaign source ledger. Cathar is the one current-response exception; it does
  not alter these mechanic flags. No latest-upstream all-card freshness claim.
- All-card ruling preparation has completed independently: `38690` validated
  rows, `18609` dated-bulk verified empty lists, `20081` nonempty lists. This
  improves facts/provenance, not effect execution or trained competence.

Artifacts are under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/knowledge-corpus/all-card-4334e37/`:
`mechanic-backlog-inventory.json`, `readiness-and-deck-coverage.json`,
`source-provenance-ledger.json`, `all-card-import-index.json`, and the immutable
campaign baseline/final reports. The inventory records **all 61 reason labels**,
row-ID sets, canonical exemplars with Oracle identity/payload hash, and actual
saved deck IDs/names. It contains no inferred numerical tactical annotations.

## Counting Contract

The `11` built-in templates contain `88` distinct canonical rows. The `76` saved
deck records (`63` distinct names) contain `113` distinct canonical rows. Both
mainboard and sideboard names are included; quantities and duplicate saved
records do not multiply unique-card counts. Resolution uses the same admitted,
playable canonical name/front-face aliases as the readiness audit, without fuzzy
matching or cache substitution. All names resolve in this snapshot.

Known-gap flags affect `4/88` built-in rows, `9/113` saved-deck rows, and `3369`
all-corpus rows. Family unions deduplicate row IDs; reason counts overlap and
**must not be summed**. Deck-record exposure counts are not distinct archetypes:
several expansion templates reuse one built-in list. A metadata-ready card can
still have a semantic gap. A deck with no known gap still lacks rule certification.

There are no generic characteristic/match-metadata gaps among these resolved
built-in or saved-deck cards. Across ALL canonical rows, `13` generic warnings
remain: ten minigame continuation type lines, two back-face starting-loyalty
exceptions, and B.F.M. characteristics. These are source-backed review cases,
not justification for guessing new values. `504` stored-name nonadmissions and
`3636` nonplayable rows are reported separately, not silently renamed/excluded
from the corpus. No cache-parity or runtime-hydration guarantee is inferred.

Nested `mechanic_metadata` is missing on all `38690` existing rows. That is a
**metadata materialization backlog**, separate from gameplay implementation.
Use a new checkpoint/output namespace, reviewed version pin
`canonical-tactical-surface-v1`, and chunks of at most `500`; preserve tags,
scores, names and ruling evidence. Do not extract ~206 MiB merely to audit
readiness. See the archived `metadata-backfill-plan.txt`. Input/version currency
does not imply semantic verification, executable support, or training quality.

## Deck-First Family Queue

Counts are canonical rows, not executions. The first table keeps narrowly
related overlapping reasons together; larger family groupings follow separately.

| Family | All Rows | Built-In Rows | Saved-Deck Rows | Canonical Exemplars | Work Type |
| --- | ---: | ---: | ---: | --- | --- |
| Suspend | 109 | 1 | 1 | Rift Bolt (`6491`), Aeon Chronicler (`24282`) | Dedicated route candidate; inspect inherited infrastructure, then bounded implementation/qualification |
| Controller-linked damage + land-entry alternatives | 3 union | 1 | 1 | Searing Blaze (`17559`), Chandra, Pyromaster (`15767`), Soul of Shandalar (`25960`) | Existing narrow handler; qualify scope, do not reimplement wholesale |
| Linked discard sequence | 58 | 1 | 1 | Fable of the Mirror-Breaker // Reflection of Kiki-Jiki (`28997`), Anje's Ravager (`21533`) | Existing narrower instructions; optional/chapter wording candidate |
| Counter replacement route + unrecognized clause | 45 union | 1 | 1 | Soul-Scar Mage (`93`), Branching Evolution (`6133`) | Existing damage/counter routes; qualification and detector reconciliation |
| Kicker + multikicker + kicked-cast trigger fidelity | 237 union | 0 | 1 | Archangel of Wrath (`367`) | Existing bounded forms; dual optional payment/ETB-count qualification |
| Domain | 57 | 0 | 2 | Herd Migration (`33730`), Leyline Binding (`27181`) | Existing token/cost paths; qualification before warning changes |
| Incubate | 37 | 0 | 2 | Chrome Host Seedshark (`19760`), Sunfall (`37951`) | Existing token/transform/X paths; qualification before warning changes |

Suspend and both Searing Blaze reasons each expose `11` saved records (`8`
distinct names), including Mono Red Aggro and Burn. Fable exposes `10` saved
records (`9` names), including Midrange. Soul-Scar Mage exposes `6` saved records
(`5` names), including Mono Red Aggro. Kicker/Domain/Incubate expose the saved
Yoshihiko Ikawa Domain Ramp deck, one record each. Removing multiple warnings
from one card is not multiple cards fixed; removing a flag alone fixes nothing.

## Next Two Bounded Batches

### Batch 1: Suspend Lifecycle, Starting With Rift Bolt

Why: reaches two built-in templates and eleven saved records with one canonical
fixture; the corpus flag covers 109 rows. A bounded first contract must not claim
all 109 forms. Frozen-source search finds Suspend only in the coverage pattern,
not a dedicated route in `backend/rules_engine` or `backend/effects`; this is
inspection evidence, not a proof that every possible execution is broken.

Canonical exemplar: Rift Bolt, row `6491`, Oracle
`2b8afa9f-4236-4c02-a8d5-3c145caecfd6`, payload SHA256
`86ac58d06d285c00371dcf0d10b5097157f350ee561b89be0d506e8b144d15df`.
Its archived printed surface has an ordinary damage spell and a Suspend 1 cost.
Use its dated verified ruling list from the import artifact; no extra fetch.

Relevant existing engine entry points:

- `backend/rules_engine/move_generator.py:72`, `legal_moves`: distinguish the
  hand special action from an ordinary paid cast and from exile cast permission.
- `backend/rules_engine/engine.py:133`, `_apply_step_start_actions`, emits the
  upkeep event at line 146; pair it with `backend/rules_engine/events.py` and
  `backend/rules_engine/keyword_triggers.py`, not an ad hoc turn polling loop.
- `backend/rules_engine/foretell.py` illustrates durable exile permissions, but
  its timing/face-down semantics are **not** Suspend semantics to copy blindly.
- `backend/game_state/state.py`, `CardInstance.reset_zone_counters`, and
  `backend/game_state/serializers.py` are the actual zone/counter/snapshot seams.
- `backend/rules_engine/cast_choice.py`, `action_validation.py`,
  `stack_engine.py`, and `oracle_effects.py` govern legal choices, announcement,
  payment alternatives, stack resolution and ordinary damage.

Acceptance plan, not executed by this sidecar: canonical paid-cast control;
legal/illegal special actions with no mutation on rejection; upkeep countdown;
last-counter removal and the printed optional cast branch; target selection;
countered/declined/unavailable-target paths; object/zone identity and restoration
at each pending boundary; both seats. Keep nonfixed/trigger-dependent forms
such as Aeon Chronicler outstanding until their own source-backed contracts pass.
No name-specific dispatch, training success claim, or broad warning removal.

### Batch 2: Optional Linked Discard Counts, Starting With Fable

Why: one built-in Midrange card exposes ten saved records. The family flag covers
58 rows, but chapter-prefix/optional-count support is a narrower first contract.
If parent already qualifies this on newer source, substitute the counter-event
qualification below rather than duplicate completed work.

Canonical exemplar: row `28997`, Oracle
`c0957e5e-c71b-439c-931c-9f55d2f76ace`, payload SHA256
`e551220e6a90bb8a89952b25b4fcb0008c7dc06460998712ab3b54b6c36eebee`.
Use the complete canonical face payload; the root has no Oracle text. Chapter II
is optional discard up to two with a draw count tied to that discard. Do not
infer a fixed draw number from keyword tags or from remaining hand size.

Actual engine paths:

- `backend/rules_engine/linked_discard.py`, `linked_discard_gaps` and
  `linked_discard_effect`: narrower complete discard/follow-up instructions are
  implemented; their recognition is not a blanket match for the canonical
  chapter's optional wording.
- `backend/rules_engine/oracle_effects.py:1399`, `extract_saga_chapters`, and
  `infer_effect_from_oracle`/`_infer_clause_effect`: chapter text extraction must
  preserve optionality and causal count linkage rather than generic partial
  draw/discard recognition.
- `backend/effects/handlers.py:2473`, `discard_cards`, and line 2503,
  `resolve_discard_followup`: actual chosen count and pending follow-up plumbing.
- `backend/rules_engine/zone_actions.py`, `engine.py`, `events.py`,
  `stack_engine.py` and serializers: counted events, owned choices,
  trigger ordering and durable continuation; inspect before changing them.
- `backend/rules_engine/keyword_actions.py:348` calls the discard follow-up
  after an owned pending selection; `engine.py` routes the mechanic choice.
- Existing evidence: `backend/tests/test_linked_discard.py`,
  `backend/tests/fixtures/linked_discard.json`, and
  `docs/testing/linked-discard.md`. Historical tests are not rerun/recertified here.

Acceptance plan: current canonical face/chapter fixture, renamed identical-text
control, decline and zero/one/two selected cards, constrained hand size,
wrong-player/duplicate/too-many selection rejection without mutation, draw
exactly the observed discard count, simultaneous trigger sequencing, restart
while pending, and both seats. Do not equate this with all Fable faces, Saga
transform rules, copied abilities, or every one of the 58 flagged rows.

## Existing-Handler Qualification Queue

Searing Blaze: frozen `linked_targets.py` already recognizes its complete
canonical instruction, enumerates linked player/planeswalker-creature pairs,
captures object references, and resolves through `resolve_linked_damage`.
Actual call sites are `oracle_effects.py:231` and `:851`,
`targeting.py:94`, `action_validation.py:25`, and the `linked_landfall_damage`
handler route in the effects registry. `land_history.py` supplies controller
history; `landfall.py` has other complete alternatives, not generic damage.
Read `docs/testing/linked-controller-targets.md` and its remaining acceptance
before selecting a new batch. The two coverage regexes remain conservative even
with this route present. Qualify the exact implementation, then consider narrowly
scoped diagnostics; do not drop the whole three-row family based on one card.

Soul-Scar Mage: `replacement.py:268`,
`replace_noncombat_damage_to_creature`, already routes converted damage through
counter placement. `effects/handlers.py:179`, `deal_damage`,
`counter_replacements.py`, `counter_placement.py`, and pending replacement
continuations are actual seams. `test_damage_counter_replacements.py:140`
explicitly tests its recipient modifier. The generic counter-clause classifier
can still flag its printed damage-to-counter instruction. Prioritize canonical
damage/provenance/prevention/order/restart qualification, not adding a duplicate
counter multiplier or asserting all 45 rows work.

Domain: `domain.py`, `hooks.py:155` (`_apply_domain_self_discount`), token
handlers, and `test_domain_tokens.py`/`test_domain_costs.py` already cover narrow
forms; the former explicitly retains a Domain known-gap flag. Incubate:
`oracle_effects.py:346`, `effects/handlers.py:725` and `:1728`, registry bindings,
and `test_incubate_rules.py` show existing dynamic-count/token/transform routes.
Kicker: `kicker.py:43`/`:83`, `permanent_kicker`/`kicker_surfaces`, and existing
permanent/nonmana/trigger goldens are narrower than arbitrary Kicker forms.
These are semantic qualification queues, not absent source facts.

## Broader Corpus Queue

After deck-first bounded contracts, tackle explicit subgrammars, never an entire
keyword based only on frequency:

| Family Union | Flagged Rows | Relevant Existing Paths |
| --- | ---: | --- |
| Conditional static predicate/instruction | 834 | `rules_engine/continuous.py`, `type_effects.py`, `tests/test_conditional_static.py` |
| Combat clause/subject/condition/payment/targeted-block requirement | 671 | `combat_constraints.py`, `combat_payments.py`, `combat_requirements.py`, `tests/test_combat_coverage_diagnostics.py` |
| Morph/Manifest | 227 | Zone/object model, `move_generator.py`, `oracle_effects.py`; dedicate face-down state and permission contracts, not generic face hydration |
| Scry trigger/replacement/dynamic X | 132 | `rules_engine/scry.py`, event and pending-choice plumbing, `tests/test_scry.py` |
| Surveil trigger/replacement/dynamic X | 55 | `rules_engine/scry.py`, `events.py`, `tests/test_surveil_mill.py` |

Further exact-label counts/exemplars are in the inventory (additional costs,
graveyard permissions, enchant restrictions, phasing, suppression, attachment,
craft/discover/mutate and others). The union of all 61 sets is 3369, not the sum
of table cells. Unknown unflagged mechanics and unsupported interactions can
remain outside every set. No all-card effect competence is claimed.

## Reproduction and Gates

The archived `backlog-inventory.py` reuses the existing immutable readiness
report, parser grammar, canonical admission/alias selection and local read-only
snapshot. Built-in literals are AST-read without bootstrap/app lifespan. It
never runs `card_mechanics_inventory.py`'s DB-initializing CLI or broad sync.
No new canonical data, tactical tags or nested metadata are materialized.

Before parent chooses a family: pin the promoted source hash, inspect the exact
canonical exemplar and ruling snapshot, run relevant isolated tests, add missing
canonical/negative/rename/restart contracts, and record results separately from
metadata completeness. Do not remove a gap based only on an empty detector or
an existing handler. The A recovery suite's 47 passing tests qualifies corpus
tooling, **not** any engine family proposed in this document.
