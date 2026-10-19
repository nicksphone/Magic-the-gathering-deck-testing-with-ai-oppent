"""Owned synthetic report/stream protocols, not native-browser qualification."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
HELPER = SCRIPTS / "ci_native_browser_notice.py"
CALLER = SCRIPTS / "run-native-browser-ci.sh"
PREFIX = "::notice title=Native browser qualification::"
LIMIT = 16 * 1024
CHECKS = ("dom_nonce", "native_identity", "direct_child_closed")
BASE_CALLER_SHA256 = "fd6856d74a98bbc604de9becaa537c63bbfbe95dff67cd6304f8122c89b1c210"
CANARY = "PRIVATE_SYNTHETIC_CANARY_%0A::error::not-an-annotation"
CALL = ('  python3 .github/scripts/ci_native_browser_notice.py '
        '"$MTG_NATIVE_REPORT_DIR" "$MTG_BROWSER_VENDOR" || :\n')


def reports(vendor="chrome"):
    return ({"schema": 1, "vendor": vendor, "ok": True,
             "checks": dict.fromkeys(CHECKS, True)},
            {"schema": 1, "exit_status": 0, "cgroup_empty": True})


def expected(vendor="chrome", preflight=None, lifecycle=None):
    if preflight is None:
        preflight, lifecycle = reports(vendor)
    return {"schema": 1, "vendor": vendor, "available": True,
            "preflight": {"ok": preflight["ok"],
                          "checks": {key: preflight["checks"][key] for key in CHECKS}},
            "lifecycle": {key: lifecycle[key] for key in ("exit_status", "cgroup_empty")}}


def unavailable(vendor="chrome"):
    return {"schema": 1, "vendor": vendor, "available": False,
            "preflight": None, "lifecycle": None}


class NativeBrowserNoticeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="native-notice-protocol-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "reports"
        self.directory.mkdir(mode=0o700)
        self.write_reports()

    def helper(self):
        # Missing implementation must fail each declared method, not collection.
        self.assertTrue(HELPER.is_file(), "Missing optional native qualification reporter")
        spec = importlib.util.spec_from_file_location("native_notice_protocol", HELPER)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        for name in ("qualification_record", "report_qualification", "main"):
            self.assertTrue(callable(getattr(helper, name, None)), "Missing reporter API: " + name)
        return helper

    def write_reports(self, preflight=None, lifecycle=None):
        default_preflight, default_lifecycle = reports()
        for name, value in (("preflight.json", default_preflight if preflight is None else preflight),
                            ("lifecycle.json", default_lifecycle if lifecycle is None else lifecycle)):
            path = self.directory / name
            path.write_text(json.dumps(value), encoding="utf-8")
            path.chmod(0o600)

    def notice(self, text, record):
        self.assertEqual(len(text.splitlines()), 1)
        self.assertTrue(text.startswith(PREFIX))
        self.assertTrue(text.endswith("\n"))
        self.assertLessEqual(len(text.encode("utf-8")), 512)
        self.assertEqual(json.loads(text[len(PREFIX):]), record)
        self.assertNotIn(CANARY, text)

    def test_chrome_and_brave_complete_reports_project_exact_public_facts(self):
        helper = self.helper()
        for vendor in ("chrome", "brave"):
            with self.subTest(vendor=vendor):
                self.write_reports(*reports(vendor))
                self.assertEqual(helper.qualification_record(self.directory, vendor), expected(vendor))

    def test_real_failure_values_are_retained_without_manufacturing_success(self):
        helper = self.helper()
        preflight, lifecycle = reports()
        preflight.update(ok=False, checks=dict.fromkeys(CHECKS, False))
        for status, empty in ((1, False), (130, True), (143, True), (255, False)):
            with self.subTest(status=status):
                lifecycle.update(exit_status=status, cgroup_empty=empty)
                self.write_reports(preflight, lifecycle)
                self.assertEqual(helper.qualification_record(self.directory, "chrome"),
                                 expected(preflight=preflight, lifecycle=lifecycle))

    def test_either_absent_required_report_is_closed_unavailable_not_zero(self):
        helper = self.helper()
        for name in ("preflight.json", "lifecycle.json"):
            with self.subTest(name=name):
                self.write_reports()
                (self.directory / name).unlink()
                self.assertEqual(helper.qualification_record(self.directory, "chrome"), unavailable())

    def test_invalid_utf8_json_duplicate_keys_and_nonfinite_values_are_closed(self):
        helper = self.helper()
        for name, valid in zip(("preflight.json", "lifecycle.json"), reports()):
            good = json.dumps(valid).encode()
            self.assertEqual(json.loads(good), valid)
            # Every duplicate/nonfinite vector otherwise has the complete valid schema.
            suffixes = [b',"schema":1}', b',"unused":{"same":0,"same":0}}',
                        b',"unused":NaN}', b',"unused":Infinity}',
                        b',"unused":-Infinity}', b',"unused":1e999}']
            bad = [b"", b"\xff", good + b" trailing", b"[]", b"null"]
            bad.extend(good[:-1] + suffix for suffix in suffixes)
            if name == "preflight.json":
                bad.append(good.replace(b'"dom_nonce": true',
                                        b'"dom_nonce": true,"dom_nonce": true'))
            for index, payload in enumerate(bad):
                with self.subTest(name=name, vector=index):
                    self.write_reports()
                    (self.directory / name).write_bytes(payload)
                    self.assertEqual(helper.qualification_record(self.directory, "chrome"), unavailable())

    def test_projected_schema_vendor_boolean_and_integer_types_are_strict(self):
        helper = self.helper()
        mutations = [
            ("preflight", "schema", True), ("preflight", "schema", 2),
            ("preflight", "vendor", "brave"), ("preflight", "vendor", CANARY),
            ("preflight", "ok", 1), ("preflight", "checks", []),
            ("lifecycle", "schema", True), ("lifecycle", "schema", 2),
            ("lifecycle", "exit_status", False), ("lifecycle", "exit_status", -1),
            ("lifecycle", "exit_status", 256), ("lifecycle", "exit_status", 0.0),
            ("lifecycle", "cgroup_empty", 1),
        ]
        for target, key, value in mutations:
            with self.subTest(target=target, key=key, value=value):
                preflight, lifecycle = reports()
                (preflight if target == "preflight" else lifecycle)[key] = value
                self.write_reports(preflight, lifecycle)
                self.assertEqual(helper.qualification_record(self.directory, "chrome"), unavailable())
        for key in CHECKS:
            for value in (None, 1, "true"):
                with self.subTest(check=key, value=value):
                    preflight, lifecycle = reports()
                    preflight["checks"][key] = value
                    self.write_reports(preflight, lifecycle)
                    self.assertEqual(helper.qualification_record(self.directory, "chrome"), unavailable())
        self.write_reports()
        for vendor in ("firefox", CANARY, ""):
            self.assertEqual(helper.qualification_record(self.directory, vendor), unavailable("unknown"))

    def test_each_file_has_an_exact_16kib_input_ceiling(self):
        helper = self.helper()
        for name in ("preflight.json", "lifecycle.json"):
            with self.subTest(name=name):
                self.write_reports()
                path = self.directory / name
                data = path.read_bytes()
                path.write_bytes(data + b" " * (LIMIT - len(data)))
                self.assertEqual(helper.qualification_record(self.directory, "chrome"), expected())
                path.write_bytes(path.read_bytes() + b" ")
                self.assertEqual(helper.qualification_record(self.directory, "chrome"), unavailable())

    def test_symlinked_reports_directory_or_nonregular_leaves_are_not_read(self):
        helper = self.helper()
        alias = self.root / "reports-alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        self.assertEqual(helper.qualification_record(alias, "chrome"), unavailable())
        for name in ("preflight.json", "lifecycle.json"):
            for kind in ("symlink", "directory"):
                with self.subTest(name=name, kind=kind):
                    self.write_reports()
                    path = self.directory / name
                    external = self.root / (name + ".owned-control")
                    external.write_bytes(path.read_bytes())
                    path.unlink()
                    try:
                        path.symlink_to(external) if kind == "symlink" else path.mkdir()
                        self.assertEqual(helper.qualification_record(self.directory, "chrome"), unavailable())
                    finally:
                        path.unlink() if kind == "symlink" else path.rmdir()

    def test_foreign_fd_owner_is_rejected_by_actual_retaining_metadata_protocol(self):
        helper = self.helper()
        real_fstat = os.fstat

        def foreign_file(fd):
            result = real_fstat(fd)
            if stat.S_ISREG(result.st_mode):
                values = list(result)
                values[4] = os.getuid() + 1
                return os.stat_result(values)
            return result

        # Simulated foreign UID only, not a native foreign-owned-file certificate.
        with patch("os.fstat", side_effect=foreign_file):
            self.assertEqual(helper.qualification_record(self.directory, "chrome"), unavailable())

    def test_unknown_raw_stderr_paths_ids_and_source_fields_never_enter_annotation(self):
        helper = self.helper()
        preflight, lifecycle = reports()
        preflight.update(binary={"path": CANARY}, browser_stderr={"text": CANARY},
                         source={"commit": CANARY}, startup_failure={"message": CANARY})
        preflight["checks"][CANARY] = CANARY
        lifecycle.update(pid=123456, cgroup=CANARY, error=CANARY)
        self.write_reports(preflight, lifecycle)
        before = {path: path.read_bytes() for path in self.directory.iterdir()}
        output = io.StringIO()
        helper.report_qualification(self.directory, "chrome", stream=output)
        self.notice(output.getvalue(), expected())
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_optional_sink_write_flush_and_closed_stream_failures_do_not_escape(self):
        helper = self.helper()

        class WriteFailure(io.StringIO):
            attempted = False

            def write(self, value):
                self.attempted = True
                raise BrokenPipeError(CANARY)

        class FlushFailure(io.StringIO):
            attempted = False

            def flush(self):
                self.attempted = True
                raise OSError(CANARY)

        closed = io.StringIO()
        closed.close()
        for stream in (WriteFailure(), FlushFailure(), closed):
            with self.subTest(stream=type(stream).__name__):
                helper.report_qualification(self.directory, "chrome", stream=stream)
                if stream is not closed:
                    self.assertIs(stream.attempted, True)

    def test_real_cli_function_outputs_only_the_notice_and_does_not_gate_status(self):
        helper = self.helper()
        for argv, record in (([str(self.directory), "chrome"], expected()),
                             ([str(self.directory), CANARY], unavailable("unknown")),
                             ([], unavailable("unknown"))):
            with self.subTest(argument_count=len(argv)):
                output, errors = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    status = helper.main(argv)
                self.assertEqual(status, 0)
                self.assertEqual(errors.getvalue(), "")
                self.notice(output.getvalue(), record)

    def test_single_optional_shell_call_preserves_all_original_bytes_and_exit_status(self):
        source = CALLER.read_text()
        self.assertEqual(source.count(CALL), 1, "Missing single optional reporter call")
        self.assertIn('NODE\n' + CALL + '  exit "$status"\n', source)
        self.assertEqual(sha256(source.replace(CALL, "").encode()).hexdigest(), BASE_CALLER_SHA256)

    def test_cyclic_report_directory_is_closed_unavailable_without_stderr(self):
        helper = self.helper()
        cycle = self.root / "reports-cycle"
        cycle.symlink_to(cycle.name, target_is_directory=True)
        output, errors = io.StringIO(), io.StringIO()
        unexpected_type = None
        status = None
        with redirect_stdout(output), redirect_stderr(errors):
            try:
                status = helper.main([str(cycle), "chrome"])
            except Exception as error:
                unexpected_type = type(error).__name__
        # Fail outside the handler so an exception chain cannot expose the path.
        if unexpected_type is not None:
            self.fail(unexpected_type)
        self.assertEqual(status, 0)
        self.assertEqual(errors.getvalue(), "")
        self.notice(output.getvalue(), unavailable())


if __name__ == "__main__":
    unittest.main()
