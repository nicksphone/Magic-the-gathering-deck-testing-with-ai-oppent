# Color domain / continuous classification audit

## Scope

Tests and report only, on exact committed
`3ccbdf203a4ee1aeb848e219769c9dfac0f20e8c`. Initial isolated source:
`/home/nick/mtg-color-domain-audit-0VXu1S`. No frozen production overlay,
parent composition, main, production helper, stack, schema, mana, or AI edits.
The committed graph was read first; it reports an older d88 build. A local
AST-only refresh is archived separately and is not an integration change.

New files only:

- `backend/tests/test_color_domain_audit.py`
- `backend/tests/fixtures/color_domain_audit/provenance.json`
- `docs/testing/color-domain-classification-audit.md`

The receipt preserves complete existing fixture rows and hashes of their source
files. Oracle IDs can be top-level or in the existing canonical `provenance`
field. No Oracle edits, fabricated gameplay cards, or balanced-deck claims.

## Observed findings

`rules_engine/continuous.py:1027` reads stored `card.colors` in
`_subject_match_result`, although it uses live effective types immediately above.
Positive and negative color predicates therefore diverge from
`card_color_symbols(card, state)` after actual checked Song resolution followed
by actual checked Nissa +1 activation and priority-pass resolution.

| Canonical source / subject | Live color | Required power | Actual power | Direction |
| --- | --- | --- | --- | --- |
| Creakwood Liege / Llanowar Elves | Colorless | 3 | 4 | False positive green bonus |
| Creakwood Liege / Blood Artist | Colorless | 3 | 4 | False positive black bonus |
| Angel of Jubilation / Blood Artist | Colorless | 4 | 3 | False negative nonblack bonus |

The land animation supplies a 0/0 base and three +1/+1 counters. Its later
type addition makes the Song-converted land a creature again; Song still makes
it colorless. Printed green/black metadata remains intact and is not the live
classification. Both seats and deserialized snapshot variants reproduce all
three discrepancies: **12 strict ordinary failures**, not xfails or green
assertions accepting incorrect classification. Reproduction receipts include
the whole snapshot, continuous trace, exact predicates, and root-purity checks.

The standalone state-aware color query is correct in these cases. This evidence
points to its consumer, not a new layer algorithm or a named-card exception.

## Passing boundaries

The new protection examples are not the earlier Hand of Honor / Etched Champion
cases. Kelsien targeting Archon of Absolution and Royal Assassin targeting
Mystic Enforcer are rejected before alteration, with authoritative target hints
excluding the protected target and the root unchanged. After legal Song/Nissa
alteration removes the target's printed protection and makes it a creature again,
checked activation and actual resolution succeed, including restored snapshots.
Royal's post-animation tapped-target precondition is established through the
target's real intrinsic Forest mana activation; Kelsien marks one damage.

`domain.py:12` counts live basic land subtypes, not card colors. A black Blood
Artist contributes zero initially, then one Forest after Song, then one Island
after an actual Spreading Seas cast. The converted permanent remains colorless.
No domain-count defect was observed; no domain production change is proposed.

Actual Naturalize removal of Song restores printed colors on the still-animated
target. Queries are scoped separately around each immutable phase. Their stats
then coincide with the previously incorrect classification, illustrating why a
single unchanged-stat or replay assertion is not a correctness certificate.

Both-seat counterfactual opponent hand/library substitutions preserve counts,
IDs and public state. `decision_view` exposes neither substituted Oracle data
nor names; stats, decisions, snapshots, and root immutability remain invariant.
Fresh child processes independently restore all six family/seat positions with
DB/network audit guards and reproduce current stats, colors and domain counts.
Those six tests certify repeatability, not correctness of the red predicates.

## Legal episodes and controlled seams

Initial main-phase boards, ready sources, ample mana and Royal's initial tapped
target are controlled fixtures. They are not full deck-to-game play histories.
Song is cast with an empty stack during its controller's main phase; Nissa's
loyalty ability is announced through `checked_action`, not direct effect calls.
No flash permission or sorcery-in-response claim is made.

Kelsien can target only opposing creatures. The test explicitly sets up a
separate controlled main-phase fixture for the target controller's Song/Nissa
sequence, then uses a real priority pass to permit Kelsien's activation. It does
not claim to have played the intervening turn. Naturalize and Spreading Seas
tests use actual checked casts and resolution. Hidden-zone substitutions are
controlled privacy counterfactuals, not legal gameplay actions.

## Qualification and reproduction

Pinned interpreter: existing main backend `.venv/bin/python`, Python 3.12.3;
all eight exact `requirements.txt` pins verified. No installs or paid services.
Serial six-module execution includes all twelve HTTP neighbor cases, without
selection exclusions. The only product failures are the twelve new strict
classification assertions. Existing neighbors are unchanged.

Final fresh-DB gate: **325 passed, 12 failed**, 25.26 seconds, 87 existing
Pydantic datetime deprecation warnings. The new module contains 41 cases:
29 passing controls and 12 strict red assertions; the 296 unchanged neighbor
cases all pass. All twelve HTTP cases pass. There are no errors, skips, xfails,
or deselections. All 17 audited SQLite connections use this checkout's freshly
created local database; no socket attempts or other database accesses occurred.
Read-only SQLite integrity verification returns `ok`.

Frozen archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/color-domain-audit/20261006-3ccbdf2`.
It includes baseline and final source, the three-new-file patch, exact fixture
receipts, ordinary red JUnit, passing HTTP case inventory, active-command
equivalents, connection receipts, snapshot reproducers, verified stopped local
SQLite copies, and the separate graph refresh. The patch changes no existing file.

Initial fixture-development attempts are retained separately. One assertion
incorrectly expected the generic combat-stat API to erase noncreature printed
stats; it was removed without changing the actual creature-color assertion.
The Starport Security exploratory target path was not suitable for the intended
episode and was replaced by Kelsien. Two test API assumptions (damage storage
and decision_view's tuple result) were corrected. None is counted as a product
finding. The first neighbor run used a DB-forbidding guard and consequently
blocked twelve HTTP setups; subsequent serial qualification permits only this
checkout's exact local SQLite path and reruns those same tests without exclusions.

From isolated `backend/`, with `E` pointing to the archived evidence harness:

```sh
PY=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
PYTHONPATH="$PWD" AUDIT_OUTPUT="$E/final-localdb-audit.json" PYTEST_ADDOPTS='' \
  "$PY" "$E/localdb-qualification.py" -q \
  tests/test_color_domain_audit.py tests/test_qualified_continuous.py \
  tests/test_basic_land_layer_goldens.py \
  tests/test_basic_land_replacement_composition.py \
  tests/test_dynamic_activation_modifiers.py tests/test_conditional_static.py \
  --junitxml="$E/final.xml"
PYTHONPATH="$PWD" "$PY" "$E/reproduce.py"
```

## Proposed ownership, not implementation

Request ownership of the narrow color-qualified creature branch in
`rules_engine/continuous.py::_subject_match_result`: replace its printed color
input with `card_color_symbols(card, state)`, preserving predicate semantics,
effective-type checks, source activity, timestamp handling and immutable query
scope. Qualify these twelve ordinary reds as ordinary greens plus all existing
neighbors before proposing integration. No helper, stack, domain, mana, costs,
action-validation or AI changes are justified by this bounded evidence.

No correction was implemented. These intentionally red tests should not be
presented as a green gate or integrated as unconditional passing CI coverage.
They do not certify all protection, colorless/multicolor predicates, color-based
selectors, conditional statics, or the parent's queued composition.

## Primary rule basis

Verified the official rules page and its linked September 25, 2026 text on
October 6, 2026. Effects can change printed color (105.3, 202.2f). Type, color,
ability and power/toughness changes have distinct layer ordering (613.1d-g).
Protection constrains abilities by source quality (702.16b); activation uses
target-announcement rules and resolution rechecks legality (602.2b, 608.2b).
These justify the specific expected predicates and target controls, not global
implementation readiness. [Official Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
[official current rules page](https://magic.wizards.com/en/rules).
