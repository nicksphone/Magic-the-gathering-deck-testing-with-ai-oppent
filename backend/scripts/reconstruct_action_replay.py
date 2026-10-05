"""Offline reconstruction of a retained match trace and resolved deck manifest."""
import argparse
import json
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
    args = parser.parse_args()
    try:
        if Path(args.output).resolve() in {Path(args.trace).resolve(), Path(args.deck_manifest).resolve()}:
            raise ValueError('Output must not overwrite the trace or deck manifest')
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
        for index, game in enumerate(games):
            try:
                report['games'].append(reconstruct_game(decks[0]['mainboard'], decks[1]['mainboard'], game))
            except ReplayMismatch as error:
                report.update({'matched': False, 'first_divergence': {'game': index, **error.diagnostic}})
                break
        Path(args.output).write_text(json.dumps(report, indent=2))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f'Reconstruction input error: {error}\n')
    print(json.dumps({'matched': report['matched'], 'games_verified': len(report['games']), 'output': args.output}))
    return 0 if report['matched'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
