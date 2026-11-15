"""Target-hint text views must retain the actual source's colour characteristics."""
import pytest

from game_state.state import CardInstance, StackItem, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.bestow import bestow_cast_view, is_bestowed
from rules_engine.cast_choice import build_cast_hints
from rules_engine.engine import RulesEngine
from rules_engine.events import trigger_target_options
from tests.test_ai_recurring_engines import fixture, resolve


def position(seat):
    state = fixture()
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool = {'R': 10, 'C': 10}
    return state


def add(state, seat, name, text, *, zone=Zone.BATTLEFIELD, types=('Creature',),
        type_line='Creature', keywords=()):
    card = CardInstance(id=state.allocate_object_id(), name=name, owner=seat,
                        controller=seat, zone=zone, mana_cost='{R}', colors=None,
                        types=list(types), type_line=type_line, oracle_text=text,
                        keywords=list(keywords), power=2 if 'Creature' in types else None,
                        toughness=4 if 'Creature' in types else None)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def guards(state, seat):
    return tuple(add(state, 3-seat, quality + ' guard', 'Protection from ' + quality,
                     keywords=['protection from ' + quality])
                 for quality in ('red', 'colorless'))


@pytest.mark.parametrize('seat', [1, 2])
def test_activated_text_view_does_not_make_a_red_source_colorless(seat):
    state = position(seat)
    red_guard, colorless_guard = guards(state, seat)
    text = '{1}: Destroy target creature.'
    red = add(state, seat, 'Red channeler', text)
    devoid = add(state, seat, 'Devoid channeler', 'Devoid\n' + text)

    def activate(source, target):
        return checked_action(state, RulesEngine(), seat,
                              {'type': 'activate_ability', 'card_id': source.id,
                               'ability_index': 0, 'targets': {'target_card_id': target.id}})

    with pytest.raises(ActionRejected):
        activate(red, red_guard)
    with pytest.raises(ActionRejected):
        activate(devoid, colorless_guard)
    state = resolve(activate(devoid, red_guard))
    assert state.cards[red_guard.id].zone == Zone.GRAVEYARD
    state = activate(red, colorless_guard)
    assert state.stack[-1].payload.get('__source_lki') is None
    state = resolve(state)
    assert state.cards[colorless_guard.id].zone == Zone.GRAVEYARD
    assert state.cards[red.id].colors is None
    assert state.cards[red.id].oracle_text == text


@pytest.mark.parametrize('seat', [1, 2])
def test_trigger_clause_view_does_not_remove_devoid(seat):
    state = position(seat)
    red_guard, colorless_guard = guards(state, seat)
    clause = 'Destroy target creature.'
    text = 'When this creature enters, destroy target creature.'
    red = add(state, seat, 'Red watcher', text)
    devoid = add(state, seat, 'Devoid watcher', 'Devoid\n' + text)

    def options(source):
        item = StackItem(id='source-colour-trigger', source_card_id=source.id,
                         controller=seat, label='Entry trigger', effect_key='destroy_permanent',
                         payload={'__trigger_event': 'enters_battlefield',
                                  '__trigger_target_clause': clause})
        return {choice['target_card_id'] for choice in trigger_target_options(state, item)}

    assert red_guard.id not in options(red)
    assert colorless_guard.id in options(red)
    assert red_guard.id in options(devoid)
    assert colorless_guard.id not in options(devoid)
    assert devoid.colors is None and devoid.oracle_text == 'Devoid\n' + text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', ['aura', 'bestow'])
def test_enchant_text_view_does_not_remove_devoid(seat, variant):
    state = position(seat)
    red_guard, colorless_guard = guards(state, seat)
    bestow = variant == 'bestow'
    text = ('Bestow {1}{R}' if bestow else 'Enchant creature') + '\nEnchanted creature gets +1/+1.'
    types = ('Enchantment', 'Creature') if bestow else ('Enchantment',)
    line = 'Enchantment Creature' if bestow else 'Enchantment — Aura'
    red = add(state, seat, 'Red enchantment', text, zone=Zone.HAND, types=types, type_line=line)
    devoid = add(state, seat, 'Devoid enchantment', 'Devoid\n' + text,
                 zone=Zone.HAND, types=types, type_line=line)

    def cast(source, target):
        action = {'type': 'cast_spell', 'card_id': source.id,
                  'targets': {'target_card_id': target.id}}
        if bestow:
            action['cost_choice'] = {'id': 'bestow'}
        return checked_action(state, RulesEngine(), seat, action)

    with pytest.raises(ActionRejected):
        cast(red, red_guard)
    with pytest.raises(ActionRejected):
        cast(devoid, colorless_guard)
    view = bestow_cast_view(devoid) if bestow else devoid
    hints = build_cast_hints(state, view, seat)
    assert red_guard.id in {target['id'] for target in hints['aura_targets']}
    assert colorless_guard.id not in {target['id'] for target in hints['aura_targets']}
    state = resolve(cast(devoid, red_guard))
    result = state.cards[devoid.id]
    assert result.zone == Zone.BATTLEFIELD and result.attached_to == red_guard.id
    assert is_bestowed(result) == bestow
    assert result.colors is None
