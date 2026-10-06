"""Compatibility entry point; original red/readiness worker is frozen on NFS."""
from pathlib import Path
import sys
from tests.queued_sequence_restart_worker import run

if __name__ == '__main__':
    run(sys.argv[1], int(sys.argv[2]), 'turn' if sys.argv[3]=='Time Warp' else 'phase', Path(sys.argv[4]))
