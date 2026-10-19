# Saved-Match Fixture Birth

The unchanged three-module saved-match baseline on `f1fdfd0e` reproduces
12 failures and 11 passes in 21.30 seconds. Its fixture changes a serialized
match ID after the factory has already captured that ID in private facts.
The restore guard correctly refuses the inconsistent snapshot.

The test-only repair gives each fixture its intended ID before factory birth.
It does not reset facts, weaken restoration, change gameplay, or rewrite nested
snapshots. All 31 assertions in the edited module and every other function
outside the two fixture producers remain unchanged. The deliberately corrupt
and mismatched-ID rejection controls remain intact.

One actual combined run passes all 83 cases in four whole modules, with
75 warnings in 16.15 seconds and zero failures, errors or skips:

- `test_lazy_saved_matches.py`: 13 cases.
- `test_lazy_saved_edges.py`: 5 cases.
- `test_lazy_saved_resume.py`: 5 cases.
- `test_library_reorder.py`: 60 cases.

The original 23 saved-match cases retain their actual file-backed SQLite,
API, concurrent-read, mutation and restart assertions. The library module
receives no SQLite capability. All 113 observed connections close; independent
checks find the 67 existing database, backup and lock files quiet, with source
and installed-runtime bytes unchanged. Earlier failed and administrative
prelaunch ledgers remain separate.

This qualifies the fixture repair on its recorded source composition. It is not
a complete backend, production deployment, all-browser, AI-strength or RC1
certificate. The private synthetic trace remains protected CI input.
