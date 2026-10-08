"""Repository paths and pytest-owned evidence for complete-body regressions."""
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
for path in (SOURCE / 'backend', HERE / 'delta', HERE / 'gap6', HERE / 'tests',
             SOURCE / 'audit/gate2-domain-compiler', SOURCE / 'audit/gate2-suncleanser'):
    sys.path.insert(0, str(path))


def pytest_collectstart(collector):
    if 'GAP6_EVIDENCE' not in os.environ:
        evidence = collector.config._tmp_path_factory.mktemp('complete-body-evidence')
        os.environ['GAP6_EVIDENCE'] = str(evidence)
    os.environ['LOYALTY_INVENTORY_SOURCE'] = str(SOURCE)
