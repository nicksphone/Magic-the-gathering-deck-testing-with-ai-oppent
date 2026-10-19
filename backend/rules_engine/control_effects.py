"""Pure layer-two control ordering and explicit mutation-boundary projection."""
from functools import lru_cache
from copy import deepcopy
import re

from game_state.state import Zone, object_incarnation, allocate_effect_timestamp


@lru_cache(maxsize=512)
def compile_attached_control(text):
    lines = [line.strip().lower() for line in (text or '').splitlines() if line.strip()]
    if len(lines) != 2:
        return False
    enchant = re.fullmatch(r'enchant (permanent|creature|artifact|land|enchantment|planeswalker)\.?', lines[0])
    return bool(enchant and lines[1] == f'you control enchanted {enchant[1]}.')


def validate_control_effects(card, players):
    base, effects = card.control_effect_base, card.control_effects
    if type(effects) is not list:
        raise ValueError('Invalid control effect list')
    if base is None:
        if effects:
            raise ValueError('Control effects require an explicit underlying controller')
        return
    if type(base) is not int or base not in players or type(effects) is not list:
        raise ValueError('Invalid control baseline or effect list')
    if card.zone != Zone.BATTLEFIELD:
        raise ValueError('Control metadata belongs to a battlefield incarnation')
    stamps = set()
    for effect in effects:
        if type(effect) is not dict or set(effect) not in (
                {'controller', 'timestamp', 'incarnation', 'sequence'},
                {'controller', 'timestamp', 'incarnation', 'sequence', 'expires_turn'}):
            raise ValueError('Invalid control effect structure')
        if any(type(value) is not int for value in effect.values()):
            raise ValueError('Control effect values must be integers, not booleans')
        if (effect['controller'] not in players or effect['timestamp'] <= 0
                or effect['timestamp'] in stamps
                or effect['incarnation'] != object_incarnation(card)
                or effect['sequence'] != card.zone_change_sequence
                or effect.get('expires_turn', 0) < 0):
            raise ValueError('Invalid or stale control effect reference')
        stamps.add(effect['timestamp'])


def restore_control_effects(raw, card, players):
    if ('control_effect_base' in raw) != ('control_effects' in raw):
        raise ValueError('Both internal control fields are required together')
    card.control_effect_base = raw.get('control_effect_base')
    card.control_effects = deepcopy(raw.get('control_effects', []))
    validate_control_effects(card, players)


def validate_temporary_control_snapshot(records, cards, players):
    """Unscoped old caches cannot safely resume gameplay without a real ledger."""
    if type(records) is not dict:
        raise ValueError('Invalid temporary control cache')
    for cid, record in records.items():
        if (type(cid) is not str or type(record) is not dict
                or set(record) != {'controller', 'expires_turn'}
                or any(type(value) is not int for value in record.values())
                or record['controller'] not in players or record['expires_turn'] < 0):
            raise ValueError('Invalid temporary control record')
        card = cards.get(cid)
        if card is None:
            raise ValueError('Temporary control target is absent')
        validate_control_effects(card, players)
        if card.control_effect_base is None or not any(
                effect.get('expires_turn') == record['expires_turn']
                for effect in card.control_effects):
            raise ValueError('Legacy temporary control lacks a retained duration ledger')


def control_layer_view(state):
    """No state mutation and no later-layer ability/type queries."""
    validate_temporary_control_snapshot(state.temporary_control_changes, state.cards, state.players)
    cards = {cid: card for cid, card in state.cards.items() if card.zone == Zone.BATTLEFIELD}
    controllers = {}
    effects = []
    for cid, card in cards.items():
        validate_control_effects(card, state.players)
        controllers[cid] = card.controller if card.control_effect_base is None else card.control_effect_base
        for index, effect in enumerate(card.control_effects):
            if effect.get('expires_turn', state.turn) >= state.turn:
                effects.append((effect['timestamp'], cid, index, None, effect['controller']))
        target = card.attached_to
        if target in cards and compile_attached_control(card.oracle_text):
            legacy = state.temporary_control_changes.get(target)
            if legacy and cards[target].control_effect_base is None:
                raise ValueError('Legacy temporary control has no timestamp for an Aura contest')
            stamp = int(card.effect_timestamp or card.static_order)
            effects.append((stamp, target, -1, cid, None))
    while effects:
        # Only an actual change creates a dependency; reevaluate after each effect.
        dependencies = {effect: {other for other in effects
            if effect != other and effect[3] is not None and other[1] == effect[3]
            and (controllers[other[3]] if other[3] is not None else other[4])
                != controllers[effect[3]]}
            for effect in effects}
        # CR 613.8b ignores dependencies within a loop, not external prerequisites.
        loop_edges = set()
        for effect, prerequisites in dependencies.items():
            for prerequisite in prerequisites:
                pending, seen = [prerequisite], set()
                while pending:
                    candidate = pending.pop()
                    if candidate == effect:
                        loop_edges.add((effect, prerequisite))
                        break
                    if candidate not in seen:
                        seen.add(candidate)
                        pending.extend(dependencies[candidate])
        loop_first = {}
        for effect in effects:
            pending, peers = [effect], set()
            while pending:
                candidate = pending.pop()
                if candidate not in peers:
                    peers.add(candidate)
                    pending.extend(other for other in dependencies[candidate]
                                   if (candidate, other) in loop_edges)
            loop_first[effect] = min(peers, key=lambda item: (item[0], item[1], item[2]))
        ready = [effect for effect in effects if loop_first[effect] == effect and not any(
            other in effects and (effect, other) not in loop_edges
            for other in dependencies[effect])]
        effect = min(ready, key=lambda item: (item[0], item[1], item[2]))
        effects.remove(effect)
        _, target, _, aura, controller = effect
        controllers[target] = controllers[aura] if aura is not None else controller
    return controllers


def transfer_controller(state, card, controller):
    """One real transfer, preserving owner/object identity/control records."""
    previous = card.controller
    if previous == controller:
        return
    if controller not in state.players or previous not in state.players:
        raise ValueError('Unknown controller')
    old = state.players[previous].battlefield
    if card.id in old:
        old.remove(card.id)
    if card.id not in state.players[controller].battlefield:
        state.players[controller].battlefield.append(card.id)
    card.controller = controller
    card.summoning_sick = True
    card.entered_turn = state.turn
    state.log.append(f'{state.players[controller].name} gains control of {card.name}.')
    from rules_engine.events import emit_event
    emit_event(state, 'control_changed', {'card_id': card.id,
        'previous_controller': previous, 'controller': controller})


def reconcile_control(state):
    controllers = control_layer_view(state)
    for cid, controller in controllers.items():
        card = state.cards[cid]
        if controller != card.controller:
            if card.control_effect_base is None:
                card.control_effect_base = card.controller
            transfer_controller(state, card, controller)


def record_control_effect(state, card, controller, *, temporary=False):
    if type(controller) is not int or controller not in state.players or card.zone != Zone.BATTLEFIELD:
        raise ValueError('Invalid control recipient or battlefield target')
    validate_control_effects(card, state.players)
    control_layer_view(state)
    if card.control_effect_base is None:
        if card.id in state.temporary_control_changes:
            raise ValueError('Legacy temporary control has no retained timestamp')
        card.control_effect_base = card.controller
    validate_control_effects(card, state.players)
    effect = {'controller': controller, 'timestamp': allocate_effect_timestamp(state),
              'incarnation': object_incarnation(card), 'sequence': card.zone_change_sequence}
    if temporary:
        effect['expires_turn'] = state.turn
        previous = state.temporary_control_changes.get(card.id, {})
        state.temporary_control_changes[card.id] = {
            'controller': previous.get('controller', card.controller), 'expires_turn': state.turn}
    else:
        state.temporary_control_changes.pop(card.id, None)
    card.control_effects.append(effect)
    reconcile_control(state)


def expire_control_effects(state):
    validate_temporary_control_snapshot(state.temporary_control_changes, state.cards, state.players)
    for card in state.cards.values():
        validate_control_effects(card, state.players)
    for card in state.cards.values():
        card.control_effects = [effect for effect in card.control_effects
                               if effect.get('expires_turn', state.turn + 1) > state.turn]
    for cid, record in list(state.temporary_control_changes.items()):
        if record['expires_turn'] > state.turn:
            continue
        card = state.cards.get(cid)
        if card is not None and card.zone == Zone.BATTLEFIELD and card.control_effect_base is None:
            transfer_controller(state, card, record['controller'])
        state.temporary_control_changes.pop(cid, None)
    reconcile_control(state)


def clear_control_effects(card):
    card.control_effect_base = None
    card.control_effects.clear()
