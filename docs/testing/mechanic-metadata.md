# Canonical Mechanic Evidence

`canonical_tactical_tags` retains its existing top-level/per-face tags and adds
`mechanic_metadata`. The nested schema is version 1, extractor
`canonical-tactical-surface-v1`; extraction changes require a version bump.

Evidence records retain original face/field, paragraph spans, context and region,
input hashes, source IDs when supplied, categorical confidence and explicit
unknown semantics. Reminder/quoted text is masked without moving offsets.
Detected roles and costs are source-text evidence, not evaluated game effects.

All execution support and learned quality remain unassessed. A missing detection
does not prove absence. Faces must not be treated as simultaneously available.
Hashing includes the full caller-supplied payload; it is payload identity, not
independent verification or a gameplay-equivalence hash. Rulings verification
remains a separate ingestion fact.

Worker verification: unchanged legacy outputs across 38,690 stored payloads;
161 focused/consumer checks pass. Parent composed-engine gate also passes 161.
No live knowledge rows were automatically migrated. Prospective full serialization
was about 206 MiB for this corpus; coordinate materialization with the bounded
readiness pipeline rather than duplicating metadata indiscriminately.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/knowledge-metadata/`.
