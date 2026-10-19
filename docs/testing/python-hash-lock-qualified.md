# Platform-Specific Python Hash Lock

`backend/requirements-py312-linux.lock` records the complete 28-package
application closure of the nine unchanged direct requirements. Each pin has
one accepted wheel SHA256; hashes and binary wheels are mandatory. Installer
pip is provisioned separately, not added to the application closure.

## Executed Qualification

An independently created local venv on CPython 3.12.3, Linux x86_64, glibc 2.39
installed the archived pip 26.2.1 wheel, then all 28 application packages with
`--no-index`, the verified local wheelhouse and `--require-hashes`. Dependencies
were enabled. All nine child stages exited zero. `pip check` passed, install
reports selected exactly the recorded wheel hashes, and the installed raw
METADATA matched the archived wheels. All 33 active dependency edges close.
The parent independently reran the installed verifier with native socket,
SQLite and child-process operations denied; it exited zero.

The first observer stopped after successful installer provisioning because it
classified a denied IPv6 capability probe as unexpected. A separate exact-code
observation established the caught pip-vendored `_has_ipv6` bind probe; the bind
remained denied. A second observer stopped on an already verified wheelhouse
freshness assertion before launching any children. Both failed wrappers remain
archived. Neither installation was repeated or a network permission added.

Evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/dependency-audit/current146f780-offline-hashlocked-install-qualified-20261008-H2PepA/`.
Archive SHA256:
`d103dd24f1bc1c1a64c7b319e793280790c3e7a2db526c0d20526931c22625e1`.
All 2,228 regular members and four symlink targets were read back and compared.
Parent verification/publication evidence is in
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/python-hash-lock-qualified-20261008/`.

## Use And Limits

After creating an isolated venv and supplying the verified wheels locally:

```sh
python -m pip --isolated --disable-pip-version-check --no-cache-dir install \
  --no-index --find-links "$VERIFIED_WHEELHOUSE" \
  --require-hashes --only-binary=:all: -r backend/requirements-py312-linux.lock
python -m pip check
```

Run `backend/verify_hash_lock.py --help` for the original-archive provenance and
installed metadata verifier. Its additional `packaging` dependency is part of
the recorded closure; it is not a standalone bootstrap installer.
`docs/python-hash-lock-proposal.md` preserves the original pre-install proposal.

The nine direct pins, existing requirements and operator launch defaults are
unchanged. Other interpreters/platforms, online wheel acquisition, advisories,
application runtime/browser gates on this new venv, clean-machine provisioning,
and deployment are not qualified by this install. A lock provides repeatable
byte selection, not a security or full-release certificate. No retained user
database or existing borrowed runtime was changed.
