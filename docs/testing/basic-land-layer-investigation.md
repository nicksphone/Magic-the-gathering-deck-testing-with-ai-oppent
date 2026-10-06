# Basic-Land Layer Investigation

## Scope And Status

Investigation baseline: `d88dbf049209e015f222f9d47d0658e8958c8c01`.
Only this new report, one new golden module, and its two new fixture files are
proposed. No production changes, existing-test changes, dependencies, mana
edits, engine edits, or main/live database writes are included.

The parent frozen reservation candidate has byte-identical `type_effects.py`,
`land_types.py`, `continuous.py`, and `colors.py`. This confirms the layer
finding applies to that candidate; it does not qualify its different mana code.
Its two Song/Elves expected failures are expanded here into independent checks.

**Song remains unsupported for the investigated characteristics.** A successful
cast or deterministic snapshot replay must not be reported as mechanic support.
Strict xfails are missing acceptance criteria, not passing gameplay coverage.

## Primary Rules

The [official rules page](https://magic.wizards.com/en/rules) linked
[CR effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
when checked on October 5, 2026. Relevant rules:

- 205.1a-b distinguish replacing card types from retaining existing types.
- 305.6-7 give basic land subtypes intrinsic mana abilities. Replacement removes
  printed/copiable abilities and old land subtypes, not abilities supplied by
  other effects. Additive land subtypes preserve the old abilities.
- 613.1d-f separate type, color, and ability layers; 613.6 preserves effects that
  already began applying across layers.
- 613.7 and 613.7e order independent effects by timestamps and retime attachments.
  613.8 gives same-layer dependency precedence.
- 113.7a preserves already stacked abilities independently of their source.
  603.10a and 608.2h govern lookback triggers and last-known information.

Wizards' [Commander Masters release notes](https://magic.wizards.com/en/news/feature/commander-masters-release-notes)
also describe Song: replacement of old card types/subtypes/colors, retained
supertypes/name, intrinsic green mana, removed printed abilities, preserved
external grants, and detachment when its target was an Aura or Equipment.
The current CR is the rules authority; the older card note is corroboration.
Gatherer's direct card endpoint returned HTTP 403, so no newly fetched Oracle
revision is claimed. Gameplay text is copied from committed canonical fixtures.

## Canonical Receipt

`backend/tests/fixtures/basic_land_layer_goldens/cards.json` contains 18 real
card rows selected from existing committed fixtures. `provenance.json` records
each source file/hash, canonical identifiers, and exact selected fields. The
golden test verifies those fields against the original rows; no Oracle edits,
invented card definitions, model downloads, or deck-balance claims are made.
Positions reuse the existing state-only MatchFactory fixture, not new decks.

Covered examples include subtype setting (Spreading Seas, Lush Growth, Blood
Moon), additive types (Prismatic Omen, Urborg), card-type replacement (Song),
resolved ability grants (Jump), mana creatures (Llanowar Elves), generic
activation (Royal Assassin), printed keyword (River Boa), entry trigger
(Soul Warden), death lookback (Blood Artist), and a static source (Humility).

The parser receipt explicitly recognizes the first three subtype setters but
not Song's attached-permanent setting. Checked casting accepts both Seas and
Song Auras and attaches them; this is only casting/attachment acceptance, not
certification of Song's continuous effect. An exploratory query of the existing
thin Mutavault fixture did not offer its nonmana animation. That unrelated
unsupported control was removed instead of claiming generic land-activation
coverage or inventing canonical identifiers.

## Observed Goldens

The new module has 64 cases: 38 passes and 26 strict expected failures on d88.
Running with `--runxfail` produces exactly 26 failures and the same 38 passes.
Both seats are exercised. Failed Song assertions are independently exposed:

| Property | Observed Deficit | Cases |
| --- | --- | --- |
| Types/subtypes/colors | Royal Assassin remains a colored creature, not a colorless Forest land | 6 |
| Printed loss/intrinsic mana | Printed suppression false; Royal Assassin has no green intrinsic mana | 4 |
| Generic activation | Royal Assassin's printed activation remains checked-executable | 2 |
| Existing keyword grant | Jump grant survives, but printed River Boa islandwalk also wrongly survives | 2 |
| Later creature-only grant | A new Jump still accepts the supposedly converted permanent | 2 |
| Entry trigger | Converted Soul Warden still creates new printed triggers | 2 |
| LKI/departure | Blood Artist LKI remains unsuppressed/creature; departure wrongly triggers | 4 |
| Static source | Song on Humility does not restore the Elf's mana ability | 2 |
| Same-layer source | Song on Blood Moon does not stop its land-setting effect | 2 |

Positive goldens verify intrinsic new-color activation and atomic old-color
rejection; retained Dryad Arbor creature types/colors; independent timestamps
versus Urborg/Moon dependencies; real Jump grants before and after subtype
setting; attachment retiming, retargeting, and source removal between immutable
query scopes. An already stacked Soul Warden trigger and Royal Assassin
activation both survive later Song attachment and actual source destruction.

Both-seat decision projections compare complete canonical private-card
counterfactuals, including opposing hand/library metadata, with unchanged public
boards. Opaque private identities, observations, public rule queries, and root
snapshots remain invariant. Fresh subprocess snapshot replay reproduces the
same observed query result for Seas and Song. For Song, faithful replay of a
known incorrect view is **not** gameplay acceptance. No hidden information is
used to compensate for the missing layer.

## Source-Grounded Cause

`rules_engine/type_effects.py:effective_types` handles existing materialized type
additions and the devotion condition, but has no attached permanent-to-land
replacement. `rules_engine/land_types.py:land_type_instructions` recognizes
land-subtype scopes, not Song's permanent scope or combined color/card-type
instruction. Its row view therefore never classifies the converted nonland as
a land, never records printed-ability loss, and never supplies Forest mana.

`continuous.py:printed_abilities_suppressed`, mana specs, generic activation,
trigger dispatch, and `events.py:capture_last_known_battlefield` depend on these
views. The deficit consequently propagates beyond a mana multiplier caller.
`colors.py` is presently card-only, so preserving raw printed color data also
requires an effective state-aware color read rather than mutating that data.

There is an additional source-activity seam to audit: `_printed_ability_loss_sources`
collects loss sources directly from printed text. A layer-four removal of the
source's own printed abilities must prevent that later loss effect from
contributing. Conversely, a later-layer loss must not erase a type effect that
already applied: the existing Magus/Moon-with-Humility controls are retained.
Simply calling the general suppression predicate recursively from every type
reader would introduce cycles and confuse those two situations.

## Proposed Correction And Ownership

**Proposal only; no product implementation is authorized or included.**

1. Use a bounded semantic instruction for attached permanent-to-basic-land
   replacement, distinct from subtype-only setting/addition. Recognize complete
   supported wording, not a named Song exception or a substring guess.
2. Share one pure layer-four result for effective card types, compatible
   subtypes/type line, intrinsic land abilities, and printed/copiable-origin
   loss. Apply timestamp/dependency rules to source eligibility as well as
   targets. Do not overwrite printed/copied characteristics, keyword grants,
   counters, or existing stack objects.
3. Feed the existing type/subtype/suppression consumers from that result. Guard
   later continuous loss-source collection against prior-layer source loss
   without suppressing legitimate earlier-layer continuations.
4. Add the associated effective color read at the color/view/LKI seam. Keep
   immutable query batches bounded; invalidate by ending a scope before any
   attachment, zone, controller, or effect mutation.
5. Have Sagan qualify existing mana callers against this view. Do not edit mana,
   engine mutation, action-validation, or schema files as an incidental fix.

Requested ownership for a subsequent implementation: a new shared pure-layer
helper plus coordinated edits to `type_effects.py`, `land_types.py`, the narrow
continuous source-activity seam, and the state-aware color/serializer consumers.
Parent/Lagrange must release or explicitly assign overlapping layer/view work;
Sagan retains mana ownership. Existing activation/trigger/LKI consumers should
be audited first and edited only if the shared view is insufficient.

Acceptance requires all 26 Song goldens to become ordinary passes, no lost
Seas/Moon/addition/grant/continuation behavior, both-seat atomicity/privacy/pure
queries, and fresh-process persistence parity. More copy/animation/attachment
combinations remain unqualified; this is not complete layer-system coverage.

## Qualification

Use the existing pinned interpreter, not system Python:

```sh
PY=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
$PY -m pytest -q -rxX backend/tests/test_basic_land_layer_goldens.py
$PY -m pytest -q --runxfail backend/tests/test_basic_land_layer_goldens.py
```

The second command must fail on the known d88 deficits. Related regressions run
in a fresh local, regular-source copy because their existing HTTP cases use
SQLite: land types, printed suppression, temporary loss, keyword timestamps,
additive mana, domain land layers, printed-query reuse, and land-view scopes.
These eight existing modules are selected for the shared-view consumers and
continuation/cache controls, not a claim of full project coverage. Logs,
executed bounds, exact unchanged-product hashes, source/runtime snapshots, and
archive verification are included in the NFS evidence report.

Initial scaffolding failures and intermediate bounds are preserved, not counted
as qualification. No live server/browser gate is needed for this tests-only
investigation; no current product fix or production-readiness claim is made.
