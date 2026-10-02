"""Rules-defined counter consequences, not arbitrary Oracle certification."""
import json
from pathlib import Path

import pytest

from ai.proliferation_policy import preferred_recipients
from effects.registry import resolve_effect
from game_state.state import Zone, Step, assign_effect_timestamp, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.continuous import effective_keywords, continuous_layer_trace
from rules_engine.counter_placement import put_counters
from rules_engine.engine import RulesEngine
from rules_engine.named_counters import KEYWORD_COUNTERS, untap_permanent
from rules_engine.combat import declare_attackers, declare_blockers
from rules_engine.proliferation import recipients
from tests.test_ai_recurring_engines import fixture, add as add_card
from rules_engine.action_validation import checked_action


CARDS = {card['name']: card for card in json.loads(
    (Path(__file__).parent / 'fixtures/named_counters.json').read_text())}


def add(state, name='Grizzly Bears', player=1):
    card = add_card(state, name, player, cards=CARDS)
    assign_effect_timestamp(state, card.id)
    card.summoning_sick = False
    return card


@pytest.mark.parametrize('kind', sorted(KEYWORD_COUNTERS))
def test_named_keyword_counter_public_keyword_is_unique_and_view_matches(kind):
    state = fixture()
    card = add(state)
    original = object_incarnation(card)
    put_counters(state, kind, 2, target_card_id=card.id)
    assert effective_keywords(state, card.id).count(kind) == 1
    assert object_incarnation(card) == original
    view = serialize_match(state)['players'][1]['battlefield'][0]
    assert kind in view['keywords'] and view['counters'][kind] == 2


def test_keyword_timestamp_orders_before_and_after_ability_removal_and_retimes_all():
    state = fixture()
    card = add(state)
    put_counters(state, 'flying', 1, target_card_id=card.id)
    old_stamp = card.counter_timestamps['flying']
    humility = add(state, 'Humility', 2)
    assert 'flying' not in effective_keywords(state, card.id)
    assert old_stamp < humility.effect_timestamp
    put_counters(state, 'flying', 1, target_card_id=card.id)
    assert card.counter_timestamps['flying'] > humility.effect_timestamp
    assert 'flying' in effective_keywords(state, card.id)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[card.id].counter_timestamps == card.counter_timestamps
    assert 'flying' in effective_keywords(restored, card.id)
    layers = continuous_layer_trace(restored, card.id)['applied_layers']
    grants = [layer for layer in layers if layer.get('counter') == 'flying']
    assert len(grants) == 1 and grants[0]['effect_timestamp'] == card.counter_timestamps['flying']


def test_cant_have_flying_overrides_newer_keyword_counter():
    state = fixture()
    card = add(state)
    add(state, 'Archetype of Imagination', 2)
    put_counters(state, 'flying', 1, target_card_id=card.id)
    assert 'flying' not in effective_keywords(state, card.id)


@pytest.mark.parametrize('amount', [0, -1])
def test_nonpositive_and_unknown_counters_do_not_grant_keywords(amount):
    state = fixture()
    card = add(state)
    card.counters.update({'flying': amount, 'charge': 5, '__eot_keyword_flying': 0})
    assert 'flying' not in effective_keywords(state, card.id)
    assert 'charge' not in effective_keywords(state, card.id)


def test_zone_reset_clears_timestamps_and_old_snapshots_load():
    state = fixture()
    card = add(state)
    put_counters(state, 'flying', 1, target_card_id=card.id)
    card.move_to_zone(Zone.HAND)
    assert card.counters == card.counter_timestamps == {}
    old = serialize_match_snapshot(state)
    for saved in old['cards'].values():
        saved.pop('counter_timestamps', None)
    restored = deserialize_match_snapshot(old)
    assert restored.cards[card.id].counter_timestamps == {}


def test_counter_flying_and_reach_change_real_block_legality():
    state = fixture()
    attacker = add(state)
    blocker = add(state, player=2)
    put_counters(state, 'flying', 1, target_card_id=attacker.id)
    state.step = Step.DECLARE_ATTACKERS
    declare_attackers(state, [attacker.id])
    declare_blockers(state, {attacker.id: blocker.id})
    assert state.blocks.get(attacker.id, []) == []
    put_counters(state, 'reach', 1, target_card_id=blocker.id)
    declare_blockers(state, {attacker.id: blocker.id})
    assert state.blocks[attacker.id] == [blocker.id]


@pytest.mark.parametrize('player', [1, 2])
def test_stun_turn_and_effect_untap_share_actual_rule_and_snapshot(player):
    state = fixture()
    state.active_player = player
    card = add(state, player=player)
    card.tapped = True
    put_counters(state, 'stun', 2, target_card_id=card.id)
    state.step = Step.UNTAP
    RulesEngine()._apply_step_start_actions(state)
    assert card.tapped and card.counters['stun'] == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_effect(restored, player, 'untap', {'target_card_id': card.id})
    assert restored.cards[card.id].tapped and 'stun' not in restored.cards[card.id].counters
    resolve_effect(restored, player, 'untap', {'target_card_id': card.id})
    assert not restored.cards[card.id].tapped


def test_untapped_and_off_battlefield_objects_do_not_consume_stun():
    state = fixture()
    card = add(state)
    put_counters(state, 'stun', 1, target_card_id=card.id)
    assert not untap_permanent(state, card.id)
    assert card.counters['stun'] == 1
    card.zone = Zone.EXILE
    card.tapped = True
    assert not untap_permanent(state, card.id) and card.counters['stun'] == 1


def test_does_not_untap_step_static_clause_does_not_spend_stun_but_spell_can():
    state = fixture()
    card = add(state, 'Deep-Slumber Titan')
    card.tapped = True
    put_counters(state, 'stun', 1, target_card_id=card.id)
    assert not untap_permanent(state, card.id, turn_based=True)
    assert card.counters['stun'] == 1
    resolve_effect(state, 1, 'untap', {'target_card_id': card.id})
    assert card.tapped and 'stun' not in card.counters
    resolve_effect(state, 1, 'untap', {'target_card_id': card.id})
    assert not card.tapped


def test_proliferation_ai_does_not_value_redundant_keyword_but_can_restore_lost_one():
    state = fixture()
    card = add(state)
    put_counters(state, 'flying', 1, target_card_id=card.id)
    assert preferred_recipients(state, 1, recipients(state)) == []
    add(state, 'Humility', 2)
    assert preferred_recipients(state, 1, recipients(state)) == [f'card:{card.id}']
    add(state, 'Archetype of Imagination', 2)
    assert preferred_recipients(state, 1, recipients(state)) == []


def test_canonical_tap_and_named_counter_spell_keeps_later_scry():
    from rules_engine.ability_model import build_spell_spec
    state = fixture()
    target = add(state, player=2)
    spell = add_card(state, 'Impede Momentum', 1, Zone.HAND, cards=CARDS)
    state.players[1].mana_pool['U'] = 1
    targets = {'target_card_id': target.id}
    spec = build_spell_spec(state, spell, 1, targets)
    assert spec.effect.key == 'effect_sequence'
    assert [effect['effect_key'] for effect in spec.effect.payload['effects']] == ['tap', 'add_counters', 'scry']
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    while state.stack and not state.pending_mechanic_choice:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.pending_mechanic_choice['kind'] == 'scry'
    state = checked_action(state, RulesEngine(), 1, {'type': 'choose_mechanic', 'card_ids': []})
    assert state.cards[target.id].tapped and state.cards[target.id].counters['stun'] == 3
    assert spell.id in state.players[1].graveyard


@pytest.mark.parametrize('prefix', ['if you do, ', 'you may ', 'whenever a creature dies, '])
def test_named_counter_conjunction_does_not_promote_conditional_syntax(prefix):
    from rules_engine.oracle_effects import _split_clauses
    text = prefix + 'tap target creature and put three stun counters on it'
    assert _split_clauses(text) == [text]


@pytest.mark.parametrize('name', ['Lightning Bolt', 'Lava Spike', 'Shock', 'Consider', 'Memory Deluge', 'Counterspell'])
def test_missing_oracle_spell_does_not_fabricate_effect_from_real_card_name(name):
    from rules_engine.oracle_effects import infer_effect_from_oracle
    from game_state.state import CardInstance
    state = fixture()
    # Deliberately incomplete metadata, not alternate text for these real cards.
    card = CardInstance('missing-metadata-fixture', name, 1, 1, Zone.HAND, ['Instant'])
    key, payload = infer_effect_from_oracle(state, card, 1)
    assert (key, payload) == ('noop', {})
    assert 'no effect fabricated' in state.log[-1]


@pytest.mark.parametrize('kind', ['Instant', 'Sorcery'])
def test_missing_spell_oracle_is_not_admissible_metadata(kind):
    from card_data.hydration import ready_for_match
    assert not ready_for_match({'type_line': kind, 'mana_cost': '{1}', 'oracle_text': ''})
    assert ready_for_match({'type_line': 'Creature', 'power': '2', 'toughness': '2', 'oracle_text': ''})
