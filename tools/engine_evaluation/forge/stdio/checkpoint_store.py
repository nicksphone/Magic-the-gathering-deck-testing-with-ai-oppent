# SPDX-License-Identifier: GPL-3.0-or-later
# Original host checkpoint store for the Forge Team/Card-Forge engine.
"""Compatibility import; the shared implementation ships with the backend."""
import importlib.util as _importlib_util
from pathlib import Path as _Path
import sys as _sys

_name = "native_checkpoint_store"
_shared = _sys.modules.get(_name)
if _shared is None:
    _path = _Path(__file__).resolve().parents[4] / "backend" / "native_checkpoint_store.py"
    _spec = _importlib_util.spec_from_file_location(_name, _path)
    _shared = _importlib_util.module_from_spec(_spec)
    _sys.modules[_name] = _shared
    _spec.loader.exec_module(_shared)
globals().update({name: value for name, value in vars(_shared).items()
                  if not name.startswith("__")})
