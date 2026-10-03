"""Canonical characteristic definitions, not complete-card certification."""
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_combat_stats
from tests.test_activation_modifiers import board
from tests.test_api_input_contracts import game, persist
from tests.test_offline_match_hydration import forbid_network
import main

REAL_HYDRATE = main._hydrate_deck_cards

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/characteristic_stats.json').read_text())}
EXPECTED = {
    'Tarmogoyf': (6, 7), 'Nighthawk Scavenger': (4, 3), 'Boneyard Wurm': (1, 1),
    'Terravore': (3, 3), 'Mortivore': (3, 3), 'Lord of Extinction': (7, 7),
    'Consuming Aberration': (3, 3), 'Lhurgoyf': (3, 4), 'Rubblehulk': (2, 2),
    "Multani, Yavimaya's Avatar": (4, 4), "Death's Shadow": (4, 4),
    'Overbeing of Myth': (2, 2), 'Multani, Maro-Sorcerer': (5, 5),
}


def add(state, name, seat=1, zone=Zone.BATTLEFIELD):
    sample = MatchFactory.from_decks([{**ROWS[name], 'card_name': name, 'quantity': 1}], [], seed=7)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def setup(name, seat=1, zone=Zone.BATTLEFIELD):
    state = board(seat)
    state.players[seat].life = 9
    for item in ['Grizzly Bears', 'Forest', 'Darksteel Citadel', 'All Is Dust']:
        add(state, item, seat, Zone.GRAVEYARD)
    for item in ['Dryad Arbor', 'Counterspell', 'Grizzly Bears']:
        add(state, item, 3-seat, Zone.GRAVEYARD)
    for _ in range(2):
        add(state, 'Forest', seat)
        add(state, 'Forest', seat, Zone.HAND)
    for _ in range(3):
        add(state, 'Forest', 3-seat, Zone.HAND)
    return state, add(state, name, seat, zone)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(EXPECTED))
def test_ai_entry_projection_uses_effective_stats_without_mutation(seat, name):
    from ai.pending_effects import prospective_creature_stats, decision_projection_scope
    state, card = setup(name, seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    with decision_projection_scope(state, seat):
        assert prospective_creature_stats(state, card, seat) == EXPECTED[name]
        assert prospective_creature_stats(state, card, seat) == EXPECTED[name]
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_graveyard_entry_removes_source_from_resource_count(seat):
    from ai.pending_effects import prospective_creature_stats
    state, card = setup('Boneyard Wurm', seat, Zone.GRAVEYARD)
    assert effective_combat_stats(state, card.id) == (2, 2)
    assert prospective_creature_stats(state, card, seat) == (1, 1)


@pytest.mark.parametrize('archetype', ['Aggro', 'Control', 'Tempo', 'Ramp', 'Midrange', 'Drain', 'Tokens', 'Tribal'])
def test_ai_closure_valuation_uses_dynamic_entry_stats(archetype):
    from ai.agent import AIAgent
    state, card = setup('Tarmogoyf', zone=Zone.HAND)
    agent = AIAgent(archetype=archetype)
    assert agent._closure_spell_score(card, card.oracle_text, state=state, player_id=1) == 6.0
    assert card.power is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('archetype', ['Aggro', 'Control', 'Tempo', 'Ramp', 'Midrange', 'Drain', 'Tokens', 'Tribal'])
def test_production_ai_casts_payable_variable_threat(seat, level, archetype):
    from ai.agent import AIAgent
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    state, card = setup('Tarmogoyf', seat, Zone.HAND)
    for cid in list(state.players[seat].hand):
        if cid != card.id:
            state.players[seat].hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            state.players[seat].library.append(cid)
    engine = RulesEngine()
    before = serialize_match_snapshot(state)
    decision = AIAgent(level, archetype).choose_action(state, engine.legal_moves(state, seat), seat)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == card.id
    assert serialize_match_snapshot(state) == before
    result = checked_action(state, engine, seat, decision.action)
    assert result.stack[-1].source_card_id == card.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Tarmogoyf', 'Nighthawk Scavenger', "Death's Shadow"])
def test_cached_characteristics_survive_http_start_and_sqlite_resume(game, monkeypatch, seat, name):
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, _ = game
    monkeypatch.setattr(main, '_hydrate_deck_cards', REAL_HYDRATE)
    forbid_network(monkeypatch)
    raw = ROWS[name]
    with Session(engine) as session:
        Repository(session).upsert_card({
            'scryfall_id': raw['id'], 'name': name, 'oracle_text': raw['oracle_text'],
            'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
            'power': raw['power'], 'toughness': raw['toughness'], 'colors': ','.join(raw['colors']),
        })
    deck = [{'quantity': 4, 'card_name': name}, {'quantity': 56, 'card_name': 'Swamp'}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'seed': 113})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    card = next(card for card in controller.state.cards.values() if card.name == name and card.owner == seat)
    assert (card.printed_power, card.printed_toughness) == (raw['power'], raw['toughness'])
    persist(controller)
    main.ACTIVE_MATCHES.pop(controller.state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), controller.state.id)
    restored = main.ACTIVE_MATCHES[controller.state.id].state
    assert (restored.cards[card.id].printed_power, restored.cards[card.id].printed_toughness) == (raw['power'], raw['toughness'])
    from game_state.serializers import serialize_card_view
    view = serialize_card_view(restored, card.id)
    assert (view['printed_power'], view['printed_toughness']) == (raw['power'], raw['toughness'])


@pytest.mark.parametrize('power,toughness', [(None, None), (None, 1), (1, None)])
def test_unknown_token_stats_use_offline_fallback_without_numeric_coercion(monkeypatch, power, toughness):
    import card_data.token_images as images
    def fail_fetch(*args, **kwargs):
        raise AssertionError('network during gameplay')
    monkeypatch.setattr(images, '_search_scryfall_token_image', fail_fetch)
    assert images.resolve_token_image_uri('Copy', power, toughness).endswith('generic-token-creature.svg')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(EXPECTED))
def test_canonical_resource_characteristics_use_the_shared_layers(seat, name):
    state, card = setup(name, seat)
    assert effective_combat_stats(state, card.id) == EXPECTED[name]
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert effective_combat_stats(restored, card.id) == EXPECTED[name]


@pytest.mark.parametrize('seat', [1, 2])
def test_damage_marks_and_kills_known_star_toughness_creature(seat):
    from effects.registry import resolve_effect
    state, card = setup('Tarmogoyf', seat)
    resolve_effect(state, 3-seat, 'deal_damage', {'target_card_id': card.id, 'amount': 3})
    assert card.counters.get('__damage_marked') == 3
    resolve_effect(state, 3-seat, 'deal_damage', {'target_card_id': card.id, 'amount': 4})
    assert card.zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Tarmogoyf', 'Nighthawk Scavenger'])
def test_printed_star_expressions_are_snapshot_safe(seat, name):
    state, card = setup(name, seat)
    assert card.printed_power == ROWS[name]['power']
    assert card.printed_toughness == ROWS[name]['toughness']
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[card.id].printed_power == card.printed_power
    assert restored.cards[card.id].printed_toughness == card.printed_toughness


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', [Zone.HAND, Zone.LIBRARY, Zone.EXILE, Zone.GRAVEYARD])
@pytest.mark.parametrize('name', list(EXPECTED))
def test_definitions_work_everywhere_but_modifiers_stay_on_battlefield(seat, zone, name):
    state, card = setup(name, seat, zone)
    expected = EXPECTED[name]
    if name == "Death's Shadow":
        expected = (13, 13)
    elif name == "Multani, Yavimaya's Avatar":
        expected = (0, 0)
    elif name in {'Overbeing of Myth', 'Multani, Maro-Sorcerer'} and zone == Zone.HAND:
        expected = (expected[0]+1, expected[1]+1)
    elif zone == Zone.GRAVEYARD and name in {'Boneyard Wurm', 'Mortivore', 'Lhurgoyf', 'Lord of Extinction'}:
        expected = (expected[0]+1, expected[1]+1)
    assert effective_combat_stats(state, card.id) == expected
    from game_state.serializers import serialize_card_view
    view = serialize_card_view(state, card.id)
    assert (view['power'], view['toughness']) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,expected', [('Tarmogoyf', (0, 1)), ('Nighthawk Scavenger', (1, 3)), ('Boneyard Wurm', (0, 0))])
def test_ability_loss_preserves_printed_constant_in_star_expression(seat, name, expected):
    from effects.registry import resolve_effect
    state, card = setup(name, seat)
    resolve_effect(state, seat, 'temporary_ability_loss', {'target_card_id': card.id})
    assert effective_combat_stats(state, card.id) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life,expected', [(20, -7), (13, 0), (12, 1), (1, 12), (0, 13), (-2, 13)])
def test_life_scaled_modifier_recalculates_and_clamps_negative_x(seat, life, expected):
    state, card = setup("Death's Shadow", seat)
    state.players[seat].life = life
    assert effective_combat_stats(state, card.id) == (expected, expected)
    from effects.registry import resolve_effect
    resolve_effect(state, seat, 'set_base_stats', {'target_card_id': card.id, 'base_power': 1, 'base_toughness': 1})
    assert effective_combat_stats(state, card.id) == (expected-12, expected-12)


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_token_preserves_expressions_and_recalculates_instead_of_copying_bonuses(seat):
    from effects.registry import resolve_effect
    state, card = setup('Tarmogoyf', seat)
    card.counters['+1/+1'] = 2
    resolve_effect(state, seat, 'create_token_copy', {'target_card_id': card.id})
    token = next(state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token)
    assert effective_combat_stats(state, token.id) == (6, 7)
    assert (token.printed_power, token.printed_toughness) == ('*', '1+*')
    resolve_effect(state, seat, 'temporary_ability_loss', {'target_card_id': token.id})
    assert effective_combat_stats(state, token.id) == (0, 1)
