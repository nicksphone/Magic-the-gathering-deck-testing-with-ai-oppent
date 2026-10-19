# Deterministic Tactical Profile Derivation

Source epoch: immutable `f2d4622cde2e8c46c91eeabed8a7ed28b5e4f15f`.
This implements the pure data-derivation portion of the original AI knowledge
plan Task2.1. Sync/persistence wiring is a separate parent increment. AI consumer,
scoring replacement, benchmarks and measured strength remain unqualified.

## Contract

`knowledge.profiles.derive_profile(raw_or_card, corpus=(), *, archetype=None)`
returns a frozen `TacticalProfile` dataclass. `FaceProfile` entries remain separate
with their original indices. Distinct single-face root characteristics are used
when supplied; a combined parent type line or missing root types selects the front
face for legacy scalars. Faces are never unioned into a single
castable object. These dataclasses freeze attribute assignment, not a security
capability; nested metadata is copied, not claimed cryptographically immutable.

`profile_payload(profile)` yields copied JSON primitives/lists using dataclass
serialization. `merge_profile_payload(existing, profile)` (alias `merge_profile`)
deep-copies the entire old profiles object, updates known keys inside
`tactical_profile`, and preserves unknown outer-profile and direct namespace
keys. Known generated structures, including `faces` and `context`, are replaced
as units, not recursively merged with extensions inside those structures.
An opaque existing namespace is rejected rather than discarded. Full `card_data`,
rulings, metadata, provenance and schema fields stay unchanged. Repository fields remain scalar
`play_value`, `threat_level`, `etb_impact`, with list conversions of `answerable_by`
and `cast_windows`; no model/schema/repository changes are made here.

## Estimator V1

`schema_version=1`, `estimator_version=deterministic-tactical-v1`. These are
documented heuristic estimates, not expected wins or measured board strength.

- Reuses `tactical_clauses`, canonical tactical tags and mechanic evidence for
  clause kind/cost/condition/spans. Existing full closed instruction/stack compilers
  must account for the complete effect body before any numeric payoff is assigned.
  Payoff extraction uses their payloads and existing numeric/token patterns; no new
  Oracle effect parser, card-name dispatch or resolver is introduced. RAW outside
  all source spans (including masked-only separate paragraphs) suppresses numeric
  effects and emits `unaccounted_raw_paragraph`. Generic printed
  self-references may use the source name, as the existing compilers do.
- Mana curve uses existing `_cmc` and `analyze_deck`. Supplied corpus accepts raw
  rows or quantity/card_metadata deck rows. Curve is weighted nonland mean mana value.
  `context` records its fingerprint, mean, mode and estimated deck archetype.
  An explicit archetype label is caller-declared, not verified. A pooled corpus
  without that label is never represented as an archetype-specific result.
- Fit =1 without a supplied nonland curve, otherwise
  `2-min(2, abs(card_mv-curve_mean))`. Play value =
  `min(10, 3+fit+.15*(known nonnegative printed P+T)+min(3,payoff/max(1,mv))+.5*engine)`.
  A land-only surface gets0. Trigger-engine bonus requires a compiled triggered
  body; frequency/conditions remain unknown. Non-numeric printed P/T is not guessed.
- Payoff units: draw `.8*count`, damage `.4*amount`, life/mill `.1*amount`, tokens
  `.2*count*(P+T)`, recognized destruction/exile/counter instruction1. Sequences
  sum recognized components. Other compiled effects receive no established numeric
  valuation in V1, not an assertion of no gameplay impact. Variable counts are not
  assigned0/1; unresolved/uncompiled surfaces are explicitly limited.
- Threat is0 for land-only or unknown type;3 for surface sweeper/mill/drain roles;
  otherwise2 for mana value>=4 or estimated self-entry impact>=4, else1. In particular,
  this coarse heuristic tier is not proof a spell is game-ending in a real position.
- ETB impact sums recognized numeric payoffs from complete self-entry clauses only.
  Another object's entry is not this card's ETB. A recognized self-entry condition
  with an uncompiled body yieldsNULL. Zero is an estimator's detected subtotal,
  never proof no other entry abilities exist.
- Answer routes use actual effect registry keys, target zone and targeting status.
  Printed intrinsic shroud removes targeted routes; indestructible removes destruction,
  not exile/counter. Hexproof keeps controller-targeting routes but excludes them
  from the legacy opponent-response candidate list. Printed complete self-uncounterable
  clauses exclude stack counter routes; conditional/global protections are not inferred.
  The finite self-clause test matches the existing targeting resolution predicate;
  it does not replace that predicate. Every route requires actual incoming-effect
  target-domain/current-rule validation, including protection, ward and controller.
- Intrinsic keyword paragraphs reuse the existing reminder-masked rules surface
  and whole-keyword matcher. RAW `keywords` lists, grants to other objects and
  conditional keyword clauses never confer intrinsic traits. This reminder handling
  does not relax the unmasked numeric-body compiler guard.
- Instants/printed intrinsic Flash expose conditional main/instant candidates;
  ordinary spells expose main candidates, lands land-play. Haste is only an
  attack-on-entry hint, never a cast permission. Priority, timing, payment, targets,
  layer changes and external permissions still require the actual engine.

Oracle text<=16384 chars, faces<=16, corpus<=1024 rows, exact integer quantities
0..1000 each; nonfinite numeric characteristics reject. Input SHA is consistency
provenance over caller data, not publisher authentication. Known-gap reporting
reuses the current coverage classifier: no known gap is never support certification.

## Observed Pure Evidence

Corrective complete cohort: originalNEW26 methods byte-exact, NEW8 review regressions,
plus unchanged whole tactical-tags and mechanic-metadata modules:
**60 passed +10 passing subtests, 2.65s**, exit0.
The ten subtests are not relabeled as ten additional ordinary test functions.
JUnit includes them as70 recorded testcase entries (0 failures/errors/skips).
Canonical RAW bytes/provenance pins checked; ten threat/window values and ten
name-metamorphic rows, full seed iteration/idempotence, face separation, legacy
preservation and strict unknown/context controls are exercised.

All266 inherited source/input pins are checked before/end. Three actual constructor
canaries (SQLite, socket, Popen) are denied before resource creation; unexpected IO[].
No SQL connection, game, external network/provider, subprocess child or AI chooser ran.

Historical ordinary failures remain separate: API absent28FAIL/1PASS; first product
run same count due missing immutable creature-subtype data; semantic2FAIL/17PASS
+10 subtests (NEW arithmetic expectation and dynamic limitation label); NEW22 green;
first whole47PASS/1FAIL+10 subtests due missing original fixture provenance; repaired
immutable inputs whole48PASS+10 subtests; compatibility2FAIL/22PASS+10 subtests before
nested-namespace preservation. No original test assertion or product body was altered.
The previous50+10 gate is separate. NEW raw parenthetical/quoted-tail controls then
failed2/24PASS+10 subtests: surface masking had hidden unaccounted text. Final numeric
derivation forwards the unmasked raw clause body and refuses the reminder-stripping
fallback on unaccounted quotes/parentheses; no existing compiler was changed.

Independent review and opt-in sync roundtrip remain separate before public promotion.

The prior3c60/52+10 source/gate/archive remains immutable. Peer review identified
three concrete defects: skipped RAW-only paragraphs, combined MDFC parent types,
and intrinsic keyword reminders. NEW8 yielded7 strictFAIL/27PASS+10 subtests with
oldNEW26 unchanged; the grants/conditions negative already passed. Correction changes
only `_face`, `derive_profile` and the tactical import; all other function AST bodies
remain exact. Actual Bala Ged Recovery RAW/provenance grounds the Sorcery//Land case;
the Instant//Land variant is explicitly inert schema data, not canonical card truth.
Full published Darksteel Sentinel RAW SHA
`cb8502e81d51884b604f60b56ca9adc85b8d943afde1ae585b714192f58bd423`
grounds Flash/Indestructible reminders. No effects/parser, API, estimator weights,
AI caller, schema or persistence code changes occur in this correction.
