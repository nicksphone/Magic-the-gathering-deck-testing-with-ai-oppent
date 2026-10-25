# Closed MatrixQuota110 Private Export

## Qualification Scope

On 2026-10-24, a managed local run passed **168 ordinary cases / 504 phases**
in 52.687937746 seconds, with no failures, errors, skips or deselections.
The actor, pytest and keeper exited 0. All keeper checks passed, including
12 expected native denials and no unexpected attempts. Every one of 20,069
data paths was checked quiet in 157 bounded fuser batches. Parent-independent
external closure at 22:23:19 UTC confirmed process/unit/C closure and unchanged
Source, Source authority, dependencies, standard library, system and role inputs.

The run covered these four **whole modules**:

| Module | Ordinary Cases |
| --- | ---: |
| `backend/tests/test_closed_matrixquota_training_export.py` | 41 |
| `backend/tests/test_ai_native_training_export.py` | 42 |
| `backend/tests/test_ai_native_training_export_current_layout.py` | 26 |
| `backend/tests/test_learned_matchup_profiles.py` | 59 |

The 41 new cases use explicitly labelled synthetic protocol vectors, not games
or approved training data. Their historical test-first `STATIC/UNRUN` comments
are retained byte-for-byte; the completed run above is the later qualification.
Actual RED41 first demonstrated 41 missing-module call failures / 123 phases.
That RED guardian failed afterward with fuser E2BIG; its rejection was preserved
and independent closure checked all 10,424 paths in 82 batches. GREEN retained
the same every-path checks with batches of at most 128 paths.

This is related-module qualification, **not full CI**. The separate whole
`test_log_priors_archetype.py` module was not part of this local role: its pure-IO
canary expects a different guard exception/denial contract. No tests in it were
filtered or waived, and its normal whole-CI requirement remains.

## Exact Source Boundary

Authoring and local qualification used immutable public base
`891e862cd44f7aab67691c84c090365baf507086`, tree
`16396771ad9060e8ecc97bd30015f1940a72bd98`, plus only these two new Python files:

- `backend/scripts/export_closed_matrixquota_training.py`
- `backend/tests/test_closed_matrixquota_training_export.py`

All 4,151 base files remained byte-identical; the qualified Source had 4,153
files. This publication adds this documentation separately. Existing importers,
producers, AI policy/defaults, resource ceilings, private inputs and dependencies
are unchanged. Later publication or CI source identities require their own join.

## Explicit API

```python
export_closed_matrixquota_training(
    *, role_root, contract, inventory, destination,
    measured_backend, expected_lineage,
    expected_contract_sha256, expected_inventory_sha256,
)
```

The new, explicit `matrixquota-closed110-v1` intake is not the legacy Schema2
entrypoint and does not add producer tuples to that entrypoint's allowlist.
It reuses the existing `derive_matchup_profiles._admit` predicate, requires the
full ordered 110-series / 55-pair schedule, original native limits and complete
resolved BO3s, and checks capsule/raw/normalized-result/source identities.

Caller-approved contract and inventory hashes and lineage are mandatory.
The contract pins a separately approved parent's closed acceptance receipt and
its strict-reader/report identities; a producer's own success flag is not enough.
Closed actor, keeper, manager and before/after receipts must agree before any
private capsule is read or output is created. The strict reader is pinned as
provenance, not executed by this exporter. Authenticity and approval of those
caller anchors remain the caller's responsibility.

Only confirmed `cast_spell` announcements count toward eligibility. A card needs
at least three casts in each of at least two explicit opponent archetypes;
activations do not count, and unavailable context is not invented. The report
separates eligible card/context counts from unavailable provenance.

Inputs are read-only. A successful export preserves raw log strings in private
`series-*/games.jsonl` files, with 0700 directories / 0600 files, without replacing
an existing destination. Eligibility and all input checks precede publication.
No priors are saved or policy activated; `priors_saved` and `task33_complete`
remain false.

## Real-Data Status

**No real completed110 corpus was accepted or exported by this qualification.**
The failed/cancelled fNH prefix remains rejected; no capsule bodies from it were
read for this change. Synthetic success vectors do not qualify that prefix or
satisfy Task3.3's real-data requirement. Any future real export still needs a
completed, independently qualified and physically closed110 with caller-approved
lineage, hashes and the required observed cast/context coverage.

No training adoption, strength, performance, full-matrix acceptance or RC
completion is claimed. Private traces and protected inputs remain private and
are not included in this publication.
