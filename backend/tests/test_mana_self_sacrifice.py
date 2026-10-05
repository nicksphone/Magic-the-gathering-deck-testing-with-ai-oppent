"""Pure-state regressions for shared typed self-sacrifice mana activation."""
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, MatchState, PlayerState, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.costs import check_cost_option_available, collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.hooks import CostContext, apply_cost_modifiers
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from rules_engine.mana_abilities import activate_mana_ability, mana_ability_specs, mana_ability_views


def position(seat):
    return MatchState(id='self-sacrifice', players={
        n: PlayerState(id=n, name=f'Player {n}') for n in (1, 2)}, cards={}, stack=[],
        active_player=seat, priority_player=seat, step=Step.PRECOMBAT_MAIN,
        pregame_pending=False, kept_hands={1, 2}, turn=5)


def add(state, seat, types, text, *, zone=Zone.BATTLEFIELD, name='Unnamed source', mana_cost=''):
    card = CardInstance(id=f'card-{len(state.cards)}', name=name, owner=seat,
        controller=seat, zone=zone, types=types, type_line=' '.join(types),
        oracle_text=text, mana_cost=mana_cost, power=1 if 'Creature' in types else None,
        toughness=1 if 'Creature' in types else None)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind,types', [
    ('artifact', ['Artifact']), ('creature', ['Creature']),
    ('enchantment', ['Enchantment']), ('permanent', ['Artifact']),
    ('token', ['Artifact', 'Token']),
])
@pytest.mark.parametrize('paid', [False, True])
def test_typed_self_sacrifice_uses_shared_planning_without_tap(seat, kind, types, paid):
    state = position(seat)
    source = add(state, seat, types,
        ('{1}, ' if paid else '') + f'Sacrifice this {kind}: Add {{U}}.')
    # Neither tapped status nor summoning sickness restricts a cost without {T}.
    source.tapped = True
    state.players[seat].mana_pool = {'C': int(paid)}
    before = serialize_match_snapshot(state)
    assert len(mana_ability_specs(source, state)) == 1
    assert mana_ability_views(state, source)
    assert can_pay_with_pool_and_lands(state, seat, '{U}')
    assert serialize_match_snapshot(state) == before
    details = {}
    assert auto_pay_cost(state, seat, '{U}', payment_details=details)
    assert details['mana_spent'] == 1
    assert source.zone == Zone.GRAVEYARD
    assert source.id not in state.players[seat].battlefield
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_thoughtcast_locks_discount_and_keeps_star_death_trigger(seat):
    directory = Path(__file__).parent / 'fixtures/affinity'
    rows = {row['name']: row for row in json.loads((directory / 'canonical.json').read_text())['data']}
    permanents = {row['name']: row for row in json.loads((directory / 'permanents.json').read_text())['data']}
    state = position(seat)
    thoughtcast = rows['Thoughtcast']
    spell = add(state, seat, ['Sorcery'], thoughtcast['oracle_text'], zone=Zone.HAND,
                name=thoughtcast['name'], mana_cost=thoughtcast['mana_cost'])
    star = add(state, seat, ['Artifact'], permanents['Chromatic Star']['oracle_text'], name='Chromatic Star')
    for _ in range(3):
        add(state, seat, ['Artifact', 'Creature'], rows['Frogmite']['oracle_text'], name='Frogmite')
    drawn = add(state, seat, ['Land'], '', zone=Zone.LIBRARY, name='Draw evidence')
    state.players[seat].mana_pool = {'C': 1}

    def discount(current):
        return apply_cost_modifiers(CostContext(player_id=seat, state=current,
            source_card_id=spell.id, card_name=spell.name, mana_cost=spell.mana_cost,
            spell_types={'Sorcery'}, oracle_text=spell.oracle_text)).generic_reduction

    before = serialize_match_snapshot(state)
    option, = collect_cost_options(state, seat, spell)
    assert discount(state) == 4
    assert check_cost_option_available(state, seat, spell, option)
    assert serialize_match_snapshot(state) == before
    result = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id})
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.cards[star.id].zone == Zone.GRAVEYARD
    assert discount(result) == 3
    assert not any(result.players[seat].mana_pool.values())
    cast = next(item for item in result.stack if item.source_card_id == spell.id)
    assert cast.payload['mana_spent'] == 1
    assert any(item.source_card_id == star.id and item.effect_key == 'draw_cards'
               and item.payload.get('__trigger_event') == 'permanent_dies' for item in result.stack)
    assert result.stack[-1].source_card_id == star.id
    assert result.priority_player == seat
    assert not result.trigger_staging and not result.staged_triggers
    from rules_engine.stack_engine import resolve_top_of_stack
    assert resolve_top_of_stack(result)
    assert drawn.id in result.players[seat].hand
    assert result.stack[-1].source_card_id == spell.id
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('blocked', ['tapped', 'sick', 'unfunded', 'reserved', 'wrong_type'])
def test_unavailable_tap_self_sacrifice_does_not_mutate(seat, blocked):
    state = position(seat)
    source = add(state, seat, ['Creature'], '{1}, {T}, Sacrifice this creature: Add {U}.')
    source.summoning_sick = blocked == 'sick'
    source.tapped = blocked == 'tapped'
    state.players[seat].mana_pool = {'C': 0 if blocked == 'unfunded' else 1}
    reserved = {source.id} if blocked == 'reserved' else set()
    if blocked == 'wrong_type':
        source.types = ['Artifact']
        source.type_line = 'Artifact'
    before = serialize_match_snapshot(state)
    assert not can_pay_with_pool_and_lands(state, seat, '{U}', reserved_card_ids=reserved)
    assert not activate_mana_ability(state, seat, source.id, 0, 'U', reserved_card_ids=reserved)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_tap_sacrifice_can_use_a_different_mana_source(seat):
    state = position(seat)
    source = add(state, seat, ['Creature'], '{1}, {T}, Sacrifice this creature: Add {U}.')
    source.summoning_sick = False
    land = add(state, seat, ['Land'], '{T}: Add {C}.')
    state.players[seat].mana_pool = {}
    assert can_pay_with_pool_and_lands(state, seat, '{U}')
    assert auto_pay_cost(state, seat, '{U}')
    assert source.zone == Zone.GRAVEYARD
    assert land.tapped
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('text', [
    '{1}, {T}, Remove a counter from this artifact: Add {U}.',
    '{1}, {T}, Exile this artifact: Add {U}.',
    '{1}, {T}, Sacrifice this artifact: Add {U}. Draw a card.',
    '{1}, {T}, Sacrifice this artifact: Add {U} for each target creature.',
])
def test_unsupported_costs_or_nonmana_effects_are_not_admitted(text):
    state = position(1)
    source = add(state, 1, ['Artifact'], text)
    state.players[1].mana_pool = {'C': 1}
    before = serialize_match_snapshot(state)
    assert not mana_ability_specs(source, state)
    assert not can_pay_with_pool_and_lands(state, 1, '{U}')
    assert not activate_mana_ability(state, 1, source.id, 0, 'U')
    assert serialize_match_snapshot(state) == before


def test_self_sacrifice_cannot_fund_itself_or_a_circular_pair():
    state = position(1)
    add(state, 1, ['Artifact'], '{1}, Sacrifice this artifact: Add {U}.')
    add(state, 1, ['Artifact'], '{1}, Sacrifice this artifact: Add {C}.')
    state.players[1].mana_pool = {}
    before = serialize_match_snapshot(state)
    assert not can_pay_with_pool_and_lands(state, 1, '{U}')
    assert not auto_pay_cost(state, 1, '{U}')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_shared_sacrifice_path_preserves_supported_creature_death_trigger(seat):
    state = position(seat)
    source = add(state, seat, ['Creature'],
        '{1}, Sacrifice this creature: Add {U}.\nWhen this creature dies, draw a card.')
    state.players[seat].mana_pool = {'C': 1}
    assert auto_pay_cost(state, seat, '{U}')
    trigger, = state.stack
    assert trigger.source_card_id == source.id
    assert trigger.effect_key == 'draw_cards'
    assert trigger.payload['__trigger_event'] == 'creature_dies'


@pytest.mark.parametrize('tap', [False, True])
def test_tap_mana_multiplier_does_not_multiply_a_nontap_sacrifice(tap):
    state = position(1)
    source = add(state, 1, ['Artifact'],
        ('{T}, ' if tap else '') + 'Sacrifice this artifact: Add {U}.')
    add(state, 1, ['Enchantment'],
        'If you tap a permanent for mana, it produces twice as much of that mana instead.')
    assert activate_mana_ability(state, 1, source.id, 0, 'U')
    assert state.players[1].mana_pool['U'] == (2 if tap else 1)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('protected', [0, 19])
def test_paid_self_sacrifice_preserves_combined_supported_life_cost(seat, protected):
    state = position(seat)
    source = add(state, seat, ['Artifact'],
        '{1}, Pay 2 life, Sacrifice this artifact: Add {U}.')
    state.players[seat].mana_pool = {'C': 1}
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{U}', protected_life=protected) == (protected == 0)
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{U}', protected_life=protected) == (protected == 0)
    if protected:
        assert serialize_match_snapshot(state) == before
    else:
        assert state.players[seat].life == 18
        assert source.zone == Zone.GRAVEYARD
        assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reference,types', [
    ('this artifact', ['Artifact']), ('this enchantment', ['Enchantment']),
    ('this creature', ['Creature']), ('this permanent', ['Artifact', 'Creature']),
    ('this token', ['Artifact', 'Token']), ('Arbitrary Source', ['Artifact']),
    ('Arbitrary Source', ['Creature']),
])
@pytest.mark.parametrize('wording', ['is put into a graveyard from the battlefield', 'dies'])
def test_generic_self_death_clause_uses_lki_and_triggers_once(seat, reference, types, wording):
    state = position(seat)
    source = add(state, seat, types,
        '{1}, Sacrifice this permanent: Add {U}.\n'
        'When this permanent enters, gain 7 life.\n'
        f'Whenever {reference} {wording}, draw a card.', name='Arbitrary Source')
    state.players[seat].mana_pool = {'C': 1}
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{U}')
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{U}')
    assert source.zone == Zone.GRAVEYARD
    assert source.last_known_battlefield['oracle_text'] == source.oracle_text
    trigger, = state.stack
    assert trigger.source_card_id == source.id
    assert trigger.controller == seat
    assert trigger.effect_key == 'draw_cards'
    assert trigger.payload['amount'] == 1
    event = 'creature_dies' if wording == 'dies' and 'Creature' in types else 'permanent_dies'
    assert trigger.payload['__trigger_event'] == event
    assert state.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_self_to_graveyard_does_not_trigger_for_another_departure_or_exile(seat):
    from rules_engine.events import emit_event_batch
    state = position(seat)
    watcher = add(state, seat, ['Artifact'],
        'When this artifact is put into a graveyard from the battlefield, draw a card.')
    other = add(state, seat, ['Artifact'], '')
    events = [{'card_id': other.id, 'controller': seat}]
    emit_event_batch(state, 'leaves_battlefield', events)
    state.players[seat].battlefield.remove(other.id)
    state.players[seat].graveyard.append(other.id)
    other.zone = Zone.GRAVEYARD
    emit_event_batch(state, 'permanent_dies', events)
    assert not state.stack
    events = [{'card_id': watcher.id, 'controller': seat}]
    emit_event_batch(state, 'leaves_battlefield', events)
    state.players[seat].battlefield.remove(watcher.id)
    state.players[seat].exile.append(watcher.id)
    watcher.zone = Zone.EXILE
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_self_sacrifice_exile_replacement_produces_mana_without_death_trigger(seat):
    state = position(seat)
    source = add(state, seat, ['Artifact'],
        '{1}, {T}, Sacrifice this artifact: Add {U}.\n'
        'When this artifact is put into a graveyard from the battlefield, draw a card.')
    add(state, 3-seat, ['Enchantment'],
        'If a card or token would be put into a graveyard from anywhere, exile it instead.')
    state.players[seat].mana_pool = {'C': 1}
    assert activate_mana_ability(state, seat, source.id, 0, 'U')
    assert source.zone == Zone.EXILE
    assert state.players[seat].mana_pool['U'] == 1
    assert not state.stack


def test_self_death_uses_predeparture_oracle_for_matching_and_effect():
    from rules_engine.events import emit_event_batch
    state = position(1)
    source = add(state, 1, ['Artifact'],
        'When this artifact is put into a graveyard from the battlefield, draw a card.')
    events = [{'card_id': source.id, 'controller': 1}]
    emit_event_batch(state, 'leaves_battlefield', events)
    state.players[1].battlefield.remove(source.id)
    state.players[1].graveyard.append(source.id)
    source.zone = Zone.GRAVEYARD
    source.oracle_text = 'When this artifact enters, gain 7 life.'
    emit_event_batch(state, 'permanent_dies', events)
    trigger, = state.stack
    assert trigger.source_card_id == source.id
    assert trigger.effect_key == 'draw_cards'
    assert trigger.payload['amount'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('types,kind', [(['Artifact'], 'artifact'), (['Creature'], 'creature')])
def test_sacrificed_source_counter_mana_uses_last_known_amount(seat, types, kind):
    state = position(seat)
    source = add(state, seat, types,
        f'{{1}}, Sacrifice this {kind}: Add {{C}} for each charge counter on this permanent.')
    source.counters['charge'] = 3
    state.players[seat].mana_pool = {'C': 1}
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{3}')
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{3}')
    assert source.zone == Zone.GRAVEYARD
    assert not source.counters
    assert source.last_known_battlefield['counters']['charge'] == 3
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_sacrificed_source_power_mana_uses_last_known_counter_modified_power(seat):
    state = position(seat)
    source = add(state, seat, ['Creature'],
        "{1}, Sacrifice this creature: Add an amount of {G} equal to this creature's power.")
    source.counters['+1/+1'] = 3
    state.players[seat].mana_pool = {'C': 1}
    assert can_pay_with_pool_and_lands(state, seat, '{4}')
    assert auto_pay_cost(state, seat, '{4}')
    assert source.zone == Zone.GRAVEYARD
    assert not source.counters
    assert source.last_known_battlefield['power'] == 4
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wording', ['dies', 'is put into a graveyard from the battlefield'])
@pytest.mark.parametrize('reference', ['this artifact', 'Named Source, With Comma'])
def test_intervening_if_self_death_is_explicitly_unsupported_not_unconditional(seat, wording, reference):
    state = position(seat)
    source = add(state, seat, ['Artifact'],
        '{1}, Sacrifice this artifact: Add {U}.\n'
        f'When {reference} {wording}, if you control a creature, draw a card.',
        name='Named Source, With Comma')
    state.players[seat].mana_pool = {'C': 1}
    assert auto_pay_cost(state, seat, '{U}')
    assert source.zone == Zone.GRAVEYARD
    assert not state.stack
    assert any('unsupported intervening-if self-death trigger' in line.lower() for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('types,draw_wording,gain_wording', [
    (['Artifact'], 'is put into a graveyard from the battlefield', 'is put into a graveyard from the battlefield'),
    (['Creature'], 'dies', 'dies'),
    (['Creature'], 'dies', 'is put into a graveyard from the battlefield'),
])
def test_separate_self_death_clauses_keep_distinct_human_order_choices(seat, types, draw_wording, gain_wording):
    from rules_engine.events import resume_trigger_order
    from rules_engine.stack_engine import resolve_top_of_stack
    state = position(seat)
    source = add(state, seat, types,
        '{1}, Sacrifice this permanent: Add {U}.\n'
        f'When this permanent {draw_wording}, draw a card.\n'
        f'When this permanent {gain_wording}, gain 1 life.')
    drawn = add(state, seat, ['Land'], '', zone=Zone.LIBRARY)
    state.players[seat].mana_pool = {'C': 1}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    assert activate_mana_ability(state, seat, source.id, 0, 'U')
    pending = state.pending_trigger_order
    assert pending and pending['current_controller'] == seat
    group = pending['groups'][str(seat)]
    assert len(group) == 2
    assert {trigger['effect_key'] for trigger in group} == {'draw_cards', 'gain_life'}
    assert len({trigger['_choice_id'] for trigger in group}) == 2
    order = [trigger['_choice_id'] for trigger in reversed(group)]
    assert resume_trigger_order(state, order)
    assert [trigger.effect_key for trigger in state.stack] == [trigger['effect_key'] for trigger in reversed(group)]
    assert [trigger.payload['__trigger_order'] for trigger in state.stack] == [0, 1]
    assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    assert state.players[seat].life == 21
    assert drawn.id in state.players[seat].hand


@pytest.mark.parametrize('seat', [1, 2])
def test_self_graveyard_return_does_not_hide_another_death_clause(seat):
    state = position(seat)
    source = add(state, seat, ['Artifact'],
        '{1}, Sacrifice this artifact: Add {U}.\n'
        "When this artifact is put into a graveyard from the battlefield, return it to its owner's hand.\n"
        'When this artifact is put into a graveyard from the battlefield, draw a card.')
    state.players[seat].mana_pool = {'C': 1}
    assert activate_mana_ability(state, seat, source.id, 0, 'U')
    assert len(state.stack) == 2
    assert {trigger.effect_key for trigger in state.stack} == {'return_from_graveyard', 'draw_cards'}
    assert len({trigger.payload['__trigger_full_clause'] for trigger in state.stack}) == 2
    returned = next(trigger for trigger in state.stack if trigger.effect_key == 'return_from_graveyard')
    assert returned.payload['target_card_id'] == source.id
    assert '__graveyard_reference' in returned.payload
