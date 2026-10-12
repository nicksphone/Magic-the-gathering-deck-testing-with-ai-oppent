# Native Worker URI And Source Scope

The import-identity worker treated a native `file:` read-only URI as a plain
filesystem path. The test-only decoder now accepts exactly canonical owned
plain paths or a local URI with only `mode=ro`, preserving the existing owner
and bootstrap assertions. Foreign paths, aliases, symlinks and extra URI options
remain rejected. Production SQLite ownership, backup and capacities are unchanged.

Historical source-scope witnesses are retained, not overwritten. Explicit
SHA-pinned public deltas are reversed only for comparison with those witnesses:
41 main,7 repository and19 keyword-prefix hunks; the sacrifice middle and
keyword suffix are untouched. Mutations inside and outside approved hunks are
negative controls. No generic hash reset or arbitrary normalization is admitted.

Original three whole modules:150 passed,5 failed34.16s. New14 controls first
produced6 failures/8 passes, then14 passes. Final169 passed45.23s; independent
fresh current parent169 passed40.20s, including original import/restart and
snapshot subprocess episodes. The combined fresh395-case cohort passes84.26s.

All95 original assertion ASTs remain;13 unrelated functions and historical JSON
are exact. The parent verifies3010 non-owned committed paths and all8 postimages.
Only test support changes. Cooperative audit is not a kernel sandbox; child
sitecustomize is not claimed as hostile-process or fatal-bootstrap proof.

Private NFS evidence: `current-2fd-interface-uri-scope-testonly` and
`current-c6-composed395`, dated2026-10-12. Full CI and AI quality remain open.

