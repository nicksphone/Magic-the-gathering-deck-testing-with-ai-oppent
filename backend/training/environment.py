"""Deterministic, in-memory consumer boundary around the authoritative engine."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from ai.information import decision_view, is_unknown
from api_contracts import Action
from card_data.fallback_cards import fallback_card_payload
from decks.builtin_decks import BUILTIN_DECKS
from game_state.serializers import (
    deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot,
)
from game_state.state import MatchFactory, pregame_actor
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine


VERSION = 'mtg.training.v1'
ACTION_PREFIX = 'mtg.action.v1:'
_ACTION = TypeAdapter(Action)
_INPUT_ERRORS = (ValidationError, ValueError, TypeError, KeyError, IndexError, AttributeError)
# Prompts are intentionally a partial surface, never engine continuation payloads.
_PROMPT_FIELDS = frozenset({
    'type', 'card_id', 'card_name', 'ability_index', 'ability_label', 'mana_cost',
    'from_exile', 'from_library', 'from_graveyard', 'selected_face_index',
    'entry_choice', 'graveyard_permission_key', 'return_card_id', 'x_value',
    'kind', 'options', 'count', 'min_count', 'label', 'option_labels',
    'option_type_lines', 'defenders', 'attackers', 'blockers', 'legal_blocks',
    'targets', 'target_hints', 'cost_options', 'outputs', 'stack_id',
    'target_card_id', 'target_player', 'trigger_order', 'replacement_source_id',
    'accept', 'cost_text', 'payment_options', 'activation_costs', 'hybrid_symbols',
    'ability_x_cost', 'output_bundles', 'output_options', 'base_output_bundles',
    'inspected_cards', 'bottom_any_order', 'bottom_random', 'trigger_labels',
    'replacement_name', 'event', 'ward_cost', 'mode_target_text',
})
_SIMPLE = frozenset({
    'pass_priority', 'keep_hand', 'mulligan', 'play_land', 'foretell',
    'choose_replacement', 'choose_trigger_order', 'choose_trigger_target',
    'choose_optional_effect',
})


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return sha256(_json(value).encode('utf-8')).hexdigest()


def _action(value):
    if not isinstance(value, dict):
        raise ActionRejected('Action must be an object')
    try:
        return _ACTION.validate_python(value).model_dump(exclude_none=True)
    except _INPUT_ERRORS as exc:
        raise ActionRejected(str(exc)) from exc


def encode_action(action):
    """Reversible canonical JSON, including ordered variable-length selections."""
    return ACTION_PREFIX + _json(_action(action))


def decode_action(identifier):
    if not isinstance(identifier, str) or not identifier.startswith(ACTION_PREFIX):
        raise ActionRejected('Unknown action encoding version')
    try:
        action = _action(json.loads(identifier[len(ACTION_PREFIX):]))
    except _INPUT_ERRORS as exc:
        raise ActionRejected(str(exc)) from exc
    if encode_action(action) != identifier:
        raise ActionRejected('Action ID must use canonical encoding')
    return action


def _engine_hash():
    root = Path(__file__).resolve().parents[1]
    files = [root / 'api_contracts.py', root / 'decks/builtin_decks.py']
    for directory in ('rules_engine', 'effects', 'game_state', 'ai', 'card_data', 'training'):
        files.extend(path for path in (root / directory).rglob('*')
                     if path.suffix in {'.py', '.json'})
    digest = sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(root)).encode('ascii') + b'\0')
        digest.update(path.read_bytes() + b'\0')
    return digest.hexdigest()


def _deck(name):
    if name not in BUILTIN_DECKS:
        raise ValueError('Use an existing built-in deck name; custom metadata is not accepted')
    rows = []
    for line in BUILTIN_DECKS[name].strip().splitlines():
        quantity, card_name = line.strip().split(' ', 1)
        metadata = fallback_card_payload(card_name)
        if not metadata or not metadata.get('scryfall_id') or not metadata.get('type_line'):
            raise ValueError(f'No canonical offline metadata for {card_name}')
        rows.append({**deepcopy(metadata), 'card_name': card_name, 'quantity': int(quantity)})
    return rows


def _seat(seat):
    if type(seat) is not int or seat not in (1, 2):
        raise ActionRejected('Seat must be integer 1 or 2')


def _unsupported_mana_choices(cost_text):
    """Describe choices the current immediate mana contract cannot carry."""
    from rules_engine.costs import parse_activated_cost
    from rules_engine.mana import hybrid_payment_symbols
    cost = parse_activated_cost(cost_text)
    result = []
    if cost.discard_cards:
        result.append('payment_choices.discard_card_ids')
    if cost.sacrifice_creatures and not cost.sacrifice_source:
        result.append('payment_choices.sacrifice_card_ids')
    if hybrid_payment_symbols(cost.mana_cost):
        result.append('hybrid_choices')
    if '{X}' in cost.mana_cost.upper():
        result.append('targets.x_value')
    return result


class TrainingEnvironment:
    """Single-process adapter. Snapshots/provenance are private evaluator data."""

    def __init__(self):
        self._rules = RulesEngine()
        self._state = None
        self._provenance = None
        self._steps = 0

    def _ready(self):
        if self._state is None:
            raise ValueError('Call reset or restore first')

    def reset(self, deck_a='Mono Red Aggro', deck_b='Blue Control', *, seed):
        if type(seed) is not int:
            raise ValueError('An explicit integer seed is required')
        decks = [_deck(deck_a), _deck(deck_b)]
        provenance = {
            'version': VERSION, 'action_version': ACTION_PREFIX,
            'seed': seed, 'deck_names': [deck_a, deck_b],
            'deck_hashes': [_digest(rows) for rows in decks],
            'engine_hash': _engine_hash(),
            'metadata_source': 'card_data/builtin_oracle_seed.json',
        }
        state = MatchFactory.from_decks(*decks, seed=seed)
        state.id = _digest(provenance)
        # Policies, not engine defaults, must resolve supported private choices.
        state.mechanic_choice_players = {1, 2}
        state.replacement_choice_required = True
        state.replacement_choice_players = {1, 2}
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {1, 2}
        self._state, self._provenance, self._steps = state, provenance, 0
        return self.observe(self.acting_seat)

    @property
    def acting_seat(self):
        self._ready()
        state = self._state
        if state.winner is not None:
            return None
        if state.pending_mechanic_choice:
            return state.pending_mechanic_choice['player_id']
        if state.pending_trigger_order:
            return int(state.pending_trigger_order['current_controller'])
        if state.pending_replacement_choice:
            return state.pending_replacement_choice['player_id']
        return pregame_actor(state) if state.pregame_pending else state.priority_player

    @property
    def terminated(self):
        self._ready()
        return self._state.winner is not None

    @property
    def rewards(self):
        self._ready()
        winner = self._state.winner
        return {seat: (0 if winner not in (1, 2) else 1 if seat == winner else -1)
                for seat in (1, 2)}

    def _view(self, seat):
        self._ready()
        _seat(seat)
        state = deepcopy(self._state)
        moves = self._rules.legal_moves(state, seat) if seat == self.acting_seat else []
        from rules_engine.costs import activated_cost_candidates, parse_activated_cost
        from rules_engine.mana import hybrid_payment_symbols
        for move in moves:
            if move['type'] == 'activate_mana_ability':
                if 'activation_costs' not in move or 'hybrid_symbols' not in move:
                    cost = parse_activated_cost(move['cost_text'])
                    if 'activation_costs' not in move:
                        move['activation_costs'] = activated_cost_candidates(state, seat, move['card_id'], cost)
                    if 'hybrid_symbols' not in move:
                        move['hybrid_symbols'] = hybrid_payment_symbols(cost.mana_cost)
        return decision_view(state, seat, moves)

    def prompts(self, seat=None):
        """Partial legal source/choice descriptions, NOT a finite action space."""
        seat = self.acting_seat if seat is None else seat
        if seat is None:
            return []
        _, moves = self._view(seat)
        return self._prompts(moves)

    @staticmethod
    def _prompts(moves):
        """Allowlisted decision descriptions; never expose continuation packets."""
        result = []
        for move in moves:
            if move['type'].endswith('_restricted'):
                continue
            hint = {key: deepcopy(value) for key, value in move.items() if key in _PROMPT_FIELDS}
            choices = {
                'cast_spell': ['cost_choice.id', 'targets (including modes/X if applicable)',
                               'hybrid/resource/additional payments if applicable'],
                'choose_mechanic': ['exactly one of card_ids, choice_id, damage_assignment'],
                'attack': ['attackers', 'attack_targets', 'hybrid_choices if applicable'],
                'block': ['blocks', 'hybrid_choices if applicable'],
                'activate_mana_ability': ['color'],
                'activate_ability': ['targets and payment_choices if applicable'],
                'activate_loyalty': ['targets including X if applicable'],
                'crew': ['crew_card_ids'], 'equip': ['target_card_id'],
            }.get(move['type'], [] if move['type'] in _SIMPLE else ['Complete action contract'])
            if move['type'] == 'choose_mechanic':
                field = ('damage_assignment' if move['kind'] == 'combat_damage' else
                         'choice_id' if move['kind'] in {'draw', 'land_entry', 'saga_entry'} else 'card_ids')
                choices = [field + ' (explicit selection; preserve order; count/range from hint)']
            elif move['type'] == 'choose_trigger_order':
                choices = ['trigger_order (complete permutation, bottom-to-top stack order)']
            elif move['type'] == 'choose_trigger_target':
                choices = ['stack_id', 'exactly one of target_card_id or target_player']
            elif move['type'] == 'choose_replacement':
                choices = ['replacement_source_id']
            elif move['type'] == 'choose_optional_effect':
                choices = ['stack_id', 'accept (explicit boolean)']
            prompt = {'hint': hint, 'required_choices': choices}
            if move['type'] == 'activate_mana_ability':
                missing = _unsupported_mana_choices(move.get('cost_text', ''))
                unsupported = [field for field in missing if field == 'targets.x_value']
                prompt['encoding_supported'] = not unsupported
                prompt['unsupported_choices'] = unsupported
                choices.extend(missing)
                if len(move.get('base_output_bundles', [])) > 1:
                    choices.append('output_bundle if color matches multiple offered base vectors')
            result.append(prompt)
        return result

    def observe(self, seat):
        """JSON allowlist over decision_view, with no private snapshot fields."""
        view, moves = self._view(seat)
        players = {}
        known = {}
        for pid, player in view.players.items():
            players[str(pid)] = {
                'life': player.life, 'poison': player.poison, 'counters': dict(player.counters),
                'hand_count': len(player.hand), 'library_count': len(player.library),
                'mana_pool': dict(player.mana_pool),
                'battlefield': list(player.battlefield), 'graveyard': list(player.graveyard),
                'exile_count': len(player.exile),
            }
            if pid == seat:
                players[str(pid)]['hand'] = list(player.hand)
        for cid, card in view.cards.items():
            if not is_unknown(card):
                known[cid] = {**serialize_card_view(view, cid), 'zone': card.zone.value}
        # Inspected nonselectable cards are also authorized by the actor's engine
        # prompt (e.g. Officer misses). Never consult an opponent's legal moves.
        for move in moves:
            for card in move.get('inspected_cards', []):
                cid = card['id']
                if cid not in known:
                    known[cid] = {**deepcopy(card), 'zone': view.cards[cid].zone.value}
        # Only allowlisted owned decision prompts cross; continuations stay private.
        pending = (view.pending_mechanic_choice or view.pending_trigger_order
                   or view.pending_replacement_choice)
        return json.loads(_json({
            'version': VERSION, 'seat': seat, 'acting_seat': self.acting_seat,
            'turn': view.turn, 'step': view.step.value, 'active_seat': view.active_player,
            'priority_seat': view.priority_player, 'pregame_pending': view.pregame_pending,
            'mulligan_count': {str(pid): count for pid, count in view.mulligan_count.items()},
            'players': players, 'known_cards': known,
            'stack': [{'id': item.id, 'source_card_id': item.source_card_id,
                       'controller': item.controller, 'label': item.label,
                       'targets': list(item.targets)} for item in view.stack],
            'attackers': list(view.attackers), 'blocks': deepcopy(view.blocks),
            'pending_choice': {'kind': pending.get('kind', pending.get('phase', 'replacement')),
                               'seat': self.acting_seat,
                               'prompts': self._prompts(moves)} if pending and seat == self.acting_seat else
                              {'kind': pending.get('kind', pending.get('phase', 'replacement')),
                               'seat': self.acting_seat} if pending else None,
            'winner': view.winner,
        }))

    def _checked(self, action, seat):
        self._ready()
        _seat(seat)
        if seat != self.acting_seat:
            raise ActionRejected('Not the acting seat, or episode is terminal')
        action = decode_action(action) if isinstance(action, str) else _action(action)
        try:
            self._require_choices(action, seat)
            return action, checked_action(self._state, self._rules, seat, action)
        except _INPUT_ERRORS as exc:
            raise ActionRejected(str(exc)) from exc

    def _require_choices(self, action, seat):
        """Close known legacy defaults, while leaving execution to checked_action."""
        from rules_engine.action_validation import require
        kind = action['type']
        if kind == 'tap_nonland_for_mana':
            from rules_engine.mana_abilities import mana_ability_views
            state = deepcopy(self._state)
            card = state.cards.get(action['card_id'])
            require(card is not None and card.id in state.players[seat].battlefield
                    and card.controller == seat, 'Mana source must be a permanent you control')
            views = mana_ability_views(state, card)
            matching = [view for view in views if action['color'] in view['outputs'] and (
                view['outputs'][action['color']] > 0
                or sum(view.get('output_bundles', {}).get(action['color'], {}).values()) > 0)]
            require(len(matching) <= 1,
                    'Missing required choice: ability_index; use activate_mana_ability')
            for view in matching:
                require(not _unsupported_mana_choices(view['cost_text']),
                        'Unsupported required choices: immediate mana resource/hybrid/X payments')
        if kind == 'choose_mechanic':
            pending = self._state.pending_mechanic_choice
            require(bool(pending), 'No pending mechanic choice')
            field = ('damage_assignment' if pending['kind'] == 'combat_damage' else
                     'choice_id' if pending['kind'] in {'draw', 'land_entry', 'saga_entry'} else 'card_ids')
            require(action.get(field) is not None, 'Missing required choice: ' + field)
        if kind in {'tap_land_for_mana', 'tap_lands_bulk'}:
            require(action.get('color') is not None, 'Missing required choice: color')
        if kind == 'attack':
            require(set(action.get('attack_targets', {})) == set(action['attackers']),
                    'Missing required choice: attack_targets for each attacker')
        if kind in {'activate_ability', 'activate_loyalty', 'activate_mana_ability'}:
            from rules_engine.costs import parse_activated_cost
            state = deepcopy(self._state)
            matching = [move for move in self._rules.legal_moves(state, seat)
                        if move['type'] == kind and move.get('card_id') == action['card_id']
                        and move.get('ability_index') == action['ability_index']]
            require(bool(matching), 'Ability is not in current engine hints')
            move = matching[0]
            if kind == 'activate_ability':
                from rules_engine.mana_abilities import mana_ability_specs
                require(not any(spec[0] == action['ability_index']
                                for spec in mana_ability_specs(state.cards[action['card_id']], state)),
                        'Immediate mana abilities require activate_mana_ability; '
                        'the generic stack route is not a payment encoding workaround')
            cost = parse_activated_cost(move.get('cost_text', move.get('mana_cost', '')))
            require(not move.get('ability_x_cost') or action.get('targets', {}).get('x_value') is not None,
                    'Missing required choice: targets.x_value')
            if kind == 'activate_mana_ability':
                require('{X}' not in cost.mana_cost.upper(),
                        'Unsupported required choice: variable mana production')
                options = [option for option in move.get('output_options', [])
                           if option['color'] == action['color']]
                require(len(options) <= 1 or action.get('output_bundle') is not None,
                        'Missing required choice: output_bundle')
            payments = action.get('payment_choices') or {}
            require(not cost.discard_cards or payments.get('discard_card_ids') is not None,
                    'Missing required choice: payment_choices.discard_card_ids')
            require(not cost.sacrifice_creatures or cost.sacrifice_source
                    or payments.get('sacrifice_card_ids') is not None,
                    'Missing required choice: payment_choices.sacrifice_card_ids')
            require(not move.get('hybrid_symbols') or action.get('hybrid_choices') is not None,
                    'Missing required choice: hybrid_choices')
        if kind != 'cast_spell':
            return
        choice = action.get('cost_choice') or {}
        require(bool(choice.get('id')), 'Missing required choice: cost_choice.id')
        state = deepcopy(self._state)
        moves = self._rules.legal_moves(state, seat)
        options = [option for move in moves if move['type'] == kind
                   and move.get('card_id') == action['card_id']
                   for option in move.get('cost_options', []) if option['id'] == choice['id']]
        require(bool(options), 'Casting cost choice is not in current engine hints')
        option = options[0]
        require(not ('{X}' in option.get('mana_cost', '').upper() or option.get('pay_life_x')
                     or option.get('discard_x')) or action.get('targets', {}).get('x_value') is not None,
                'Missing required choice: targets.x_value')
        require(not option.get('hybrid_symbols') or action.get('hybrid_choices') is not None,
                'Missing required choice: hybrid_choices')
        require(not option.get('resource_payment_candidates') or action.get('resource_payment') is not None,
                'Missing required choice: resource_payment')
        require(not (option.get('discard_cards') or option.get('discard_x'))
                or choice.get('discard_card_ids') is not None,
                'Missing required choice: cost_choice.discard_card_ids')
        require(not option.get('sacrifice_creatures') or choice.get('sacrifice_card_ids') is not None,
                'Missing required choice: cost_choice.sacrifice_card_ids')
        require(not option.get('exile_graveyard') or action.get('escape_exile_ids') is not None,
                'Missing required choice: escape_exile_ids')
        card = state.cards[action['card_id']]
        require(card.layout not in {'modal_dfc', 'adventure', 'split'}
                or action.get('selected_face_index', action.get('targets', {}).get('selected_face_index')) is not None,
                'Missing required choice: selected_face_index')

    def lookup(self, action, seat=None):
        """Validate a complete proposal by trial execution on an engine copy."""
        seat = self.acting_seat if seat is None else seat
        action, _ = self._checked(action, seat)
        return {'id': encode_action(action), 'action': deepcopy(action)}

    def action_mask(self, actions, seat=None):
        """Mask only the consumer's finite proposals; never claim exhaustive moves."""
        mask = []
        for action in actions:
            try:
                self.lookup(action, seat)
                mask.append(True)
            except ActionRejected:
                mask.append(False)
        return mask

    def lookup_intent(self, intent, seat=None):
        """Consumer move-display intents use the shared contract, never infer choices.

        Encoded actions and lookup/step remain strict. This explicit convenience
        boundary strips presentation fields using the parent-owned model map.
        """
        from ai.action_contract import complete_action
        from api_contracts import (
            ManaAbilityAction, TapAction, NonlandManaAction, BulkTapAction, CastAction, AbilityAction,
            EquipAction, CrewAction, CycleAction, MechanicChoice, OptionalEffectChoice, TriggerChoice,
            ReplacementChoice, TriggerTargetChoice, AttackAction, BlockAction, ForetellAction,
        )
        models = {'activate_mana_ability': ManaAbilityAction, 'tap_land_for_mana': TapAction,
                  'tap_nonland_for_mana': NonlandManaAction, 'tap_lands_bulk': BulkTapAction,
                  'cast_spell': CastAction, 'activate_ability': AbilityAction,
                  'activate_loyalty': AbilityAction, 'equip': EquipAction,
                  'crew': CrewAction, 'cycle_card': CycleAction,
                  'choose_mechanic': MechanicChoice, 'choose_optional_effect': OptionalEffectChoice,
                  'choose_trigger_order': TriggerChoice,
                  'choose_replacement': ReplacementChoice, 'choose_trigger_target': TriggerTargetChoice,
                  'attack': AttackAction, 'block': BlockAction, 'foretell': ForetellAction}
        if isinstance(intent, dict) and isinstance(intent.get('type'), str) and intent['type'] in models:
            display = {'card_name', 'mana_cost', 'cost_options', 'target_hints', 'outputs',
                       'cost_text', 'ability_label', 'label', 'payment_options',
                       'activation_costs', 'hybrid_symbols', 'ability_x_cost', 'output_bundles',
                       'output_options', 'base_output_bundles', 'required_choices'}
            contract = 'Mana'
            if intent['type'] == 'cast_spell':
                display = {'card_name', 'mana_cost', 'cost_options', 'target_hints'}
                contract = 'Cast'
            elif intent['type'] == 'foretell':
                display = {'card_name', 'mana_cost', 'fixed_costs', 'granted_reductions', 'card_view'}
                contract = 'Foretell'
                try:
                    ForetellAction.model_validate({key: value for key, value in intent.items()
                                                   if key not in display})
                    supplied = display & set(intent)
                    if supplied:
                        actor = self.acting_seat if seat is None else seat
                        candidate = deepcopy(self._state)
                        view = next((move for move in self._rules.legal_moves(candidate, actor)
                                     if move['type'] == 'foretell'
                                     and move['card_id'] == intent['card_id']), None)
                        if view is not None and 'card_view' in supplied:
                            view['card_view'] = serialize_card_view(candidate, intent['card_id'])
                        if view is None or any(key not in view or _json(intent[key]) != _json(view[key])
                                               for key in supplied):
                            raise ActionRejected('Foretell metadata does not match current public view')
                except _INPUT_ERRORS as exc:
                    raise ActionRejected('Invalid foretell intent') from exc
            elif intent['type'] == 'activate_ability':
                display = {'card_name', 'mana_cost', 'ability_label', 'payment_options',
                           'activation_costs', 'hybrid_symbols', 'target_hints'}
                contract = 'Activated ability'
            elif intent['type'] == 'activate_loyalty':
                display = {'card_name', 'ability_label', 'ability_delta', 'activation_costs',
                           'ability_x_cost', 'ability_x_sign', 'target_hints'}
                contract = 'Loyalty ability'
            elif intent['type'] == 'equip':
                display = {'card_name', 'mana_cost', 'targets'}
                contract = 'Equip'
                # The offered candidates are display, not a chosen Targets object.
                if 'targets' in intent:
                    candidates = intent['targets']
                    if not (isinstance(candidates, list) and candidates and all(
                            isinstance(candidate, dict) and set(candidate) == {'id', 'name'}
                            and all(isinstance(candidate[key], str) and candidate[key]
                                    for key in ('id', 'name')) for candidate in candidates)):
                        raise ActionRejected('Equip targets must be a display candidate list')
            elif intent['type'] == 'crew':
                display = {'card_name', 'crew_value', 'suggested_crew_card_ids',
                           'activation_costs', 'crew_candidates'}
                contract = 'Crew'
            elif intent['type'] == 'cycle_card':
                display = {'card_name', 'mana_cost', 'activation_costs', 'cycling_variant'}
                contract = 'Cycling'
            elif intent['type'] == 'choose_mechanic':
                display = {'kind', 'options', 'count', 'min_count', 'label',
                           'option_labels', 'option_type_lines', 'inspected_cards',
                           'inspected_card_ids', 'effect_payload', 'top_reference',
                           'top_ids', 'bottom_any_order', 'bottom_random'}
                contract = 'Mechanic choice'
                # Whole engine views carry continuations, not authoritative input.
                context = {'player_id', 'effect_controller', 'followup_effect', 'resolving_item'}
                pending = self._state.pending_mechanic_choice or {}
                actor = self.acting_seat if seat is None else seat
                _seat(actor)
                if pending.get('player_id') != actor:
                    raise ActionRejected('Mechanic view context does not match pending actor')
                moves = self._rules.legal_moves(deepcopy(self._state), actor)
                offered = next((move for move in moves if move['type'] == 'choose_mechanic'), {})
                for key in (display | context) & set(intent):
                    try:
                        authoritative = pending if key in context else offered
                        matches = (key in authoritative
                                   and _json(intent[key]) == _json(authoritative[key]))
                    except _INPUT_ERRORS as exc:
                        raise ActionRejected('Invalid mechanic view context') from exc
                    if not matches:
                        raise ActionRejected('Mechanic view context does not match pending state')
                display |= context
            elif intent['type'] == 'choose_optional_effect':
                display = set()
                contract = 'Optional effect choice'
            elif intent['type'] == 'choose_trigger_order':
                display = {'trigger_labels', 'event'}
                contract = 'Trigger order'
                if 'trigger_labels' in intent:
                    labels = intent['trigger_labels']
                    if not (isinstance(labels, list) and labels
                            and all(isinstance(label, str) and label for label in labels)):
                        raise ActionRejected('Trigger labels must be a display string list')
                if 'event' in intent and not (isinstance(intent['event'], str) and intent['event']):
                    raise ActionRejected('Trigger event must be a display string')
            elif intent['type'] == 'choose_replacement':
                display = {'event', 'replacement_name'}
                contract = 'Replacement choice'
                for key in display & set(intent):
                    if not (isinstance(intent[key], str) and intent[key]):
                        raise ActionRejected('Replacement metadata must be a display string')
            elif intent['type'] == 'choose_trigger_target':
                display = {'target_name'}
                contract = 'Trigger target choice'
                if 'target_name' in intent and not (isinstance(intent['target_name'], str)
                                                   and intent['target_name']):
                    raise ActionRejected('Trigger target name must be a display string')
            elif intent['type'] in {'attack', 'block'}:
                display = ({'options', 'defenders', 'banding_attackers', 'attack_taxes',
                            'attack_costs', 'declaration_limits'} if intent['type'] == 'attack' else
                           {'attackers', 'blockers', 'legal_blocks', 'blocker_capacities',
                            'target_requirements', 'block_taxes', 'block_costs', 'declaration_limits'})
                contract = 'Combat declaration'
                # Display is a current public view, never an authoritative choice.
                supplied = display & set(intent)
                if supplied:
                    try:
                        actor = self.acting_seat if seat is None else seat
                        view = next((move for move in self._rules.legal_moves(deepcopy(self._state), actor)
                                     if move['type'] == intent['type']), None)
                        matches = view is not None and all(
                            key in view and _json(intent[key]) == _json(view[key]) for key in supplied)
                    except _INPUT_ERRORS as exc:
                        raise ActionRejected('Invalid combat display metadata') from exc
                    if not matches:
                        raise ActionRejected('Combat display metadata does not match current public view')
            if set(intent) - set(models[intent['type']].model_fields) - display - {'_invalid_ai_choice'}:
                raise ActionRejected(contract + ' contract cannot carry requested fields')
            if intent['type'] == 'choose_mechanic':
                # Check the public chosen-parameter model before any completion helper.
                try:
                    action = MechanicChoice.model_validate({key: value for key, value in intent.items()
                                                           if key in MechanicChoice.model_fields})
                except _INPUT_ERRORS as exc:
                    raise ActionRejected('Malformed mechanic choice parameters') from exc
                intent = {**action.model_dump(exclude_none=True),
                          **({'_invalid_ai_choice': intent['_invalid_ai_choice']}
                             if '_invalid_ai_choice' in intent else {})}
        return self.lookup(complete_action(intent), seat)

    def simple_actions(self):
        """Convenience subset; no target, payment, attack or choice guesses."""
        result = {}
        for prompt in self.prompts():
            hint = prompt['hint']
            if hint['type'] not in _SIMPLE:
                continue
            # Descriptions are not action input, even for the simple subset.
            fields = {'type', 'card_id', 'from_exile', 'from_graveyard',
                      'graveyard_permission_key', 'selected_face_index', 'entry_choice',
                      'replacement_source_id', 'trigger_order', 'stack_id',
                      'target_card_id', 'target_player', 'accept'}
            proposal = {key: value for key, value in hint.items() if key in fields}
            try:
                item = self.lookup(proposal)
                result[item['id']] = item
            except ActionRejected:
                continue
        return [result[key] for key in sorted(result)]

    def step(self, action, seat=None):
        seat = self.acting_seat if seat is None else seat
        action, candidate = self._checked(action, seat)
        # Construct the response before committing, including read-side helpers.
        staged = TrainingEnvironment()
        staged._state, staged._provenance = candidate, self._provenance
        staged._steps = self._steps + 1
        observer = staged.acting_seat or seat
        result = {'observation': staged.observe(observer), 'rewards': staged.rewards,
                  'terminated': staged.terminated, 'acting_seat': staged.acting_seat,
                  'action_id': encode_action(action), 'steps': staged._steps}
        self._state, self._steps = candidate, staged._steps
        return result

    def snapshot(self):
        """Private JSON resume envelope, never a policy observation."""
        self._ready()
        state = json.loads(_json(serialize_match_snapshot(self._state)))
        return {'version': VERSION, 'provenance': deepcopy(self._provenance),
                'steps': self._steps, 'state': state, 'state_hash': _digest(state)}

    def restore(self, snapshot):
        """Trusted local snapshots only. Validate fully before replacing state."""
        if not isinstance(snapshot, dict) or not {'version', 'provenance', 'steps', 'state', 'state_hash'} <= snapshot.keys():
            raise ValueError('Incomplete training snapshot envelope')
        data = deepcopy(snapshot)
        if data['version'] != VERSION or data['provenance']['version'] != VERSION:
            raise ValueError('Unsupported training snapshot version')
        if data['provenance']['engine_hash'] != _engine_hash():
            raise ValueError('Snapshot engine/adapter/metadata differs from this checkout')
        if data['state_hash'] != _digest(data['state']):
            raise ValueError('Snapshot state digest mismatch')
        if type(data['steps']) is not int or data['steps'] < 0:
            raise ValueError('Invalid episode step count')
        expected = [_digest(_deck(name)) for name in data['provenance']['deck_names']]
        actual = [_digest(data['state']['starting_decks'][str(pid)]) for pid in (1, 2)]
        if expected != actual or actual != data['provenance']['deck_hashes']:
            raise ValueError('Snapshot deck provenance mismatch')
        if (len(expected) != 2 or type(data['provenance']['seed']) is not int
                or data['provenance']['action_version'] != ACTION_PREFIX
                or data['state']['id'] != _digest(data['provenance'])):
            raise ValueError('Snapshot episode provenance mismatch')
        candidate = deserialize_match_snapshot(data['state'])
        if json.loads(_json(serialize_match_snapshot(candidate))) != data['state']:
            raise ValueError('Snapshot does not round-trip on this engine')
        staged = TrainingEnvironment()
        staged._state, staged._provenance, staged._steps = candidate, data['provenance'], data['steps']
        observation = staged.observe(staged.acting_seat or 1)
        self._state, self._provenance, self._steps = candidate, data['provenance'], data['steps']
        return observation
