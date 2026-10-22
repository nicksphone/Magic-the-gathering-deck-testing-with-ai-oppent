#!/usr/bin/env bash
set -euo pipefail
export MTG_HOSTED_CLEAN_CONTAINER=1
ROOT=/tmp/mtg-hosted-clean
umask 077
test -d /public/backend && test -d "$ROOT"
# Root provisioning output stays inside owned private scratch, never Docker logs.
mkdir "$ROOT/provision-private"
ulimit -S -f 131072
timeout --signal=TERM --kill-after=15s 1200s \
    /bin/bash /public/ops/ci/hosted-clean/provision.sh \
    >"$ROOT/provision-private/stdout" 2>"$ROOT/provision-private/stderr"
# Outer admission includes the actual image, writable layer and both owned trees.
touch "$ROOT/PROVISION_READY"
for second in $(seq 1 30); do
    test ! -f "$ROOT/PROVISION_ADMITTED" || break
    sleep 1
done
test "$(cat "$ROOT/PROVISION_ADMITTED")" = true
ulimit -S -f 524288
# Actual user/capability drop, not mocked uid or shared-host permission changes.
exec setpriv --reuid="$MTG_UID" --regid="$MTG_GID" --clear-groups \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
    env -i PATH=/usr/bin:/bin HOME="$ROOT/home" TMPDIR="$ROOT/tmp" \
    LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 MTG_HEAD="$MTG_HEAD" \
    MTG_UID="$MTG_UID" MTG_GID="$MTG_GID" \
    /usr/bin/python3.12 -B /public/ops/ci/hosted-clean/guest.py
