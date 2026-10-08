from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Backend regressions reuse these committed fixtures, not their audit test cohorts.
AUDIT_ROOT = os.path.join(os.path.dirname(ROOT), "audit")
for fixture_dir in ("brainstorm", "gate2-suncleanser", "gate2-suncleanser-abi",
                    "gate2-domain-compiler"):
    fixture_path = os.path.join(AUDIT_ROOT, fixture_dir)
    if fixture_path not in sys.path:
        sys.path.append(fixture_path)
