# Static Replacement Shuffle ABI

Scoped executable helper/collector increment over frozen 9714ee5 + unchanged
5a74ed4 audit + FwXitN f9c389c + staged Lagrange 2fe39a2 + strict20 5133939d.
Not a composed actual replacement release: its producer has not yet adopted the
new keyword. Current strict20 remains 12 FAIL / 8 PASS (eight missing Probe,
four Tower destination bypass). No Probe-zero characterization is desired green.

## Exact Signature and Commit Order

```python
receipt = prepare_static_replacement_cause(state, plan)
# Lagrange owns the validated zone/list/reveal commit; do it exactly once.
shuffle_library(state, plan.owner, cause=receipt)
```

Signatures in rules_engine.shuffle_actions:
`prepare_static_replacement_cause(state, plan) -> StaticReplacementCause`;
`shuffle_library(state, player_id, *, resolving_item=None, cause=None)`.
Static and resolving-item causes are mutually exclusive. The original genuine
resolving_item constructor-dictionary path and its derived source contract
remain unchanged. Do not supply a fake StackItem or paid-spell receipt for a
printed replacement. Static stack_id is OMITTED, never None.

The factory accepts the real frozen GraveyardEntryPlan, revalidates membership
in current pure plans and the selected printed self-shuffle destination, matches
the complete generic printed clause against the real source, and captures its
index/text plus owner/controller/origin/incarnation/sequence. It is read-only;
prepare ALL batch receipts before departures/events/lists/logs/reveals. A
competing library/exile choice belongs to Lagrange's existing explicit selection
and prepayment rejection; the factory does not invent precedence or choices.

An immutable internal StaticReplacementCause has source_card_id, controller,
source_owner, source_zone (Zone), incarnation, zone_change_sequence,
ability_clause and ability_index, plus private factory seal/proof. It is an
in-process capability, not an external action field or persisted cross-request
receipt. Python module privacy is not a hostile-code security boundary.

After the one commit, the helper validates typed factory provenance, unchanged
receipt fields, player=owner, source/controller/owner, actual library zone,
exactly one owner-library membership and no other player-zone membership,
retained incarnation and expected sequence: old+(origin!=LIBRARY). Legitimate
same-library transitions preserve sequence/incarnation. The PRE reference is
emitted, not recomputed. Suppression is checked at preparation, not re-evaluated
in the post-move zone where relevant abilities may legitimately differ.

Malformed/unknown causes, wrong owner, duplicate membership, unexpected
transition, changed receipt or simultaneous cause arguments reject before
shuffle RNG/log/event mutation. This helper cannot undo a caller's earlier zone
mutations; the producer must do the pre-commit validation above. Each prepared
receipt must be dispatched once by its trusted commit; no public API/retry field
or external payload can create it. Existing action idempotency belongs to the
real caller qualification, not this supplementary seam test.

## Complete Emitted Cause

```python
{
    'kind': 'static',
    'mechanism': 'replacement',
    'source_card_id': receipt.source_card_id,
    'controller': receipt.controller,
    'source_owner': receipt.source_owner,
    'source_zone': receipt.source_zone.value,
    'source_reference': {
        'incarnation': receipt.incarnation,
        'zone_change_sequence': receipt.zone_change_sequence,
    },
    'ability_key': 'printed_graveyard_reveal_shuffle',
    'ability_clause': receipt.ability_clause,
    'ability_index': receipt.ability_index,
}
```

The shuffle collector recognizes only this complete static vocabulary, alongside
unchanged spell/activated/triggered causes. Generic kind=ability, stack_id=None,
incomplete shapes and arbitrary cause dictionaries are not accepted static
inputs to the dispatcher. Cosi's causal-independent branch remains unchanged;
no-cause generic shuffle still does not trigger Probe.

## Qualification Boundary

43 supplementary controls PASS4.40s: both seats/two canonical self families,
three origin families, private immutable preparation, relevant-zone Humility,
foreign owner/controller, pre-reference/same-library correctness, exact restart,
complete Probe/Cosi collection, malformed-cause root/RNG/log immutability and
no-cause controls. The commit seam is explicitly controlled, NOT legal episode
proof and not a substitute for Lagrange's real producer.

Four WHOLE unchanged legacy modules PASS92 in5.40s. Unchanged strict20 ordinary
ledger FAIL12/PASS8 in5.33s, with no exclusions/xfails. New desired cases and
original60 assertions are not weakened. Kozilek remains separate. Initial test
scratch-parent setup errors and one mistyped neighbor command are retained in
evidence, followed by actual corrected whole-module execution.

Actual paid Village Rites/other spell/mill/stack/exile observer resolution,
APNAP/timing/privacy/restart/idempotency must be requalified after Lagrange
forwards prepared causes. Tower manual-cost caller and direct death/combat/
keyword routes are outside this helper increment. No main/current B or global
replacement semantics/readiness claim.
