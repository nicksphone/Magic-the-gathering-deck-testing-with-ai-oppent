# Opt-In Tactical Profile Sync

The existing corpus sync command now supports `--profile`, which derives the
versioned estimates documented in [profile derivation](knowledge-profiles-current-derivation.md)
after canonical sync. Neither the command nor its estimates certify rules support
or playing strength. AI policy and scoring consumers are unchanged.

```bash
python -m scripts.sync_corpus_cards --database /local/path/knowledge.sqlite --profile
python -m scripts.sync_corpus_cards --database /local/path/knowledge.sqlite --profile --profile-deck "Stored Deck"
```

Without `--profile`, the existing sync summary and behavior remain unchanged.
The default profile context is the requested canonical corpus, not a verified
archetype. `--profile-deck` supplies actual stored mainboard quantities and the
existing deck-analysis estimate; it requires `--profile`. Empty, zero-copy,
oversized or invalid quantity contexts reject before archetype expansion.

Profiling preserves complete canonical `card_data`, rulings, provenance and
unowned outer-profile metadata. Unknown direct tactical namespace keys survive;
known generated structures are replaced, not recursively extension-merged.
It refuses missing/invalid canonical rows and opaque tactical
namespaces instead of overwriting them. Alias duplicates are written once, and
an identical repeat does not update the row or its timestamp. `profiled` and
`profiles_updated` are separate summary fields. Profile errors make the command
exit nonzero; independent row updates are not promised to be a batch transaction.
Additional search results need explicit requested names for corpus profiling.

## Observed Evidence

The later [physical legacy-copy CLI qualification](phase2-legacy-profile-cli-current.md)
executes the original command twice on the same owned file: 158 requested names
resolve to 150 profiled rows, with 150 updates followed by zero updates and
unchanged full tables/timestamps on repetition. This is separate from the earlier
in-memory component below and does not migrate a live database.

The final six-whole-module declaration passed **85 ordinary tests plus 10
subtests in 34.66s**, with no failures, errors, skips or selection filters.
It includes the four new modules and both unchanged tactical/metadata neighbors.
Complete official API objects for all 155 shipped names were inserted through
the real repository, profiled, read in a new session, then profiled again with
zero updates. All canonical objects, identity, metadata and pending rulings were
preserved. Four memory database handles closed; the default app database remained
absent. This is session persistence, not a file-database cold-process certificate.

The public fixture is complete canonical card data from three official API batch
responses, not a private game trace. Its provenance records URI/source epoch,
response counts and snapshot hash. No Oracle text or IDs were fabricated from
the normalized seed, and ruling URLs are not represented as fetched rulings.

The initial nine pure controls failed because the path did not exist. The
expanded thirteen controls recorded twelve failures and one unchanged-mode pass
on the original script, then thirteen passes after implementation. Eight added
quantity/context controls reproduced eight failures before the pre-analysis
guard and passed afterward.

The corrected four-whole-module composition passed **58 ordinary tests plus
10 subtests in 3.05s**, including real SQLModel/Repository memory-database
roundtrips, new-session persistence, repeat timestamp equality and invalid-row
nonmutation. All six source hashes stayed equal; three memory handles closed.
Physical-file SQLite, network, subprocess and provider access were denied.
The initial memory harness attempted to install its SQLite authorizer before
connection initialization and recorded three setup errors. That harness-only
repair was made after the actual error; no product or test assertion changed.

A separate eight-whole-module diagnostic recorded **107 passes, two failures
and ten passing subtests**. Its two failures are physical SQLite requests in the
unchanged ingestion neighbors, which the memory-only scope denies. Its final
closure assertion also found an open memory handle. That declaration is not
reclassified as a passing broader gate. No test was skipped or weakened.

The corrected profile dependency was independently re-reviewed after three
concrete defects in its first candidate. Historical raw-tail, MDFC and keyword
reminder ledgers remain unchanged. Final release qualification, complete canonical
corpus persistence, AI consumers and measured improvement remain separate work.
