"""Role-bound health worker; shares v3 game, replay, parity and limits unchanged."""
import sys


def main(argv=None):
    if sys.flags.optimize or not sys.flags.dont_write_bytecode:
        raise SystemExit('Run v3 health worker without optimization and with -B')
    from scripts.archetype_worker_v3 import main as worker_main
    return worker_main(argv,kind='health')


if __name__=='__main__':
    raise SystemExit(main())
