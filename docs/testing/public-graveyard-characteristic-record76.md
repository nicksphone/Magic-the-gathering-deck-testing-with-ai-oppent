# Public Graveyard Characteristic-Record Coverage

This component corrects the public inventory's stale CardInstance schema pin and
explicitly reviews the newly retained `characteristic_record` field. It does not
change CardInstance, snapshot formats, copy operations, rules clauses, planner
weights, or the existing future-field and context vetoes.

The old pin describes 50 fields. Current CardInstance has 51 fields; removing only
`characteristic_record` reproduces the old digest. The reviewed current digest is
`c6cd00f22c8838effbffa7cdd9d19d29fd16f5879346a071a25d5253bceef8e4`.
MatchState and PlayerState pins remain unchanged.

## Bounded Record Admission

For already-public battlefield/graveyard cards, after existing modification vetoes:

- Require an exact version1 dictionary with only `version`, `physical`, `values`.
- Require exact existing `PHYSICAL`/`FIELDS` keys and the shared `_valid` rules-value
  checks, including scalar/container types and rejection of bool-as-int values.
- Require retained values equal physical rules values equal current public rules
  values. Copy/form divergence and live-rule drift are outside this coverage domain.
- Require retained empty faces, normal layout and no selected face. Retained artwork
  must be a string or null; artwork identity differences alone do not change rules.
- Missing/null/empty records remain unknown. Do not reconstruct unavailable legacy
  provenance, silently initialize it during the query, or admit future fields.
- Do not inspect hidden hand/library records, mutate input, or serialize the record
  into inventory receipts.

This is a consistency boundary, not cryptographic proof of official card provenance.
It does not extend copy-operation support or certify arbitrary card/ability families.

## Actual Local Qualification

Immutable source base: `76b0befd7b3aed9365c7a5c5b9d20faafa77ef02`.

NEW60 baseline: 52 failed / 8 passed, zero errors/skips. Unmodified-pin positives
expose the schema failure; explicit test-only current-pin controls expose why a
blind production repin would admit malformed or contradictory records.

The first full run retained 718 passed / 1 failed: the existing native-denial test
expects AssertionError, whereas the outer runner initially raised PermissionError.
No SQL connection was admitted. That complete attempt is preserved. Only the private
runner's negative-control ABI was then corrected: actual collected function
code/globals, six exact ordered denied probes, no native access or global waiver.
Production and all original10/NEW60 test bytes were unchanged between full runs.

Final original10 plus NEW module: **719 passed in 293.03s**, zero failures/errors/
skips, 11 whole modules, 2157 passed setup/call/teardown phases. All 659 original
identities and 60 new identities remain; no pruning or assertion edits. The exact
162 historical0efa failed-node hashes occur among the ordinary local passed calls.

Both full runs used pre-import SQL/socket/child/provider/startup denial, ceiling1500
and unchanged 900-second outer/inner bounds plus15-second outer kill grace. Nine
initial denial canaries and the original six denied probes were observed in the
final run; unexpected events were empty. Source file bytes and dependency files/
links/directory inventories matched; descriptors, threads and children were quiet.
No SQL database or TestClient/startup was created. The guard is cooperative trusted-
source test enforcement, not a hostile-code OS sandbox or native workload grant.

This document was written after the gate, outside its source inventory. No shared
working-tree/index/graph/dependency writes or hosted backend, browser, native game,
Phase1-wide, or release qualification follows from this local component result.
