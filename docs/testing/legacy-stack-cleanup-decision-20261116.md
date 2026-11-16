# Decision memo: legacy stack-frame source cleanup

**Recommendation: approve a narrow collision guard for RC, not a wholesale
legacy-frame migration.** It can close the two recorded strict xfails without
changing ordinary typed spells/abilities or stripping cleanup from every old
spell. This is a proposal, not an approved or implemented rules change.

Branch base / reviewed main: `ec26f6f5ef68003d731a85648b2f40c282a4d449`.
The relevant legacy tests, stack/classifier/reference/serializer source and
inverse helper are unchanged from the initial `d82d916d` inspection.
`backend/rules_engine/stack_engine.py` SHA-256:
`799fee7d0bdfbbf823c7ceb5c6600f79260ef1a3d9173af3665d658d7dd0ad45`.
Recheck that base before implementation; later merges may require another layer.

## What is demonstrated

The two tests in [the failure ledger](known-failures.md) construct an untyped
historical Azure Mage ability, really bounce and pay to recast its source, then
explicitly finish the older frame. The separate new spell frame remains pending,
but `finish_stack_resolution` enters its physical card onto the battlefield.
The typed-activation controls preserve the card on the stack.

This is the direct historical/resumed-frame finisher seam, not a demonstrated
normal-game exploit: normal LIFO would resolve the recast spell first. The tests
are strict expected failures limited to `LegacySourceCleanupMismatch`; they do
not hide unrelated exceptions. No new test run is claimed by this memo.

Current relevant behavior:

- [`targeting.stack_object_kind`](../../backend/rules_engine/targeting.py) uses
  retained publication shapes, not a card's current zone/name, to classify old
  frames. It deliberately leaves insufficient evidence as `legacy_unknown`.
- [`finish_stack_resolution`](../../backend/rules_engine/stack_engine.py)
  currently includes `legacy_unknown` in the spell-cleanup route. A physical
  source on `Zone.STACK` is sufficient to enter/move it, even when another spell
  frame for that card remains pending.
- [`trigger_source_reference`](../../backend/rules_engine/events.py) can fall
  back to the current card. `_resolve_top_of_stack` can store that value only at
  resolution. Presence of `__stack_source_reference` alone therefore does not
  prove which historical incarnation the old frame originally owned.

## Minimal containment change

Change only the physical-source cleanup eligibility inside
`finish_stack_resolution`. When the resolving item is `legacy_unknown`, prevent
it from moving/entering the source if the remaining stack contains a **different,
valid, non-copy spell frame for the same physical card**. Preserve the rest of
the finisher, including resolution logging and state-based-action/staging work;
an early return could accidentally skip that work.

Use the existing stack-kind contract for the competing frame; exclude spell
copies, which do not own their source's physical card. Filter frame/source IDs
before classification so this guard does not inspect unrelated malformed frames.
If a same-source candidate fails the existing classifier, propagate its
`ActionRejected` rather than silently treating it as proof or ignoring it.
Compute that eligibility before the finisher's own mutations; verify normal
action/HTTP rollback if higher-level work preceded the finisher. This is a new
refusal path for malformed legacy storage and needs explicit acceptance. Do not infer the old
frame's kind from its name, effect key, source zone or controller. The old frame
can still finish its effect; it simply cannot consume the other pending spell's
card. Typed behavior and a lone genuine legacy spell retain their current routes.

This directly addresses the two tests without rewriting their assertions. After
approval and a real RED/GREEN run, remove only their expected-failure decorators
and update the ledger. Do not describe this as universal legacy provenance
verification: it detects the demonstrated competing-frame collision, not every
possible ambiguous or corrupted old save.

Alternatives and why they are broader:

- Requiring a newly defined announcement-time receipt for every physical cleanup
  is a stronger long-term policy. It needs a versioned receipt bound to frame ID,
  source ID, incarnation and zone-change sequence, captured before resolution;
  old ambiguous frames need explicit rejection or reviewed migration. A receipt
  minted from the current card during restore/resolution cannot repair history.
- Treating all `legacy_unknown` frames as abilities, or rejecting all of them,
  changes genuine old-spell compatibility. Neither is the minimal collision fix.
  Leaving everything unchanged preserves compatibility but keeps a known unsafe
  finisher for historical/resumed inputs.

## Files and source-review delta

| File | Proposed work after approval |
| --- | --- |
| `backend/rules_engine/stack_engine.py` | One narrowly reviewed cleanup-eligibility change. Do not change publication, stack ordering, AI, serializers, or generic zone movement for this containment patch. |
| `backend/tests/test_legacy_unknown_source_recast.py` | Turn the two demonstrated cases into ordinary passes only after RED/GREEN; keep typed controls, add collision/copy and genuine legacy-spell compatibility cases. |
| `backend/tests/fixtures/interface_scope_compatibility/accepted_legacy_stack_cleanup_delta.json` | **New proposed file**: exact reviewed old/new source hashes and finite reversible hunks. No candidate hash exists yet. |
| `backend/tests/interface_scope_compatibility.py` | Hash-pin the new recipe and add explicit stack-source restoration dispatch; retain all existing recipes and rejection behavior. |
| New focused delta-contract tests | Prove the candidate restores byte-exactly to the reviewed base and reject altered hunks, outside edits, wrong hashes/spans/operands, and altered recipe bytes. |
| `docs/testing/known-failures.md` | Record the actual new result and retained limitations; do not silently delete the historical failure. |

The current helper's `restore_reviewed_source` admits `main.py`, repository,
costs and the private-choice fixture source; its `compatible_product_hash`
production entry point admits only main and repository. **Neither currently
has a stack-engine entry.** `accepted_pr55_deltas.json` contains costs/keyword
changes, not this stack change. There is no existing stack recipe to overwrite
or an existing costs chain to append this unrelated source to.

Follow the finite-inverse pattern in
[`accepted_sacrifice_query_cost_delta.json`](../../backend/tests/fixtures/interface_scope_compatibility/accepted_sacrifice_query_cost_delta.json)
and [`accepted_pr55_deltas.json`](../../backend/tests/fixtures/interface_scope_compatibility/accepted_pr55_deltas.json):
create a new reviewed layer, validate each exact new hunk at its measured line
span, undo in reverse order, and require the entire old-source digest. Bind both
candidate and recipe bytes; an extra newline or edit outside approved hunks must
still fail. Only extend a consumer entry point if a real consumer needs it.

A search of tracked public tests/metadata found no literal pin for the current
stack-engine digest above. That is not proof that private CI inputs or external
historical snapshots impose no constraints. Preserve those inputs and the
existing historical pin files, including `approved_public_deltas.json`,
`accepted_pr55_deltas.json`, and `reviewed_25ef_pins.json`. Run the complete pin
slice and full CI; if another source guard fails, report its consumer and add a
separately reviewed layer rather than replacing its expected hash. This memo
creates no delta and authorizes no pin change.

## Snapshot risk and required acceptance

The current deserializer preserves stack and pending `resolving_item` payloads;
it cannot reconstruct missing historical publication evidence. The proposed
collision guard changes the outcome of an old save containing the demonstrated
competing frames: it leaves the new spell/card pending instead of entering it
prematurely. Ordinary old spells without a competing physical spell retain
cleanup; modern typed frames and serialized payload shapes need not change.

Ambiguous duplicate/stale frames are still a compatibility risk. The guard must
not promise it has identified their rightful owner or silently migrate them.
Stronger refusal/provenance policy remains a separate decision, especially for
older paused choices whose finisher runs through `resume_paused_resolution`.

Before merging the narrow patch, require:

1. The unchanged two-seat assertions fail on the old source with `--runxfail`,
   then pass without xfail on the candidate. Typed controls remain ordinary passes.
2. Both-seat cases for matching-source competing physical spells, unrelated
   sources, spell copies, malformed same-source versus unrelated frames, and a
   genuine standalone legacy spell. Cover permanent
   entry, instant/sorcery cleanup and failed resolution; preserve logs/staging/SBA.
3. Snapshot round trips and a real paused-choice continuation retain the same
   protection. Include a late/current-card reference to ensure it is not mistaken
   for historical ownership. Rejection must not commit a partial HTTP state.
4. Stack publication/kind, copies, activation, trigger, entry, fizzle, replacement,
   serialization and saved-game regression slices; exact inverse/pin tests;
   full configured backend/frontend/browser CI. Report exact results and source.

The recommendation is to **fix this bounded collision now**, subject to Claude's
approval and those compatibility checks. If approval or those checks cannot be
completed for RC, keep both strict xfails and this limitation explicit; accepting
that limitation is a maintainer release decision, not a passing test result.
Do not expand the patch into automatic legacy inference to close a checkbox.
