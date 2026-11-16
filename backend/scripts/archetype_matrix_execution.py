"""Frozen pilot scheduling and streamed engine traces; no game runs on import."""
from copy import deepcopy
from pathlib import Path
import re

from scripts.archetype_matrix_plan import build_plan, digest

PILOT_SEEDS = [2026111901, 2026111902]


def _matrix(matrix):
    try:
        source = (Path(__file__).resolve().parents[1] / 'decks/builtin_decks.py').read_text()
        rebuilt = build_plan(matrix['revision'], source)
        if digest(matrix) != digest(rebuilt):
            raise ValueError('Matrix differs from the frozen v2 plan')
    except (KeyError, TypeError) as exc:
        raise ValueError('Complete frozen matrix required') from exc


def build_pilot(matrix, run_id):
    _matrix(matrix)
    if type(run_id) is not str or re.fullmatch(r'archetype-pilot-20261116-v2-[A-Za-z0-9-]{1,48}', run_id) is None:
        raise ValueError('A unique v2 pilot run ID is required')
    names = sorted(matrix['decks'])
    pairs = sorted({tuple(sorted((name, names[(i+1) % len(names)])))
                    for i, name in enumerate(names)})
    cells = []
    for a, b in pairs:
        for seed in PILOT_SEEDS:
            for seat in (1, 2):
                identity = {'deck_a': a, 'deck_b': b, 'seed': seed, 'deck_a_seat': seat}
                cells.append({'cell_id': digest({'pilot_run': run_id, **identity}), **identity})
    return {'schema': 1, 'kind': 'pilot', 'run_id': run_id,
            'revision': matrix['revision'], 'matrix_sha256': digest(matrix),
            'matrix': deepcopy(matrix), 'seeds': PILOT_SEEDS.copy(), 'cells': cells,
            'policy': deepcopy(matrix['policy']), 'accepts_matrix_or_strength': False}


def validate_pilot(pilot):
    try:
        expected = build_pilot(pilot['matrix'], pilot['run_id'])
        if digest(pilot) != digest(expected):
            raise ValueError('Pilot schedule or policy changed')
    except (KeyError, TypeError) as exc:
        raise ValueError('Complete frozen pilot required') from exc


def execution_matrix(plan):
    """Admit one cell's frozen matrix or pilot without authorizing a batch run."""
    if isinstance(plan, dict) and plan.get('kind') == 'pilot':
        validate_pilot(plan)
        return deepcopy(plan['matrix'])
    _matrix(plan)
    return deepcopy(plan)
