# Canonical Tribal Entry Fixture

Over an isolated `36ce25f52cae12c9f6f0faf9f6b32e4bedb903ab` archive,
`test_tribal_entry_trigger.py` now materializes its Elvish Warmaster positive
from the complete committed official object rather than handwritten fields.
The former Oracle text already matched that object exactly; the fixture was
missing its mana cost, color and layout. This is not an Oracle rules correction.

The existing `canonical_positive_fixtures.raw_card` loader checks the seed155
snapshot SHA-256
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.
Its committed provenance records complete Scryfall collection responses,
HTTP 200, the 2026-10-12 intake epoch and no Oracle modification. The full
Warmaster object's sorted compact JSON SHA-256 is
`686c827295fa497372527b45b4119788b1e9c1fa779a16c436020d6e0325e215`.
No new provider request or fixture-data rewrite was needed.

A separate Factory materializes the full object. A never-drawn library card
supplies the trusted battlefield pose, retaining `watcher`, player 1 ownership
and control, and the original runtime defaults. The original 60-Forest game,
seed 87, static-order assignment, eight test names, all 30 assertions, and every
event/action sequence are unchanged. No original-stock capture is erased or
recertified; this synthetic pose is not evidence of casting or stock admission.

The alternate-wording, Zombie and generic team-ability cases remain explicit
noncanonical parser protocols. Their bodies and anonymous entrant/token
construction are unchanged, not presented as official named-card facts.

## Observed Component Acceptance

Two complete modules were run under the existing pure precollection audit
guard: `test_tribal_entry_trigger` and new
`test_tribal_entry_fixture_fidelity`. The new checks observe actual source
objects produced by three original test bodies before their actions, verify
complete official bytes/provenance, and check object/mutable-data independence.

- Before migration: 10 passed, 3 fidelity failures, 1.87 seconds; all eight
  original tests passed. Failures exposed the actual source's missing fields.
- After migration: 13 passed, 2.02 seconds, no failures/errors/skips.
- Both runs: eight physical pre-import SQL/socket/child/provider denials;
  no unexpected events; all 3,373 source files and 2,946 runtime files plus four
  runtime links byte-equal before/end. The documentation was added afterward.
- File descriptors were unchanged; no children or non-main threads remained;
  neither routed nor source-default databases were created. Generated token
  placeholder media stayed in owned runtime, outside source.

No production/shared-helper changes, SQL, network, browser, native-game,
installation, or full-project/Phase 1 signoff is claimed by this component.
