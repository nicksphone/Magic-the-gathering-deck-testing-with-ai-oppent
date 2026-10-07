from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace
from game_state.state import NumericPreventionShield, Zone, object_incarnation, allocate_effect_timestamp
from rules_engine.action_validation import ActionRejected


PLAYER_SHIELD_KEY = "prevent_damage_shield"
CARD_SHIELD_KEY = "__prevent_damage_shield"


def _reference_valid(ref, *, target=False):
    keys = {'incarnation', 'zone_change_sequence'} | ({'card_id'} if target else set())
    return (isinstance(ref, dict) and set(ref) == keys
            and all(type(ref[k]) is int and ref[k] >= 0 for k in ('incarnation', 'zone_change_sequence'))
            and (not target or isinstance(ref['card_id'], str) and bool(ref['card_id'])))


def has_numeric_prevention_instruction(key, payload):
    return key == 'prevent_damage' or key == 'effect_sequence' and any(
        isinstance(effect, dict) and has_numeric_prevention_instruction(
            effect.get('effect_key'), effect.get('payload') or {}) for effect in payload.get('effects', []))


def validate_prevention_source(payload):
    ref = payload.get('__prevention_source_reference', payload.get(
        '__activation_source_reference', payload.get('__trigger_source_reference')))
    if not _reference_valid(ref):
        raise ActionRejected('Malformed retained numeric prevention source reference')
    return dict(ref)


def validate_prevention_item(state, item):
    validate_prevention_source(item.payload or {})
    if (type(item.controller) is not int or item.controller not in state.players
            or any(not isinstance(getattr(item, key), str) or not getattr(item, key)
                   for key in ('id', 'source_card_id', 'label'))
            or (item.payload or {}).get('__stack_copy_kind') not in (None, 'spell', 'activated', 'triggered')
            or any(r.resolving_stack_id == item.id for r in state.numeric_prevention_shields)):
        raise ActionRejected('Malformed numeric prevention resolving identity')

    def instruction(key, payload):
        if key == 'prevent_damage':
            if type(payload.get('amount')) is not int or payload['amount'] <= 0:
                raise ActionRejected('Invalid numeric prevention amount')
        elif key == 'effect_sequence':
            for effect in payload.get('effects', []):
                instruction(effect.get('effect_key'), effect.get('payload') or {})
    instruction(item.effect_key, item.payload or {})


def _matches(state, receipt, target_card_id=None, target_player=None):
    if receipt.created_turn != state.turn or receipt.remaining <= 0:
        return False
    if target_player is not None:
        return receipt.target_player == target_player
    ref = receipt.target_reference
    card = state.cards.get(target_card_id)
    return (ref is not None and card is not None and card.zone == Zone.BATTLEFIELD
            and ref['card_id'] == target_card_id and ref['incarnation'] == object_incarnation(card)
            and ref['zone_change_sequence'] == card.zone_change_sequence)


def _balance(state, target_card_id=None, target_player=None):
    total = (getattr(state.players[target_player], PLAYER_SHIELD_KEY) if target_player is not None
             else state.cards[target_card_id].counters.get(CARD_SHIELD_KEY, 0))
    known = sum(r.remaining for r in state.numeric_prevention_shields
                if _matches(state, r, target_card_id, target_player))
    if type(total) is not int or total < known or total < 0:
        raise ActionRejected('Inconsistent numeric prevention balance')
    return total, known


def numeric_prevention_options(state, *, target_card_id=None, target_player=None, amount=None):
    if amount is not None and amount <= 0:
        return []
    _balance(state, target_card_id, target_player)
    return [(SimpleNamespace(id='numeric-prevention:' + r.receipt_id,
                             name=r.source_label + ' prevention', controller=r.source_controller,
                             effect_timestamp=r.effect_timestamp, static_order=r.effect_timestamp),
             'numeric-prevention') for r in state.numeric_prevention_shields
            if _matches(state, r, target_card_id, target_player)]


def check_legacy_prevention_boundary(state, candidates, *, target_card_id=None, target_player=None):
    total, known = _balance(state, target_card_id, target_player)
    if total > known and candidates:
        raise ActionRejected('Legacy numeric prevention provenance cannot be ordered')


def validate_legacy_damage_boundary(state, item):
    """Check the bounded damage instruction before its stack/event mutation."""
    key, payload = item.effect_key, item.payload or {}
    if key == 'conditional_instruction':
        from rules_engine.conditional_instructions import selected_instruction
        key, payload = selected_instruction(state, item.controller, payload)
    recipients = []
    if key == 'deal_damage':
        recipients = [payload]
    elif key == 'damage_each_creature':
        from rules_engine.type_effects import effective_types
        # Only inspect legacy balances; the wrapper still owns packet construction.
        recipients = [{'target_card_id': cid, 'amount': payload.get('amount')}
                      for player in state.players.values() for cid in player.battlefield
                      if state.cards[cid].counters.get(CARD_SHIELD_KEY, 0)
                      and 'Creature' in effective_types(state, state.cards[cid])]
    from rules_engine.replacement import replacement_options
    for recipient in recipients:
        cid, pid = recipient.get('target_card_id'), recipient.get('target_player')
        if pid not in state.players and cid not in state.cards:
            continue
        total, known = _balance(state, cid, pid)
        if total > known:
            replacement_options(state, 'damage_to_player' if pid is not None else 'damage_to_permanent',
                target_player=pid, target_card_id=cid, source_card_id=item.source_card_id,
                source_lki=payload.get('__source_lki'), amount=recipient.get('amount'))


def consume_numeric_prevention_shield(state, source_id, amount, *, target_card_id=None, target_player=None):
    receipt = next((r for r in state.numeric_prevention_shields
                    if 'numeric-prevention:' + r.receipt_id == source_id
                    and _matches(state, r, target_card_id, target_player)), None)
    if receipt is None or amount <= 0:
        raise ActionRejected('Numeric prevention shield is no longer applicable')
    _balance(state, target_card_id, target_player)
    prevented = min(receipt.remaining, amount)
    receipt.remaining -= prevented
    if target_player is not None:
        state.players[target_player].prevent_damage_shield -= prevented
    else:
        card = state.cards[target_card_id]
        card.counters[CARD_SHIELD_KEY] -= prevented
        if not card.counters[CARD_SHIELD_KEY]:
            card.counters.pop(CARD_SHIELD_KEY)
    return amount - prevented, prevented


def create_numeric_prevention_shield(state, controller, payload):
    frame = payload.get('__resolving_item')
    if not isinstance(frame, dict) or frame.get('controller') != controller:
        raise ActionRejected('Missing actual numeric prevention resolving frame')
    if any(not isinstance(frame.get(k), str) or not frame[k]
           for k in ('id', 'source_card_id', 'label')) or type(controller) is not int or controller not in state.players:
        raise ActionRejected('Malformed numeric prevention resolving frame')
    source_ref = validate_prevention_source(frame.get('payload') or {})
    amount = payload.get('amount')
    target_player = payload.get('target_player')
    target_id = payload.get('target_card_id')
    if type(amount) is not int or amount <= 0 or (target_player is None) == (target_id is None):
        raise ActionRejected('Invalid numeric prevention instruction')
    if any(r.resolving_stack_id == frame['id'] for r in state.numeric_prevention_shields):
        raise ActionRejected('Duplicate numeric prevention application')
    target_ref = None
    if target_player is not None:
        if type(target_player) is not int or target_player not in state.players:
            raise ActionRejected('Invalid numeric prevention player')
    else:
        card = state.cards.get(target_id)
        if card is None or card.zone != Zone.BATTLEFIELD:
            raise ActionRejected('Invalid numeric prevention permanent')
        target_ref = {'card_id': target_id, 'incarnation': object_incarnation(card),
                      'zone_change_sequence': card.zone_change_sequence}
        if not _reference_valid(target_ref, target=True):
            raise ActionRejected('Invalid numeric prevention target reference')
    _balance(state, target_id, target_player)
    receipt = NumericPreventionShield(1, state.allocate_object_id(), frame['id'], frame['source_card_id'],
        controller, frame['label'], source_ref, target_player, target_ref, amount, state.turn,
        True, allocate_effect_timestamp(state))
    state.numeric_prevention_shields.append(receipt)
    if target_player is not None:
        add_player_prevention_shield(state, target_player, amount)
    else:
        add_card_prevention_shield(state.cards[target_id], amount)
    return receipt


def restore_numeric_prevention_shields(snapshot):
    rows = snapshot.get('numeric_prevention_shields', [])
    if not isinstance(rows, list):
        raise ActionRejected('Malformed numeric prevention receipts')
    receipts, ids, frames, sums = [], set(), set(), {}
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(NumericPreventionShield)}:
            raise ActionRejected('Malformed numeric prevention receipt shape')
        if (type(raw['version']) is not int or raw['version'] != 1
                or any(not isinstance(raw[k], str) or not raw[k] for k in
                       ('receipt_id', 'resolving_stack_id', 'source_card_id', 'source_label'))
                or raw['receipt_id'] in ids
                or raw['resolving_stack_id'] in frames
                or type(raw['source_controller']) is not int or str(raw['source_controller']) not in snapshot['players']
                or any(type(raw[k]) is not int or raw[k] < 0 for k in
                       ('remaining', 'created_turn', 'effect_timestamp'))
                or raw['expires_at_cleanup'] is not True or not _reference_valid(raw['source_reference'])):
            raise ActionRejected('Malformed numeric prevention receipt values')
        player, ref = raw['target_player'], raw['target_reference']
        if (player is None) == (ref is None) or (player is not None and (
                type(player) is not int or str(player) not in snapshot['players'])) or (
                ref is not None and not _reference_valid(ref, target=True)):
            raise ActionRejected('Malformed numeric prevention recipient')
        from copy import deepcopy
        receipt = NumericPreventionShield(**deepcopy(raw))
        receipts.append(receipt)
        ids.add(receipt.receipt_id)
        frames.add(receipt.resolving_stack_id)
        active = receipt.created_turn == snapshot.get('turn', 1)
        if player is not None:
            key = ('player', player)
            total = snapshot['players'][str(player)].get(PLAYER_SHIELD_KEY, 0)
        else:
            card = snapshot['cards'].get(ref['card_id'])
            active = active and card is not None and card.get('zone') == 'battlefield' and (
                ref['zone_change_sequence'] == card.get('zone_change_sequence', 0)
                and ref['incarnation'] == (card.get('battlefield_incarnation')
                    if card.get('battlefield_incarnation') is not None else
                    card.get('effect_timestamp', 0) or card.get('static_order', 0)))
            key = ('card', ref['card_id'])
            total = (card or {}).get('counters', {}).get(CARD_SHIELD_KEY, 0)
        if active:
            sums[key] = sums.get(key, 0) + receipt.remaining
            if type(total) is not int or total < sums[key]:
                raise ActionRejected('Inconsistent numeric prevention snapshot balance')
    return receipts


def add_player_prevention_shield(state, player_id: int, amount: int) -> None:
    if amount <= 0:
        return
    player = state.players[player_id]
    current = int(getattr(player, PLAYER_SHIELD_KEY, 0))
    setattr(player, PLAYER_SHIELD_KEY, current + int(amount))


def add_card_prevention_shield(card, amount: int) -> None:
    if amount <= 0:
        return
    card.counters[CARD_SHIELD_KEY] = int(card.counters.get(CARD_SHIELD_KEY, 0)) + int(amount)


def consume_player_prevention_shield(state, player_id: int, amount: int) -> tuple[int, int]:
    if amount <= 0:
        return 0, 0
    player = state.players[player_id]
    total, known = _balance(state, target_player=player_id)
    shield = total - known
    prevented = min(shield, int(amount))
    setattr(player, PLAYER_SHIELD_KEY, total - prevented)
    return int(amount) - prevented, prevented


def consume_card_prevention_shield(card, amount: int, *, state=None) -> tuple[int, int]:
    if amount <= 0:
        return 0, 0
    total, known = _balance(state, target_card_id=card.id) if state is not None else (int(card.counters.get(CARD_SHIELD_KEY, 0)), 0)
    shield = total - known
    prevented = min(shield, int(amount))
    card.counters[CARD_SHIELD_KEY] = total - prevented
    if int(card.counters.get(CARD_SHIELD_KEY, 0)) == 0:
        card.counters.pop(CARD_SHIELD_KEY, None)
    return int(amount) - prevented, prevented
