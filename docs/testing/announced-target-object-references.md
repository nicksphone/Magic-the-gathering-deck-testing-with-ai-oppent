# Announced Target Object References

## Boundary

Normal cast and generic activation frames capture genuine selected card-object
identities after target legality checks and before any cost/payment mutation.
Internal payload `__announced_target_references` is version1 with a `targets`
shape parallel to `__announced_targets`: scalar `target_card_id`, positional
`target_card_ids`, per-recipient `target_distribution`, and recursive
`mode_targets`. Player and stack targets remain their existing targets.
Each card receipt contains exactly `card_id`, nonnegative integer `incarnation`,
and nonnegative integer `zone_change_sequence`. Boolean values are not integers.
No public action/schema expansion, Oracle exceptions, guessed historical receipts,
or policy changes are introduced.

The complete bundle is validated before resolution can pop an early conditional
or trigger frame, mutate bestow, or execute an effect. Individual target identity
is then checked alongside existing type, protection, hexproof, and specialized
legality. Stale recipients are pruned without redistributing damage or deleting
independent legal clauses. Real sources plus authoritative retained source LKI
remain protection inputs; ability hint copies are only hint inputs.

Old frames without this field deliberately retain legacy behavior. Identity
cannot be reconstructed safely from today's same-ID card. Specialized trigger,
ordered, linked, and bestow receipts are preserved, not replaced globally.
Bestow creature fallback retires both announcement and corresponding generic
receipt. This is not certification of every target grammar or ability producer.

## Pure Helper ABI

`capture_announced_target_references(state, announced)` returns the versioned
parallel receipt bundle. `validate_announced_target_references(announced, bundle)`
rejects complete malformed shape/identity fields without mutation.
`announced_target_reference_matches(state, bundle, slot_path, card_id)` compares
one validated slot to the live object (legacy absent bundle returns true).

`replace_announced_target_reference(state, bundle, announced, changed_slots,
*, remapped_slots=None)` rebuilds the FINAL announcement shape, captures live
identity ONLY for explicitly chosen changed card slots, and deep-copies inherited
receipts for every untouched slot. Optional mappings are new-path -> old-path.
Scalar/modal and linked scalar/list reshapes migrate old receipts, never query
live identity for untouched targets. Keep/resume cannot refresh a receipt.
An explicit same-ID/new-object target choice refreshes only its chosen slot.
Divided damage preserves the chosen slot amount and rejects collisions with other
recipients. Copied frames retain independently deep-copied inherited receipts.

## Executed Qualification

Immutable input is the parent's blink-clause-reference-current-stage-20261006
frozen-coupled-source.tar.gz, SHA256
269188d71a1dbaead317a3ed1e4379a89488e1c3349265b428f80c2a71d2ecea.
Source is exact21db +36d retained-source +84bb blink +4dcc clause composition.
Parent's recorded866 baseline was854PASS12FAIL (8Ray +4Favor blink); not rerun
or represented as a new local baseline.

Initial whole6 focused:154PASS8strictRayFAIL104.12s. New whole13 copy/neighbors:
292PASS6FAIL50.64s. Four actual hint/protection input regressions corrected;
two scheduler-fixture failures independently reproduced on all seven original
preimages: whole2 baseline103PASS2FAIL12.78s.
Final corrected whole19:450PASS10FAIL94warnings142.39s, zero errors/skips/xfails.
Eight original Ray episodes remain unsupported; two original turn-boundary tests
still produce inconsistent phase/cursor snapshot fixtures. Neither is weakened.
Additional state-only normal/stale graveyard-target controls4PASS4.59s under a
network/ALL-SQLite prohibition. Pure helper12PASS0.26s was supplementary only.

All five required copy/bestow acceptance seams have actual evidence: divided
own-slot keep/new/collision with amount preservation; scalar-to-modal old receipt
migration plus selected refresh; linked shape migration both directions with
untouched generic and specialized receipt equality; malformed-before-pop/bestow
full-root checks including HTTP422/cold SQLite restore; bestow creature fallback
receipt retirement. Both seats use actual canonical paid responses and snapshots.
Conditional copy explicit refresh and Favor independent-clause/private continuations
are ordinary passing controls. Canonical raw fixture JSON is retained unmodified;
board/resource setups are declared retained positions, not complete legal histories.

Original Favor lifecycle/HTTP/clause tests and targeted lifecycle40 remain byte
identical. Final module list and complete commands/logs live in the independent
artifact. Seven production functions/files are scoped by preimage/postimage
hashes and AST evidence; no costs/events/Oracle/AI/main changes.
Parent's external Act audit is not executed here and remains a coupling check.
The fixture correction proposed for the two historical scheduler failures is an
explicit test-position adapter, not a runtime repair or an included test change.
