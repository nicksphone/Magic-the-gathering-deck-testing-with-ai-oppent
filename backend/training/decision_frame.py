"""Actor-authorized decision frames and data-only, reference-bound feature trees."""
from copy import deepcopy
import itertools
import json
import math
import re

from rules_engine.action_validation import ActionRejected
from training.environment import _action, _PROMPT_FIELDS, _public_target_projection

DECISION_VERSION = 'mtg.decision.v1'
FEATURE_VERSION = 'mtg.features.v1'
FEATURE_SCHEMA_SHA256 = '0b3aadfead9f66999c8b6c3ddc13699ad7dc5dd1c76179e95585042ba0339ed5'
CONTEXT_DECISION_VERSION = 'mtg.decision.v2'
CONTEXT_FEATURE_VERSION = 'mtg.features.v2'
CONTEXT_FEATURE_SCHEMA_SHA256 = '9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06'
_OBSERVATION_FIELDS = {'version', 'seat', 'acting_seat', 'turn', 'step', 'active_seat',
    'priority_seat', 'pregame_pending', 'mulligan_count', 'players', 'known_cards',
    'stack', 'attackers', 'blocks', 'pending_choice', 'winner'}
_CARD_FIELDS = {'card_id', 'source_card_id', 'target_card_id', 'return_card_id',
    'top_choice_hand_id', 'top_choice_exile_id', 'attached_to'}
_REFERENCE_FIELDS = _CARD_FIELDS | {'stack_id', 'target_stack_id', 'choice_id',
                                  'replacement_source_id'}
_REFERENCE_LISTS = {'card_ids', 'target_card_ids', 'bottom_card_ids', 'search_card_ids',
    'topdeck_card_ids', 'top_choice_bottom_ids', 'escape_exile_ids', 'exile_card_ids',
    'discard_card_ids', 'sacrifice_card_ids', 'crew_card_ids', 'trigger_order',
    'attackers', 'bands', 'delve', 'improvise', 'hand', 'battlefield', 'graveyard'}
_REFERENCE_MAPS = {'attack_targets', 'blocks', 'target_distribution', 'damage_assignment'}
_RELATIVE_SEATS = {'seat', 'acting_seat', 'active_seat', 'priority_seat',
                   'target_player', 'controller', 'owner'}
_CARD_METADATA_ONLY = {'id', 'image_uri', 'image_uris', 'scryfall_id', 'oracle_id',
                       'uri', 'scryfall_uri', 'rulings_uri', 'prints_search_uri'}
_SET_FIELDS = {'types', 'keywords', 'base_keywords', 'colors', 'mana_source_colors'}
_CONTEXT_SET_FIELDS = {'incoming_attachments', 'slots'}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _preflight(value):
    # Iterators bound the walk itself; do not copy or flatten oversized input first.
    stack = [(iter((value,)), 0)]
    count = text_bytes = 0
    while stack:
        iterator, depth = stack[-1]
        try:
            item = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        count += 1
        if count > 262144 or depth > 64:
            raise ValueError('Decision node/depth budget exceeded')
        if isinstance(item, str):
            if len(item) > 65536:
                raise ValueError('Decision text limit exceeded')
            size = len(item.encode('utf-8'))
            text_bytes += size
            if size > 65536 or text_bytes > 1048576:
                raise ValueError('Decision text budget exceeded')
        elif isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError('Decision object keys must be strings')
            stack.append((itertools.chain(item.keys(), item.values()), depth + 1))
        elif isinstance(item, list):
            stack.append((iter(item), depth + 1))
        elif item is not None and type(item) is not bool:
            try:
                valid = type(item) in (int, float) and math.isfinite(item)
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError('Decision values must be finite JSON primitives')


def _validate(observation, prompts):
    _preflight({'observation': observation, 'prompts': prompts})
    if not isinstance(observation, dict) or set(observation) != _OBSERVATION_FIELDS:
        raise ValueError('Observation schema mismatch')
    seat = observation['seat']
    if (observation['version'] != 'mtg.training.v1' or type(seat) is not int or seat not in (1, 2)
            or type(observation['acting_seat']) is not int
            or observation['acting_seat'] != seat or observation['winner'] is not None):
        raise ValueError('Expected the current nonterminal actor observation')
    players = observation['players']
    if (not isinstance(players, dict) or set(players) != {'1', '2'}
            or any(not isinstance(player, dict) for player in players.values())
            or 'hand' in players[str(3-seat)]
            or any('library' in player for player in players.values())):
        raise ValueError('Private opposing hand/library is forbidden')
    known = observation['known_cards']
    if not isinstance(known, dict) or any(not isinstance(card, dict) or card.get('id') != cid
                                          for cid, card in known.items()):
        raise ValueError('Known-card identity mismatch')
    pending = observation['pending_choice']
    if pending is not None and (not isinstance(pending, dict)
            or set(pending) - {'kind', 'seat', 'prompts'}
            or 'prompts' in pending and pending['prompts'] != prompts):
        raise ValueError('Owned pending prompts must agree with the captured decision domain')
    if not isinstance(prompts, list):
        raise ValueError('Prompts must be a list')
    for prompt in prompts:
        if (not isinstance(prompt, dict) or 'hint' not in prompt
                or set(prompt) - {'hint', 'required_choices', 'encoding_supported', 'unsupported_choices'}
                or not isinstance(prompt['hint'], dict)
                or set(prompt['hint']) - _PROMPT_FIELDS):
            raise ValueError('Prompt schema mismatch; private continuations are forbidden')


def _card_facts(value):
    if isinstance(value, dict):
        return {key: _card_facts(item) for key, item in value.items()
                if key not in _CARD_METADATA_ONLY and key != 'attached_to'}
    if isinstance(value, list):
        return [_card_facts(item) for item in value]
    return value


def _validate_public_context(observation, context):
    _preflight(context)
    if (not isinstance(context, dict) or set(context) != {'version', 'seat', 'stack'}
            or context['version'] != 'mtg.public-context.v1'
            or type(context['seat']) is not int or context['seat'] != observation['seat']
            or not isinstance(context['stack'], list)):
        raise ValueError('Public context schema/actor mismatch')
    if (any(not isinstance(item, dict) or not isinstance(item.get('stack_id'), str)
            for item in context['stack'])
            or [item.get('stack_id') for item in context['stack']]
            != [item['id'] for item in observation['stack']]):
        raise ValueError('Public context must match the complete ordered public stack')
    for item in context['stack']:
        if (set(item) != {'stack_id', 'announcement_available', 'announced_targets', 'reference_lifecycle'}
                or type(item['announcement_available']) is not bool
                or item['reference_lifecycle'] != 'unknown'
                or _public_target_projection(item['announced_targets']) != item['announced_targets']
                or not item['announcement_available'] and item['announced_targets']):
            raise ValueError('Invalid public announcement context')


def _target_slots(targets):
    """Typed incidence paths contain semantic fields/positions, never opaque IDs."""
    for field, role in (('target_card_id', 'card'), ('target_stack_id', 'stack')):
        if field in targets:
            yield role, targets[field], [field], None
    for index, cid in enumerate(targets.get('target_card_ids', [])):
        yield 'card', cid, ['target_card_ids', index], None
    for cid, amount in targets.get('target_distribution', {}).items():
        if cid not in {'1', '2'}:
            yield 'card', cid, ['target_distribution'], amount
    for mode, selected in targets.get('mode_targets', {}).items():
        for field, role in (('target_card_id', 'card'), ('target_stack_id', 'stack')):
            if field in selected:
                yield role, selected[field], ['mode_targets', mode, field], None


def _public_references(observation, context):
    for player in observation['players'].values():
        for zone in ('hand', 'battlefield', 'graveyard'):
            for cid in player.get(zone, []):
                yield 'card', cid
    for item in observation['stack']:
        yield 'card', item['source_card_id']
    for card in observation['known_cards'].values():
        if card.get('attached_to') is not None:
            yield 'card', card['attached_to']
    for item in context['stack']:
        for role, cid, _, _ in _target_slots(item['announced_targets']):
            yield role, cid


def _normalize(action):
    try:
        return _action(action)
    except ActionRejected as exc:
        raise ValueError('Complete action schema mismatch') from exc


class _Bindings:
    """Private addressing only. Neither maps nor raw identifiers enter feature nodes."""

    def __init__(self, observation, prompts, public_context=None):
        self.entries = []
        self.references = {}
        self.reverse = {}
        self.costs = {}
        self.permissions = {}
        self.observation, self.prompts = observation, prompts
        self.public_context = public_context
        known = observation['known_cards']
        order = []
        for pid in ('1', '2'):
            for zone in ('hand', 'battlefield', 'graveyard'):
                order.extend(observation['players'][pid].get(zone, []))
        order.extend(item['source_card_id'] for item in observation['stack'])
        for prompt in prompts:
            hint = prompt['hint']
            if hint.get('card_id') in known:
                order.append(hint['card_id'])
            order.extend(cid for cid in hint.get('options', []) if isinstance(cid, str) and cid in known)
        order.extend(sorted(known, key=lambda cid: _canonical(_card_facts(known[cid]))))
        for cid in order:
            if cid in known:
                self._add(cid, 'card', _card_facts(known[cid]))
        if public_context is not None:
            stack_ids = {item['id'] for item in observation['stack']}
            for role, cid in _public_references(observation, public_context):
                if cid in known or cid in stack_ids:
                    if (cid in known) != (role == 'card'):
                        raise ValueError('Contradictory public reference role')
                    continue
                self._add(cid, 'public_reference', {'reference_role': role, 'visibility': 'unknown'})
        for item in observation['stack']:
            self._add(item['id'], 'stack', {key: value for key, value in item.items()
                                          if key not in {'id', 'targets'}})
        for prompt in prompts:
            hint = prompt['hint']
            source = hint.get('card_id')
            for card in hint.get('inspected_cards', []):
                if isinstance(card, dict) and card.get('id'):
                    self._add(card['id'], 'card', _card_facts(card))
            labels, types = hint.get('option_labels') or {}, hint.get('option_type_lines') or {}
            for index, option in enumerate(hint.get('options', [])):
                if isinstance(option, dict):
                    key = option.get('id')
                    facts = {k: v for k, v in option.items() if k != 'id'}
                elif isinstance(option, str):
                    key = option
                    if key in self.references:
                        continue
                    label = labels.get(key) if isinstance(labels, dict) else labels[index] if index < len(labels) else None
                    type_line = types.get(key) if isinstance(types, dict) else types[index] if index < len(types) else None
                    facts = {'choice_kind': hint.get('kind'), 'label': label, 'type_line': type_line}
                    if label is None and option in {'yes', 'no', 'pay', 'decline', 'draw', 'finish'}:
                        facts['literal'] = option
                    elif label is None:
                        raise ValueError('Offered choice lacks an authorized semantic descriptor')
                else:
                    raise ValueError('Unsupported option descriptor')
                if not key or not facts:
                    raise ValueError('Offered choice lacks a semantic descriptor')
                self._add(key, 'option', facts)
            for option in hint.get('cost_options', []):
                key = option.get('id')
                if source not in self.references or not key:
                    raise ValueError('Cost option lacks its visible source')
                alias = self._add((source, key), 'cost', {'card_id': source,
                    **{k: v for k, v in option.items() if k != 'id'}})
                self.costs[(source, key)] = alias
            permission = hint.get('graveyard_permission_key')
            if permission is not None:
                if source not in self.references:
                    raise ValueError('Permission lacks its visible source')
                self.permissions[(source, permission)] = self._add((source, permission), 'permission',
                    {'card_id': source, 'from_graveyard': hint.get('from_graveyard'),
                     'from_exile': hint.get('from_exile')})
            replacement = hint.get('replacement_source_id')
            if replacement is not None and replacement not in self.references:
                if not hint.get('replacement_name'):
                    raise ValueError('Replacement lacks a semantic descriptor')
                self._add(replacement, 'replacement', {'name': hint['replacement_name'],
                                                       'event': hint.get('event')})

    def _add(self, key, kind, facts):
        lookup = (kind, key)
        if lookup in self.reverse:
            if kind != 'card' and next(entry[3] for entry in self.entries
                                       if entry[0] == self.reverse[lookup]) != facts:
                raise ValueError('One identifier has conflicting offered descriptors')
            return self.reverse[lookup]
        if isinstance(key, str) and key in self.references:
            raise ValueError('One identifier has conflicting semantic roles')
        if len(self.entries) >= 4096:
            raise ValueError('Decision entity budget exceeded')
        alias = kind + ':' + str(len(self.entries) + 1)
        self.entries.append((alias, kind, key, facts))
        self.reverse[lookup] = alias
        if isinstance(key, str):
            self.references[key] = alias
        return alias

    def _ref(self, value, inverse=False):
        if inverse:
            matches = [entry[2] for entry in self.entries if entry[0] == value]
            if len(matches) == 1 and isinstance(matches[0], str):
                return matches[0]
        elif value in self.references:
            return self.references[value]
        raise ValueError('Unresolved actor-authorized reference')

    def _walk(self, value, key=None, *, inverse=False, source=None):
        if isinstance(value, dict):
            if value.get('type') and value.get('card_id') is not None:
                source = self._ref(value['card_id'], True) if inverse else value['card_id']
            result = {}
            for name, item in value.items():
                mapped = self._ref(name, inverse) if key in _REFERENCE_MAPS and name not in {'1', '2'} else name
                if name == 'id' and key == 'cost_choice':
                    if inverse:
                        match = [entry[2] for entry in self.entries if entry[0] == item and entry[1] == 'cost']
                        if len(match) != 1 or match[0][0] != source:
                            raise ValueError('Cost reference source mismatch')
                        item = match[0][1]
                    else:
                        item = self.costs.get((source, item))
                        if item is None:
                            raise ValueError('Cost option is not offered for this source')
                    result[mapped] = item
                else:
                    result[mapped] = self._walk(item, name if key not in _REFERENCE_MAPS else key,
                                                inverse=inverse, source=source)
            return result
        if isinstance(value, list):
            return [self._walk(item, key, inverse=inverse, source=source) for item in value]
        if isinstance(value, str):
            if key == 'graveyard_permission_key':
                if inverse:
                    matches = [entry[2] for entry in self.entries if entry[0] == value and entry[1] == 'permission']
                    if len(matches) != 1 or matches[0][0] != source:
                        raise ValueError('Permission reference source mismatch')
                    return matches[0][1]
                result = self.permissions.get((source, value))
                if result is None:
                    raise ValueError('Permission is not offered for this source')
                return result
            if value.startswith('planeswalker:'):
                return 'planeswalker:' + self._ref(value[len('planeswalker:'):], inverse)
            if value.startswith('player:') or value in {'1', '2'} and key in _REFERENCE_MAPS:
                return value
            if key in _REFERENCE_FIELDS | _REFERENCE_LISTS | _REFERENCE_MAPS:
                return self._ref(value, inverse)
            if not inverse and key != 'kind' and value in self.references:
                return self.references[value]
        return value

    def action(self, value):
        action = _normalize(value)
        return self._walk(action, source=action.get('card_id'))

    def actual_action(self, value):
        action = _normalize(value)
        source = self._ref(action['card_id'], True) if 'card_id' in action else None
        return self._walk(action, inverse=True, source=source)

    def frame(self):
        observation = self._walk(self.observation)
        observation['known_cards'] = {self._ref(cid): {**self._walk(card), 'id': self._ref(cid)}
                                      for cid, card in self.observation['known_cards'].items()}
        for card in observation['known_cards'].values():
            card.pop('image_uri', None)
        for original, item in zip(self.observation['stack'], observation['stack']):
            item['id'] = self._ref(original['id'])
        prompts = []
        for prompt in self.prompts:
            hint = prompt['hint']
            mapped = self._walk(prompt, source=hint.get('card_id'))
            if 'options' in hint:
                mapped['hint']['options'] = [self._ref(item['id'] if isinstance(item, dict) else item)
                                             for item in hint['options']]
            for field in ('option_labels', 'option_type_lines'):
                if isinstance(hint.get(field), dict):
                    mapped['hint'][field] = {self._ref(key): value for key, value in hint[field].items()}
            if 'cost_options' in hint:
                mapped['hint']['cost_options'] = [{**self._walk(option),
                    'id': self.costs[(hint['card_id'], option['id'])]} for option in hint['cost_options']]
            prompts.append(mapped)
        if observation['pending_choice'] is not None and 'prompts' in observation['pending_choice']:
            observation['pending_choice']['prompts'] = deepcopy(prompts)
        result = {'version': DECISION_VERSION, 'observation': observation, 'prompts': prompts}
        if self.public_context is not None:
            result.update(version=CONTEXT_DECISION_VERSION,
                          public_context=self._walk(self.public_context))
        return result


def build_decision_frame(observation, prompts, *, public_context=None):
    if public_context is not None:
        _preflight({'observation': observation, 'prompts': prompts, 'public_context': public_context})
    _validate(observation, prompts)
    if public_context is not None:
        _validate_public_context(observation, public_context)
    bindings = _Bindings(deepcopy(observation), deepcopy(prompts), deepcopy(public_context))
    return bindings.frame(), bindings


def validate_frame(frame):
    if not isinstance(frame, dict) or frame.get('version') not in {DECISION_VERSION, CONTEXT_DECISION_VERSION}:
        raise ValueError('Decision frame version/schema mismatch')
    expected = {'version', 'observation', 'prompts'}
    if frame['version'] == CONTEXT_DECISION_VERSION:
        expected.add('public_context')
    if set(frame) != expected:
        raise ValueError('Decision frame version/schema mismatch')
    if frame['version'] == CONTEXT_DECISION_VERSION:
        _preflight(frame)
    _validate(frame['observation'], frame['prompts'])
    if frame['version'] == CONTEXT_DECISION_VERSION:
        _validate_public_context(frame['observation'], frame['public_context'])
    if (any(not re.fullmatch(r'card:\d+', cid) for cid in frame['observation']['known_cards'])
            or any(not re.fullmatch(r'stack:\d+', item['id']) for item in frame['observation']['stack'])):
        raise ValueError('Decision records must use public encounter aliases')
    return deepcopy(frame)


def feature_contract(frame):
    validate_frame(frame)
    if frame['version'] == CONTEXT_DECISION_VERSION:
        return {'decision_version': CONTEXT_DECISION_VERSION, 'feature_version': CONTEXT_FEATURE_VERSION,
                'feature_schema_sha256': CONTEXT_FEATURE_SCHEMA_SHA256}
    return {'decision_version': DECISION_VERSION, 'feature_version': FEATURE_VERSION,
            'feature_schema_sha256': FEATURE_SCHEMA_SHA256}


class _FeatureEncoder:
    def __init__(self, frame):
        validate_frame(frame)
        self.context = frame.get('public_context')
        self.set_fields = _SET_FIELDS | (_CONTEXT_SET_FIELDS if self.context is not None else set())
        self.bindings = _Bindings(frame['observation'], frame['prompts'], self.context)
        self.indices = {}
        for index, (alias, _, identifier, _) in enumerate(self.bindings.entries):
            self.indices[alias] = index
            self.indices[identifier if isinstance(identifier, str) else identifier[1]] = index
        self.seat = frame['observation']['seat']
        self.nodes = 0
        self.base_indices = self.indices
        self.root_indices = dict(self.base_indices)
        self.context_entries = []
        if self.context is not None:
            selected = [entry for entry in self.bindings.entries
                        if entry[1] in {'card', 'stack', 'public_reference'}]
            if len(self.bindings.entries) + len(selected) > 4096:
                raise ValueError('Combined base/context entity budget exceeded')
            for entry in selected:
                alias, _, identifier, _ = entry
                index = len(self.bindings.entries) + len(self.context_entries)
                self.root_indices[alias] = self.root_indices[identifier] = index
                self.context_entries.append(self._context_record(entry))

    def _context_record(self, entry):
        _, kind, identifier, facts = entry
        role = facts['reference_role'] if kind == 'public_reference' else kind
        if role == 'stack':
            announcement = next((item for item in self.context['stack']
                                 if item['stack_id'] == identifier), None)
            visible = next((item for item in self.bindings.observation['stack']
                            if item['id'] == identifier), None)
            targets = visible.get('targets', []) if visible else []
            if any(target not in self.base_indices and target not in {'1', '2', 'player:1', 'player:2'}
                   for target in targets):
                raise ValueError('Unresolved untyped legacy target')
            return {'entity_kind': 'stack_context', 'intrinsic': identifier,
                    'announcement_available': announcement['announcement_available'] if announcement else False,
                    'announced_targets': announcement['announced_targets'] if announcement else {},
                    'legacy_targets': targets, 'reference_lifecycle': 'unknown'}
        known = self.bindings.observation['known_cards']
        incoming = []
        for item in self.context['stack']:
            slots = [{'path': path, 'quantity': quantity}
                     for target_role, cid, path, quantity in _target_slots(item['announced_targets'])
                     if target_role == 'card' and cid == identifier]
            if slots:
                incoming.append({'stack_id': item['stack_id'], 'slots': slots})
        return {'entity_kind': 'card_context', 'intrinsic': identifier,
                'attached_to': known.get(identifier, {}).get('attached_to'),
                'incoming_attachments': [cid for cid, card in known.items()
                                         if card.get('attached_to') == identifier],
                'incoming_stack_targets': incoming}

    def node(self, value, key=None, available=None):
        self.nodes += 1
        if self.nodes > 262144:
            raise ValueError('Feature node budget exceeded')
        indices = self.base_indices if available is not None else self.root_indices
        if isinstance(value, dict):
            if key == 'known_cards':
                value = {cid: {'intrinsic': cid, 'attached_to': card.get('attached_to')}
                         for cid, card in value.items()}
            pairs = []
            for name, item in value.items():
                name_node = self.node(name, 'reference_key' if name in indices else
                    'player_key' if key in {'players', 'mulligan_count'}
                        or key in _REFERENCE_MAPS and name in {'1', '2'} else None, available)
                if name == 'id' and item in indices:
                    item_node = self.node(item, 'reference', available)
                else:
                    item_node = self.node(item, name, available)
                pairs.append([name_node, item_node])
            return {'kind': 'map', 'items': sorted(pairs, key=lambda pair: _canonical(pair[0]))}
        if isinstance(value, list):
            if key == 'stack' and all(isinstance(item, dict) and 'id' in item for item in value):
                value = [{'stack_id': item['id'], 'targets': item.get('targets', [])} for item in value]
            elif key == 'inspected_cards':
                value = [{'card_id': item['id']} for item in value]
            items = [self.node(item, key, available) for item in value]
            return {'kind': 'set' if key in self.set_fields else 'list',
                    'items': sorted(items, key=_canonical) if key in self.set_fields else items}
        if value is None:
            return {'kind': 'null'}
        if type(value) is bool:
            return {'kind': 'bool', 'value': value}
        if (key in _RELATIVE_SEATS and value in (1, 2)
                or key in {'player_key', 'targets', 'legacy_targets'} and value in ('1', '2')):
            return {'kind': 'text', 'value': 'self' if int(value) == self.seat else 'opponent'}
        if isinstance(value, str):
            if value in indices:
                index = indices[value]
                if available is not None and index >= available:
                    raise ValueError('Entity references must point to an earlier semantic record')
                return {'kind': 'ref', 'index': index}
            if value.startswith('planeswalker:'):
                return self.node({'defender_type': 'planeswalker', 'card_id': value[13:]}, available=available)
            if value.startswith('player:'):
                return self.node({'target_player': int(value[7:])}, available=available)
            return {'kind': 'text', 'value': value}
        if type(value) in (int, float) and math.isfinite(value):
            return {'kind': 'number', 'value': value}
        raise ValueError('Unknown feature value')

    def pack(self, root):
        entities = [self.node({'entity_kind': kind, **facts}, available=index)
                    for index, (_, kind, _, facts) in enumerate(self.bindings.entries)]
        entities.extend(self.node(record, available=len(self.bindings.entries))
                        for record in self.context_entries)
        result = {'version': CONTEXT_FEATURE_VERSION if self.context is not None else FEATURE_VERSION,
                  'root': self.node(root), 'entities': entities}
        _preflight(result)
        return result


def encode_state(frame):
    encoder = _FeatureEncoder(frame)
    return encoder.pack({'observation': frame['observation'], 'prompts': frame['prompts']})


def encode_action(frame, complete_aliased_action):
    encoder = _FeatureEncoder(frame)
    action = _normalize(complete_aliased_action)
    # Resolve every reference before encoding; generic strings cannot hide an unknown ID.
    encoder.bindings.action(action)
    return encoder.pack(action)
