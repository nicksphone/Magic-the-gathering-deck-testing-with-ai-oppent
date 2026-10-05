"""Offline first-divergence review; private views never become AI inputs."""
from copy import deepcopy
from itertools import zip_longest
import json


FIELDS = ('game', 'seed', 'starting_player', 'decision', 'trace', 'players',
          'stack', 'attackers', 'blocks', 'attack_bands')
COMBAT_METADATA = ('banding_attackers', 'legal_blocks', 'blocker_capacities')


def decision_records(path):
    """Require complete versioned reconstruction evidence, not a partial log."""
    with open(path, encoding='utf-8') as stream:
        header = None
        footer = None
        count = 0
        game = -1
        decision = -1
        setup = None
        for line in stream:
            if not line.endswith('\n'):
                raise ValueError('Unterminated reconstruction record')
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('Expected object record')
            if header is None:
                if (row.get('kind') != 'private_reconstruction_start'
                        or type(row.get('schema_version')) is not int
                        or row['schema_version'] != 1
                        or type(row.get('games_expected')) is not int
                        or row['games_expected'] < 1
                        or type(row.get('reverse_seats')) is not bool
                        or not isinstance(row.get('input_provenance'), dict)):
                    raise ValueError('Expected version-one reconstruction header')
                header = row
                yield row
            elif footer is not None:
                raise ValueError('Record after reconstruction footer')
            elif row.get('kind') == 'decision_state':
                if (any(field not in row for field in FIELDS)
                        or not isinstance(row['trace'], dict)
                        or not isinstance(row['trace'].get('action'), dict)):
                    raise ValueError('Incomplete decision view')
                if (type(row['game']) is not int or type(row['decision']) is not int
                        or type(row['seed']) is not int
                        or type(row['starting_player']) is not int
                        or row['starting_player'] not in (1, 2)):
                    raise ValueError('Invalid decision coordinates')
                if row['game'] != game:
                    if row['game'] != game + 1 or row['decision'] != 0:
                        raise ValueError('Missing or reordered game decisions')
                    game, decision = row['game'], -1
                    setup = (row['seed'], row['starting_player'])
                if row['decision'] != decision + 1 or setup != (row['seed'], row['starting_player']):
                    raise ValueError('Missing, reordered or inconsistent decisions')
                decision = row['decision']
                count += 1
                yield row
            elif row.get('kind') == 'private_reconstruction_end':
                if (row.get('matched') is not True
                        or type(row.get('games_verified')) is not int
                        or row['games_verified'] != header['games_expected']
                        or game + 1 != header['games_expected']):
                    raise ValueError('Reconstruction did not verify every game')
                footer = row
            else:
                raise ValueError('Unexpected reconstruction record')
        if footer is None or not count:
            raise ValueError('Missing completed reconstruction or decision views')


def compare_decision_views(baseline, candidate, *, allow_added_combat_metadata=False):
    left, right = decision_records(baseline), decision_records(candidate)
    headers = (next(left), next(right))
    for field in ('input_provenance', 'reverse_seats', 'games_expected'):
        if field not in headers[0] or headers[0].get(field) != headers[1].get(field):
            raise ValueError(f'Incompatible reconstruction provenance: {field}')
    counts = [0, 0]
    first = None
    ignored = []
    for index, (old, new) in enumerate(zip_longest(left, right)):
        counts[0] += old is not None
        counts[1] += new is not None
        if old is None or new is None:
            if first is None:
                first = {'index': index, 'fields': ['sequence_length'],
                         'baseline': old, 'candidate': new}
            continue
        normalized = new
        if allow_added_combat_metadata:
            normalized = deepcopy(new)
            for field in COMBAT_METADATA:
                if field not in old['trace']['action'] and field in new['trace']['action']:
                    ignored.append({'index': index, 'field': field,
                                    'value': normalized['trace']['action'].pop(field)})
        changed = [field for field in FIELDS if old[field] != normalized[field]]
        if changed and first is None:
            first = {'index': index, 'fields': changed,
                     'baseline': {field: old[field] for field in changed},
                     'candidate': {field: new[field] for field in changed},
                     'turn': new['trace'].get('turn'), 'step': new['trace'].get('step'),
                     'actor': new['trace'].get('pid')}
        # Consume the entire streams even after divergence to validate footers.
    return {'schema_version': 1, 'matched': first is None,
            'baseline_decisions': counts[0], 'candidate_decisions': counts[1],
            'comparison_fields': list(FIELDS), 'excluded_fields': ['legal_moves'],
            'ignored_added_combat_metadata': ignored, 'first_divergence': first,
            'warning': 'Private offline comparison, not a verdict on optimal play'}
