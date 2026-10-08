# Qualified Python Wheel Hash Lock Proposal

New paths only: backend/requirements-py312-linux.lock,
backend/verify_hash_lock.py and this document. Existing requirements, setup,
ops, application code and borrowed dVB runtime are unchanged. Source anchor:
146f780b28f2a0b805adcbe0615dd3ef2410b09b; application bytes equal 1c3fbbd.
No installation, download, resolver, advisory query, SQL, server or browser
was run for this proposal. Actual fresh offline installation is still pending
parent qualification in an independently authorized capacity-safe interval.

## Exact Scope And Provenance

CPython 3.12/Linux x86_64/glibc 2.39 only; observed interpreter 3.12.3.
Native wheel compatibility is checked against actual interpreter tags.
Other Python versions, architectures, operating systems and libc versions
are not qualified. Do not silently skip all packages using platform markers.
The verifier refuses unsupported scope; run it before installation.

The nine unchanged direct requirements have SHA256
7aa9f2b409551322171d8fdc0fcdde02fc5f38aedacdb9c904d6e47966c95b97.
The lock expands their actual recorded closure into 28 exact versions and
one original wheel SHA256 each, with --require-hashes and --only-binary=:all:.
All 33 active metadata dependency edges and 124 inactive marked edges are
recorded in verifier output. Extras are not enabled. pytest remains included
because it is one of the nine declared direct requirements.

Existing read-only archive:
/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/dependency-audit/current9f50190-fresh-install-20261008-dQ5OgZ/full-public-source-dependencies-wheel-proofs.tar.gz

Archive SHA256:
bed4f930c4a0e9be876a52ea7193ddf70d03c0c969e184bbcbef12fd8cbb3330

The archive's wheels/ contains 29 wheels, including separately bootstrapped
pip26.2.1. Its companion WHEEL-PROVENANCE.json records original filenames,
SHA256s and sizes. Verification checks archive identity, all wheel hashes,
filenames/tags/Requires-Python, raw wheel and installed application METADATA,
unchanged direct pins, active transitive constraints and exact lock closure.
It reads archive members in memory; nothing is extracted or installed.
The existing packaging26.3 library performs standards-based requirements,
marker, version and wheel-tag parsing. It is itself in the hash-locked closure;
the verifier is not a standalone bootstrap installer.

pip is excluded from the application lock: none of the nine direct pins or
their active dependencies requires it. Its archived wheel SHA256 remains
71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e.
Installer provisioning/maintenance is separate, never an application-package
upgrade or authorization to change the borrowed runtime. The proposal does
not alter any direct or resolved package version.

## Parent-Owned Future Qualification

First run the read-only verifier using an already qualified interpreter,
immutable requirements and the original provenance sidecar. --installed
additionally compares the current app METADATA bytes (not pip). Its JSON stdout
is evidence; parser failure exits nonzero without dumping package inputs.

```sh
PYTHONDONTWRITEBYTECODE=1 "$QUALIFIED_PYTHON" backend/verify_hash_lock.py \
  --archive "$ORIGINAL_WHEEL_ARCHIVE" \
  --provenance "$ORIGINAL_WHEEL_PROVENANCE" \
  --requirements backend/requirements.txt \
  --lock backend/requirements-py312-linux.lock --installed
```

After review, independently create a disposable venv and extract only the
recorded wheels into a local owned wheelhouse. Exact pinned installer bootstrap
is separate. For the application stage, the proposed command is:

```sh
"$NEW_VENV/bin/python" -m pip --isolated --disable-pip-version-check --no-cache-dir install \
  --no-index --find-links "$LOCAL_VERIFIED_WHEELHOUSE" \
  --only-binary=:all: --require-hashes \
  -r backend/requirements-py312-linux.lock
"$NEW_VENV/bin/python" -m pip check
```

These are proposed commands, not executed evidence. Parent must record real
terminal status, wheel identities, installation report, pip-check, installed
metadata/closure and before/after source/installer separation. Qualifying
installation does not itself qualify runtime/browser/SQL, security freshness,
all platforms, clean-machine provisioning or deployment. Hashes establish
exact byte selection relative to the accepted archive, not security safety.

The application lock intentionally provides one accepted artifact per package;
no alternate wheels, sdists, URL credentials or new resolution are authorized.
Do not use --no-deps: dependency completeness remains checked by pip in
hash-required mode. Default install paths are not changed by this sidecar.

## Failure Ledger

The first pre-edit observer incorrectly compared importlib.metadata.read_text()
with raw wheel bytes for sniffio. read_text normalized 104 CRLF pairs; actual
installed and wheel METADATA bytes both have length3875 and are exactly equal.
This observer failure is retained separately. No package/source edit, install
or replay of an application gate resulted. Raw METADATA paths are now read
as bytes. The completed verifier is tested read-only with immediate native
SQL/socket denials, positive actual provenance and negative lock/scope cases.
