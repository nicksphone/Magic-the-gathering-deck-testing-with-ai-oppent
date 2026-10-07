# Release Acceptance Status

Checkpoint: 2026-10-07. Application baseline before this documentation update:
`f5833b542c7d2a08c745df25f49ca35cddcf149c`. Overall release remains unfinished.
The requirements in `plan.md` are unchanged; component passes below are not a
substitute for qualification of the final combined source.

## Verified Components

| Component | Observed evidence | Qualification boundary |
| --- | --- | --- |
| Offline backend | Pinned `441201c`: cold 155 hydrated/served, then eight whole modules / 73 passes, 23 paired lifespans | Not the later hardened source, browser or proxy |
| Native browser BO3 | Pinned `2331bb2`: HH three natural games, 2-1, 787 writes; human/Master two natural games, 2-0, 818 writes including 399 AI beats; cold restore and closure passed | Encountered UI branches only; reused declared dependency cache; not AI strength |
| Browser-origin boundary | Exact five applied product/test/doc postimages: nine whole modules / 235 passes; parent pure policy 101 passes | Origin rejection, not authentication, LAN trust or whole-current browser qualification |
| Frontend dependencies | Fresh locked install, typecheck, lint, configured test chain and build passed; full/production advisory scans reported zero | Clean frontend component, not a clean-machine end-to-end installation |
| Python installer maintenance | Qualified EnC3vJ runtime pip 24.0 -> 26.2.1; pip check passed; all non-pip file hashes and package versions equal | Installer-only change; no application gate inferred from pip check |
| Pending-stack privacy | Current `db16186` composition: 22 whole pure modules / 950 passes; parent applied tested bytes | Mixed HTTP/SQL and complete private hand-to-library response remain separate |

Immutable evidence under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`:

- `release-gate-1-7-current-gate/441201c-v2/`
- `parent-integration/native-browser-r9-qualified-20261007/`
- `diagnostics/api-security/retained2331-origin-20261007-ExTz1I/`
- `diagnostics/dependency-audit/retained2331-fresh-20261007-v8A4Tj/`
- `parent-integration/pip-only-maintenance-20261007/`
- `parent-integration/pending-source-privacy-current-db161-20261007/`

Read each report's source pin, failure history, isolation limits and raw evidence
before transferring a result. Closed SQLite evidence must be copied locally for
inspection; never execute a database on NFS.

## Required Before Completion

1. Complete pending-source privacy mixed HTTP/SQL and final-union acceptance.
   The current pure qualification and exact parent integration are documented
   in `pending-stack-privacy-current.md`; they do not cover those other gates.
2. Resolve or explicitly classify the 12 hydrated preflight gaps in the 155-card
   inventory with genuine canonical cost/target/execution tests. The other 143
   cards lacking a known admission gap are not fully semantics-certified.
3. Requalify current built UI, offline assets, BO3 and recovery with the exact
   origin configuration and fresh locked dependencies. Test supported actions
   not encountered in the successful browser episodes.
4. Qualify the proposed private HTTPS/auth proxy: verified certificates,
   authentication, API/media routing, rejected-mutation atomicity, restart and
   resource closure. Static configuration checks are not runtime proof.
5. Complete the declared job/cancellation/retention/backup/restore, clean-machine,
   soak, accessibility and supported-topology operator acceptance requirements.
6. Measure legal hidden-information decision quality and completed, seed/seat-
   balanced games across all declared archetypes. Short probes and a browser
   opponent result do not establish seasoned-player strength.
7. Audit every original Gate 1/2/3 requirement against the final frozen source,
   retain unresolved broader all-rules/arbitrary-card objectives, and perform
   approved publication/deployment only after the relevant gates pass.

No live server, user database, global trust store or service configuration was
changed by these qualifications. A Git push is not a live deployment.
