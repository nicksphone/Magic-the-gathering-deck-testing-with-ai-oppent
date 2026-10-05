"""Offline reconstruction of a retained match trace and resolved deck manifest."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics.action_replay import ReplayMismatch, reconstruct_game
from scripts.regression_matrix_replay import _load_deck_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deck-manifest', required=True)
    parser.add_argument('--trace', required=True, help='Retained run_match JSON with complete games and per-game seeds')
    parser.add_argument('--reverse-seats', action='store_true')
    parser.add_argument('--output', required=True, help='Private JSON report; divergences may contain hand/log data')
    parser.add_argument('--decision-output', help='New private JSONL file with BOTH hands/boards before each recorded action; never passed to AI')
    args = parser.parse_args()
    try:
        inputs = {Path(args.trace).resolve(), Path(args.deck_manifest).resolve()}
        outputs = [Path(args.output).resolve()]
        if args.decision_output:
            outputs.append(Path(args.decision_output).resolve())
        if len(set(outputs)) != len(outputs) or any(path in inputs for path in outputs):
            raise ValueError('Outputs must be distinct from each other, the trace and deck manifest')
        if any(path.exists() for path in outputs):
            raise ValueError('Outputs must be new files; existing evidence is never overwritten')
        decks, provenance = _load_deck_manifest(args.deck_manifest, 2)
        if len(decks) != 2:
            raise ValueError('Exactly two selected decks are required')
        if args.reverse_seats:
            decks.reverse()
        packet = json.loads(Path(args.trace).read_text())
        games = packet.get('games') if isinstance(packet, dict) else None
        if not isinstance(games, list) or not games or not all(isinstance(game, dict) for game in games):
            raise ValueError('Trace must contain a nonempty games array')
        report = {'matched': True, 'input_provenance': provenance, 'games': []}
        with ExitStack() as stack:
            def private_file(path):
                return stack.enter_context(os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w'))

            output = private_file(args.output)
            decisions = private_file(args.decision_output) if args.decision_output else None

            def emit(record):
                if decisions is not None:
                    decisions.write(json.dumps(record) + '\n')
                    decisions.flush()

            emit({'kind': 'private_reconstruction_start', 'schema_version': 1, 'input_provenance': provenance,
                  'reverse_seats': args.reverse_seats, 'games_expected': len(games),
                  'warning': 'Contains both hands; offline evidence only, not an AI view or quality verdict'})
            for index, game in enumerate(games):
                def observe(record):
                    emit({'kind': 'decision_state', 'game': index, 'seed': game['seed'],
                          'starting_player': game['starting_player'], **record})

                try:
                    report['games'].append(reconstruct_game(decks[0]['mainboard'], decks[1]['mainboard'], game,
                        decision_observer=observe if decisions is not None else None))
                except ReplayMismatch as error:
                    report.update({'matched': False, 'first_divergence': {'game': index, **error.diagnostic}})
                    break
            emit({'kind': 'private_reconstruction_end', 'matched': report['matched'],
                  'games_verified': len(report['games']), 'first_divergence': report.get('first_divergence')})
            output.write(json.dumps(report, indent=2))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f'Reconstruction input error: {error}\n')
    print(json.dumps({'matched': report['matched'], 'games_verified': len(report['games']), 'output': args.output}))
    return 0 if report['matched'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
