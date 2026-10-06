# Local Corpus Diagnostic

The reporter in `backend/scripts/oracle_corpus_report.py` uses the same
read-only hydration and runtime factory as live/simulation preparation. It
retains admitted local canonical knowledge, cached fields, offline seed data
and face metadata rather than constructing text-only card approximations.
An injected repository avoids database initialization in tests.

Each row records data sources, match-data admission, parser status, unresolved
resolution clauses, choices, modes and face metadata. All rows and faces have
`semantics_verified: false`. Default characteristics are compiled; alternate
faces are listed, not independently compiled. Parser fallbacks can include
unselected choices, so they are not themselves proof of unsupported gameplay.
Static/noop or structured-event classification is not rules certification.

The standalone candidate is based on published `c16ea8d`; it does not include
the still-failing death/protection composition or unfinished worker products.
Its diagnostic reports 112 unique cards / 3,795 deck copies
across 11 built-in and 52 expansion lists. Its three fallback classifications
are Searing Blaze, March of the Multitudes and Secure the Wastes. The default
run has an isolated local database; it does not measure a user's populated
cache or every custom deck. These are follow-up candidates, not diagnosed
gameplay defects.

Initial regression check: 31 passes across the new reporter tests and the
whole hydration and mechanic-metadata modules. Coverage includes canonical
Memory Deluge knowledge without cache, preserved Delver faces/runtime facts,
canonical vanilla Oracle handling and empty-corpus behavior.

The standalone candidate's three whole modules pass all 31 cases in 1.57s.
The actual CLI exits 0 and reports the same census. Frontend lint, configured
tests and build also pass with reused dependencies and the explicit isolated
test interpreter. All pre-gate backend hashes match after these commands.

These outputs are archived separately from the earlier death/protection gates;
those did not include this reporter change. The latter's gameplay changes
still have the two known Ballista activation failures. No full browser game,
fresh dependency install or professional AI strength is certified.
