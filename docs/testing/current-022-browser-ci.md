# Published 022 Browser CI

Published source `022758e64debeeab8b8e698cce2cd76d35ba82d5` has a terminal
successful browser job in run `38991162003`, attempt 1, job `117273643758`.
It starts at 2026-10-17 01:30:35 UTC and completes at 02:05:29 UTC. The separate
frontend job `117273643781` also succeeds. Backend job `117273643621` is still
in progress at the 02:25 UTC observation; this note does not certify it.

Before retrieving this terminal public browser log, the exact published
workflow's browser job was checked: it has no protected trace input or secret
binding. No private synthetic trace or raw backend job log was read. Saved
browser log SHA-256:
`5fbe74bf82f41004342e88a24ec3024347e7f836afb33d24eaf1e91c02f518ea`.
Published workflow SHA-256:
`5e329085b04edf45dc8ed60667dc87fa738e38cc2f9d862359fc76588d164fff`.
Run/job metadata, the workflow and the complete public browser log are archived
with verified bytes in the project's NFS diagnostics storage.

This is the existing hosted compatibility lane, using
`MTG_BROWSER_NO_SANDBOX=1`; it is not native Chrome/Brave/Firefox, other operating
systems, LAN HTTPS, all rules or RC acceptance. The earlier `aa7fdc62` browser
failure remains an unexplained aborted legal-action read during start recovery.
Frontend bytes are unchanged between those commits. A later success does not
prove its original cause was fixed, and no speculative application fix is
included here. Remaining Phase 1 fixture work and full backend acceptance are
still open.
