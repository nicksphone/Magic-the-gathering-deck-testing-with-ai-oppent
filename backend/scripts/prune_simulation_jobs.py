"""Explicit-path, dry-run-first maintenance; run with python -m scripts.prune_simulation_jobs."""
import argparse
import json
import sqlite3
import sys

from persistence.job_retention import prune_jobs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="absolute path to an isolated local database")
    parser.add_argument("--max-age-seconds", type=float)
    parser.add_argument("--keep", type=int)
    parser.add_argument("--protect-id", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--apply", action="store_true", help="delete; otherwise read-only dry run")
    args = parser.parse_args(argv)
    try:
        report = prune_jobs(args.database, max_age_seconds=args.max_age_seconds,
                            keep=args.keep, timeout=args.timeout, apply=args.apply,
                            protected_ids=args.protect_id)
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "error_type": type(exc).__name__}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
