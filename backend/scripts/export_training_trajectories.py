"""Offline canonical-builtin heuristic demonstrations, never expert labels."""
try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

import argparse
import json
from pathlib import Path
import signal
import subprocess

from decks.builtin_decks import BUILTIN_DECKS
from training.environment import TrainingEnvironment
from training.dataset import (DatasetRun, HeuristicTeacher, MAX_BYTES, MAX_EPISODES,
                              MAX_TICKS, digest, episode_groups, episode_records,
                              grouped_split_report)


def output_path(output, ci_temp):
    path = Path(output).absolute()
    if ci_temp:
        root = Path(ci_temp).resolve(strict=True)
        if path.parent.resolve(strict=True) != root:
            raise ValueError('Explicit CI output must be a new direct child of --ci-temp')
    else:
        root = Path('/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/training-groundwork/dataset')
        if root not in path.parents:
            raise ValueError('Use verified dataset NFS storage or explicit --ci-temp')
        mounted = subprocess.check_output(['findmnt', '-T', '/mnt/rchfiles/codex-storage',
                                          '-n', '-o', 'FSTYPE'], text=True).splitlines()
        if not mounted or mounted[-1] not in {'nfs', 'nfs4'}:
            raise ValueError('Dataset storage requires mounted NFS; no local fallback')
        # Resolve existing parent paths to reject escapes through directory symlinks.
        root.mkdir(parents=True, exist_ok=True)
        if root.resolve() not in path.parent.resolve().parents and path.parent.resolve() != root.resolve():
            raise ValueError('Output escapes the verified storage root')
    if not path.parent.is_dir() or path.is_symlink():
        raise ValueError('Output parent must exist; run directory cannot be a symlink')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--ci-temp', help='Explicit ephemeral CI root; no automatic SSD fallback')
    parser.add_argument('--deck-a', choices=sorted(BUILTIN_DECKS), default='Mono Red Aggro')
    parser.add_argument('--deck-b', choices=sorted(BUILTIN_DECKS), default='Blue Control')
    parser.add_argument('--seeds', type=int, nargs='+', required=True)
    parser.add_argument('--ticks', type=int, default=16)
    parser.add_argument('--max-bytes', type=int, default=MAX_BYTES)
    parser.add_argument('--difficulty', choices=['strong', 'master'], default='strong')
    parser.add_argument('--family-a', help='Declare the shared family for deck variants')
    parser.add_argument('--family-b', help='Declare the shared family for deck variants')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= len(args.seeds) <= MAX_EPISODES or len(set(args.seeds)) != len(args.seeds):
        parser.error('Use 1..64 distinct seeds; repeated games belong to the same group')
    if not 1 <= args.ticks <= MAX_TICKS or not 4096 <= args.max_bytes <= MAX_BYTES:
        parser.error('Ticks/bytes must be finite and within dataset bounds')
    path = output_path(args.out, args.ci_temp)
    environment = TrainingEnvironment()
    environment.reset(args.deck_a, args.deck_b, seed=args.seeds[0])
    teacher = HeuristicTeacher(args.difficulty)
    metadata = teacher.provenance(environment)
    families = [args.family_a or args.deck_a, args.family_b or args.deck_b]
    config = {'seeds': args.seeds, 'decks': [args.deck_a, args.deck_b], 'families': families,
              'ticks': args.ticks, 'difficulty': args.difficulty}
    manifest = {'configuration_hash': digest(config), **metadata}
    run = DatasetRun(path, manifest, resume=args.resume, max_bytes=args.max_bytes)
    cancelled = False
    def cancel(signum, frame):
        nonlocal cancelled
        cancelled = True
    old_handlers = {sig: signal.signal(sig, cancel) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        if len(run.completed) > len(args.seeds):
            raise ValueError('Run has more episodes than configured')
        for index in range(len(run.completed), len(args.seeds)):
            if cancelled:
                break
            environment.reset(args.deck_a, args.deck_b, seed=args.seeds[index])
            # Stateless teacher instances per episode make boundary resume reproducible.
            teacher = HeuristicTeacher(args.difficulty)
            groups = episode_groups(args.seeds[index], families, metadata['deck_hashes'])
            end = run.write_episode(episode_records(environment, teacher,
                episode=f'episode-{index:04d}', groups=groups, tick_budget=args.ticks,
                origin='heuristic', cancelled=lambda: cancelled))
            print(json.dumps({'episode': end['episode'], 'complete': end['complete'],
                              'reason': end['reason'], 'steps': end['steps']}, sort_keys=True))
            if end['reason'] in {'cancelled', 'interrupted', 'output_budget'}:
                break
        headers = []
        for index in range(len(run.completed)):
            with (path / f'episode-{index:04d}.jsonl').open() as shard:
                headers.append(json.loads(shard.readline()))
        # Diagnostic output only: do not add a mutable file to the sealed run.
        print(json.dumps(grouped_split_report(headers), sort_keys=True))
        return 130 if cancelled else 0
    finally:
        run.close()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    raise SystemExit(main())
