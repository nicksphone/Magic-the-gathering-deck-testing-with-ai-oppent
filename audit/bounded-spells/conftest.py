"""Canonical bounded-spell fixtures and pytest-owned evidence paths."""
import os
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[2]
for relative in ('backend', 'audit/gate2-domain-compiler', 'audit/bounded-spells'):
    sys.path.insert(0, str(SOURCE / relative))


def pytest_collectstart(collector):
    if 'GAP6_EVIDENCE' not in os.environ:
        os.environ['GAP6_EVIDENCE'] = str(
            collector.config._tmp_path_factory.mktemp('bounded-spell-evidence'))
