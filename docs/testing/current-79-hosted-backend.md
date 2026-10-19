# Hosted Backend At 79e215fb

Exact source `79e215fb4c39ccc49073c1a3963712608d25203c` completes backend job
`116821297131` in run `38854005765`, attempt 1, successfully on October 16.
Independent reconciliation of its bounded sanitized metadata establishes:

- 29,502 unique collected identities, with no deselection or collection error.
- 29,420 passed setup/call/teardown triples.
- 82 setup skips, each with a passed teardown; these are not passing bodies.
- 111 separately counted passing subtest reports.
- No failed, missing, duplicate or expected-failure phases.

The artifact is exactly
`backend-metadata-79e215fb4c39ccc49073c1a3963712608d25203c-1`.
Its 3,553,409-byte ZIP matches the API digest and contains only the
20,523,568-byte `backend-metadata.json`, with verified CRC. The member SHA256 is
`a478ece579ff3e3440b6a6a531b43efe471f880b9bb2c5f2fd1b841450480902`.
Existing local intake was reused; no protected trace or raw backend job log was
downloaded for the independent review.

An additional independent identity join verifies all retained 899 knowledge
component cases and all retained 759 fixture-component cases: each has exactly
one passed setup, call and teardown. These rosters overlap and are not summed.
Their test modules are byte-identical between `79e215fb` and `5763e072`.

## Source Boundary

Git objects for `backend/knowledge`, `backend/card_data`, `backend/persistence`,
`backend/decks`, `backend/scripts`, backend requirements and the CI workflow are
identical between this source and `5763e072`. This supports the unchanged
knowledge/data implementation; it does not transfer a whole-backend pass to
later changes elsewhere in the rules engine or tests.

Phase 1 remains unsigned: other canonical fixture migrations and the literal
handwritten-data requirement are unfinished. Browser, native vendor, AI quality,
live-deployment and full release acceptance remain distinct requirements.

Independent source-object and phase reconciliation is archived under
`diagnostics/ci/hosted79-parent-reconciliation-20261016-e5jvk27m/` in the project's
NFS evidence store. The earlier and later failed ledgers remain unchanged.
The retained-component follow-up is separately archived under
`diagnostics/ci/hosted79-parent-retained-phase-join-20261016-2iTTSBDB/`.
