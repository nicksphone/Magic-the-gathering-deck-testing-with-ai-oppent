#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
: "${RUNNER_TEMP:?}" "${GITHUB_PATH:?}"
runtime="$RUNNER_TEMP/ci-app-backend"
if [[ -e "$runtime" || -L "$runtime" ]]; then
  echo 'CI application runtime must be fresh.' >&2
  exit 2
fi
python .github/scripts/ci_backend_shards.py platform
python -m venv "$runtime"
"$runtime/bin/python" -m pip install --require-hashes --only-binary=:all: --no-cache-dir \
  -r backend/requirements-py312-linux.lock
"$runtime/bin/python" .github/scripts/ci_backend_shards.py runtime "$RUNNER_TEMP/ci-app-runtime.json"
printf '%s\n' "$runtime/bin" >> "$GITHUB_PATH"
