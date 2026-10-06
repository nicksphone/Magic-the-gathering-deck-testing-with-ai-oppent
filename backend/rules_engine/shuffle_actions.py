"""Explicit library shuffle actions, not a wrapper around randomization."""
from dataclasses import dataclass, field
import re

from game_state.state import StackItem, Zone, object_incarnation


_STATIC_CAUSE_SEAL = object()


@dataclass(frozen=True)
class StaticReplacementCause:
    source_card_id: str
    controller: int
    source_owner: int
    source_zone: Zone
    incarnation: int
    zone_change_sequence: int
    ability_clause: str
    ability_index: int
    _seal: object = field(repr=False, compare=False)
    _proof: tuple = field(repr=False)


def _receipt_fields(cause):
    return (cause.source_card_id, cause.controller, cause.source_owner,
            cause.source_zone, cause.incarnation, cause.zone_change_sequence,
            cause.ability_clause, cause.ability_index)


def prepare_static_replacement_cause(state, plan):
    """Validate the real plan before any departure, reveal or zone-list change."""
    from rules_engine.replacement import GraveyardEntryPlan, graveyard_entry_plans

    if (type(plan) is not GraveyardEntryPlan or plan.reveal_shuffle is not True
            or plan.destination != Zone.LIBRARY
            or plan.replacement_source_id != plan.card_id
            or plan.card_id not in state.cards
            or plan not in graveyard_entry_plans(state, plan.card_id)):
        raise ValueError('Unavailable printed shuffle replacement plan')
    source = state.cards[plan.card_id]
    if (type(plan.controller) is not int or plan.controller not in state.players
            or type(plan.owner) is not int or plan.owner not in state.players
            or type(plan.source_incarnation) is not int or plan.source_incarnation < 0
            or type(plan.source_sequence) is not int or plan.source_sequence < 0
            or plan.source_incarnation != object_incarnation(source)
            or plan.source_sequence != source.zone_change_sequence):
        raise ValueError('Invalid pre-transition replacement source')
    reference = rf'(?:{re.escape(source.name)}|this card|this creature|this permanent)'
    pattern = re.compile(
        rf'if {reference} would be put into a graveyard from anywhere, '
        rf'reveal {reference} and shuffle (?:it|{reference}) into its owner\'s library instead\.', re.I)
    for index, clause in enumerate((source.oracle_text or '').splitlines()):
        if pattern.fullmatch(clause.strip()):
            values = (source.id, plan.controller, plan.owner, plan.origin,
                      plan.source_incarnation, plan.source_sequence, clause, index)
            return StaticReplacementCause(*values, _STATIC_CAUSE_SEAL, values)
    raise ValueError('Missing complete printed shuffle replacement clause')


def is_static_replacement_event_cause(cause):
    """Recognize only the complete internal static-cause vocabulary."""
    keys = {'kind', 'mechanism', 'source_card_id', 'controller', 'source_owner',
            'source_zone', 'source_reference', 'ability_key', 'ability_clause', 'ability_index'}
    if not isinstance(cause, dict) or set(cause) != keys:
        return False
    ref = cause['source_reference']
    return (cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
            and isinstance(cause['source_card_id'], str) and bool(cause['source_card_id'])
            and type(cause['controller']) is int and type(cause['source_owner']) is int
            and isinstance(cause['source_zone'], str)
            and cause['source_zone'] in {zone.value for zone in Zone}
            and isinstance(ref, dict) and set(ref) == {'incarnation', 'zone_change_sequence'}
            and all(type(value) is int and value >= 0 for value in ref.values())
            and cause['ability_key'] == 'printed_graveyard_reveal_shuffle'
            and isinstance(cause['ability_clause'], str) and bool(cause['ability_clause'].strip())
            and type(cause['ability_index']) is int and cause['ability_index'] >= 0)


def _static_cause_after_commit(state, player_id, cause):
    if (type(cause) is not StaticReplacementCause or cause._seal is not _STATIC_CAUSE_SEAL
            or cause._proof != _receipt_fields(cause)):
        raise ValueError('Shuffle requires a prepared internal replacement receipt')
    source = state.cards.get(cause.source_card_id)
    expected_sequence = cause.zone_change_sequence + (cause.source_zone != Zone.LIBRARY)
    if (source is None or player_id != cause.source_owner
            or source.owner != cause.source_owner or source.controller != cause.controller
            or source.zone != Zone.LIBRARY
            or object_incarnation(source) != cause.incarnation
            or source.zone_change_sequence != expected_sequence
            or state.players[player_id].library.count(source.id) != 1):
        raise ValueError('Replacement receipt does not match committed library transition')
    for pid, player in state.players.items():
        for zone in Zone:
            ids = getattr(player, zone.value, [])
            if (pid, zone) != (player_id, Zone.LIBRARY) and source.id in ids:
                raise ValueError('Replacement source has duplicate zone membership')
    return {'kind': 'static', 'mechanism': 'replacement',
            'source_card_id': cause.source_card_id, 'controller': cause.controller,
            'source_owner': cause.source_owner, 'source_zone': cause.source_zone.value,
            'source_reference': {'incarnation': cause.incarnation,
                                 'zone_change_sequence': cause.zone_change_sequence},
            'ability_key': 'printed_graveyard_reveal_shuffle',
            'ability_clause': cause.ability_clause, 'ability_index': cause.ability_index}


def shuffle_library(state, player_id, *, resolving_item=None, cause=None):
    from rules_engine.events import emit_event
    from rules_engine.targeting import stack_object_kind

    if type(player_id) is not int or player_id not in state.players:
        raise ValueError('Unknown shuffling player')
    if cause is not None and resolving_item is not None:
        raise ValueError('Announce only one shuffle cause')
    if cause is not None:
        cause = _static_cause_after_commit(state, player_id, cause)
    if resolving_item is not None:
        item = StackItem(**resolving_item)
        source = state.cards.get(item.source_card_id)
        if source is None or type(item.controller) is not int or item.controller not in state.players:
            raise ValueError('Shuffle requires a retained resolving source and controller')
        cause = {
            'stack_id': item.id, 'source_card_id': item.source_card_id,
            'controller': item.controller, 'kind': stack_object_kind(state, item),
            'source_reference': {'incarnation': object_incarnation(source),
                                 'zone_change_sequence': source.zone_change_sequence},
        }
    state.rng.shuffle(state.players[player_id].library)
    state.log.append(f'{state.players[player_id].name} shuffles their library.')
    emit_event(state, 'shuffle', {'player_id': player_id, 'cause': cause})
