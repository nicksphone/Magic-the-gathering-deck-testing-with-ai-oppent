# November 8 dependency advisory finding

**RC blocker: the frontend pins vulnerable Vite 6.4.4.** The manifest, lockfile
and reused installed package all report that version.

The maintainer's
[GHSA-8g5g-mxqh-grgj](https://github.com/vitejs/vite/security/advisories/GHSA-8g5g-mxqh-grgj),
published October 21, identifies 6.4.4 as affected and 6.4.5 as patched. It describes
a development-server deny-list bypass, conditional on network exposure and
relevant sensitive files within allowed directories. `frontend/vite.config.ts`
binds the dev server to `0.0.0.0`; no private-file contents or exploit probes were
used to investigate the finding. This is not a finding about the Caddy production
static server. The official
[6.4.5 release](https://github.com/vitejs/vite/releases/tag/v6.4.5) is available.

The connected search service can read the primary advisory after the earlier
web-API attempts failed. This corrects an evidence-access limitation, not the
dependency. The local npm cache lists only a Vite 8.2.0 tarball, and the shell
previously failed npm/GitHub name resolution. The registry metadata request also
failed through the web tool. No guessed integrity, hand-built package contents,
major-version substitute or manifest-only remediation is represented as a fix.

Next work: obtain authoritative registry metadata and the patched Vite package,
update the exact dependency and complete lockfile, then qualify an actual clean
install, frontend contracts, lint/build and relevant served-file controls. Preserve
the current failed offline-install receipt and verify the installed version after
the upgrade. A successful build using reused 6.4.4 dependencies cannot qualify the
patched dependency. The whole dependency advisory gate remains open; this narrow
finding is not a complete direct/transitive audit.
