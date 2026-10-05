"""Actor-private trajectories, not expert supervision or private replay files."""
from copy import deepcopy
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re

from rules_engine.action_validation import ActionRejected
from training.environment import decode_action, encode_action


VERSION = 'mtg.dataset.v1'
MAX_EPISODES = 64
MAX_TICKS = 1000
MAX_BYTES = 50 * 1024 * 1024
ORIGINS = {'heuristic', 'scripted', 'unverified'}
_RAW_ID = re.compile(r'p[12]-\d+|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
_OBSERVATION_FIELDS = {'version', 'seat', 'acting_seat', 'turn', 'step', 'active_seat',
    'priority_seat', 'pregame_pending', 'mulligan_count', 'players', 'known_cards',
    'stack', 'attackers', 'blocks', 'pending_choice', 'winner'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


class EpisodeAliases:
    """Per-observer public encounter IDs; the reverse map never leaves memory."""

    def __init__(self):
        self._maps = {1: {}, 2: {}}

    def _replace(self, value, mapping):
        if isinstance(value, dict):
            return {self._replace(key, mapping): self._replace(item, mapping)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [self._replace(item, mapping) for item in value]
        if not isinstance(value, str) or not mapping:
            return value
        pattern = '|'.join(re.escape(key) for key in sorted(mapping, key=len, reverse=True))
        return re.sub(pattern, lambda match: mapping[match[0]], value)

    def observation(self, observation):
        seat = observation['seat']
        mapping = self._maps[seat]
        known = observation['known_cards']
        order = []
        for player in observation['players'].values():
            for zone in ('hand', 'battlefield', 'graveyard'):
                order.extend(player.get(zone, []))
        order.extend(item['source_card_id'] for item in observation['stack'])
        # Remaining authorized memory is ordered by public characteristics, not deck IDs.
        order.extend(sorted(known, key=lambda cid: canonical({key: value for key, value
                          in known[cid].items() if key not in {'id', 'attached_to'}})))
        for cid in order:
            if cid in known and cid not in mapping:
                mapping[cid] = f'card:{len(mapping) + 1}'
        for item in observation['stack']:
            if item['id'] not in mapping:
                mapping[item['id']] = f'stack:{len(mapping) + 1}'
        result = self._replace(observation, mapping)
        # Metadata URI/Oracle identifiers are canonical card data, not instance IDs.
        for card in result['known_cards'].values():
            card.pop('image_uri', None)
        return result

    def action(self, action, seat):
        result = self._replace(decode_action(encode_action(action)), self._maps[seat])
        if _RAW_ID.search(canonical(result)):
            raise ActionRejected('Action references an object absent from the observation')
        return result

    def actual_action(self, action, seat):
        inverse = {alias: actual for actual, alias in self._maps[seat].items()}
        return decode_action(encode_action(self._replace(action, inverse)))


def baseline_teacher_config(difficulty):
    if difficulty not in {'strong', 'master'}:
        raise ValueError('Unsupported baseline teacher difficulty')
    return {'implementation': 'AIAgent', 'mode': 'baseline_generic',
            'difficulty': difficulty, 'archetype': 'Midrange',
            'opponent_archetype': None, 'deck_identity_analysis': False}


class HeuristicTeacher:
    """Trusted adapter: only this teacher accesses the environment's private view."""
    origin = 'heuristic'

    def __init__(self, difficulty='strong'):
        from ai.agent import AIAgent
        self.config = baseline_teacher_config(difficulty)
        self.agents = {seat: AIAgent(difficulty=difficulty, archetype='Midrange',
                                   opponent_archetype=None) for seat in (1, 2)}
        root = Path(__file__).resolve().parents[1]
        files = [path for path in (root / 'ai').rglob('*') if path.suffix in {'.py', '.json'}]
        files.extend((root / 'knowledge').glob('*.py'))
        files.append(root / 'scripts/export_training_trajectories.py')
        files.append(Path(__file__).resolve())
        files.sort()
        self.policy_hash = digest({'teacher_config': self.config,
            'files': {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
                      for path in files}})

    def __call__(self, environment):
        seat = environment.acting_seat
        view, moves = environment._view(seat)
        return self.agents[seat].choose_action(view, moves, seat).action

    def provenance(self, environment):
        # The full trusted snapshot is never returned, saved or made a model input.
        source = environment.snapshot()['provenance']
        return {'engine_hash': source['engine_hash'], 'deck_hashes': source['deck_hashes'],
                'policy_hash': self.policy_hash, 'origin': self.origin,
                'teacher_config': deepcopy(self.config)}


def episode_records(environment, teacher, *, episode, groups, tick_budget,
                    origin='unverified', cancelled=lambda: False):
    """Yield pre-action input and the complete action actually accepted by the engine."""
    if origin not in ORIGINS or (origin == 'heuristic' and not isinstance(teacher, HeuristicTeacher)):
        raise ValueError('No expert origin is certified by this exporter')
    if isinstance(teacher, HeuristicTeacher) and origin != 'heuristic':
        raise ValueError('The current AI teacher is always heuristic')
    if type(tick_budget) is not int or not 1 <= tick_budget <= MAX_TICKS:
        raise ValueError('Finite tick budget required')
    if not re.fullmatch(r'episode-\d{4}', episode) or not groups or any(
            not re.fullmatch(r'(?:seed|family|deck|position):[0-9a-f]{64}', value) for value in groups):
        raise ValueError('Use opaque hashed groups, never raw seeds or private position data')
    aliases = EpisodeAliases()
    yield {'version': VERSION, 'kind': 'episode_start', 'episode': episode,
           'groups': sorted(set(groups)), 'origin': origin}
    count, reason = 0, 'tick_budget'
    try:
        while not environment.terminated and count < tick_budget:
            if cancelled():
                reason = 'cancelled'
                break
            seat = environment.acting_seat
            observation = aliases.observation(environment.observe(seat))
            proposed = teacher(environment)
            if cancelled():
                reason = 'cancelled'
                break
            action = environment.lookup(proposed, seat)['action']
            public_action = aliases.action(action, seat)
            if aliases.actual_action(public_action, seat) != action:
                raise ActionRejected('Action aliases do not round-trip')
            if cancelled():
                reason = 'cancelled'
                break
            result = environment.step(action, seat)
            # No next observation, replay trace, reasoning or private evaluator state.
            yield {'version': VERSION, 'kind': 'transition', 'episode': episode,
                   'index': count, 'input': observation, 'action': public_action,
                   'action_id': encode_action(public_action), 'accepted': True}
            count += 1
            if result['terminated']:
                reason = 'terminal'
    except ActionRejected:
        reason = 'rejected_action'
    except KeyboardInterrupt:
        reason = 'interrupted'
    except Exception:
        reason = 'teacher_or_engine_error'
    terminal = environment.terminated and reason in {'terminal', 'tick_budget'}
    yield {'version': VERSION, 'kind': 'episode_end', 'episode': episode,
           'steps': count, 'complete': terminal, 'reason': 'terminal' if terminal else reason,
           'terminal_rewards': {str(k): v for k, v in environment.rewards.items()} if terminal else None}


def model_input(record):
    """Only this current actor's observation is a feature; labels/provenance stay out."""
    if record.get('kind') != 'transition' or record.get('accepted') is not True:
        raise ValueError('Expected an accepted transition')
    value = record['input']
    if set(value) != _OBSERVATION_FIELDS or type(value['seat']) is not int or value['seat'] not in (1, 2):
        raise ValueError('Observation schema mismatch; provenance/future fields are forbidden')
    if value['winner'] is not None or 'hand' in value['players'][str(3-value['seat'])]:
        raise ValueError('Terminal/future or opposing hand in model input')
    if any('library' in player for player in value['players'].values()):
        raise ValueError('Private library in model input')
    if any(not re.fullmatch(r'card:\d+', cid) or card['id'] != cid
           for cid, card in value['known_cards'].items()):
        raise ValueError('Raw card instance IDs must not be model features')
    return deepcopy(value)


def episode_groups(seed, families, deck_hashes, *, position_group=None):
    groups = ['seed:' + digest(seed)]
    groups.extend('family:' + digest(family) for family in families)
    groups.extend('deck:' + value for value in deck_hashes)
    if position_group is not None:
        groups.append('position:' + digest(position_group))
    return sorted(set(groups))


def grouped_split(episodes, *, eval_fraction=.2):
    """Connected components prevent seed/family/deck/position overlap across splits."""
    if not 0 <= eval_fraction <= 1:
        raise ValueError('Invalid evaluation fraction')
    parent = list(range(len(episodes)))
    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    seen = {}
    for index, episode in enumerate(episodes):
        if not episode.get('groups') or not episode.get('episode'):
            raise ValueError('Episode groups are required')
        for group in [*episode['groups'], 'episode:' + episode['episode']]:
            if group in seen:
                parent[find(index)] = find(seen[group])
            seen[group] = index
    components = {}
    for index, episode in enumerate(episodes):
        components.setdefault(find(index), []).append(episode)
    result = {'train': [], 'eval': []}
    for members in components.values():
        key = sorted({group for item in members for group in item['groups']})
        split = 'eval' if int(digest(key), 16) / 2**256 < eval_fraction else 'train'
        result[split].extend(item['episode'] for item in members)
    return {key: sorted(set(value)) for key, value in result.items()}


def grouped_split_report(episodes, *, eval_fraction=.2):
    """Report unusable partitions explicitly; nonempty splits are not policy qualification."""
    split = grouped_split(episodes, eval_fraction=eval_fraction)
    reasons = []
    if not split['eval']:
        reasons.append('empty_heldout_split')
    if not split['train']:
        reasons.append('empty_training_split')
    return {'kind': 'split_report', **split, 'partition_ready': not reasons,
            'status': 'NOT evaluation-ready' if reasons else 'partitions_available',
            'reasons': reasons}


def validate_episode(path, expected_episode):
    """Fail closed on partial/malformed shards; never repair or truncate caller files."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Unsafe episode file')
    content = sha256()
    count, last = 0, None
    with path.open('rb') as source:
        for index, line in enumerate(source):
            if not line.endswith(b'\n') or len(line) > 2 * 1024 * 1024:
                raise ValueError('Partial or oversized record')
            row = json.loads(line)
            if row.get('version') != VERSION or row.get('episode') != expected_episode:
                raise ValueError('Episode/version mismatch')
            schemas = {
                'episode_start': {'version', 'kind', 'episode', 'groups', 'origin'},
                'transition': {'version', 'kind', 'episode', 'index', 'input', 'action', 'action_id', 'accepted'},
                'episode_end': {'version', 'kind', 'episode', 'steps', 'complete', 'reason', 'terminal_rewards', 'content_sha256'},
            }
            if set(row) != schemas.get(row.get('kind')):
                raise ValueError('Unexpected fields; snapshots/future data are forbidden')
            if last and last['kind'] == 'episode_end':
                raise ValueError('Records after episode end')
            if index == 0:
                if row['kind'] != 'episode_start' or row.get('origin') not in ORIGINS:
                    raise ValueError('Invalid episode header')
                if not isinstance(row['groups'], list) or not row['groups'] or any(
                        not re.fullmatch(r'(?:seed|family|deck|position):[0-9a-f]{64}', group)
                        for group in row['groups']):
                    raise ValueError('Invalid opaque episode groups')
            elif row['kind'] == 'transition':
                if type(row['index']) is not int or row['index'] != count or row['accepted'] is not True:
                    raise ValueError('Invalid transition sequence')
                if encode_action(row['action']) != row['action_id']:
                    raise ValueError('Action encoding mismatch')
                model_input(row)
                count += 1
            elif row['kind'] == 'episode_end':
                if row['steps'] != count or row.get('content_sha256') != content.hexdigest():
                    raise ValueError('Episode digest/count mismatch')
                if type(row['complete']) is not bool or row['complete'] != (row['reason'] == 'terminal'):
                    raise ValueError('Invalid terminal label')
                if (row['terminal_rewards'] is None) != (not row['complete']):
                    raise ValueError('Incomplete episode cannot have terminal rewards')
                if row['complete'] and (set(row['terminal_rewards']) != {'1', '2'}
                        or any(type(value) is not int or value not in {-1, 0, 1}
                               for value in row['terminal_rewards'].values())
                        or sum(row['terminal_rewards'].values()) != 0):
                    raise ValueError('Invalid terminal reward pair')
            else:
                raise ValueError('Invalid record type')
            content.update(line)
            last = row
    if last is None or last['kind'] != 'episode_end':
        raise ValueError('Incomplete shard; start a fresh run, do not silently append')
    return last


class DatasetRun:
    """Exclusive immutable shards; resume only at verified episode boundaries."""

    def __init__(self, path, manifest, *, resume=False, max_bytes=MAX_BYTES):
        if type(max_bytes) is not int or not 4096 <= max_bytes <= MAX_BYTES:
            raise ValueError('Output byte budget must be 4096..MAX_BYTES')
        fields = {'configuration_hash', 'engine_hash', 'deck_hashes', 'policy_hash', 'origin'}
        if manifest.get('origin') == 'heuristic':
            fields.add('teacher_config')
            config = manifest.get('teacher_config')
            if not isinstance(config, dict) or config != baseline_teacher_config(config.get('difficulty')):
                raise ValueError('Heuristic provenance requires exact baseline teacher configuration')
        if set(manifest) != fields or manifest['origin'] not in ORIGINS:
            raise ValueError('Only versioned hash provenance is accepted; no expert certification')
        hashes = [manifest[key] for key in ('configuration_hash', 'engine_hash', 'policy_hash')]
        if not isinstance(manifest['deck_hashes'], list) or len(manifest['deck_hashes']) != 2:
            raise ValueError('Two canonical deck hashes required')
        if any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
               for value in hashes + manifest['deck_hashes']):
            raise ValueError('Invalid provenance hash')
        self.path, self.max_bytes = Path(path), max_bytes
        self.manifest = {'version': VERSION, 'max_bytes': max_bytes, **manifest}
        if self.path.is_symlink():
            raise ValueError('Run directory must not be a symlink')
        if resume:
            meta = self.path / 'manifest.json'
            lock = self.path / 'run.lock'
            if meta.is_symlink() or lock.is_symlink() or not lock.is_file():
                raise ValueError('Unsafe resume manifest/lock')
            if meta.stat().st_size > 65536 or lock.stat().st_size != 0:
                raise ValueError('Malformed resume manifest/lock')
            if json.loads(meta.read_text()) != self.manifest:
                raise ValueError('Resume configuration/engine/policy differs')
        else:
            self.path.mkdir(mode=0o700)
            with (self.path / 'manifest.json').open('x') as stream:
                stream.write(canonical(self.manifest) + '\n')
            (self.path / 'run.lock').touch(mode=0o600, exist_ok=False)
        self._lock = os.open(self.path / 'run.lock', os.O_RDWR | os.O_NOFOLLOW)
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            entries = list(self.path.iterdir())
            allowed = {'manifest.json', 'run.lock'}
            shards = sorted(item for item in entries if re.fullmatch(r'episode-\d{4}\.jsonl', item.name))
            if len(shards) > MAX_EPISODES or any(item.name not in allowed and item not in shards for item in entries):
                raise ValueError('Unknown/pending run files; no implicit repair')
            self.completed = []
            for index, shard in enumerate(shards):
                if shard.name != f'episode-{index:04d}.jsonl':
                    raise ValueError('Noncontiguous episode shards')
                self.completed.append(validate_episode(shard, f'episode-{index:04d}'))
            self.used = sum(item.stat().st_size for item in entries)
            if self.used > max_bytes:
                raise ValueError('Existing run exceeds output budget')
        except BaseException:
            self.close()
            raise

    def close(self):
        if getattr(self, '_lock', None) is not None:
            os.close(self._lock)
            self._lock = None

    def write_episode(self, records):
        if self._lock is None or len(self.completed) >= MAX_EPISODES:
            raise ValueError('Closed/full run')
        index = len(self.completed)
        episode = f'episode-{index:04d}'
        pending = self.path / f'.pending-{index:04d}.jsonl'
        final = self.path / f'{episode}.jsonl'
        content, count, ended = sha256(), 0, False
        with pending.open('xb') as stream:
            os.chmod(pending, 0o600)
            for row in records:
                if row.get('episode') != episode or row.get('version') != VERSION:
                    raise ValueError('Wrong episode/version')
                row = deepcopy(row)
                if row['kind'] == 'episode_start' and row.get('origin') != self.manifest['origin']:
                    raise ValueError('Episode/manifest teacher origins disagree')
                if row['kind'] == 'episode_end':
                    row['content_sha256'] = content.hexdigest()
                    ended = True
                line = (canonical(row) + '\n').encode()
                if not ended and (len(line) > 2 * 1024 * 1024 or self.used + len(line) + 1024 > self.max_bytes):
                    row = {'version': VERSION, 'kind': 'episode_end', 'episode': episode,
                           'steps': count, 'complete': False, 'reason': 'output_budget',
                           'terminal_rewards': None, 'content_sha256': content.hexdigest()}
                    line, ended = (canonical(row) + '\n').encode(), True
                if self.used + len(line) > self.max_bytes:
                    raise ValueError('No space for bounded episode end')
                stream.write(line)
                self.used += len(line)
                content.update(line)
                count += row['kind'] == 'transition'
                if ended:
                    break
            if not ended:
                raise ValueError('Missing explicit episode end')
            stream.flush()
            os.fsync(stream.fileno())
        end = validate_episode(pending, episode)
        os.link(pending, final, follow_symlinks=False)
        pending.unlink()
        self.completed.append(end)
        return end
