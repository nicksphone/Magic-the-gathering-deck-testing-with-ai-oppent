#!/usr/bin/env bash
# Guest-only, root phase. This file is never a workstation installer.
set -euo pipefail
test "${MTG_HOSTED_CLEAN_CONTAINER:-}" = 1
test "$(id -u)" = 0
test "${MTG_UID:?}" -gt 0
test "${MTG_GID:?}" -gt 0
# Only NEW guest OS/public tools use public traversal/execution modes.
umask 022
export DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
unset VITE_API_BASE_URL PYTHONPATH NODE_OPTIONS GIT_DIR GIT_WORK_TREE
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
apt-get update -qq
# Missing authenticated exact .16 is a STOP, never an unreviewed curl refresh.
if ! apt-cache show curl=8.5.0-2ubuntu10.16 >/dev/null 2>&1; then
    printf 'CURL_UNAVAILABLE\n' >&2
    exit 78
fi
apt-get install -y --no-install-recommends ca-certificates curl=8.5.0-2ubuntu10.16 \
    python3 python3-venv python3-pip git openssl iproute2 psmisc util-linux xz-utils
printf '%s  /usr/bin/curl\n' \
    1ccbd3dae948374ba8eef1ebda26c64b783ede50b463196e53666e0880bdac60 | sha256sum -c -
/usr/bin/python3 -c 'import platform,sys; assert sys.version_info[:3]==(3,12,3); assert platform.libc_ver()==("glibc","2.39")'
mkdir -p /opt/intake /opt/tool-build/home /opt/tool-build/tmp /opt/node
cd /opt/intake
curl --fail --location --proto '=https' --tlsv1.2 --max-time 180 \
    https://nodejs.org/dist/v24.22.0/node-v24.22.0-linux-x64.tar.xz -o node.tar.xz
printf '%s  node.tar.xz\n' cc2f601cee82d9a5a233302fe307abc600727035fd7d2c3a3571755989e95008 | sha256sum -c -
tar -xJf node.tar.xz --strip-components=1 --no-same-owner -C /opt/node
printf '%s  /opt/node/bin/node\n' 67ca5783febb8bf85736c79fcdd92c8d6d465a0eb2a082672bcdfa76a506751c | sha256sum -c -
printf '%s  /opt/node/lib/node_modules/npm/bin/npm-cli.js\n' 8e5f6f3429f8cdbe693cdc29904e9d5a7b127a494bd15c804bd54c7403bfcbe7 | sha256sum -c -
curl --fail --location --proto '=https' --tlsv1.2 --max-time 180 \
    https://go.dev/dl/go1.26.9.linux-amd64.tar.gz -o go.tar.gz
printf '%s  go.tar.gz\n' 42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d | sha256sum -c -
tar -xzf go.tar.gz --no-same-owner -C /opt
mkdir /opt/tool-build/caddy
cp /public/ops/ci/hosted-clean/caddy/{go.mod,go.sum,main.go} /opt/tool-build/caddy/
cd /opt/tool-build/caddy
export HOME=/opt/tool-build/home TMPDIR=/opt/tool-build/tmp GOTMPDIR=/opt/tool-build/tmp
export PATH=/opt/go/bin:/usr/bin:/bin:/usr/sbin:/sbin GOROOT=/opt/go GOPATH=/opt/tool-build/gopath
export GOMODCACHE=/opt/tool-build/modules GOCACHE=/opt/tool-build/cache
export GOENV=off GOWORK=off GOTOOLCHAIN=local GOTELEMETRY=off GOVCS='*:off'
export GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org GOMAXPROCS=2
unset GOPRIVATE GONOSUMDB GONOPROXY GOFLAGS GOEXPERIMENT
go mod download
go mod verify
# No compiler dependency network after authenticated module intake.
export GOPROXY=off
CADDY=/home/nick/.local/share/mtg-deck-testing-lab/runtimes/caddy2117-e8d654-restored-20261021-xq0syqfu/bin/caddy
mkdir -p "$(dirname "$CADDY")"
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -p 2 -trimpath -mod=readonly \
    -tags nobadger,nomysql,nopgx -ldflags '-s -w' -o "$CADDY" .
printf '%s  %s\n' e8d6545c8485f7bd723fc3a6a2fb5662e89a235ae0d32ccde3f43d81577b0db0 "$CADDY" | sha256sum -c -
F=/home/nick/.local/share/mtg-deck-testing-lab/runtimes/app-py312-certifi20261019-20261021-iMMqrycK
test ! -e "$F"
mkdir -p "$F/wheels"
chmod 700 "$F"
/usr/bin/python3 -m pip download --isolated --disable-pip-version-check --no-cache-dir \
    --index-url https://pypi.org/simple --require-hashes --only-binary=:all: --no-deps \
    --dest "$F/wheels" -r /public/backend/requirements-py312-linux.lock \
    -r /public/ops/ci/hosted-clean/python5/installer.lock
# The complete fresh download set is checked again by unchanged installer/metadata helpers.
getent group "$MTG_GID" >/dev/null || groupadd --gid "$MTG_GID" gate
getent passwd "$MTG_UID" >/dev/null || useradd --uid "$MTG_UID" --gid "$MTG_GID" --no-create-home --home-dir /tmp/mtg-hosted-clean/home gate
chown -R "$MTG_UID:$MTG_GID" "$F" /tmp/mtg-hosted-clean
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > /tmp/mtg-hosted-clean/OS_PACKAGES.tsv
chmod 444 /tmp/mtg-hosted-clean/OS_PACKAGES.tsv
