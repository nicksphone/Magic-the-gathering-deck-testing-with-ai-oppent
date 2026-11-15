# SPDX-License-Identifier: GPL-3.0-or-later
# Original strict position comparator; Forge sources retain their own notices.
import json
from pathlib import Path
import sys


def compare(before, after):
    if type(before) is not dict or type(after) is not dict:
        raise ValueError("Expected native fact objects")
    if not {"players", "pending_stack"} <= before.keys() or not {"players", "pending_stack"} <= after.keys():
        raise ValueError("Missing observed native position fields")
    missing = object()
    different = sorted(k for k in before.keys() | after.keys()
                       if before.get(k, missing) != after.get(k, missing))
    return {"strict_full_position_equal": not different,
            "pending_stack_equal": before["pending_stack"] == after["pending_stack"],
            "different_fields": different}


if __name__ == "__main__":
    before, after, output = map(Path, sys.argv[1:])
    result = compare(json.loads(before.read_text()), json.loads(after.read_text()))
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["strict_full_position_equal"] else 1)
