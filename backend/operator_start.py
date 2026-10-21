"""Explicit trusted startup; no model selection from HTTP, environment or saves."""
import argparse
import hashlib
from pathlib import Path
import re
import sys


class _Arguments(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default diagnostic can echo private argument values.
        raise ValueError('Invalid operator startup arguments')


def load_binding(checkpoint, expected_sha256):
    from ai import learned_policy, learned_qv

    if (type(expected_sha256) is not str
            or re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is None
            or not Path(checkpoint).is_absolute()):
        raise ValueError('Invalid checkpoint identity')
    raw = learned_qv.read_bytes(checkpoint, learned_qv.MAX_CHECKPOINT_BYTES)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Checkpoint identity mismatch')
    return learned_policy.bind_live_policy(raw)


def main(argv=None):
    try:
        parser = _Arguments(description='Trusted learned-policy startup')
        parser.add_argument('--checkpoint', type=Path, required=True)
        parser.add_argument('--checkpoint-sha256', required=True)
        parser.add_argument('--host', choices=['127.0.0.1'], required=True)
        parser.add_argument('--port', type=int, required=True)
        args = parser.parse_args(argv)
        if not 1024 <= args.port <= 65535:
            raise ValueError('Invalid loopback port')
        binding = load_binding(args.checkpoint, args.checkpoint_sha256)
        import main as application
        application.configure_new_match_policy(binding)
        import uvicorn
        uvicorn.run(application.app, host=args.host, port=args.port, workers=1,
                    access_log=False, proxy_headers=False, log_level='critical')
        return 0
    except Exception:
        print('Learned policy startup rejected.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
