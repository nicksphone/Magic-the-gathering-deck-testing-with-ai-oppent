# Graveyard Inventory: Nullable Mana Continuation

The reviewed `MatchState` grew from90 to91 fields when `mana_continuation` was
added. The inventory fingerprint still described90 fields, so otherwise valid
queries failed closed as incomplete state metadata. CardInstance and PlayerState
fingerprints were already current; their pins and validation remain unchanged.

This correction explicitly reviews the91-field schema and requires
`mana_continuation is None` before certifying inactive context. A truthiness
check would incorrectly admit an empty dictionary. Nonempty and opaque
dictionaries are also rejected without interpreting their contents. Missing or
malformed runtime fields still fail metadata validation. Serializer, schema,
continuation producers, card records, private-field checks and future-field
rejection are not changed.

## Evidence

The existing sanitized worker2 artifact for run39161755968 reports118 inventory
assertion failures and one separate BO3 missing-evidence failure. Only the
allowlisted metadata JSON and public collection plan were retrieved; no raw
backend log or protected trace was accessed. Public test definitions, frame
lines and source hashes were checked against the exact committed source.

The local seven-whole-module baseline runs338 cases:194 pass and144 fail.
These comprise118 inherited semantic failures, eight new semantic controls,
and18 call failures from a missing `MTG_GY_INVENTORY_EVIDENCE` output binding.
The new controls include a clearly labeled pin-only protocol fixture: it exposes
the unsafe empty/opaque-dictionary result independently of the stale pin. It is
not a genuine resumable-mana frame or gameplay certificate.

The candidate runs the same338 cases and passes all338 in208.43 seconds.
The evidence variable is explicitly bound inside owned runtime scratch;
guard permissions are unchanged. Because that binding differs, the baseline
and candidate are not described as identical-environment runs. Original test
bodies remain byte-identical. All15 source/runtime/resource checks pass, with
the original10 native/private denial controls, no unexpected IO, no surviving
database, thread or child, and no skipped cases. Physical release is
`2026-10-18T21:34:45.188183Z`.

A separate three-whole-module142-case follow-up passes in147.07 seconds:
104 reviewed-context cases,36 numeric-inventory cases and two new linked-discard
stock cases. Its numeric output binding is also owned runtime scratch. All15
finality checks pass; physical release is `2026-10-18T21:45:28.238609Z`.
These two runs are not combined into an invented480-case invocation.

The whole109-case public-inventory module remains unmodified and is not claimed
as locally qualified here: its explicit guard-probe test expects AssertionError
accounting, unlike this runner's PermissionError contract. No individual case
was pruned, retuned or waived. Canonical CI must exercise its matching guard.

Immutable receipts are in project archives
`diagnostics/ci/INVENTORY338-BASELINE-CANDIDATE-CLOSED-20261018-QDVA8iLo` and
`diagnostics/ci/STOCK142-PASS-CLOSED-20261018-t1KIyoUd`.
Whole-backend, native BO3, Phase1 and release acceptance remain separate.
