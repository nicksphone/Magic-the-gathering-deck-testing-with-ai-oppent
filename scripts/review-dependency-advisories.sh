#!/usr/bin/env bash
# Query current advisories without installing/upgrading application dependencies.
set -euo pipefail
root=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
cd "$root"
work=$(mktemp -d "${TMPDIR:-/tmp}/mtg-advisory-review-XXXXXX")
echo "Audit output: $work"
git rev-parse HEAD > "$work/revision.txt"
inputs=(frontend/package.json frontend/package-lock.json backend/requirements.txt backend/requirements-py312-linux.lock)
sha256sum "${inputs[@]}" > "$work/inputs.sha256"
node --version > "$work/node-version.txt"
npm --version > "$work/npm-version.txt"
# Work on copied npm inputs: neither audit can rewrite the application lock.
mkdir "$work/frontend"
cp frontend/package.json frontend/package-lock.json "$work/frontend/"
cd "$work/frontend"
set +e
timeout 180s npm audit --json --package-lock-only --ignore-scripts --registry=https://registry.npmjs.org --cache "$work/npm-cache" --fetch-retries=0 > "$work/npm-all.json" 2> "$work/npm-all.stderr"
printf '%s\n' "$?" > "$work/npm-all.exit"
timeout 180s npm audit --json --package-lock-only --ignore-scripts --omit=dev --registry=https://registry.npmjs.org --cache "$work/npm-cache" --fetch-retries=0 > "$work/npm-production.json" 2> "$work/npm-production.stderr"
printf '%s\n' "$?" > "$work/npm-production.exit"
set -e
cd "$root"
python_bin=${MTG_AUDIT_PYTHON:-python3}
"$python_bin" -m venv "$work/auditor-venv"
py="$work/auditor-venv/bin/python"
# Auditor only. No --fix, app install, requirements edit or dependency upgrade.
"$py" -m pip install --no-cache-dir --retries 0 --timeout 30 --index-url https://pypi.org/simple pip-audit==2.10.1 > "$work/auditor-install.log" 2>&1
"$py" -m pip_audit --version > "$work/pip-audit-version.txt"
set +e
timeout 300s "$py" -m pip_audit --disable-pip --no-deps --format=json --progress-spinner=off --timeout 30 --cache-dir "$work/advisory-cache" -r backend/requirements-py312-linux.lock > "$work/pip-audit.json" 2> "$work/pip-audit.stderr"
printf '%s\n' "$?" > "$work/pip-audit.exit"
set -e
sha256sum --check "$work/inputs.sha256"
"$py" - "$work" <<'PY'
import json, pathlib, sys
r=pathlib.Path(sys.argv[1]); summary={}; failed=False
for name in ('npm-all','npm-production','pip-audit'):
    code=int((r/(name+'.exit')).read_text())
    try:
        report=json.loads((r/(name+'.json')).read_text())
        if name.startswith('npm'):
            assert 'error' not in report
            counts=report['metadata']['vulnerabilities']
            findings=counts['total']
            summary[name]={'exit':code,'counts':counts}
        else:
            dependencies=report['dependencies']
            assert len(dependencies)==28 and all('skip_reason' not in d for d in dependencies)
            findings=sum(len(d['vulns']) for d in dependencies)
            summary[name]={'exit':code,'audited_packages':len(dependencies),'package_advisory_findings':findings}
        assert code == (1 if findings else 0)
        failed=failed or findings>0
    except (ValueError,KeyError,TypeError,AssertionError):
        summary[name]={'exit':code,'status':'incomplete_or_error'}; failed=True
(r/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
raise SystemExit(1 if failed else 0)
PY
