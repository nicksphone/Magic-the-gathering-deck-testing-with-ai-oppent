"""Paid canonical Channel/reentry episodes; no injected events or stack frames."""

from copy import deepcopy

from dataclasses import asdict

import hashlib

import json

import os

from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot

from game_state.state import Step, Zone, object_incarnation, assign_static_order_on_battlefield_entry

from rules_engine.action_validation import checked_action, ActionRejected

from rules_engine.engine import RulesEngine

from rules_engine.oracle_effects import extract_activated_abilities

from rules_engine.targeting import stack_object_kind

from tests.test_linked_damage_targets import raw_card

from tests.test_soulscar_preflight_rules_audit import position

RAW = Path(__file__).resolve().parents[2] / 'hand-source-causal/raw'

for line in (RAW / 'SHA256SUMS').read_text().splitlines():
    digest, filename = line.split()
    assert hashlib.sha256((RAW / filename).read_bytes()).hexdigest() == digest

ROWS = {row['name']: row for row in
        (json.loads(path.read_text()) for path in RAW.glob('*.json') if path.name != 'intake.json')}

RULES = RulesEngine()

def record(label, state, **details):
    directory = os.environ.get('MTG_HAND_SOURCE_EVIDENCE')
    if directory:
        with (Path(directory) / 'episodes.jsonl').open('a') as stream:
            stream.write(json.dumps({'case': os.environ.get('PYTEST_CURRENT_TEST'),
                'label': label, 'snapshot': serialize_match_snapshot(state), **details},
                sort_keys=True) + '\n')

def reload_exact(state):
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(before)))
    assert serialize_match_snapshot(restored) == before
    return restored

def act(state, actor, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RULES, actor, action)
    assert serialize_match_snapshot(state) == before
    record('checked-action', result, actor=actor, action=action)
    return result

def priority(state, actor):
    if state.priority_player != actor:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == actor
    return state

def add(state, name, actor, zone=Zone.BATTLEFIELD):
    card = raw_card(state, ROWS[name], actor, zone)
    if zone == Zone.BATTLEFIELD:
        # Declared retained-board fixture, never an actual freshly cast creature.
        card.summoning_sick = False
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id

def setup(seat, family, whip=False, suppress_entry=True):
    state = position(seat if family == 'sniper' else 3-seat)
    for player in state.players.values():
        player.mana_pool = {color: 24 for color in 'WUBRGC'}
    state.mechanic_choice_players = {1, 2}
    add(state, 'Leyline of Anticipation', seat)
    if family == 'sniper' and suppress_entry:
        add(state, 'Humility', seat)
    if whip:
        # Real retained-source timestamps: the lifelink grant is later than Humility.
        add(state, 'Whip of Erebos', seat)
    source = add(state, 'Twinshot Sniper' if family == 'sniper' else 'Eiganjo, Seat of the Empire', seat, Zone.HAND)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    spells = {name: add(state, name, seat, Zone.HAND) for name in
              ['Zombify', 'Regrowth', 'Growth Spiral', 'Boomerang', 'Unsummon']}
    spells['Ray of Command'] = add(state, 'Ray of Command', 3-seat, Zone.HAND)
    if family == 'land':
        # Actual combat declaration supplies the attacking target requirement.
        state.step = Step.DECLARE_ATTACKERS
        state.attackers_declared = False
        state = act(state, 3-seat, {'type': 'attack', 'attackers': [target]})
        assert target in state.attackers
    return state, source, target, spells

def announce(state, source, target, seat):
    state = priority(state, seat)
    ability = next(a for a in extract_activated_abilities(state.cards[source])
                   if a['activation_zone'] == 'hand')
    before = deepcopy(state.cards[source])
    targets = ({'target_player': 3-seat} if state.cards[source].name == 'Twinshot Sniper'
               else {'target_card_id': target})
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source,
                            'ability_index': ability['index'],
                            'targets': targets})
    item = next(i for i in state.stack if i.source_card_id == source)
    ref = {'incarnation': object_incarnation(before), 'zone_change_sequence': before.zone_change_sequence}
    assert item.payload['__activation_source_reference'] == ref
    assert '__source_lki' not in item.payload
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert item.controller == seat and stack_object_kind(state, item) == 'activated'
    record('original-real-hand-frame', state, frame=asdict(item))
    return state, item.id, ref

def cast(state, cid, actor, targets):
    state = priority(state, actor)
    pool = deepcopy(state.players[actor].mana_pool)
    state = act(state, actor, {'type': 'cast_spell', 'card_id': cid,
                             'cost_choice': {'id': 'base'}, 'targets': targets})
    assert state.cards[cid].zone == Zone.STACK
    assert state.players[actor].mana_pool != pool
    return state, next(i.id for i in state.stack if i.source_card_id == cid)

def until(state, predicate):
    for _ in range(48):
        if predicate(state):
            return state
        assert not state.pending_replacement_choice, 'Upstream replacement continuation needs explicit actor selection'
        assert not state.pending_trigger_order, 'Upstream APNAP choice needs explicit actor selection'
        assert not state.pending_mechanic_choice, state.pending_mechanic_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('48 genuine priority actions did not reach the requested boundary')

def resolve_response(state, frame, original):
    state = until(state, lambda s: all(i.id != frame for i in s.stack))
    # Resolve actual entry triggers above the original Channel, not the Channel itself.
    return until(state, lambda s: s.stack and s.stack[-1].id == original)

def reenter(state, seat, family, source, original, spells):
    if family == 'sniper':
        state, frame = cast(state, spells['Zombify'], seat, {'target_card_id': source})
        state = resolve_response(state, frame, original)
    else:
        state, frame = cast(state, spells['Regrowth'], seat, {'target_card_id': source})
        state = resolve_response(state, frame, original)
        assert state.cards[source].zone == Zone.HAND
        state, frame = cast(state, spells['Growth Spiral'], seat, {})
        state = until(state, lambda s: s.pending_mechanic_choice is not None)
        pending = state.pending_mechanic_choice
        assert pending['kind'] == 'land_from_hand' and pending['player_id'] == seat
        state = reload_exact(state)
        state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [source]})
        state = resolve_response(state, frame, original)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    if family == 'sniper' and any(card.name == 'Humility' and card.zone == Zone.BATTLEFIELD
                                  for card in state.cards.values()):
        assert not any(i.id != original and i.source_card_id == source for i in state.stack)
        from rules_engine.continuous import has_keyword, effective_power, effective_toughness
        assert not has_keyword(state, source, 'reach')
        assert effective_power(state, source) == effective_toughness(state, source) == 1
    record('genuine-source-reentry', state, original=original, source=source)
    return state

def depart(state, seat, family, source, original, spells):
    name = 'Unsummon' if family == 'sniper' else 'Boomerang'
    state, frame = cast(state, spells[name], seat, {'target_card_id': source})
    state = resolve_response(state, frame, original)
    assert state.cards[source].zone == Zone.HAND
    return state
