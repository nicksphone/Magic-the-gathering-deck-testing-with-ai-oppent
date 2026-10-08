# Opt-in paid Spree HTTP regression cohort

This package contains twelve real paid HTTP cases, their owned fixture helper,
and unchanged canonical card data/provenance. It is deliberately outside
`backend/tests`; ordinary backend discovery must not collect this cohort.
The relocation changed only the helper import in the test module. All assertions,
parameters, game flows, helper bytes and fixture bytes were retained.

Run only through a reviewed isolated-source/local-SQL harness, with owned
evidence and the exact actor/owner/startup/restart policies. Do not run against
the retained application database or execute SQLite on NFS. Merely adding this
directory to PYTHONPATH is not an isolation or resource-closure contract.

## Actual qualification

On the frozen prior Spree composition, the relocated nine-whole-module cohort
collected the exact 299 ordered nodes, then passed all 299 in 149.56 seconds
(88 warnings, exit0). There were 897 test-phase reports, 36 actual lifespans,
36 owner epochs and verified closed startup backups, and 40 fixed JSON restart
children. The 43 native-control preflight and three original alias denials
passed; no unexpected denials were observed. Source, controls, runtime, media
and backup checks passed. Owners, native DB/socket descriptors, children and
non-main threads were absent at closure; actual existing SQL-family fuser
returned1 with empty output before the exclusive slot released.

Evidence and full byte-compared source/runtime/closed-SQL archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/spree-optin-mixed299-qualified-20261008-Ka21Uz/`.

The first relocation preflight stopped before runtime because its source seal
omitted historical graph caches. That failure remains archived separately. The
successful gate used a fresh exact-file reconstruction, not a weakened check.
The separate normal-backend baseline/delivery collection comparison found no
new discovery regression; the later backend fixture-import repair has its own
23,178-node collection evidence.

This is prior-composition packaging and bounded HTTP evidence, not current
AI/Springheart union, full browser, HTTPS, fresh-install or release completion.
