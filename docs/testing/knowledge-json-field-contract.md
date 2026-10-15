# Knowledge JSON Field Contract

## Reproduced Task 1.1 Gap

On published `f2200b08970fd81099ea420df919f472a0e7323c`, an isolated audit
observes 112 failures and 244 passing controls. The specified `answerable_by`
and `cast_windows` JSON `list[str]` contract was not validated after decoding:
wrong containers and non-string elements could be persisted, including over
existing values. Malformed encoded JSON was also admitted by explicit model
validation. Manual schema controls demonstrate this without fabricated Oracle
text or gameplay claims.

## Admission Correction

Two model field validators decode `answerable_by_json` and `cast_windows_json`
and require lists containing strings. A third validator checks `profiles_json`
with the existing standard-library JSON decoder, retaining any accepted value:
the plan says JSON blob, not object-only schema. It adds no stricter numeric
constant policy than that decoder. Existing downstream analyses may require a structured profile object;
this change does not certify those consumers for arbitrary blob shapes.

Validators return the original encoded string, preserving whitespace, escapes,
duplicate keys and unknown metadata rather than rewriting stored data. They add
no effect-key enum, nonempty-string rule, scoring bound or finiteness restriction.
Valid defaults and the existing repository's normalization remain unchanged.

The repository's existing explicit model-validation call runs these checks
before its first connection/query or ORM mutation. Direct ORM construction,
assignment and legacy-row reads remain compatible; this is not a DB CHECK,
schema migration, legacy cleanup or universal bypass-prevention mechanism.
The Unicode repository correction and all prior provenance/score bounds remain
unchanged.

Separate compilation of the preimage and corrected model confirms byte-identical
SQLite table and index DDL, SHA-256
`9e2ded91711a4e0885baa97ef69f589cb7708df47c6094181d5f1bab4f60aed9`.
SQL, sockets and children are denied before imports for that compilation proof;
it does not execute SQLite or start the application.

## Acceptance Boundaries

The original audit and its exact assertions remain private and immutable under
`diagnostics/phase1-task11-typed-json-audit-20261015-uFAvqVLA/`.
The corrected frozen model is
`9209f35d6104c6834d39e5e7303ae0c15a92b2144e501a3a60ddb09f91956d3a`.
The complete corrected component and real copied-data follow-up are qualified
separately, not inferred from the earlier Unicode-only result.

The corrected focused declaration passes 428 cases: 254 new JSON-boundary
cases, the unchanged 135 Unicode cases, 34 domain cases and five original
model cases. Its test-first preimage is 156 failures and 272 passes. Replaying
the separate unchanged 356-case diagnostic yields 312 passes and 44 historical
characterization failures: those cases deliberately expected invalid writes
to succeed. That immutable baseline is not relabeled as a current green suite.

The parent composition passes **899 ordinary cases in 29 whole modules** in
442.82 seconds, with zero failures, errors, skips or I/O denials. Independent
raw-XML accounting retains all 645 preceding test identities and adds exactly
254 new cases. All preceding backend test/data bytes are unchanged; only the
model and new test module differ. The original application startup/shutdown,
all ingestion controls and natural-game test remain. The latter's measured
call is 320.039 seconds, not an AI-quality or causal performance measurement.

Source hashes remain unchanged across the run. The runner closes inherited
fixture connections and leaves zero jobs/other threads. An external check finds
all 332 existing owned SQLite files quiet. Its native pre-import guard remains
the same trusted-cohort boundary, not a hostile-SQL or absolute-host proof.
Full frontend tests, build and lint also exit zero with this model and the
reviewed held-response diagnostic follow-up present together.

A distinct fresh owned legacy-copy run executes the actual completeness and
sync CLIs on this model source: 158 complete names, zero missing/pending,
zero synced, 158 cached, zero errors and zero HTTP attempts. All table rows,
schema and full-file hash remain identical; original data and sidecars are
unchanged and all handles close. Exact model/repository/test pins match the
parent composition. Its private summary is
`diagnostics/phase1-json-copy-followup-20261015-ClSnoyC6/summary.json`, SHA-256
`c37419eb717c297fdbc72eb3d507fa5712b1cc69a96e77e3c60a8e2f6a8aaec8`.
This is not selection or migration of a live deployment.

No live user database, canonical seed, learned data, AI coefficient, game rule
or new dependency is changed. Phase 1 and the full release remain unsigned.
