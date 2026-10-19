# Lossless Seed Export Preservation ABI v1

## Qualified Scope

Product path ONLY: `backend/scripts/export_builtin_oracle_seed.py`.
Base is frozen5d0 catalog+seed qualified archive, not current55.
No seed/provenance production JSON, parser, hydration, SQL schema, API or AI edits.
The historical119 module/fixtures/worker/assertions are unchanged. The original
full155 refusal audit stays immutable in its historical NFS archive; new success
acceptance tests replace no historical evidence and weaken no release assertion.

## Admission and Preservation

Validate every existing projected value against cache/knowledge facts BEFORE
preserving baseline properties. Verify all fullraw/unknown fields against exact
canonical printing ID/name/Oracle ID/raw facts. For slim rows also validate any
available exact raw values; admitted bulk and knowledge for the same printing
must agree. Missing mandatory fullraw or conflicting canonical/cache facts
reject; no silent Oracle/printing/color/stat/format update policy exists.

Preserve all baseline cohort/order/aliases/IDs/root properties/unknown fields,
all36 fullraw rows, and existing source labels. No unsolicited root colors.
Only originally authorized missing face colors/loyalty may be added, after
existing full-face semantic/printing admission. A legacy slim `layout=""`
remains unknown only against a no-face canonical `normal` layout; the writer
does not fill it or treat other mismatched layouts as admitted.

For original slim cache rows lacking available fullraw, only their existing
projected facts are checked; this is NOT blanket canonical re-certification.
Unknown nonprojected fields require exact raw availability or reject.

## Explicit Prior Facts

New optional Python keywords: `preservation_ledger`,
`preservation_ledger_sha256`. CLI options:
`--preservation-ledger PATH --preservation-ledger-sha256 SHA256`.

The caller pins existing external provenance. Each prior fact is revalidated
against exact raw identity/hash, preserved value, recognized face-color or
loyalty path, and existing reviewed admission for derived colors. Duplicates,
unsupported paths, malformed or conflicting facts reject before publication.
All historical provenance fields/order remain intact; matching newly generated
facts do not relabel prior source hashes. New facts append only if absent.

Full155 acceptance supplies the original17 pinned facts and preserves their
bytes exactly across repeated runs. Historical callers without prior input
remain compatible but can claim only newly emitted verified facts, NOT retention
of unspecified historical external provenance. Nothing reconstructs unknown
prior provenance from an enriched seed or card name.

## CLI and Failure Boundary

The CLI preserves JSON property/inventory order and stable indentation, rather
than resorting keys. Fresh full155 output is byte-identical to the admitted
seed; repeated export and prior-ledger publication are byte-idempotent.
Real cache route uses pinned canonical bulk; real knowledge route uses exact
Scryfall profiles without bulk. Neither downloads or mutates SQL/input facts.

Output and ledger cannot overwrite database, bulk, or semantic admission files.
Existing input/seed/output/ledger bytes remain unchanged on validation or staging
failure; new destinations remain absent. Existing `_write_outputs` stages both
files before replacement. It is NOT a two-file crash transaction: failure after
the first `os.replace` may leave one file replaced. No crash rollback/recovery
certificate is claimed or implemented. Existing staging/duplicate-path tests
retain their original assertions.

## Evidence

NEW non-collected fixture constructors are AST-equal extractions from the
immutable refusal audit. All canonical rows remain verified original source
facts; corrupted-data negative controls are explicitly not canonical updates.
Acceptance includes full155/119nonloss/36fullraw/17facts/order/ID preservation,
cache and knowledge real CLI success/idempotence, genuine conflict and partial
source rejection, source/semantic/ledger hash refusal, unknown field retention,
legacy layout limits, simultaneous canonical-source conflicts, and SQL immutability.

Metadata preservation is not complete mechanics/engine certification, strategy
quality, current-format legality or arbitrary-card regeneration completeness.
