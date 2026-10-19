# Task 3.2 Measured-Epoch Preparation

This narrowly scoped preparation changes only the reviewed measurement lineage
in `backend/ai/matchup_profiles.py`. It is not a profile artifact, derivation,
strength measurement or authorization to consume running matrix output.

## Exact Epoch

Immutable consumer source base: `2f42a6eb352480fae1940018b70f4395c478c38e`.
The actual measurement source is different and remains:

```text
source_base_commit:     7c5e933a73755b53da5efd50159c1bb248cf4906
backend_sha256:         9a9b0bd326a05e05b36ac3a01819f9d22709586a78da3c2a50352cf40f78da67
source_binding_sha256:  123b889fbe544bac3dd31689baf793be55daac1da1976210cf034bc41ac212fa
```

The first entry was already correct and is unchanged. Only the two stale
backend/binding literals (`57b0...` / `7059...`) change. This is one exact
three-entry epoch, not an allowlist, fallback epoch or hash of the consumer
after installation. Producer `scripts/matchup_round_robin.py` is bound by the
original header to
`9061cc3b92c136a6d44bd3bb9b3ecef3297dde125f04e18ccb36e49cabb0775b`.

Verification read only the specifically authorized sealed original
`contract-fullmatrix.json` and its completed parity receipt. Original header
raw SHA256 is
`d3ad887eac58b3c4a205508f900ca989ffb7b774f68d6751a745b8ca88d718c5`.
SHA256 of canonical `backend_files` equals the declared `9a9b...`; SHA256 of
canonical full `source_binding` equals `123b...`. The completed parity receipt
matches its header-retained hash
`647bf2330f428287dc6d972da68b28a76f4bc070031a8a196e727724f2a05a78`,
has status `equal_budget_two_seat_pass`, and names the same backend hash.
These checks do not establish final full-matrix completion or source closure.
No measured source, active runtime, game capsule or matrix summary was read.

## Tests And Boundary

`test_matchup_profiles_epoch.py` contains explicit synthetic loader-protocol
controls, NOT native data or learned profiles. A hand-checked balanced packet
in disposable test scratch exercises the real unchanged loader/default cache.
It verifies acceptance of the exact target tuple; rejects the old tuple,
mixed old/new hashes, installed consumer commit, foreign/missing/extra epoch
fields and malformed/unqualified data; and preserves the legacy fallback.
Its `qualified` field is a parser-fixture value, not native qualification.
No new derivation is invoked and no production artifact is written.

The original learned-profile and AI-decision tests remain byte-identical and
run whole under the before-collection SQL/socket/provider/process denial
runner. Their existing synthetic derivation/CLI tests remain synthetic; no
real matrix data is passed to them. The SQL/HTTP
`test_builtin_metadata_refresh.py` cohort is required separately on the
parent's own local IO harness, not silently represented as pure-qualified.

Every function body/signature, loader/cache/CLI API, advisory coefficient and
old test is unchanged. Reversing only the two literals restores the complete
module preimage byte for byte. No agent/rule/planner/mana/UI/provider changes,
no old/new broad allowlist, no actual profile artifact and no learned-data
claim. Independent actual terminal matrix qualification remains required
before data consumption or Task 3.2 completion.
