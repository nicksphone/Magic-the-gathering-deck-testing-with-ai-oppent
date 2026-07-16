from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT_STR = str(BACKEND_ROOT)
if BACKEND_ROOT_STR not in sys.path:
    sys.path.insert(0, BACKEND_ROOT_STR)
