"""Canonical printed abilities across loss, death LKI and existing stack items."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import CardInstance, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import printed_abilities_suppressed, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.mana import nonland_mana_outputs, repeatable_nonland_mana_outputs, can_pay_with_pool_and_lands, land_can_produce_mana
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve
from tests.test_api_input_contracts import game, persist


CARDS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/ability_suppression.json').read_text())}


def add(state, name, player=1):
    card = raw_add(state, name, player, cards=CARDS)
    assign_static_order_on_battlefield_entry(state, card.id)
    card.summoning_sick = False
    return card


@pytest.mark.parametrize('player', [1, 2])
def test_suppressed_mana_creature_cannot_fund_spells_or_reappear_after_keyword_grant(player):
    state = fixture()
    elf = add(state, 'Llanowar Elves', player)
    state.players[player].mana_pool = {}
    assert nonland_mana_outputs(state, elf.id, elf) == {'G': 1}
    removal = add(state, 'Humility', 3-player)
    assert printed_abilities_suppressed(state, elf.id)
    assert nonland_mana_outputs(state, elf.id, elf) == {}
    assert repeatable_nonland_mana_outputs(elf, state=state) == {}
    assert not can_pay_with_pool_and_lands(state, player, '{G}')
    resolve_effect(state, player, 'grant_keyword', {'target_card_id': elf.id, 'keyword': 'haste'})
    assert has_keyword(state, elf.id, 'haste')
    assert nonland_mana_outputs(state, elf.id, elf) == {}
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert printed_abilities_suppressed(restored, elf.id)
    resolve_effect(restored, player, 'destroy_permanent', {'target_card_id': removal.id})
    assert nonland_mana_outputs(restored, elf.id, restored.cards[elf.id]) == {'G': 1}


@pytest.mark.parametrize('player', [1, 2])
def test_suppressed_activated_ability_hidden_and_checked_write_is_atomic(player):
    state = fixture()
    state.active_player = state.priority_player = player
    assassin = add(state, 'Royal Assassin', player)
    target = add(state, 'Llanowar Elves', 3-player)
    target.tapped = True
    assert any(m['type'] == 'activate_ability' and m.get('card_id') == assassin.id for m in RulesEngine().legal_moves(state, player))
    add(state, 'Humility', 3-player)
    before = serialize_match_snapshot(state)
    assert not any(m['type'] == 'activate_ability' and m.get('card_id') == assassin.id for m in RulesEngine().legal_moves(state, player))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), player, {'type': 'activate_ability', 'card_id': assassin.id,
                       'ability_index': 0, 'targets': {'target_card_id': target.id}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
def test_entry_trigger_suppression_does_not_change_printed_oracle_and_restores_when_source_leaves(player):
    state = fixture()
    warden = add(state, 'Soul Warden', player)
    removal = add(state, 'Humility', 3-player)
    elf = add(state, 'Llanowar Elves', player)
    emit_event(state, 'enters_battlefield', {'card_id': elf.id, 'controller': player})
    assert not state.stack
    assert warden.oracle_text == CARDS['Soul Warden']['oracle_text']
    resolve_effect(state, player, 'destroy_permanent', {'target_card_id': removal.id})
    emit_event(state, 'enters_battlefield', {'card_id': elf.id, 'controller': player})
    assert any(item.source_card_id == warden.id for item in state.stack)


@pytest.mark.parametrize('player', [1, 2])
def test_suppressed_self_death_trigger_uses_predeparture_abilities_after_snapshot(player):
    state = fixture()
    artist = add(state, 'Blood Artist', player)
    add(state, 'Humility', 3-player)
    resolve_effect(state, 3-player, 'destroy_permanent', {'target_card_id': artist.id})
    assert state.cards[artist.id].zone == Zone.GRAVEYARD
    assert artist.last_known_battlefield['printed_abilities_suppressed'] is True
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert not state.stack and not restored.stack
    assert restored.cards[artist.id].last_known_battlefield['printed_abilities_suppressed'] is True


@pytest.mark.parametrize('player', [1, 2])
def test_ability_already_on_stack_remains_independent_after_its_source_loses_abilities(player):
    state = fixture()
    state.active_player = state.priority_player = player
    assassin = add(state, 'Royal Assassin', player)
    target = add(state, 'Llanowar Elves', 3-player)
    target.tapped = True
    state = checked_action(state, RulesEngine(), player, {'type': 'activate_ability', 'card_id': assassin.id,
                           'ability_index': 0, 'targets': {'target_card_id': target.id}})
    add(state, 'Humility', 3-player)
    assert state.stack and printed_abilities_suppressed(state, assassin.id)
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('player', [1, 2])
def test_real_dress_down_keeps_its_enchantment_entry_draw_and_only_suppresses_creatures(player):
    state = fixture()
    warden = add(state, 'Soul Warden', player)
    suppression = add(state, 'Dress Down', 3-player)
    emit_event(state, 'enters_battlefield', {'card_id': suppression.id, 'controller': 3-player})
    assert not printed_abilities_suppressed(state, suppression.id)
    assert printed_abilities_suppressed(state, warden.id)
    assert any(item.source_card_id == suppression.id and item.effect_key == 'draw_cards' for item in state.stack)
    state = resolve(state)
    assert len(state.players[3-player].hand) == 1


@pytest.mark.parametrize('player', [1, 2])
def test_entry_trigger_already_stacked_is_not_removed_by_later_suppression(player):
    state = fixture()
    warden = add(state, 'Soul Warden', player)
    elf = add(state, 'Llanowar Elves', player)
    emit_event(state, 'enters_battlefield', {'card_id': elf.id, 'controller': player})
    assert any(item.source_card_id == warden.id for item in state.stack)
    add(state, 'Humility', 3-player)
    life = state.players[player].life
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.players[player].life == life + 1


@pytest.mark.parametrize('player', [1, 2])
def test_synthetic_land_animation_loses_intrinsic_basic_land_mana_only_while_creature(player):
    state = fixture()
    land = CardInstance(state.allocate_object_id(), 'Forest', player, player, Zone.BATTLEFIELD,
                        ['Land'], type_line='Basic Land - Forest', summoning_sick=False)
    state.cards[land.id] = land
    state.players[player].battlefield.append(land.id)
    add(state, 'Humility', 3-player)
    assert land_can_produce_mana(state, land.id)
    land.types.append('Creature')  # Explicit characteristic-change fixture, not a made-up card.
    assert not land_can_produce_mana(state, land.id)
    land.types.remove('Creature')
    assert land_can_produce_mana(state, land.id)


@pytest.mark.parametrize('player', [1, 2])
def test_http_suppression_survives_sqlite_restore_and_rejects_mana_and_ability_writes(game, player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = match.state
    state.active_player = state.priority_player = player
    elf = add(state, 'Llanowar Elves', player)
    assassin = add(state, 'Royal Assassin', player)
    victim = add(state, 'Llanowar Elves', 3-player)
    victim.tapped = True
    add(state, 'Humility', 3-player)
    persist(match)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    before = serialize_match_snapshot(restored.state)
    moves = client.get(f'/matches/{state.id}/legal-moves?player_id={player}').json()['moves']
    assert not any(m['type'] == 'activate_ability' and m.get('card_id') == assassin.id for m in moves)
    for action in [
        {'type': 'tap_nonland_for_mana', 'card_id': elf.id, 'color': 'G'},
        {'type': 'activate_ability', 'card_id': assassin.id, 'ability_index': 0, 'targets': {'target_card_id': victim.id}},
    ]:
        response = client.post(f'/matches/{state.id}/action', json={'player_id': player, 'action': action})
        assert response.status_code == 422, response.text
        assert serialize_match_snapshot(restored.state) == before
