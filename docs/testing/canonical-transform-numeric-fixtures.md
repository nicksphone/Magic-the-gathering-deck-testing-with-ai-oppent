# Canonical Numeric Transform Fixtures

This test-only migration is based on immutable `6900e9d1dd0bf5589a0c32b6c12cd05effc02e87`.
No production code, shared canonical fixture helper or other owner's tests change.

## Exact Fixture Scope

The two original `test_transform_numeric_ai.py` tests retain their names and all five ordered assertions.
Their `_game()` helper, seed77, 60-Island boards, main phase, actor, original transform calls, battlefield placement and pass-only AI assessment are unchanged.

Kumano, Delver and Lightning Bolt are loaded as complete official rows from the existing pinned seed155 snapshot, using the existing read-only `raw_card` helper.
There is no new intake, dependency or handwritten named-card Oracle text.
The original Kumano fixture omitted chapters I/II and both old transforming fixtures omitted canonical face fields.
The old top card changed only Island's name/types; it retained incomplete/wrong instant metadata.

One private test helper now uses actual `MatchFactory` materialization, including physical-front selection and numeric conversion.
Eight identical canonical rows leave one never-drawn library template after the factory's normal opening draw.
`dataclasses.replace` gives that fresh template the trusted fixture's operational identity/zone/order, preserving `kumano`/`delver` IDs and the actual library-top ID and slot.
The Bolt replacement supplies its entire materialized printed state, not just a renamed land's type.
No root stock facts are cleared, reinitialized or asserted authoritative for these synthetic poses.
These are direct trusted transform seams: not paid-cast history, resolved Saga chapter III, captured-stock consistency or AI strength certification.

## Evidence

The new fidelity module wraps each real imported transform function, records the actual source/top immediately before transformation, then invokes the real function and retains the original assertions.
It compares complete ordered raw faces, the physical front and numeric stats, complete Bolt fields, seed bytes/provenance and independent fresh objects/nested faces.

- Meaningful RED, both whole original/new modules: **4 passed, 3 failed in 1.66 seconds**. The actual Kumano/Delver faces and the renamed land's empty Oracle fail, not a missing helper.
- Focused GREEN, same two whole modules: **7 passed in 1.73 seconds**.
- Final modest neighbor gate, those two whole modules plus whole `test_optional_reveal_transform.py`: **28 passed in 4.94 seconds, zero failures/errors/skips**.

Each gate ran with no conftest under the same 300-second bound.
Pre-import controls denied both SQLite connect aliases, the native SQLite constructor, both socket constructors, child/shell launch and provider import; persistent audit denial stayed active throughout.
All 3,357 source files and 2,946 cached-runtime files plus four links matched before/after the final gate; SVG media was generated only under owned runtime.
Unexpected I/O was empty, FDs matched, no children/non-main threads remained, and routed/default databases were absent.
The documentation and local AST graph are post-gate metadata, not a changed tested code epoch.

This closes the bounded fixture-fidelity issue only. It is not whole backend/CI or a Task1.3/Phase1 signoff, and it does not replace the existing optional-reveal module's own declared semantics.
