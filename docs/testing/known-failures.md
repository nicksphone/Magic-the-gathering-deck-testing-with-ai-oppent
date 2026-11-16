# Known failure ledger

This ledger names intentionally expected failures added during current acceptance
work. It is not a claim that the full test suite has no other failures. Expected
failures must remain visible in test summaries and are not RC passes.

## Legacy untyped resolution-finisher source cleanup

- Owner: Claude/project maintainer. Decision **2026-11-16: retain as a documented
  RC limitation**, with no guard or migration approved. No natural-LIFO exploit
  has been shown; changing stack cleanup would require a new source-review layer
  and old-save compatibility work without demonstrated normal-gameplay gain.
  Both strict xfails remain; they are not passes.
- Tests: `tests/test_legacy_unknown_source_recast.py::test_untyped_historical_finisher_must_not_move_distinct_recast_spell[1]`
  and `[2]`; both strict xfails. The typed-activation controls are ordinary passes.
- Seam: `finish_stack_resolution` treats `legacy_unknown` as a spell for source
  cleanup. If an older untyped frame is finished while a different incarnation
  of its source is currently on the stack, it enters that new creature into play
  even though the new spell's own frame remains pending.
- Reachability limit: the test explicitly invokes the older frame's finisher.
  Normal LIFO resolves a newly recast spell before the older ability; bounce and
  recast alone do not establish a legal gameplay exploit. This is a historical/
  resumed-frame provenance diagnostic, not a claimed played sequence.
- Fixture: canonical Azure Mage and Vedalken Orrery printing data, real return-to-
  hand and checked paid recast. The old untyped frame is an authored storage
  input. No production source, stack order policy or source pins are changed.
- Expected failure is restricted to `LegacySourceCleanupMismatch`, raised only
  for the demonstrated premature source entry. Other setup/assertion failures
  are not converted to xfails. `strict=True` makes an unexpected pass fail CI.
- Local evidence: related scope **28 passed, 2 xfailed**. To expose the defect:
  `python -m pytest -q --runxfail tests/test_legacy_unknown_source_recast.py`.

Recommended policy for a separate approved change: source cleanup should require
proof that the physical stack incarnation belongs to the resolving frame. Keep
modern typed spell/activation behavior and compatibility cases covered. For
ambiguous legacy rows without retained provenance, choose an explicit migration/
rejection policy rather than guessing from current zone, card name or effect.
A reference minted from the current source only at resolution is too late to
prove historical ownership. Do not silently classify all legacy rows as abilities
or remove their cleanup without reviewing genuine legacy spell compatibility.
