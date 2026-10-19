"""Real settings checks with file-only fixtures, not TLS or binary qualification."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]


def deny_world_io(event, _args):
    if event.startswith(("sqlite3.", "socket.", "subprocess.", "os.exec")) or event in {
        "os.system", "os.fork", "os.forkpty", "os.posix_spawn", "ctypes.dlopen"
    }:
        raise RuntimeError("File-only operator test attempted world I/O")


sys.addaudithook(deny_world_io)
spec = importlib.util.spec_from_file_location("operator_boundary_under_test", HERE / "run.py")
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


class RuntimeDistBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mtg-operator-dist-boundary-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        backend = self.source / "backend"
        backend.mkdir(parents=True)
        shutil.copy2(SOURCE / "backend/browser_origin.py", backend / "browser_origin.py")
        material = self.root / "material"
        material.mkdir()
        for name in ("caddy", "cert", "key"):
            path = material / name
            path.write_bytes(b"Explicit file fixture; not an executable or TLS credential.\n")
            path.chmod(0o600)
        self.old_source, self.old_pin = operator.SOURCE, operator.CADDY_SHA256
        self.old_path = sys.path[:]
        self.old_origin = sys.modules.get("browser_origin")
        self.old_config = os.environ.get("MTG_OPERATOR_CONFIG")
        operator.SOURCE = self.source
        # Pin actual fixture bytes: this tests path admission, not native provenance.
        operator.CADDY_SHA256 = hashlib.sha256((material / "caddy").read_bytes()).hexdigest()
        self.config_path = material / "operator.json"
        os.environ["MTG_OPERATOR_CONFIG"] = str(self.config_path)
        self.config = {
            "origin": "https://localhost:18443", "backend_port": 18444,
            "runtime": str(self.root / "runtime"), "python": sys.executable,
            "caddy": str(material / "caddy"), "dist": str(self.root / "web"),
            "cert": str(material / "cert"), "key": str(material / "key"),
            "user": "fixture", "password_hash": "$2b$12$" + "A" * 53,
        }

    def tearDown(self):
        operator.SOURCE, operator.CADDY_SHA256 = self.old_source, self.old_pin
        sys.path[:] = self.old_path
        if self.old_origin is None:
            sys.modules.pop("browser_origin", None)
        else:
            sys.modules["browser_origin"] = self.old_origin
        if self.old_config is None:
            os.environ.pop("MTG_OPERATOR_CONFIG", None)
        else:
            os.environ["MTG_OPERATOR_CONFIG"] = self.old_config
        self.temp.cleanup()

    def settings(self, runtime, dist):
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text("<!doctype html><title>Explicit fixture</title>")
        self.config.update(runtime=str(runtime), dist=str(dist))
        self.config_path.write_text(json.dumps(self.config))
        self.config_path.chmod(0o600)
        return operator.settings()

    def test_runtime_below_dist_is_rejected(self):
        dist = self.root / "web"
        with self.assertRaises(ValueError):
            self.settings(dist / "runtime", dist)

    def test_deep_runtime_below_dist_is_rejected(self):
        dist = self.root / "web"
        with self.assertRaises(ValueError):
            self.settings(dist / "assets/private/runtime", dist)

    def test_runtime_equal_to_dist_is_rejected(self):
        dist = self.root / "web"
        with self.assertRaises(ValueError):
            self.settings(dist, dist)

    def test_dist_below_runtime_is_still_rejected(self):
        runtime = self.root / "runtime"
        with self.assertRaises(ValueError):
            self.settings(runtime, runtime / "web")

    def test_separate_sibling_runtime_is_accepted(self):
        runtime = self.root / "runtime"
        self.assertEqual(self.settings(runtime, self.root / "web")["runtime"], runtime)

    def test_similar_name_is_not_directory_containment(self):
        runtime = self.root / "web-runtime"
        self.assertEqual(self.settings(runtime, self.root / "web")["runtime"], runtime)

    def test_runtime_below_source_is_still_rejected(self):
        with self.assertRaises(ValueError):
            self.settings(self.source / "runtime", self.root / "web")

    def test_source_build_with_external_runtime_is_accepted(self):
        runtime = self.root / "runtime"
        self.assertEqual(self.settings(runtime, self.source / "frontend/dist")["runtime"], runtime)


if __name__ == "__main__":
    unittest.main()
