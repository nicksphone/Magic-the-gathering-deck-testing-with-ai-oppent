"""Explicit offline, exclusive-owned retirement; no background/live API mutation."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--selection', required=True, type=Path,
                        help='Operator JSON with explicit job_ids and snapshot_ids arrays')
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text())
    if not isinstance(selection, dict) or set(selection) != {'job_ids', 'snapshot_ids'}:
        parser.error('Selection must contain exactly job_ids and snapshot_ids')
    if not all(isinstance(selection[k], list) for k in selection):
        parser.error('Selections must be arrays')
    if not args.database.is_file():
        parser.error('An existing application database is required')
    from sqlmodel import Session, create_engine
    from persistence.capacity import DatabaseOwner, initialize_capacity
    from persistence.repository import Repository
    engine = create_engine('sqlite:///' + str(args.database))
    owner = DatabaseOwner(engine).acquire()
    try:
        initialize_capacity(owner, args.backup)
        with Session(engine) as session:
            result = Repository(session).retire_simulations(**selection)
        print(json.dumps(result, sort_keys=True))
    finally:
        owner.close()


if __name__ == '__main__':
    main()
