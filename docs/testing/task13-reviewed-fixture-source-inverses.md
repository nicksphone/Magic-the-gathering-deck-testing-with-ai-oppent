# Reviewed Fixture Source Inverses

The historical printed-facts guard compares protected function source against
`UNCHANGED_FUNCTION_SHA256.json`. Its golden file and original assertions remain
unchanged. Canonicalizing Soul Warden and the two Seal of Removal constructors
requires three finite inverses in the existing metadata-only compatibility helper.

The new JSON pins the exact old and reviewed function hashes and constructor hunks.
It is itself SHA-256 pinned, has exactly three entries, and each old hash must match
the unchanged golden. Restoration returns inert source text; restored constructors
are never imported, compiled, or executed as gameplay fixtures. Only the canonical
constructors in the real test modules execute during the full suite.

Six stdlib regressions cover all eight old/new constructor combinations, exact
historical hashes, idempotence, mutated constructors, out-of-hunk assertions and
state pose, missing/duplicate functions, unknown modules, and unrelated siblings.
Before the helper addition, the corrected regression draft produced five assertion
failures and one pass. Afterward all six passed. An earlier test-only indentation
mutation produced one syntax error and is retained separately in the evidence.

Local verification is metadata-only, with application imports, SQLite, sockets,
native loading, and subprocesses denied. It is not a native gameplay or full CI
qualification. The complete GitHub workflow must qualify each published head.
