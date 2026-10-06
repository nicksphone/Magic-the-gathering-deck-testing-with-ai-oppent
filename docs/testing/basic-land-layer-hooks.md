# Incremental Layer Consumer Hooks

## Baseline And Scope

This is an incremental patch over the verified 1,313-file bounded layer candidate
archived at `basic-land-layer-implementation/20261006-d88dbf0`, not a patch over
bare main. The original upstream base is
`d88dbf049209e015f222f9d47d0658e8958c8c01`. A private local commit records the
frozen input for reproducible incremental diffs; its ID is not a published main
revision. The input archive, complete file manifest, and replay are verified.

Only four existing production files change:

- `events.py:capture_last_known_battlefield` captures effective colors/types and
  no power/toughness for noncreature permanents. Existing stack receipt attachment
  and its `setdefault` preservation policy are unchanged.
- `protection.py:source_matches_quality/protection_match_reason` supply state to
  the existing color reader. Type matching, unrestricted protection, keywords,
  and source/controller/target policies are not rewritten.
- `attachments.py` adds optional state to Aura/Equipment classification and uses
  effective classification in attachment legality. Nonattachments cannot attach.
  Fortification classification retains the CR exception to generic detachment;
  this is not certification of a fortify announcement/activation implementation.
- `state_based_actions.py:_apply_attachment_state_checks` detaches a permanent
  which is no longer an Aura/Equipment/Fortification without destroying it.
  Detaching bestow ends its bestow characteristics, but the independently active
  land replacement still applies. Ordinary illegal Auras go to the graveyard;
  Equipment detaches and stays on the battlefield.

The pure layer helper and all its prior consumer edits are byte-unchanged.
Helper SHA-256:
`81834b6475e80e151b783b386f71a82d02dd6faa54cb3f3de0ccc1f906e04728`.
No engine, costs, mana, API/main, schema, frontend, information, agent,
dependencies, existing testing modules, or shared parent files are edited.
New files are one golden module, one canonical receipt fixture, and this report.

## Canonical Goldens

The new module has 39 ordinary cases, both seats throughout. Additional canonical
rows are copied whole from six existing fixture families into a receipt file:
Leafcrown Dryad, Belt of Giant Strength, Bonesplitter, Prodigal Pyromancer,
Hand of Honor, and Knight of Grace. The module verifies original source hashes,
exact rows, and Oracle IDs. It also reuses the frozen 18-card golden corpus.
No invented gameplay cards or Oracle edits are used.

Physical cards are hydrated through real `MatchFactory.from_decks` in controlled
one-card hydration fixtures, then placed in the existing MatchFactory state
fixture. This preserves production keyword inference from canonical Oracle
text, including protection qualities; it is not a competitive deck construction
or deck-balance claim.

New acceptance covers:

- Actual checked Song cast/resolution, each LKI color/stat field independently.
- Live source-quality, protection, and hexproof consumers before and after
  replacement, with unchanged root snapshots during pure queries.
- Actual checked Seas casting, bestow casting, and Equipment activation;
  subsequent actual Song resolution detaches the converted source as a land.
- No reattachment of converted sources and checked invalid-equipment rejection
  without root mutation.
- Older checked Royal Assassin and Prodigal Pyromancer activations retain their
  stack objects and accurate departure LKI, then resolve after snapshot restart.
- Returning/re-entering the same card ID gives a new incarnation and cannot
  overwrite the older stack object's colorless-land LKI with its new black
  creature receipt. Actual old ability resolution still occurs after restart.
- Ordinary host departure preserves Aura versus Equipment versus bestow behavior.
- Both-seat opponent-hand/library canonical counterfactual invariance, immutable
  root queries, and a fresh-process JSON snapshot round trip.

Stack-LKI setup uses a **controlled canonical Song attachment fixture** after
the real checked activation, followed by the existing destruction/bounce effect
primitive. It does not pretend Song can be cast in response as a sorcery. The
engine correctly rejects that announcement; no flash permission is invented and
no stack/timing rule is bypassed inside a claimed actual cast. Those seam tests
qualify retained stack resolution and LKI, not a complete legal deck episode
containing an unqualified flash enabler. The other Song/attachment cases use
actual checked casts and resolution.

## Red And Green Proof

The exact final 39-case module, without product changes, is run in a separate
local copy of the frozen input. Result: **32 assertion failures, 7 passes**,
exit 1, 4.93 seconds. No xfail/skip marks mask these failures, and no missing
API/attribute/scaffolding exceptions remain in this final red proof.

After the four seams, the same test bytes pass ordinarily. The final broader
gate includes them and the prior 583-case gate plus existing bestow, hexproof,
equip, aura, ward, stack-copy, combat-ability provenance, targeting, conditional
static, and opening-hand controls: **1,071 passes**, no skips or xfails, exit 0,
84.16 seconds. Its 118 existing Pydantic UTC deprecation warnings are recorded.
The 39-case focused run is a subset, not additional cases.

The pinned interpreter is
`/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`, Python 3.12.3.
All eight committed backend dependency pins were checked exactly before gates.
No install, paid service, model download, live SQLite, or user game was used.
Existing HTTP tests ran only in the isolated local source with its own SQLite.
This is affected-backend qualification, not a whole-project/shared-browser gate.

Commands use `-m pytest -q` from the isolated `backend/`:

```text
tests/test_basic_land_hooks.py
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
tests/test_bestow.py
tests/test_hexproof_variants.py
tests/test_equip_context.py
tests/test_aura_costs.py
tests/test_ward_resolution.py
tests/test_ward_forms.py
tests/test_copy_stack_characteristics.py
tests/test_combat_ability_provenance.py
tests/test_target_restrictions.py
tests/test_targeting_advanced.py
tests/test_conditional_static.py
tests/test_opening_hand.py
```

A second local composition starts from the prior verified
`qualified-parent-composition.tar.gz`. All four owned source files are checked
against the frozen input before applying the incremental change. Parent mana,
engine, and other code stay byte-unchanged. The new goldens and its 264-case
produced-type module pass together: **303 ordinary passes**, exit 0, 11.23
seconds. These are a separate source context, not 303 additional distinct cases
on top of the first gate. No new existing-test xfail removal is included.

Early scaffolding failures are archived but not acceptance evidence: equip
requires a top-level target ID; raw metadata-only card construction omitted
production protection inference; sorcery casting cannot interrupt an ability;
JSON wire round trips normalize integer dictionary keys and tuple containers.
The final red run and ordinary gates correct these tests without weakening their
gameplay assertions or changing the frozen helper.

## Rules And Limits

The [official rules page](https://magic.wizards.com/en/rules) linked
[CR effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
when checked October 6. Relevant rules: 208.3 (noncreature stats), 305.7 (basic
subtype setting and ability origin), 613 (layers/dependency/continuation),
113.7a/608.2h (stack independence/LKI), 702.103f (bestow detachment), and
704.5m-p (attachment SBAs). No fresh Oracle revision is claimed.

The three previously reproduced hook defects are resolved in these ordinary
tests. **Whole Song support is still not certified.** The following existing
printed-color readers remain outside ownership and require coordinated audit:

- `effects/handlers.py:deal_damage` uses correct receipt color names when LKI is
  supplied, but its live-source fallback still reads printed colors. Propose
  a separately owned state-aware live-source path with real prevention tests.
- `targeting.py` source-quality construction still appends printed color names;
  the approved protection/hexproof paths are now state-aware, but other selector
  consumers need independent goldens before changing their policies.
- `static_conditions.py` and `oracle_effects.py` have live permanent-color
  selectors/counts. Propose state-aware forwarding only where the queried
  object's current battlefield characteristics are required.
- `casting_resources.py` and `costs.py` read colors for resource/payment choices.
  These remain Sagan/parent-owned; later animation of a converted colorless land
  is particularly relevant to colored-resource acceptance.
- `combat.py` color-dependent blocking and `hooks.py` source-color context reads
  require coordinated color/source-LKI and incarnation qualification.
- `mana.py` resource-color helpers and the AI's colored-permanent readers remain
  unedited. Graveyard and copied-spell color reads may intentionally be printed
  reads; `stack_engine.py` spell-copy handling must not be blindly rewritten.

No edits or production exceptions for these readers are proposed as part of this
patch. Scope approval and separate red/green cases are required before expanding.
The tested source-handle direction is old colorless-land LKI versus a new black
creature incarnation; all source-copy/old-versus-new characteristic combinations,
general layer cycles, Fortification gameplay, and the full corpus remain
unqualified. Existing effective classification's legacy no-state callers are
preserved for compatibility; further consumers need targeted ownership.

## Artifacts

Verified completed evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/basic-land-layer-hooks/20261006-frozen-candidate`.
It contains the four-file product patch, separate tests/report patch, complete
incremental patch, exact frozen/final manifests, red/green logs and commands,
canonical receipts, source/runtime snapshots, parent composition, zero-API AST
graph refresh, patch replay, and NFS copy/checksum verification. Active source,
test scratch, and SQLite stayed local; only stopped evidence is archived.
