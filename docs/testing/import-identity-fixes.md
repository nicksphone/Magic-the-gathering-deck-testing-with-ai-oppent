# Official Import Identity and Sideboard Admission

Baseline: frozen-qualified-audit-source.tgz from expansion-startup-classification/
human-ready-3eL65X, SHA256 056558b91e69efd708bf9b973d3212efa26fbcdb334d1bd441e5eaae82426064.
Prerequisite: previously qualified incremental-fixtures.patch (test-only helper extraction).
This is not a claim about the current parent/main version.

## Production Scope

- decks/service.py: official imports select the newest row with the exact normalized
  official namespace, reusing its exact stored source. Empty catalog imports use lowercase.
- persistence/repository.py: one guard normalizes whitespace for namespace validation;
  the source equality query and persisted source remain exact and unchanged.
- No parser, API, schema, AI, bootstrap, source identity migration or data deletion changes.
- Official calls alone opt into catalog upsert for historical leading-whitespace sources.
  Generic imports retain explicit case-sensitive source identity and user append behavior.
- After parsing, total sideboard quantity above MatchStart's existing 15-card maximum
  raises HTTPException 422 with detail code sideboard_limit_exceeded, maximum and actual.
  This service-layer HTTP exception deliberately avoids edits to parent-owned API handlers;
  ordinary text, file and official handlers already propagate it.
- Parser-rejected imports retain HTTP 200 errors/deck_id=null compatibility and resolve
  display metadata read-only, rather than materializing local knowledge cache records.
  This is not broader format, copy legality, unknown-card rejection or deck legality validation.

## Desired Contracts

112 ordinary tests, memory and local file SQLite, concurrency one. Real offline canonical
LEA Burn and ARN Tempo templates; no fabricated card metadata, network sync, policy replacement,
hidden-library access or strength claims. Actual analysis/provenance remains unchanged and
missing facts still classify unknown. Older and newest normalized sources, whitespace,
case, custom namespace suffixes, same-name users, repeated requests and exact-source history
are compared by ID and complete stored rows, not deduplicated by names.

Boundary 15/16 aggregates multiple sideboard entries. New and existing records, admitted and
missing facts, malformed text and actual file upload 422 are covered. Invalid syntax keeps
its existing compatibility response while blocking persistence/materialization.

Fresh-process actual lifespan tests use both controller arrangements and actual API match
creation/settings/import/read/replay. Full state pickle (including RNG), serialized snapshot,
controller config and receipts are unchanged by imports/rejections. Rejected sideboard and
malformed imports compare complete SQL dumps. Restart verifies IDs/source/history and real
canonical physical inventory equivalence; startup's existing front-face literal spelling
refresh is explicitly permitted, not misreported as byte-identical deck text. Private hands
and library remain absent from public API, debug hands disabled. Start/settings retries
retain receipts/revision. No external socket or default database access is allowed.

Original 82 bug characterizations remain immutable NFS evidence, not a release gate.
The old 24 generic audit remains a historical source artifact, not promoted default tests.
The previously approved helper extraction makes canonical32 and these tests self-contained
without that audit module. Ship only scoped patches, never the full evidence source archive.
