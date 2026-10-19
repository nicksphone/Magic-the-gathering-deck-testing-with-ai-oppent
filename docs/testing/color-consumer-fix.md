# Bounded Color Consumer Fix

## Input And Ownership

Incremental over frozen test-only patch `5fdace0d`, not a current-parent whole-gate
claim. Its qualified source archive SHA256 is
`5692903699cb2f04b098b4510b5ddf6a44d81f546b7d156f4372c000643674cb`.
That source includes the assigned parent current-surviving-access composition
(layer hooks d389 plus resource9f5b), then the unchanged 45 canonical requirements.
The archive chain, input source hashes and private baseline commit are retained
with the evidence. No parent active root, published main or live DB was written.

Exactly five existing product files change:

| File | Individually Bounded Change |
| --- | --- |
| `effects/handlers.py` | Supply state only to live damage-source colors and the colored mass-exile affected-set selector. Captured damage LKI still takes precedence. |
| `rules_engine/static_conditions.py` | Supply state only in the existing color-permanent branch, for both supported AND and OR reads. The characteristic-color branch is untouched. |
| `rules_engine/protection.py` | Accept optional captured source colors/types in source_matches_quality and protection_match_reason, including a local retained-source query view; keep current target protections. |
| `rules_engine/targeting.py` | Forward optional source_lki in the two protection/hexproof validators. Target zones, controllers, effective keywords and player immunity still use current state. |
| `rules_engine/stack_engine.py` | Forward captured source_lki for the existing single-target activated-ability recheck and retain it on that local copied source for nested hint filtering. |

Product diff: 27 insertions, 16 deletions. Two new files accompany it: a four-case
type-projection regression and this report. No new production helper is needed.
Original 45 tests, their canonical receipt, prior report, basic_land_layer.py,
events.py and all other existing files remain byte-identical. In particular,
**events.py is not edited**; Sagan retains self-death LKI ownership. No mana,
costs, engine, action_validation, AI, schema/API, frontend or CI changes occur.

## Retained Source Interface

The existing validators keep their call shape; `source_lki` is an optional
keyword-only input. When provided, captured `color_names` and `types` are
authoritative, including empty colors. There is no fallback to printed/current
source characteristics merely because a captured set is empty. Omitted receipt
retains existing state-aware live source behavior. A reader can use a supplied
receipt without a current source card, but absent-card stack execution is not
newly qualified here.

Stack resolution already makes a shallow local copy and overlays receipt fields.
The fix additionally labels that local query copy `_retained_source_lki`, so
nested target-hint protection/hexproof readers receive the same frozen source
characteristics even when they do not expose a receipt parameter themselves.
This does not add a dataclass/schema field, annotate the state-owned card, change
its zone/Oracle or disable global layers. The marker is read-only and confined
to the query view. Existing explicit validators also receive the receipt directly.
Target characteristics are never frozen by this source projection.

The source controller remains the existing captured field; ability controller
remains the existing StackItem controller. Receipt dictionaries and old
incarnation references are not rewritten. No caching or query scope is added
across capture, exile, triggers or other mutations.

## Ordinary Qualification

The **unchanged 45** final requirements reproduce **20 assertion failures,
25 passes**, exit 1, 8.78 seconds before any production edit. After the initial
explicit-receipt fix they pass 45/45 in 8.26 seconds. Final focused qualification,
with the added type controls and the complete projection, passes **49/49** in
10.19 seconds, exit 0, with no skips, xfails or deselections.

The supplemental four cases cover both seats and both old/new type directions.
Royal Assassin's activation is actually checked. The creature departure branch
actually casts/resolves Unsummon; the converted-land departure uses an explicitly
controlled bounce primitive, not a claimed legal Unsummon. Reentry, Song/Spirit
Mantle attachment and later canonical Nissa animation are controlled seams, not
a claim of sorcery-speed spells/loyalty activation in response. Exact existing
Spirit Mantle and Nissa fixture hashes/Oracle IDs are checked. No Oracle card is
invented or edited; Nissa's canonical +1 is projected onto a local parser surface.

With explicit receipt forwarding but **without** the local query-view projection,
the final four tests produce **2 ordinary target-zone assertion failures and
2 passes**, exit 1, 1.64 seconds. A departed land source's receipt is wrongly
replaced by its later animated reentry's creature type during nested hint
filtering. With projection, the captured land can still resolve its old ability
against Spirit Mantle's protection-from-creatures target; an old creature source
still cannot. This is why the marker propagation is required beyond the original
45 color cases, not a speculative global extension.

Exploration is retained separately: the first nonanimated four type controls
passed without the marker; they did not prove the later-animation boundary.
An initial animation setup incorrectly required the types set to contain only
Land/Creature, omitting the engine's Elemental subtype. Those two setup failures
are not counted as ordinary production-red evidence. The corrected final test
bytes use the appropriate inclusion assertion and reach the target-zone failure.

The final affected gate passes **371 checks**, exit 0, 28.36 seconds, across the
15 modules listed in qualification-command.sh. It includes all final 49 cases,
the complete previously selected 144 existing neighbor cases, and additional
source-quality targeting, static suppression, counterability, copy, prevention,
hexproof and combat-ability provenance checks. Counts overlap and are not additive.
**Nine HTTP cases are deliberately deselected** by `-k 'not http'`; their exact
node IDs are archived. This is not an API/browser or full-project gate.

SQLite/socket audit guards are active before collection and throughout execution.
Existing main backend venv Python 3.12.3 and all eight exact requirements.txt pins
are verified; no dependency installs. No SQLite file is created in the isolated
checkout. Both seats' immutable roots, retained receipts/controller/incarnation,
restart, atomic rejection, fresh subprocess snapshots and opponent hand/library
counterfactual decision_view invariance are exercised by the unchanged goldens.

Ten before/after state receipts also reproduce actual Ugin selection, actual Song
static conditions and live/departed damage. All ten bounded outcomes now match
their expectations; retained input roots remain unchanged. These are controlled
canonical positions, not naturally chosen competitive episodes or win-rate proof.

## Commands And Rules

From the isolated backend, with E set to the evidence directory:

```sh
PY=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
PYTHONPATH="$PWD" "$PY" "$E/qualification.py" -q \
  tests/test_color_consumer_goldens.py tests/test_retained_source_type_projection.py
E="$E" "$E/qualification-command.sh"
PYTHONPATH="$PWD" "$PY" "$E/reproduce-receipts.py" /tmp/color-consumer-receipts.json
```

The frozen investigation's rules basis remains Wizards' [rules page](https://magic.wizards.com/en/rules)
and [Comprehensive Rules effective 2026-09-25](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt):
CR 113.7a/608.2b/608.2h for independent abilities and LKI, 400.7 for reentry,
613 for layers, and 702.16/702.11 for protection/hexproof. No new Oracle freshness
or wider rules certification is inferred from the cited rules.

## Remaining Bounds

No whole-Song, all-printed-color-reader or current-parent composition certificate.
Static characteristic-color predicates, combat blocking, costs/mana/AI readers,
library/graveyard filters, triggered target selection, other multiselect/conditional
stack branches, missing-source execution, prevention-lock source identity and
arbitrary copied/incarnation combinations remain unqualified or separately owned.
No events capture policy or shared schema is changed to mask those boundaries.
Parent integration with Sagan's later events changes requires its own qualification.

NFS evidence preserves input provenance, ordinary red/green logs, exact commands,
state receipts, source manifests, surgical production and integration patches,
supplemental tests/report and a refreshed AST graph (no API cost). Frozen hashes
and archived copies are verified before disposable local checkout cleanup.
