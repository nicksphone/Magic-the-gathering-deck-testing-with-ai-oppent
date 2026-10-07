"""Canonical conditional instructions are alternatives selected at resolution."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.stack_engine import resolve_top_of_stack


FIXTURES = Path(__file__).parent / 'fixtures/resolution_conditions'
CARDS = {}
for filename in ['seed-cards.json', 'indestructible.json', 'twincast.json',
                 'furnace-of-rath.json', 'tokens.json']:
    rows = json.loads((FIXTURES / filename).read_text())
    CARDS.update({row['name']: row for row in (rows if isinstance(rows, list) else [rows])})


def position(seat=1):
    deck = [{**CARDS['Island'], 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=2207)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {'B': 5, 'R': 5, 'U': 5, 'C': 5}
    return state


def add(state, name, seat=1, zone=Zone.BATTLEFIELD):
    raw = CARDS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=2207)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def cast(state, name, target, seat):
    spell = add(state, name, seat, Zone.HAND)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': target.id}})
    return state, spell.id


def reload(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_push_target_condition_is_not_an_announcement_restriction(seat):
    state = position(seat)
    targets = [add(state, name, 3-seat) for name in
               ['Sprite Dragon', 'Topiary Stomper', 'Sheoldred, the Apocalypse', 'Torrential Gearhulk']]
    spell = add(state, 'Fatal Push', seat, Zone.HAND)
    hints = inspect_target_hints(state, spell, seat)
    assert {target.id for target in targets} <= {row['id'] for row in hints['creature_targets']}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enhanced', [False, True])
def test_heat_resolves_two_or_six_never_eight(seat, enhanced):
    state = position(seat)
    target = add(state, 'Ugin, the Spirit Dragon', 3-seat)
    if enhanced:
        for name in ['Island', 'Lightning Bolt', 'Lava Spike', "Witch's Oven"]:
            add(state, name, seat, Zone.GRAVEYARD)
    state, spell = cast(state, 'Unholy Heat', target, seat)
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].loyalty == 7-(6 if enhanced else 2)
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enhanced', [False, True])
@pytest.mark.parametrize('name,mv', [('Sprite Dragon', 2), ('Topiary Stomper', 3),
                                  ('Sheoldred, the Apocalypse', 4), ('Torrential Gearhulk', 6)])
def test_push_announces_any_creature_but_resolves_at_two_or_four(seat, enhanced, name, mv):
    state = position(seat)
    target = add(state, name, 3-seat)
    if enhanced:
        from rules_engine.zone_actions import sacrifice_selected
        resource = add(state, "Witch's Oven", seat)
        assert sacrifice_selected(state, seat, [resource.id])
    state, spell = cast(state, 'Fatal Push', target, seat)
    state = reload(state)
    assert resolve_top_of_stack(state)
    expected = Zone.GRAVEYARD if mv <= (4 if enhanced else 2) else Zone.BATTLEFIELD
    assert state.cards[target.id].zone == expected
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('departure', ['none', 'opponent', 'sacrifice', 'token', 'bounce', 'exile', 'stolen'])
def test_push_observes_real_departure_after_cast_and_reload(seat, departure):
    from effects.registry import resolve_effect
    from rules_engine.zone_actions import sacrifice_selected
    state = position(seat)
    target = add(state, 'Sheoldred, the Apocalypse', 3-seat)
    actor = 3-seat if departure == 'opponent' else seat
    resource = add(state, 'Treasure' if departure == 'token' else "Witch's Oven", actor)
    if departure == 'stolen':
        resource.owner = 3-seat
    state, spell = cast(state, 'Fatal Push', target, seat)
    if departure in ['opponent', 'sacrifice', 'token', 'stolen']:
        assert sacrifice_selected(state, actor, [resource.id])
    elif departure in ['bounce', 'exile']:
        resolve_effect(state, actor, 'return_permanent_to_hand' if departure == 'bounce' else 'exile',
                       {'target_card_id': resource.id})
    state = reload(state)
    assert resolve_top_of_stack(state)
    expected = Zone.BATTLEFIELD if departure in ['none', 'opponent'] else Zone.GRAVEYARD
    assert state.cards[target.id].zone == expected
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_departure_history_resets_at_real_turn_boundary(seat):
    from rules_engine.zone_actions import sacrifice_selected
    state = position(3-seat)
    resource = add(state, "Witch's Oven", seat)
    assert sacrifice_selected(state, seat, [resource.id])
    state.step = Step.CLEANUP
    RulesEngine().next_step(state)
    assert state.active_player == seat
    assert state.players_with_permanent_departure == set()
    for expected in (Step.DRAW, Step.PRECOMBAT_MAIN):
        RulesEngine().next_step(state)
        assert state.step == expected
    state.players[seat].mana_pool = {'B': 1}
    target = add(state, 'Sheoldred, the Apocalypse', 3-seat)
    state, _ = cast(state, 'Fatal Push', target, seat)
    state = reload(state)
    assert resolve_top_of_stack(state)
    assert target.id in state.players[3-seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['add', 'remove', 'opponent', 'duplicates', 'four'])
def test_heat_reads_current_unique_own_graveyard_types_not_cast_snapshot(seat, change):
    from effects.registry import resolve_effect
    state = position(seat)
    target = add(state, 'Ugin, the Spirit Dragon', 3-seat)
    actor = 3-seat if change == 'opponent' else seat
    names = ['Island', 'Lightning Bolt', 'Lava Spike', "Witch's Oven"]
    if change == 'duplicates':
        names = ['Island', 'Island', 'Lightning Bolt', 'Counterspell']
    grave = [add(state, name, actor, Zone.GRAVEYARD) for name in names[:3]]
    if change in ['remove', 'four', 'opponent', 'duplicates']:
        grave.append(add(state, names[3], actor, Zone.GRAVEYARD))
    state, _ = cast(state, 'Unholy Heat', target, seat)
    if change == 'add':
        add(state, names[3], seat, Zone.GRAVEYARD)
    elif change == 'remove':
        resolve_effect(state, seat, 'exile_from_graveyard', {'target_card_id': grave[-1].id})
    state = reload(state)
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].loyalty == (1 if change in ['add', 'four'] else 5)


@pytest.mark.parametrize('seat', [1, 2])
def test_delirium_counts_each_card_type_but_not_token_supertypes_or_subtypes(seat):
    from rules_engine.card_types import graveyard_card_types
    state = position(seat)
    for name in ['Darksteel Myr', 'Lava Spike', 'Intangible Virtue']:
        add(state, name, seat, Zone.GRAVEYARD)
    add(state, 'Treasure', seat, Zone.GRAVEYARD)
    assert graveyard_card_types(state, [seat]) == {'Artifact', 'Creature', 'Sorcery', 'Enchantment'}
    target = add(state, 'Ugin, the Spirit Dragon', 3-seat)
    state, _ = cast(state, 'Unholy Heat', target, seat)
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].loyalty == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell_name', ['Fatal Push', 'Unholy Heat'])
@pytest.mark.parametrize('retarget', [False, True])
def test_real_twincast_copy_uses_copy_controller_resources_and_current_target(seat, spell_name, retarget):
    state = position(seat)
    copier = 3-seat
    target_name = 'Topiary Stomper' if spell_name == 'Fatal Push' else 'Ugin, the Spirit Dragon'
    old = add(state, target_name, copier)
    new = add(state, target_name, seat)
    state, spell = cast(state, spell_name, old, seat)
    original = state.stack[-1].id
    if spell_name == 'Fatal Push':
        from rules_engine.zone_actions import sacrifice_selected
        resource = add(state, "Witch's Oven", copier)
        assert sacrifice_selected(state, copier, [resource.id])
    else:
        for name in ['Island', 'Lightning Bolt', 'Lava Spike', "Witch's Oven"]:
            add(state, name, copier, Zone.GRAVEYARD)
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    twincast = add(state, 'Twincast', copier, Zone.HAND)
    state = checked_action(state, RulesEngine(), copier, {
        'type': 'cast_spell', 'card_id': twincast.id, 'targets': {'target_stack_id': original}})
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    state = reload(state)
    state = checked_action(state, RulesEngine(), copier, {'type': 'choose_mechanic',
        'card_ids': [f'target_card_id:{new.id}' if retarget else 'keep']})
    assert state.cards[twincast.id].zone == Zone.GRAVEYARD
    assert len(state.stack) == 2
    assert resolve_top_of_stack(state)
    selected, unselected = (new, old) if retarget else (old, new)
    if spell_name == 'Fatal Push':
        assert state.cards[selected.id].zone == Zone.GRAVEYARD
        assert state.cards[unselected.id].zone == Zone.BATTLEFIELD
    else:
        assert state.cards[selected.id].loyalty == 1
        assert state.cards[unselected.id].loyalty == 7
    assert resolve_top_of_stack(state)
    if spell_name == 'Fatal Push':
        # Retargeting the copy kills the original caster's creature, enabling Revolt.
        if retarget:
            assert seat in state.players_with_permanent_departure
        assert state.cards[old.id].zone == Zone.GRAVEYARD
    else:
        assert state.cards[old.id].loyalty == (5 if retarget else -1)
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell_name', ['Fatal Push', 'Unholy Heat'])
@pytest.mark.parametrize('copied', [False, True])
def test_departure_return_is_not_the_announced_target_incarnation(seat, spell_name, copied):
    from effects.handlers import copy_spell
    from effects.registry import resolve_effect
    state = position(seat)
    target = add(state, 'Sprite Dragon', 3-seat)
    state, _ = cast(state, spell_name, target, seat)
    if copied:
        copy_spell(state, seat, {'target_stack_id': state.stack[-1].id})
    resolve_effect(state, seat, 'exile', {'target_card_id': target.id})
    state.players[3-seat].exile.remove(target.id)
    state.cards[target.id].move_to_zone(Zone.BATTLEFIELD)
    state.players[3-seat].battlefield.append(target.id)
    state = reload(state)
    while state.stack:
        assert resolve_top_of_stack(state)
    assert state.cards[target.id].zone == Zone.BATTLEFIELD
    assert state.cards[target.id].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_push_preserves_indestructible_and_graveyard_replacement(seat):
    from rules_engine.zone_actions import sacrifice_selected
    state = position(seat)
    resource = add(state, "Witch's Oven", seat)
    assert sacrifice_selected(state, seat, [resource.id])
    target = add(state, 'Darksteel Myr', 3-seat)
    state, _ = cast(state, 'Fatal Push', target, seat)
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].zone == Zone.BATTLEFIELD
    state.priority_player = seat
    add(state, 'Rest in Peace', 3-seat)
    target = add(state, 'Sprite Dragon', 3-seat)
    state, spell = cast(state, 'Fatal Push', target, seat)
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].zone == Zone.EXILE
    assert state.cards[spell].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_heat_uses_source_metadata_for_noncombat_damage_replacement(seat):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    state, _ = cast(state, 'Unholy Heat', target, seat)
    assert state.stack[-1].payload.get('__trigger_event') == 'spell_cast'
    assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].counters.get('-1/-1', 0) == 2
    assert state.cards[target.id].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_opponents_spell_copy_uses_copy_controller_for_damage_replacement(seat):
    from effects.handlers import copy_spell
    state = position(seat)
    copier = 3-seat
    add(state, 'Soul-Scar Mage', copier)
    target = add(state, 'Torrential Gearhulk', seat)
    state, _ = cast(state, 'Unholy Heat', target, seat)
    copy_spell(state, copier, {'target_stack_id': state.stack[-1].id})
    state = reload(state)
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].counters.get('-1/-1', 0) == 2
    assert state.cards[target.id].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_competing_damage_replacements_pause_reload_and_resume_once(seat):
    state = position(seat)
    target = add(state, 'Darksteel Myr', 3-seat)
    furnaces = [add(state, 'Furnace of Rath', seat), add(state, 'Furnace of Rath', 3-seat)]
    for name in ['Island', 'Lightning Bolt', 'Lava Spike', "Witch's Oven"]:
        add(state, name, seat, Zone.GRAVEYARD)
    state.replacement_choice_required = True
    state.replacement_choice_players = {1, 2}
    state, spell = cast(state, 'Unholy Heat', target, seat)
    assert not resolve_top_of_stack(state)
    assert state.pending_replacement_choice['event'] == 'damage_to_permanent'
    state = reload(state)
    state = checked_action(state, RulesEngine(), 3-seat, {
        'type': 'choose_replacement', 'replacement_source_id': furnaces[0].id})
    assert state.pending_replacement_choice['amount'] == 12
    assert state.cards[spell].zone == Zone.STACK
    state = reload(state)
    state = checked_action(state, RulesEngine(), 3-seat, {
        'type': 'choose_replacement', 'replacement_source_id': furnaces[1].id})
    assert state.pending_replacement_choice is None
    assert state.cards[target.id].counters['__damage_marked'] == 24
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enhanced', [False, True])
def test_actual_ai_push_uses_effective_target_but_hints_keep_all_legal_creatures(seat, enhanced):
    from ai.agent import AIAgent
    from rules_engine.zone_actions import sacrifice_selected
    state = position(seat)
    small = add(state, 'Sprite Dragon', 3-seat)
    medium = add(state, 'Sheoldred, the Apocalypse', 3-seat)
    large = add(state, 'Torrential Gearhulk', 3-seat)
    if enhanced:
        resource = add(state, "Witch's Oven", seat)
        assert sacrifice_selected(state, seat, [resource.id])
    spell = add(state, 'Fatal Push', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    decision = AIAgent(archetype='Control' if seat == 1 else 'Ramp', difficulty='master').choose_action(state, moves, seat)
    assert decision.action['card_id'] == spell.id
    assert decision.action['targets']['target_card_id'] in ({small.id, medium.id} if enhanced else {small.id})
    assert serialize_match_snapshot(state) == before
    assert large.id in {row['id'] for row in inspect_target_hints(state, spell, seat)['creature_targets']}
    state = checked_action(state, RulesEngine(), seat, decision.action)
    chosen = decision.action['targets']['target_card_id']
    assert resolve_top_of_stack(state)
    assert state.cards[chosen].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_no_effect_push_remains_legally_available_but_ai_does_not_spend_it(seat):
    from ai.agent import AIAgent
    state = position(seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    spell = add(state, 'Fatal Push', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move.get('card_id') == spell.id for move in moves)
    decision = AIAgent(archetype='Control', difficulty='master').choose_action(state, moves, seat)
    assert decision.action['type'] == 'pass_priority'
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': target.id}})
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_rejected_noncreature_target_preserves_complete_state(seat):
    state = position(seat)
    target = add(state, "Witch's Oven", 3-seat)
    spell = add(state, 'Fatal Push', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': target.id}})
    assert serialize_match_snapshot(state) == before


def test_complete_parser_and_coverage_do_not_certify_adjacent_conditional_grammar():
    from rules_engine.conditional_instructions import parse_instruction, instruction_gaps
    from rules_engine.coverage import known_unsupported_mechanics
    from rules_engine.oracle_effects import infer_effect_from_oracle
    for name in ['Fatal Push', 'Unholy Heat']:
        raw = CARDS[name]
        assert parse_instruction(raw['oracle_text'], name) is not None
        assert instruction_gaps(raw['oracle_text'], name) == []
        assert 'unsupported resolution conditional instruction' not in known_unsupported_mechanics(raw['oracle_text'], card_name=name)
        # Malformed parser inputs are not fixtures or invented printed cards.
        extra = raw['oracle_text']+'\n'+CARDS['Lightning Bolt']['oracle_text']
        assert parse_instruction(extra, name) is None
        assert instruction_gaps(extra, name) == ['unsupported resolution conditional instruction']
        state = position()
        proxy = deepcopy(add(state, name, 1, Zone.HAND))
        proxy.oracle_text = extra
        assert infer_effect_from_oracle(state, proxy, 1)[0] == 'noop'
