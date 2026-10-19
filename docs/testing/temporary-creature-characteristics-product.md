# Temporary Creature Characteristics: Partial Product

This document preserves the earlier partial-stage evidence. The later effective
subtype reader correction is composed and passes 232 checks on the current parent;
see [current acceptance](temporary-characteristics-current-composition.md).
The old ten-failure ledger below is historical, not the current pure result.

Frozen input is the verified RlF62U audit source archive, followed by Jason's
55283 target-reference production patch. No latest-parent equivalence is claimed.
Original 42 tests and canonical raw fixtures remain byte-identical.

## Product Scope

The new pure whole-body compiler recognizes the complete temporary creature
instruction: loss of all abilities, one explicit color, one supported creature
subtype, numeric base power/toughness, and optionally exactly `Draw a card.`.
Unknown complete tails are unsupported before clause splitting; grammar probes
are not fabricated gameplay cards or certification of further Oracle forms.

One new handler composes existing type/subtype/color, base-stat and all-ability
loss records. A single real resolution timestamp is shared; each native record
binds the target object's incarnation. Source ID/name use existing record fields;
no new source-incarnation field or model is invented. Printed characteristics,
counters, other card types and native cleanup/serialization are preserved.

The inherited target-reference dependency checks the whole spell before this
single handler runs, including a same-ID returned new object. Existing type,
protection and hexproof legality are not relaxed. The optional draw uses the
native effect dispatcher after the characteristic change. No shared stack edits
are included in this incremental product.

## Measured Gates

- Original unchanged 42: 32 PASS / 10 FAIL, 12.44s.
- New whole product-control module: 26 PASS, 4.67s.
- Four whole neighbor modules: 148 PASS, 2 warnings, 17.89s.
- Distinct product-stage cases: 216, comprising 206 PASS / 10 FAIL; no skips/xfails.

All SQLite and socket connections were denied by a runtime audit guard. Actual
owned import paths and executable are recorded. Constructed canonical positions,
real paid casts, native priority/stack resolution, same-state JSON restore and
root/RNG snapshots are evidence, not natural-game or SQL/API certificates.

New controls include canonical colorless Ornithopter for nontrivial blue/green
setting, actual paid Jump before/after removal, actual post-resolution Cloudshift
new-object cleanup and real animated Mutavault retaining Land type. Full existing
canonical JSON is reused without edits; input file hashes are in the artifact.

## Unresolved Shared-Layer Seam

Layer four computes creature subtype operations for nonlands but omits their
effective type-line publication. Consequently the original Bird remains reported
as Bird rather than Frog/Snake. Four subtype, four cleanup-prerequisite and two
draw-order cases fail. Cleanup assertions do not reach native advancement in
these four original cases; do not call them qualified cleanup or distinct bugs.

An unapplied proposal adds explicit creature-subtype operations to the existing
line-publication condition in `basic_land_layer._resolve`. This requires a
separate shared-layer grant. No source edit, overlay, monkeypatch, fixture adapter
or assertion relaxation was used to hide the seam. Proposal apply-check alone is
not execution qualification. Original baseline 8 PASS / 34 FAIL and its timeout
ledger remain immutable. HTTP waits for the shared SQL slot.
