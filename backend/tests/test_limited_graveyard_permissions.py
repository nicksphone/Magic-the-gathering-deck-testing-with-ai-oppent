"""Real once-per-turn permissions retain source-local usage across restart."""
import json
import hashlib

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_graveyard_play_permissions import DIRECTORY, ROWS, position, moves
from tests.test_ai_recurring_engines import add

LIMITED = {row['name']: {**row, 'power': row.get('power'), 'toughness': row.get('toughness')}
           for row in json.loads((DIRECTORY / 'limited-permissions.json').read_text())['data']}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source,spell', [('Lurrus of the Dream-Den', 'Sol Ring'),
                                        ('Gisa and Geralf', 'Diregraf Ghoul')])
def test_one_cast_per_source_per_own_turn_survives_snapshot(seat, source, spell):
    state = position(seat)
    state.players[seat].mana_pool = {'B': 4, 'C': 4}
    grant = add(state, source, seat, cards=LIMITED)
    first, second = [add(state, spell, seat, Zone.GRAVEYARD, cards=ROWS) for _ in range(2)]
    available = moves(state, seat, first.id)
    assert available and available[0]['type'] == 'cast_spell'
    option = available[0]['cost_options'][0]
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': first.id,
        'from_graveyard': True, 'cost_choice': {'id': option['id']}})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(state)
    assert not moves(restored, seat, second.id)
    before = serialize_match_snapshot(restored)
    with pytest.raises(ActionRejected):
        checked_action(restored, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': second.id,
            'from_graveyard': True, 'cost_choice': {'id': option['id']}})
    assert serialize_match_snapshot(restored) == before
    restored.stack.clear()
    restored.turn += 2
    assert moves(restored, seat, second.id)
    restored.active_player = 3-seat
    assert not moves(restored, seat, second.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_sources_are_independent_without_stale_fallback(seat):
    state = position(seat)
    state.players[seat].mana_pool = {'B': 5, 'C': 5}
    for source in ('Lurrus of the Dream-Den', 'Gisa and Geralf'):
        add(state, source, seat, cards=LIMITED)
    cards = [add(state, 'Diregraf Ghoul', seat, Zone.GRAVEYARD, cards=ROWS) for _ in range(3)]
    available = moves(state, seat, cards[0].id)[0]['cost_options']
    assert len(available) == 2
    assert available[0]['id'] != available[1]['id']
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': cards[0].id,
        'from_graveyard': True, 'cost_choice': {'id': available[0]['id']}})
    state.stack.clear()
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': cards[1].id,
            'from_graveyard': True, 'cost_choice': {'id': available[0]['id']}})
    assert serialize_match_snapshot(state) == before
    assert moves(state, seat, cards[1].id)


@pytest.mark.parametrize('seat', [1, 2])
def test_limited_sources_keep_original_spell_filters_and_prohibitions(seat):
    state = position(seat)
    state.players[seat].mana_pool = {'B': 10, 'C': 10}
    add(state, 'Lurrus of the Dream-Den', seat, cards=LIMITED)
    costly = add(state, 'Ancient Greenwarden', seat, Zone.GRAVEYARD, cards=ROWS)
    assert not moves(state, seat, costly.id)
    add(state, 'Gisa and Geralf', seat, cards=LIMITED)
    not_zombie = add(state, 'Black Knight', seat, Zone.GRAVEYARD, cards=ROWS)
    # Lurrus independently permits the two-mana non-Zombie.
    assert len(moves(state, seat, not_zombie.id)[0]['cost_options']) == 1
    zombie = add(state, 'Diregraf Ghoul', seat, Zone.GRAVEYARD, cards=ROWS)
    assert len(moves(state, seat, zombie.id)[0]['cost_options']) == 2
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    assert not any(move['type'] == 'cast_spell' for move in moves(state, seat, zombie.id))


@pytest.mark.parametrize('seat', [1, 2])
def test_source_reentry_refreshes_permission_but_suppression_does_not(seat):
    state = position(seat)
    state.players[seat].mana_pool = {'C': 5}
    grant = add(state, 'Lurrus of the Dream-Den', seat, cards=LIMITED)
    first, second = [add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS) for _ in range(2)]
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': first.id, 'from_graveyard': True})
    state.stack.clear()
    assert not moves(state, seat, second.id)
    lock = add(state, 'Humility', seat, cards=ROWS)
    assert not moves(state, seat, second.id)
    state.players[seat].battlefield.remove(lock.id)
    lock.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(lock.id)
    assert not moves(state, seat, second.id)
    source = state.cards[grant.id]
    state.players[seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    source.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(source.id)
    assert moves(state, seat, second.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x,accepted', [(0, True), (1, True), (2, False)])
def test_actual_x_spell_mana_value_is_checked_before_payment(seat, x, accepted):
    from rules_engine.costs import collect_cost_options, check_cost_option_available
    file = DIRECTORY / 'walking-ballista.json'
    raw = json.loads(file.read_text())
    provenance = json.loads((DIRECTORY / 'walking-ballista.json.provenance.json').read_text())
    assert hashlib.sha256(file.read_bytes()).hexdigest() == provenance['sha256']
    state = position(seat)
    state.players[seat].mana_pool = {'C': 10}
    add(state, 'Lurrus of the Dream-Den', seat, cards=LIMITED)
    card = add(state, raw['name'], seat, Zone.GRAVEYARD, cards={raw['name']: raw})
    option = collect_cost_options(state, seat, card)[0]
    assert check_cost_option_available(state, seat, card, option, x_value=x) == accepted
    action = {'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
              'cost_choice': {'id': option.id}, 'targets': {'x_value': x}}
    before = serialize_match_snapshot(state)
    if accepted:
        result = checked_action(state, RulesEngine(), seat, action)
        assert result.cards[card.id].zone == Zone.STACK
        assert len(result.graveyard_permission_uses) == 1
    else:
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Midrange', 'Reanimator'])
def test_ai_materializes_limited_permission_without_mutating_usage(seat, style):
    from ai.agent import AIAgent
    state = position(seat)
    add(state, 'Gisa and Geralf', seat, cards=LIMITED)
    card = add(state, 'Diregraf Ghoul', seat, Zone.GRAVEYARD, cards=ROWS)
    before = serialize_match_snapshot(state)
    ai = AIAgent(difficulty='master', archetype=style)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell' and decision.action['card_id'] == card.id
    result = checked_action(state, RulesEngine(), seat, decision.action)
    assert result.cards[card.id].zone == Zone.STACK
    assert len(result.graveyard_permission_uses) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('chosen_type,remaining_type', [('Artifact', 'Creature'), ('Creature', 'Artifact')])
def test_per_type_permission_lets_player_choose_multitype_slot(seat, chosen_type, remaining_type):
    from tests.test_cast_resource_payments import ROWS as RESOURCE_ROWS
    state = position(seat)
    add(state, 'Muldrotha, the Gravetide', seat, cards=LIMITED)
    first, second = [add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=RESOURCE_ROWS) for _ in range(2)]
    cost = next(option for option in moves(state, seat, first.id)[0]['cost_options']
                if option['label'].endswith(f'({chosen_type})'))
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': first.id,
        'from_graveyard': True, 'cost_choice': {'id': cost['id']}})
    state.stack.clear()
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    available = moves(restored, seat, second.id)[0]['cost_options']
    assert len(available) == 1 and available[0]['label'].endswith(f'({remaining_type})')
    restored = checked_action(restored, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': second.id,
        'from_graveyard': True, 'cost_choice': {'id': available[0]['id']}})
    restored.stack.clear()
    third = add(restored, 'Ornithopter', seat, Zone.GRAVEYARD, cards=RESOURCE_ROWS)
    assert not moves(restored, seat, third.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_per_type_land_slot_remains_subject_to_global_land_allowance(seat):
    state = position(seat)
    add(state, 'Muldrotha, the Gravetide', seat, cards=LIMITED)
    first, second = [add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS) for _ in range(2)]
    raw = json.loads((DIRECTORY / 'exploration.json').read_text())
    provenance = json.loads((DIRECTORY / 'exploration.json.provenance.json').read_text())
    assert hashlib.sha256((DIRECTORY / 'exploration.json').read_bytes()).hexdigest() == provenance['sha256']
    add(state, raw['name'], seat, cards={raw['name']: {**raw, 'power': None, 'toughness': None}})
    move = moves(state, seat, first.id)[0]
    assert move['graveyard_permission_key'].endswith(':Land')
    state = checked_action(state, RulesEngine(), seat, {key: value for key, value in move.items()
        if key in {'type', 'card_id', 'from_graveyard', 'graveyard_permission_key'}})
    assert state.players[seat].lands_played_this_turn == 1
    assert not moves(state, seat, second.id)
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    available = moves(state, seat, second.id)
    assert available and all('graveyard_permission_key' not in move for move in available)
    state = checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': second.id, 'from_graveyard': True})
    assert state.players[seat].lands_played_this_turn == 2
    third = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    assert not moves(state, seat, third.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_limited_land_source_choice_is_stale_safe_and_survives_projection(seat):
    from ai.pending_effects import planning_copy
    state = position(seat)
    source = add(state, 'Muldrotha, the Gravetide', seat, cards=LIMITED)
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    options = moves(state, seat, land.id)
    assert len(options) == 2
    limited = next(move for move in options if move.get('graveyard_permission_key'))
    before = serialize_match_snapshot(state)
    bad = {'type': 'play_land', 'card_id': land.id, 'from_graveyard': True,
           'graveyard_permission_key': 'missing'}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, bad)
    assert serialize_match_snapshot(state) == before
    result = checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': land.id,
        'from_graveyard': True, 'graveyard_permission_key': limited['graveyard_permission_key']})
    assert len(result.graveyard_permission_uses) == 1
    clone = planning_copy(result)
    assert clone.graveyard_permission_uses == result.graveyard_permission_uses
    clone.graveyard_permission_uses.clear()
    assert len(result.graveyard_permission_uses) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_implicit_cost_fallback_can_use_a_different_valid_permission(seat):
    raw = json.loads((DIRECTORY / 'walking-ballista.json').read_text())
    state = position(seat)
    state.players[seat].mana_pool = {'C': 10}
    add(state, 'Lurrus of the Dream-Den', seat, cards=LIMITED)
    add(state, 'Muldrotha, the Gravetide', seat, cards=LIMITED)
    card = add(state, raw['name'], seat, Zone.GRAVEYARD, cards={raw['name']: raw})
    result = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id,
        'from_graveyard': True, 'targets': {'x_value': 2}})
    assert result.cards[card.id].zone == Zone.STACK
    assert len(result.graveyard_permission_uses) == 1
    assert next(iter(result.graveyard_permission_uses)).endswith((':Artifact', ':Creature'))
