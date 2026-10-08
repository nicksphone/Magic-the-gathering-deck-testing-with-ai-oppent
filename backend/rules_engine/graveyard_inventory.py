"""Bounded positive public clause/context coverage, never absence-of-action proof."""
from dataclasses import fields
import hashlib

from game_state.state import CardInstance, MatchState, PlayerState, Zone, object_incarnation
from rules_engine.alternative_casts import escape_cost, flashback_cost
from rules_engine.events import public_trigger_clause_coverage
from rules_engine.oracle_effects import complete_stack_instruction_coverage
from rules_engine.oracle_text import without_reminder_text


_SCHEMA_PINS = {
    MatchState: '267ad792255087305d0baea0fbfa3d57d93362c03526a99c2c44ea2b37ec617e',
    CardInstance: '1b7bf44009e4e1c7bf43bd5dddae383493bca47dc3b9940fde0e93bdcbe58b6f',
    PlayerState: 'dd8f36bedf446625796592fe8045ce675eb471d167ffe68cedb2124ccae1e973',
}


def _metadata_covered(value, schema):
    # A future serialized permission field requires explicit coverage review.
    declared = fields(schema)
    if hashlib.sha256('\n'.join(f.name for f in declared).encode()).hexdigest() != _SCHEMA_PINS[schema]:
        return False
    if not isinstance(value, schema) or not {f.name for f in declared}.issubset(vars(value)):
        return False
    for field in declared:
        item = getattr(value, field.name)
        annotation = str(field.type)
        if item is None and ' | None' in annotation:
            continue
        kind = annotation.split(' | ')[0].split('[')[0]
        expected = {'list': list, 'dict': dict, 'set': set,
                    'int': int, 'bool': bool, 'str': str}.get(kind)
        if expected is not None and type(item) is not expected:
            return False
    return True


def _reviewed_context_covered(state):
    history = state.spell_color_history
    return (type(history) is dict and set(history) == {1, 2}
            and all(type(seat) is int for seat in history)
            and all(type(colors) is set and not colors for colors in history.values())
            and state.spell_color_history_known is True
            and type(state.turn_spell_protection) is set and not state.turn_spell_protection
            and type(state.turn_player_hexproof) is dict and not state.turn_player_hexproof
            and type(state.retained_counter_prohibitions) is list
            and not state.retained_counter_prohibitions)


def public_graveyard_inventory(state, actor_id):
    """Return JSON-safe structural receipts using only public source identities."""
    receipts = []

    def result(status, reason):
        return {'status': status, 'reason': reason, 'receipts': receipts}

    if not _metadata_covered(state, MatchState) or set(state.players) != {1, 2}:
        return result('unknown', 'incomplete state metadata')
    if not _reviewed_context_covered(state):
        return result('unknown', 'uncovered reviewed permission/protection context')
    if actor_id not in state.players or type(actor_id) is not int:
        return result('unknown', 'invalid actor')
    if any(not isinstance(card, CardInstance) or not isinstance(card.zone, Zone)
           for card in state.cards.values()):
        return result('unknown', 'incomplete zone metadata')
    state_fields = {f.name for f in fields(MatchState)}
    if (not state_fields.issubset(vars(state))
            or set(vars(state)) - state_fields - {'ai_information_player'}):
        return result('unknown', 'uncovered state field')
    # Each nonempty continuation is a separate source/context domain, not an
    # inactive printed ability. Do not flatten it into the current legal view.
    context_fields = (
        'stack', 'pending_mechanic_choice', 'pending_replacement_choice',
        'pending_trigger_order', 'staged_triggers', 'trigger_staging',
        'cleanup_deferred_triggers', 'delayed_triggers', 'pending_entry_counters',
        'temporary_control_changes', 'linked_exiles', 'adventure_permissions',
        'graveyard_permission_uses', 'combat_cost_effects', 'phase_plan',
        'extra_turns', 'turn_cant_gain_life', 'turn_damage_cant_be_prevented',
        'numeric_prevention_shields',
        'cleanup_pending', 'cleanup_repeat_required',
    )
    if any(getattr(state, key, None) for key in context_fields):
        return result('unknown', 'uncovered continuation/effect context')
    card_fields = {f.name for f in fields(CardInstance)}
    from rules_engine.land_types import BASIC_TYPES, effective_type_line, has_land_type
    from rules_engine.mana_abilities import tap_only_outputs
    from rules_engine.type_effects import effective_types
    from rules_engine.card_types import printed_card_types

    player_fields = {f.name for f in fields(PlayerState)}
    for pid, player in state.players.items():
        if (not _metadata_covered(player, PlayerState)
                or player.prevent_damage_shield != 0
                or set(vars(player)) != player_fields or player.id != pid
                or not all(isinstance(getattr(player, key), list)
                           for key in ('battlefield', 'graveyard', 'exile', 'hand'))):
            return result('unknown', 'uncovered player context')
    listed = [cid for player in state.players.values()
              for cid in player.battlefield + player.graveyard]
    if (not all(isinstance(cid, str) for cid in listed)
            or len(listed) != len(set(listed)) or set(listed) != {
            cid for cid, card in state.cards.items()
            if card.zone in {Zone.BATTLEFIELD, Zone.GRAVEYARD}}):
        return result('unknown', 'uncovered public zone membership')

    for pid, player in state.players.items():
        if player.exile or player.exile_play_until:
            return result('unknown', 'uncovered exile context')
        for zone in (Zone.GRAVEYARD, Zone.BATTLEFIELD):
            ids = getattr(player, zone.value)
            if len(ids) != len(set(ids)):
                return result('unknown', 'duplicate public membership')
            for cid in ids:
                card = state.cards.get(cid)
                if (not _metadata_covered(card, CardInstance) or not isinstance(card.zone, Zone)
                        or card.id != cid or card.zone != zone or card.owner not in state.players
                        or zone == Zone.GRAVEYARD and card.owner != pid
                        or zone == Zone.BATTLEFIELD and card.controller != pid
                        or not card_fields.issubset(vars(card))
                        or set(vars(card)) - card_fields):
                    return result('unknown', 'uncovered source identity')
                if (not isinstance(card.name, str) or not card.name
                        or not isinstance(card.mana_cost, str)
                        or not isinstance(card.oracle_text, str)
                        or not isinstance(card.type_line, str) or not card.type_line
                        or not isinstance(card.types, list)
                        or not all(isinstance(t, str) for t in card.types)
                        or not isinstance(card.keywords, list)
                        or not all(isinstance(k, str) for k in card.keywords)
                        or not isinstance(card.granted_flashback, dict)
                        or not isinstance(card.card_faces, list) or card.card_faces
                        or card.selected_face_index is not None
                        or card.layout != 'normal' or card.is_token
                        or card.printed_characteristics or card.bestow_characteristics
                        or card.type_effects or card.type_effect_base is not None
                        or card.keyword_effects or card.base_stat_effects
                        or card.was_kicked is not False
                        or card.kicker_count is not None and (
                            type(card.kicker_count) is not int or card.kicker_count != 0)
                        or card.granted_flashback or card.foretell_record or card.suspend_haste
                        or card.attached_to or card.chosen_creature_type or card.counters):
                    return result('unknown', 'uncovered source modification/metadata')
                reference = {'id': cid, 'owner': card.owner, 'controller': card.controller,
                             'zone': zone.value, 'incarnation': object_incarnation(card),
                             'zone_change_sequence': card.zone_change_sequence}
                body = without_reminder_text(card.oracle_text).strip()
                types = set(effective_types(state, card))
                if types != set(printed_card_types(card.type_line)):
                    return result('unknown', 'uncovered characteristic mismatch')
                if zone == Zone.GRAVEYARD:
                    if flashback_cost(card) or escape_cost(card):
                        return result('interactive', 'printed graveyard cast permission')
                    covered = complete_stack_instruction_coverage(card)
                    if (types not in ({'Instant'}, {'Sorcery'}) or card.keywords
                            or covered is None):
                        return result('unknown', 'uncovered graveyard clause')
                    receipts.append({'reference': reference, 'coverage': covered})
                    continue
                if ('Land' in types and 'Creature' not in types and not body and not card.keywords
                        and effective_type_line(state, card)
                        and any(has_land_type(state, card, t) for t in BASIC_TYPES)
                        and tap_only_outputs(state, card, ignore_readiness=True)):
                    receipts.append({'reference': reference, 'coverage': 'intrinsic_land_mana'})
                    continue
                if 'Creature' not in types or not body:
                    return result('unknown', 'uncovered battlefield source')
                clauses = [line.strip() for line in body.splitlines() if line.strip()]
                keywords = {line.lower() for line in clauses if line.lower() in {'flash', 'deathtouch'}}
                if set(k.lower() for k in card.keywords) != keywords:
                    return result('unknown', 'uncovered keyword domain')
                for clause in clauses:
                    if clause.lower() in keywords:
                        receipts.append({'reference': reference, 'coverage': {'keyword': clause.lower()}})
                        continue
                    covered = public_trigger_clause_coverage(card, clause)
                    if covered is None:
                        return result('unknown', 'uncovered battlefield clause')
                    receipts.append({'reference': reference, 'coverage': covered})
    return result('inert', 'complete bounded public source/context coverage')
