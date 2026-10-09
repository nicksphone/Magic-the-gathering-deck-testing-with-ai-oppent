# Modal Cost View Contract

Base: published `00b8c8d4`, composed with the self-entry control increment.
This fixes a public move producer, not a frontend validation exception.

## Fix

The modal/adventure/split branch emitted raw `CostOption` attributes, including
inactive hand-exile fields. The unchanged strict frontend rejected the actual
canonical modal packet. The branch now uses the existing public cost serializer.
An optional keyword-only selected-card argument supplies face characteristics
to resource, kicker and X-hint readers. Additional-cost exclusion still uses the
physical spell ID; previous callers retain their original behavior.

Only `_cost_option_view` and its modal call site change in
`backend/rules_engine/move_generator.py`. Its postimage is
`8f017017ec5bba92b0b76aa8eac9805e529317ec8e6b359f6c6017ee44901225`.
Three new repository-native helper/test files accompany the fix. No frontend
parser, action schema, payment algorithm or engine change is included.

## Executed Qualification

One actual combined declaration completed **441 ordinary passes across 22 whole
modules, two warnings, 169.59 seconds, exit 0**. It includes the self-entry
control declaration, new modal contract/boundary modules and the unchanged
63-case resource-payment module. XML has no failures, errors or skips.
All 2,124 source files and the complete file set are unchanged before/after.
Two native controls denied both SQLite aliases; gameplay attempted no SQL,
sockets or subprocesses. Parent production/test postimages match the tested
composition. This is not a sum of overlapping component pass counts.

Separate actual Node execution accepted the full canonical modal packet and
all seven casts using the unchanged parser. Selected-face resource/kicker/X
callback controls prove the callback contract, not invented paid-card semantics.
The original modal rejection and earlier fixture/RNG ledgers remain archived.

Evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/control-modal-current-00b8-20261009/`.

## Remaining Acceptance

The owner's frontend lint/build passed. Its initial configured npm-test command
stopped because a native guard denied Vite's unused WebSocket listener; it was
not a modal assertion failure. A separate middleware-only harness correction
and its terminal frontend qualification remain distinct from this backend run.
The remote full backend/frontend/browser workflow must qualify the published
composition. Static Aura layers, HTTP/cold restart, complete modal-card rules,
all-card correctness, measured AI strength and release/deployment remain open.
