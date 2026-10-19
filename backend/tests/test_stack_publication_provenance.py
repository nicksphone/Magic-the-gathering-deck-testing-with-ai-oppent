"""Actual paid announcement/event paths versus deliberately untyped legacy rows."""
import json
from pathlib import Path

import pytest

from effects.handlers import copy_spell, counter_ability
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_object_kind
from tests.test_linked_damage_targets import raw_card
from tests.test_snow_spend import SEARCH_FOR_GLORY

FIXTURES = Path(__file__).parent / 'fixtures'
MAGECRAFT = ('Magecraft — Whenever you cast or copy an instant or sorcery spell, '
             'this creature gets +1/+1 until end of turn.')


def position(seat):
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck, seed=731)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    return state


def watcher(state, seat):
    # Trusted primitive board placement, not a claimed naturally paid creature birth.
    card = CardInstance('copy-watcher', 'Copy-event diagnostic', seat, seat, Zone.BATTLEFIELD,
                        ['Creature'], power=1, toughness=1, oracle_text=MAGECRAFT)
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    return card.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('watcher_before_cast', [False, True])
def test_paid_opt_actual_copy_event_and_combined_cast_copy_are_distinct(seat, watcher_before_cast):
    state = position(seat)
    observer = watcher(state, seat) if watcher_before_cast else None
    opt = raw_card(state, json.loads((FIXTURES / 'global_flash_timing_audit/opt.json').read_text()),
                   seat, Zone.HAND)
    state.players[seat].mana_pool['U'] = 1
    assert any(m.get('card_id') == opt.id for m in RulesEngine().legal_moves(state, seat))
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': opt.id})
    original = next(i for i in state.stack if i.source_card_id == opt.id)
    assert original.payload['mana_spent'] == 1 and stack_object_kind(state, original) == 'spell'
    if watcher_before_cast:
        assert len(state.stack) == 2
        assert resolve_top_of_stack(state)
        assert effective_power(state, observer) == 2
    else:
        assert len(state.stack) == 1
        observer = watcher(state, seat)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.stack[0].payload == original.payload
    assert stack_object_kind(restored, restored.stack[0]) == 'spell'
    copy_spell(restored, seat, {'target_stack_id': original.id})
    assert len(restored.stack) == 3
    copied, trigger = restored.stack[-2:]
    assert copied.payload['__stack_copy_kind'] == 'spell'
    assert copied.payload['__copied_from_stack_id'] == original.id
    assert trigger.effect_key == 'temporary_pt_buff' and trigger.source_card_id == observer
    assert stack_object_kind(restored, trigger) == 'triggered'
    assert resolve_top_of_stack(restored)
    assert effective_power(restored, observer) == (3 if watcher_before_cast else 2)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_creature_native_etb_trigger_is_countered_without_source_inference(seat):
    state = position(seat)
    warden = CardInstance('warden', 'Soul Warden', seat, seat, Zone.BATTLEFIELD, ['Creature'],
                         power=1, toughness=1,
                         oracle_text='Whenever another creature enters the battlefield, you gain 1 life.')
    state.cards[warden.id] = warden
    state.players[seat].battlefield.append(warden.id)
    bear = raw_card(state, json.loads((FIXTURES / 'creature_observer_audit/grizzly-bears.json').read_text()),
                    seat, Zone.HAND)
    state.players[seat].mana_pool.update({'G': 1, 'C': 1})
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': bear.id})
    assert state.stack[-1].payload['mana_spent'] == 2
    assert resolve_top_of_stack(state)
    assert state.cards[bear.id].zone == Zone.BATTLEFIELD and len(state.stack) == 1
    trigger = state.stack[-1]
    assert trigger.source_card_id == warden.id and trigger.effect_key == 'gain_life'
    assert trigger.payload['__trigger_event'] == 'enters_battlefield'
    assert stack_object_kind(state, trigger) == 'triggered'
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert stack_object_kind(restored, restored.stack[-1]) == 'triggered'
    counter_ability(restored, seat, {'target_stack_id': trigger.id})
    assert restored.stack == [] and restored.players[seat].life == 20
    assert restored.cards[warden.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_full_search_for_glory_copy_has_zero_snow_spend(seat):
    state = position(seat)
    # Explicit default automated optional search, like the existing whole-card neighbor.
    state.mechanic_choice_players = set()
    spell = CardInstance('glory', 'Search for Glory', seat, seat, Zone.HAND,
                         ['Sorcery', 'Snow'], type_line='Snow Sorcery', mana_cost='{2}{W}',
                         oracle_text=SEARCH_FOR_GLORY)
    state.cards[spell.id] = spell
    state.players[seat].hand.append(spell.id)
    state.players[seat].mana_pool.update({'C': 2, 'W': 1})
    state.players[seat].snow_mana_pool['C'] = 2
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id})
    original = state.stack[-1]
    assert original.effect_key == 'effect_sequence'
    assert original.payload['mana_spent'] == 3 and original.payload['snow_mana_spent'] == 2
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    copy_spell(state, seat, {'target_stack_id': original.id})
    assert len(state.stack) == 2
    assert state.stack[-1].payload['snow_mana_spent'] == 0
    assert state.stack[-1].payload['snow_mana_colors'] == {}
    assert state.players[seat].life == 20
    assert resolve_top_of_stack(state) and state.players[seat].life == 20
    assert resolve_top_of_stack(state) and state.players[seat].life == 22


@pytest.mark.parametrize('effect', ['draw_cards', 'gain_life', 'trigger_label'])
def test_unknown_legacy_rows_never_gain_kind_from_card_name_zone_or_effect(effect):
    state = position(1)
    card = CardInstance('legacy-source', 'Opt' if effect == 'draw_cards' else 'Soul Warden',
                        1, 1, Zone.STACK if effect == 'draw_cards' else Zone.BATTLEFIELD,
                        ['Instant'] if effect == 'draw_cards' else ['Creature'])
    state.cards[card.id] = card
    item = StackItem('legacy-row', card.id, 1, 'Soul Warden trigger' if effect == 'trigger_label' else card.name,
                     'draw_cards' if effect == 'draw_cards' else 'gain_life',
                     {'amount': 1, 'snow_mana_spent': 2})
    state.stack.append(item)
    before = serialize_match_snapshot(state)
    assert stack_object_kind(state, item) == 'legacy_unknown'
    copy_spell(state, 1, {'target_stack_id': item.id})
    counter_ability(state, 1, {'target_stack_id': item.id})
    assert serialize_match_snapshot(state) == before
