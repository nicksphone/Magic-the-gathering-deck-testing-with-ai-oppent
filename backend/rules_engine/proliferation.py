"""Non-targeting proliferation with atomic, resumable multi-kind placement."""
from copy import deepcopy

from game_state.state import Zone, object_incarnation
from rules_engine.counter_placement import put_counters
from rules_engine.counter_replacements import counter_effect_amounts
from rules_engine.events import emit_event, emit_event_batch, flush_staged_triggers


def counter_kinds(recipient, *, player=False):
    if player:
        from rules_engine.player_counters import public_counters
        return [kind for kind in public_counters(recipient) if not kind.startswith('__')]
    kinds = {kind for kind, amount in recipient.counters.items()
             if not kind.startswith('__') and int(amount) > 0}
    if int(recipient.loyalty or 0) > 0:
        kinds.add('loyalty')
    if 'Saga' in recipient.type_line and recipient.counters.get('__lore', 0) > 0:
        kinds.add('lore')
    return sorted(kinds)


def recipients(state):
    out = {}
    for pid in (state.active_player, 3-state.active_player):
        player = state.players[pid]
        kinds = counter_kinds(player, player=True)
        if kinds:
            out[f'player:{pid}'] = {'target_player': pid, 'affected_player': pid,
                                   'counter_amounts': dict.fromkeys(kinds, 1)}
        for cid in player.battlefield:
            card = state.cards[cid]
            kinds = counter_kinds(card)
            if kinds and card.zone == Zone.BATTLEFIELD:
                out[f'card:{cid}'] = {'target_card_id': cid, 'affected_player': pid,
                                    'incarnation': object_incarnation(card),
                                    'zone_sequence': card.zone_change_sequence,
                                    'counter_amounts': dict.fromkeys(kinds, 1)}
    return out


def _same_recipient(state, packet):
    cid = packet.get('target_card_id')
    if cid is None:
        return packet.get('target_player') in state.players
    card = state.cards.get(cid)
    return (card is not None and card.zone == Zone.BATTLEFIELD
            and object_incarnation(card) == packet['incarnation']
            and card.zone_change_sequence == packet['zone_sequence'])


def proliferate(state, controller, payload):
    data = deepcopy(payload)
    if 'packets' not in data:
        available = recipients(state)
        if 'recipients' not in data and available and controller in state.mechanic_choice_players:
            labels = {}
            for option, packet in available.items():
                target = state.players[packet['target_player']] if 'target_player' in packet else state.cards[packet['target_card_id']]
                labels[option] = f"{target.name}: {', '.join(packet['counter_amounts'])}"
            state.pending_mechanic_choice = {
                'kind': 'proliferate', 'player_id': controller, 'controller': controller,
                'options': list(available), 'option_labels': labels,
                'count': len(available), 'min_count': 0, 'effect_payload': data,
                'label': 'Proliferate: choose any number, including none. Each gets every existing counter kind.',
            }
            state.priority_player = controller
            state.passed_priority = set()
            return
        selected = data.get('recipients')
        if selected is None:
            from ai.proliferation_policy import preferred_recipients
            selected = preferred_recipients(state, controller, available)
        # Replacement decisions use APNAP order, not checkbox click order.
        data['packets'] = [packet for option, packet in available.items() if option in selected]
        data['packet_index'] = 0
        data['prepared'] = []
    while data['packet_index'] < len(data['packets']):
        packet = data['packets'][data['packet_index']]
        if not _same_recipient(state, packet):
            state.log.append('Proliferation recipient changed zones; no counters placed on the new object.')
            data['packet_index'] += 1
            for key in ('counter_amounts', 'target_player', 'target_card_id', '__counter_used', '__counter_choice'):
                data.pop(key, None)
            continue
        event = {**data, **packet}
        if 'counter_amounts' in data:
            event['counter_amounts'] = data['counter_amounts']
        amounts = counter_effect_amounts(state, controller, 'proliferate', event)
        if amounts is None:
            return
        data['prepared'].append({**packet, 'counter_amounts': amounts})
        data['packet_index'] += 1
        for key in ('counter_amounts', 'target_player', 'target_card_id', '__counter_used', '__counter_choice'):
            data.pop(key, None)
    staged_here = not state.trigger_staging
    if staged_here:
        state.trigger_staging = True
        state.trigger_staging_event = 'proliferated'
    lore_events, player_events, permanent_events = [], [], []
    for packet in data['prepared']:
        pid, cid = packet.get('target_player'), packet.get('target_card_id')
        if cid is not None:
            card = state.cards.get(cid)
            if not _same_recipient(state, packet):
                state.log.append('Proliferation recipient changed zones; no counters placed on the new object.')
                continue
            old_lore = int(card.counters.get('__lore', 0))
        actual = {}
        for kind, amount in packet['counter_amounts'].items():
            placed = put_counters(state, kind, amount, target_player=pid, target_card_id=cid,
                                  placement_checked=True, emit_events=False)
            if placed:
                actual[kind] = placed
                if pid is not None:
                    player_events.append({'player_id': pid, 'controller': controller,
                                          'counter': kind, 'amount': placed})
        if cid is not None and actual:
            permanent_events.append({'card_id': cid, 'controller': controller, 'counters': actual})
            if 'lore' in actual and 'Saga' in card.type_line:
                lore_events.append({'card_id': cid, 'old_lore': old_lore, 'new_lore': card.counters['__lore']})
    # Trigger conditions must see all placements, not an intermediate board.
    emit_event_batch(state, 'saga_lore_added', lore_events)
    emit_event_batch(state, 'player_counters_added', player_events)
    emit_event_batch(state, 'permanent_counters_added', permanent_events)
    emit_event(state, 'proliferated', {'controller': controller, 'source_card_id': data.get('__source_card_id')})
    state.log.append(f'{state.players[controller].name} proliferates.')
    if staged_here:
        flush_staged_triggers(state)
