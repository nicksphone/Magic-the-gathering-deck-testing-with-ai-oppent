# Verified Rulings For The Shipped Corpus

The October 12, 2026 intake requested the official rulings endpoint for each of
the 155 complete canonical card objects already committed in
`backend/tests/fixtures/knowledge_profiles/seed155-scryfall.jsonl`.
All 155 responses returned HTTP 200. They contain 443 rulings; 35 cards have
verified empty lists. An empty official list is complete, not a missing-data
failure. Requests were spaced by at least 500 ms after each response.

The new JSONL retains the complete official list payload for each card, its
printing identity, Oracle identity, and requested URL. Provenance records the
card-object hash, rulings snapshot hash, intake interval, and raw-intake hash.
Original response bytes and per-request status/timestamps were archived and
verified before offline checks. No Oracle text was rewritten.

## Persistence Qualification

`test_knowledge_rulings_corpus.py` exercises the existing `KnowledgeIngestor`,
real SQLModel repository, and actual cache and knowledge tables. Its mock HTTP
transport replays the archived official responses; it does not synthesize
rulings or replace the repository. The database is owned in-memory SQLite.

- All 155 shipped names, including actual face aliases, have canonical
  knowledge and verified rulings in `knowledge_report`.
- Profile generation preserves every raw card object and ruling, plus the
  canonical ruling provenance and content hashes.
- A new SQLModel session reads the same data. Repeating named sync performs
  zero HTTP requests; repeating profiling changes zero rows and timestamps.
- Mismatched Oracle identity and cyclic pagination reject before writing
  either table. Verified empty lists remain cached and complete.

The four-case whole-module check passes in 32.23 seconds, with all four owned
memory handles closed and no unexpected SQL/network/process denial. Its
offline runner denies physical databases, sockets, subprocesses, and providers.
The official intake ran separately, before installing that offline policy.

The subsequent seven-whole-module composed check passes all 89 ordinary cases
in 58.50 seconds, including the 85 existing profile/tactical/mechanic cases.
All eight memory handles close; the unexpected-denial ledger is empty. No
test is skipped, deselected, or marked as an expected failure.

## Limits

This is evidence for the committed 155-name shipped corpus at `4ff6a814`, not
every additional saved/user deck or every Scryfall card. It does not modify a
live application database, prove all-card rules support, or demonstrate AI
strength. The original full-project rules and measured-decision requirements
remain open. Intake provenance deliberately describes intake only; it does not
claim that the fetch itself ran a database test.
