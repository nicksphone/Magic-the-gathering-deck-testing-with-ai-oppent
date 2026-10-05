"""Compare completed private reconstruction exports without running AI."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analytics.decision_comparison import compare_decision_views


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', required=True, help='New private report; never overwrite evidence')
    parser.add_argument('--allow-added-combat-metadata', action='store_true')
    args = parser.parse_args()
    try:
        output = Path(args.output).resolve()
        if output in {Path(args.baseline).resolve(), Path(args.candidate).resolve()} or output.exists():
            raise ValueError('Output must be new and distinct from inputs')
        report = compare_decision_views(args.baseline, args.candidate,
                                       allow_added_combat_metadata=args.allow_added_combat_metadata)
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f'Comparison input error: {error}\n')
    print(json.dumps({'matched': report['matched'],
                      'first_divergence_index': (report['first_divergence'] or {}).get('index'),
                      'output': str(output)}))
    return 0 if report['matched'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
