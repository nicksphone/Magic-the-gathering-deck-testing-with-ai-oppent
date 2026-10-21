"""Optional fixed-field notice from two owned local native-browser reports."""
import json
import math
import os
from pathlib import Path
import stat
import sys


LIMIT = 16 * 1024
CHECKS = ("dom_nonce", "native_identity", "direct_child_closed")
PREFIX = "::notice title=Native browser qualification::"


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite number")


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite number")
    return number


def _read_report(directory_fd, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                 dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or before.st_size > LIMIT):
            raise ValueError("unavailable report")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(LIMIT + 1)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_size", "st_mtime_ns")
        if (len(data) > LIMIT or len(data) != before.st_size
                or any(getattr(before, key) != getattr(after, key) for key in fields)):
            raise ValueError("changed report")
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_float=_float)
    finally:
        os.close(fd)


def qualification_record(directory, vendor):
    vendor = vendor if type(vendor) is str and vendor in ("chrome", "brave") else "unknown"
    unavailable = {"schema": 1, "vendor": vendor, "available": False,
                   "preflight": None, "lifecycle": None}
    if vendor == "unknown":
        return unavailable
    try:
        path = Path(directory).absolute()
        if Path(os.path.realpath(path, strict=True)) != path:
            return unavailable
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                return unavailable
            preflight = _read_report(fd, "preflight.json")
            lifecycle = _read_report(fd, "lifecycle.json")
        finally:
            os.close(fd)
        if (type(preflight) is not dict or type(lifecycle) is not dict
                or type(preflight.get("schema")) is not int or preflight["schema"] != 1
                or type(lifecycle.get("schema")) is not int or lifecycle["schema"] != 1
                or preflight.get("vendor") != vendor
                or type(preflight.get("ok")) is not bool
                or type(preflight.get("checks")) is not dict
                or any(type(preflight["checks"].get(key)) is not bool for key in CHECKS)
                or type(lifecycle.get("exit_status")) is not int
                or not 0 <= lifecycle["exit_status"] <= 255
                or type(lifecycle.get("cgroup_empty")) is not bool):
            return unavailable
        return {"schema": 1, "vendor": vendor, "available": True,
                "preflight": {"ok": preflight["ok"],
                              "checks": {key: preflight["checks"][key] for key in CHECKS}},
                "lifecycle": {key: lifecycle[key] for key in ("exit_status", "cgroup_empty")}}
    except (OSError, ValueError, TypeError, RecursionError, OverflowError):
        return unavailable


def report_qualification(directory, vendor, stream=None):
    record = qualification_record(directory, vendor)
    line = PREFIX + json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n"
    # Fixed enums, booleans and a 0..255 integer bound every possible notice.
    if len(line.encode("utf-8")) > 512:
        return
    try:
        stream = sys.stdout if stream is None else stream
        stream.write(line)
        stream.flush()
    except (OSError, ValueError):
        pass


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    directory, vendor = args if len(args) == 2 else (None, "unknown")
    report_qualification(directory, vendor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
