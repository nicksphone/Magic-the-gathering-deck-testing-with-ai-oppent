# Bounded Basic-Land Replacement

## Candidate And Boundaries

Base: `d88dbf049209e015f222f9d47d0658e8958c8c01`, isolated from main.
The earlier four-file golden patch is included unchanged except that its 26
Song expected-failure annotations become ordinary assertions after qualification.
This candidate is not a complete Song, color-layer, or layer-system certification.

Owned production files:

- NEW `backend/rules_engine/basic_land_layer.py`: pure, bounded semantic
  replacement parser and shared immutable layer-four characteristic result.
- `type_effects.py`: consult the shared result while retaining existing base
  devotion/materialized type logic and proxy compatibility.
- `land_types.py`: delegate resolution to the shared helper; public APIs and
  subtype parser remain unchanged.
- `continuous.py`: exclude prior-layer ability-lost sources from later loss,
  keyword removal, base-stat continuation, and diagnostic trace contributions.
  Its existing attached color-count consumer now supplies state.
- `colors.py`: optional state-aware color reads, preserving printed reads for
  callers without state and never overwriting canonical color/Oracle metadata.
- `game_state/serializers.py`: supply state to public effective-color projection.

No mana, costs, engine, action validation, schema, main, frontend, information,
agent, trigger, protection, attachment, or SBA product files are edited.
Two new testing modules, the previously frozen canonical fixture/provenance
files, and two new testing documents complete the integration patch.

## Semantics And Interface

`permanent_land_replacement(text)` recognizes a complete instruction of the
form `Enchanted permanent is a colorless <basic-subtype> land.` The five basic
subtypes are recognized; conditional, additive, creature-only, and combined
extra-ability wording is not guessed. This is semantic recognition, not a
named-card exception. Gameplay tests retain exact committed canonical rows.

`layer_four_view(state, entering=None, controller=None)` returns read-only type
line overrides, a frozen printed-ability-loss set, read-only type overrides,
and a frozen colorless-continuation set. Subtype-only setters preserve other
card types/subtypes/colors. Permanent replacement retains supertypes, replaces
card types/subtypes, and removes printed/copiable-origin abilities. Resolved
external grants, counters, and existing stack items are not cleared.

Same-layer source-loss and changed land-target sets impose dependencies before
timestamps. Independent setters and resolved additions retain timestamp order;
attachment timestamps continue to come from the existing engine. Later ability
loss does not erase earlier type effects, while a source stripped in layer four
cannot begin a later ability-loss/base-stat effect. Existing Magus/Humility,
Urborg/Moon, Omen/Moon, reattachment, and cache controls remain qualified.

The resolver memoizes only complete immutable value rows. State-bound reuse
exists only inside the existing immutable `rule_query_scope`; mutations must
occur between scopes. Returned maps and sets cannot be mutated, and returned
effective type lists are defensive copies. No global state cache or hidden
information compensation is introduced.

Sagan's interface is unchanged: `effective_types(state, card)`,
`effective_type_line(state, card, entering=...)`, and
`printed_land_abilities_lost(state, card, entering=...)`. Intrinsic mana and
printed-loss consumption are exercised without changing any mana implementation.
New consumers may use `card_color_symbols(card, state)` or
`card_color_names(card, state)`; omitted state deliberately means printed color.

Rules authority: the [official rules page](https://magic.wizards.com/en/rules)
still linked [CR effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
when checked during this implementation. Relevant rules are 205.1a-b, 305.6-7,
613.1d-f, 613.6-8, 113.7a, 603.10a, and 608.2h. The earlier investigation
contains canonical fixture receipts and official card-note corroboration; no
fresh Oracle revision is claimed.

## Executed Qualification

Interpreter: `/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`, Python
3.12.3. All eight committed backend requirement pins were checked exactly.
No dependency installation, model download, paid service, live database, or
user game was used. Existing HTTP regressions used SQLite only in the isolated
local candidate. Active databases were never run on NFS.

The final owned candidate has **583 ordinary passes**, no skips or xfails, in
60.01 seconds. This includes the original 64 goldens, all 26 formerly failing
Song assertions, and 15 new composition cases. Coverage includes both seats,
checked invalid-action immutability, hidden-info invariance, root purity,
fresh-process snapshot replay, subtype/dependency timestamps, actual canonical
Nissa animation effect paths, source departure, and immutable result controls.
Nissa tests exercise the existing real effect inference/resolution primitive,
not a claim that every loyalty announcement/choice is supported.

Executed modules, from `backend/` with the pinned interpreter and `-m pytest -q`:

```text
tests/test_basic_land_layer_goldens.py
tests/test_basic_land_replacement_composition.py
tests/test_land_type_layers.py
tests/test_ability_suppression.py
tests/test_temporary_ability_loss.py
tests/test_keyword_effect_timestamps.py
tests/test_additive_mana.py
tests/test_domain_land_type_layers.py
tests/test_printed_suppression_query_reuse.py
tests/test_land_view_scope.py
tests/test_devotion.py
tests/test_type_effect_lifecycle.py
tests/test_death_last_known.py
tests/test_triggers.py
tests/test_trigger_power_damage.py
tests/test_named_death_triggers.py
tests/test_attachments.py
tests/test_static_ability_suppression.py
tests/test_continuous_static_order.py
tests/test_continuous_static_effects.py
tests/test_continuous_source_queries.py
tests/test_split_card_casts.py
tests/test_card_hydration.py
```

These modules cover changed characteristic readers, source activity,
continuation, activation, mana, triggers/LKI, serializer colors, devotion, type
lifecycle, and query reuse. They do not establish full project/browser coverage.
Twenty existing Pydantic UTC deprecation warnings are preserved in the log.

A separate local composition starts from the parent's verified
`announced-source-qualified-backend-source.tar.gz` under
`parent-integration/spell-reservations-d88dbf0`. All five existing owned product
files were byte-identical to d88 before composition. Only the six owned product
files and the qualified Song test annotation were replaced. Parent mana,
engine, and other implementations remain byte-unchanged.

`tests/test_produced_type_mana.py` first passes all **264** cases with
`--runxfail`. Only after this result, its two Song expected failures are removed
in that disposable qualified composition. Final exact-helper rerun: **264
ordinary passes**, no skips/xfails, in 5.88 seconds. The separate annotation-only
patch is for parent review, not an ownership claim over Sagan's product files.
The focused four-case Seas/Song run is a subset, not four additional cases.
These two source contexts are reported separately rather than claiming the
583-case gate tested the entire later parent candidate.

Scaffolding failures and intermediate runs remain in evidence, not in final
pass totals. They exposed an activated-proxy attribute assumption and excess
scalar-query wrapper calls, both corrected. A typo in an optional test filename
produced a collection-only failure before the correctly named final gate.

## Required Cross-Scope Hooks

The existing trigger paths already consult effective types and printed
suppression. Blood Artist departure suppression and independently stacked
Soul Warden/Royal Assassin effects pass without trigger/stack edits. However,
the new diagnostic probe reproduces these remaining defects in **both seats**:

- `events.py:capture_last_known_battlefield` records printed black and 1/1 for
  a converted Royal Assassin, despite its effective colorless noncreature view.
  Request ownership of that LKI seam: pass state to both color reads and capture
  no power/toughness when the effective object is not a creature. Preserve
  printed text/name and stack independence, and qualify lookback/replay effects.
- `protection.py:source_matches_quality` still classifies that converted source
  as black because its color reads omit state. Request ownership of its narrow
  color-consumer seam, including `protection_match_reason`, with actual target
  and damage/source-LKI controls before acceptance.
- `attachments.py` and `state_based_actions.py:_apply_attachment_state_checks`
  still treat a converted Spreading Seas as an Aura from printed characteristics;
  it remains attached after SBA. Request the effective attachment-classification
  and non-Aura/non-Equipment detachment seam. Do not mutate printed types or
  destroy the newly non-Aura land. Qualify bestow, Equipment, and Aura controls.

These files are **not edited**. Approval was requested before any additional
product edits. `remaining-hooks-observed.json` is a defect diagnostic, not
acceptance evidence. Thus removing the narrow old Song/mana xfails does not
certify full Song gameplay.

Other printed-color readers need a separately coordinated audit: targeting,
static conditions, casting resources, Oracle effect selectors, handlers, combat,
and hooks. Mana/costs remain Sagan-owned; AI remains outside this scope. Spell or
nonbattlefield printed-color reads may be intentionally correct, so a blind
global replacement is not proposed. General copy/animation combinations,
dependency cycles, extra replacement wording, and all corpus cards remain
unqualified beyond these executed controls.

## Evidence

Completed artifacts are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/basic-land-layer-implementation/20261006-d88dbf0`.
The archive includes complete/incremental patches, the separate parent annotation
delta, exact source snapshots, stopped local runtime evidence, source manifests,
graph refresh, commands/logs, diagnostics, and checksum verification. Main,
parent staging, and their live databases were never written.
