# Numeric Prevention Receipts

This isolated increment represents each actually resolving numeric prevention instruction with one typed `NumericPreventionShield` and a private `MatchState.numeric_prevention_shields` list. Existing player/card numeric totals remain compatibility balances, not replacement source identities.

## Receipt And Lifetime

Version 1 retains independent receipt ID, actual resolving stack ID/controller/label, physical source ID and announced PRE source incarnation/zone-change sequence, current recipient player or permanent incarnation reference, remaining amount, creation turn, cleanup expiry and effect timestamp. Real cast producers capture physical references after movement to STACK and before callbacks. Actual popped frame transport supplies resolution identity; copied spells retain the original physical reference but get their genuine copied frame/controller. Source departure does not invalidate an applied shield. Target departure/reentry does not refresh its reference.

Replacement options use `numeric-prevention:<receipt_id>` virtual views, never fabricated card objects. Selecting a shield consumes only that receipt and its compatibility balance. Multipliers/conversion requery the remaining damage; counter-placement pauses retain the native resolving frame. Cleanup clears receipts and compatibility balances together. Combat changes are exactly two state-aware compatibility-consume calls, not new assignment or multi-source allocation semantics.

## Snapshot Boundary

Snapshot restore defaults a missing receipt field to the legacy empty list. New receipts require exact typed fields, complete nonnegative integer references (no booleans), unique application/frame identities and consistent active aggregate balances before constructing restored state. Restore never mutates its input. Independent applied shields and their remaining quantities survive cold snapshot round trips.

Anonymous legacy scalar shields retain standalone prevention behavior. When an anonymous scalar competes with a known replacement, ordering cannot be reconstructed: reject instead of inventing provenance. Pre-pop checks currently cover direct damage, selected conditional damage, and the creature-only damage wrapper. Arbitrary containing damage sequences are not certified by this bounded check; no global legacy migration is claimed.

## Qualification

Run using the pinned shared interpreter, not system Python:

```sh
/home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python evidence/run_pure.py -q backend/tests/test_numeric_prevention_receipts.py
```

The strong runner denies every SQLite connect audit event and every socket audit event before pytest imports. New tests use actual paid canonical Healing Salve, Mending Hands, Lightning Bolt, Hornet Sting, Furnace of Rath, Pyroclasm, Twincast, Counterspell and Cloudshift episodes, both seats. Controlled malformed-frame, lock, cleanup and combat bridge checks are explicitly component tests, not invented card episodes. Canonical counter modifiers exercise native counter pauses; snapshot/privacy assertions remain ordinary assertions.

Original strict Salve assertions remain unchanged. See the frozen REPORT and raw ledgers for exact whole-module counts, including the existing HTTP case blocked when TestClient attempts a socketpair. No HTTP qualification, universal prevention-ordering claim, source-controller correction, combat simultaneous-source allocation certification, AI readiness or live promotion is implied.
