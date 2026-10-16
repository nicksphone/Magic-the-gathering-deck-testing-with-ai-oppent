# Backend Regression Recovery

The exact `0efab0bf86cc41e9b2e7aa511db465c351255e92` backend job
`117117544523` in run `38943739926`, attempt 1, completed with failure on
2026-10-16. Independently verified sanitized metadata records 30,639 unique nodes:
30,333 passed calls, 224 failed calls and 82 setup skips. Its 111 passing subtest
reports are separate. All collected nodes completed; no unresolved diagnostic
rows or metadata errors were reported.

Only the terminal sanitized metadata artifact was downloaded. Its API digest,
size, sole JSON member, CRC and source/run/job identities were checked. The
protected game trace and raw backend logs were not downloaded or published.

## Failure Clusters

These counts group the 224 observed failed calls; they are not a count of
independent production bugs or a whole-current-backend success claim.

| Calls | Boundary | Relevant evidence |
| --- | --- | --- |
| 162 | Public inventory rejected the new CardInstance schema. | Reviewed strict record coverage passes 719 cases, including every historical failed identity in this group. |
| 30 | Cycling's expected publication sequence omitted completed nonmana activation. | The reviewed test-only update passes all 94 cases, preserving full event capture and the original 48 assertions. |
| 7 | Printed-field fidelity omitted the retained characteristic record. | The helper correction passes the original fidelity/binding checks in the final 120-case declaration. |
| 4 | A shared fixture assumed every full official row had power/toughness keys. | The optional-stat correction passes all 60 cases without inventing zero for missing stats. |
| 3 | Historical finite source checks did not account for approved later changes. | Exact inverses retain all 60 historical SHA operands; the 224-case compatibility declaration passes. |
| 1 | The creature-copy fixture retained Forest stock under a renamed creature. | Genuine named birth and native roundtrip/tamper controls pass in the final 120-case declaration. |
| 17 | Protected historical replay and its dependent compatibility controls. | Public-source contract investigation is available; original-input acceptance remains protected-CI-only. |

The inventory update is the only production change in this recovery batch. It
does not merely accept a new schema hash: strict version, record shape, unchanged
rules values and normal-card face metadata are checked. Missing or malformed
provenance remains unknown; hidden records are not traversed or reconstructed.
See [the exact 719-case boundary](public-graveyard-characteristic-record76.md).

Historical failed/intermediate runs remain archived, including the inventory
guard-denial ABI mismatch and the copy fixture's incomplete first correction.
Component results use their exact source/runtime boundaries. The subsequent
combined declaration and complete published-backend result are separate checks;
none of these counts alone signs off Phase 1 or the release.
