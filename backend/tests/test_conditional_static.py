"""Canonical static clauses; fixtures are not whole-card certification."""
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_combat_stats, effective_keywords
from tests.test_activation_modifiers import board
from tests.test_api_input_contracts import game, persist
from tests.test_offline_match_hydration import forbid_network
import main

REAL_HYDRATE = main._hydrate_deck_cards

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/conditional_static.json').read_text())}
CASES = {
    'Nimble Mongoose': ('graveyard', 2, 2, None),
    'Werebear': ('graveyard', 3, 3, None),
    'Krosan Beast': ('graveyard', 7, 7, None),
    'Mystic Enforcer': ('graveyard', 3, 3, 'flying'),
    'Mystic Zealot': ('graveyard', 1, 1, 'flying'),
    'Carapace Forger': ('artifacts', 2, 2, None),
    'Ardent Recruit': ('artifacts', 2, 2, None),
    'Auriok Sunchaser': ('artifacts', 2, 2, 'flying'),
    'Jor Kadeen, the Prevailer': ('artifacts', 3, 0, None),
    'Etched Champion': ('artifacts', 0, 0, 'protection from red'),
    'Grim Flayer': ('card_types', 2, 2, None),
    'Gnarlwood Dryad': ('card_types', 2, 2, None),
    'Moldgraf Scavenger': ('card_types', 3, 0, None),
    'Gathan Raiders': ('hand', 2, 2, None),
    'Rakdos Pit Dragon': ('hand', 0, 0, 'double strike'),
    'Serra Ascendant': ('life', 5, 5, 'flying'),
    'Abzan Kin-Guard': ('colors', 0, 0, 'lifelink'),
    'Wild Nacatl': ('land_types', 2, 2, None),
    "Dragon's Rage Channeler": ('card_types', 2, 2, 'flying'),
}


def add(state, name, seat=1, zone=Zone.BATTLEFIELD):
    raw = ROWS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=7)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def setup(name, seat=1, active=False):
    state = board(seat)
    card = add(state, name, seat)
    group = CASES[name][0]
    resources = []
    if group == 'graveyard':
        resources = [add(state, 'Forest', seat, Zone.GRAVEYARD) for _ in range(6 + int(active))]
    elif group == 'artifacts':
        resources = [add(state, 'Darksteel Citadel', seat) for _ in range(2 + int(active) - int('Artifact' in card.types))]
    elif group == 'card_types':
        resources = [add(state, item, seat, Zone.GRAVEYARD) for item in ['Forest', 'Grizzly Bears', 'Counterspell']]
        if active:
            resources.append(add(state, 'All Is Dust', seat, Zone.GRAVEYARD))
    elif group == 'hand' and not active:
        resources = [add(state, 'Forest', seat, Zone.HAND)]
    elif group == 'life':
        state.players[seat].life = 30 if active else 29
    elif group == 'colors' and active:
        resources = [add(state, 'Savannah Lions', seat)]
    elif group == 'land_types' and active:
        resources = [add(state, item, seat) for item in ['Mountain', 'Plains']]
    return state, card, resources


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('active', [False, True])
@pytest.mark.parametrize('name', list(CASES))
def test_canonical_conditional_stats_and_keywords_use_live_resources(seat, active, name):
    state, card, _ = setup(name, seat, active)
    _, p, t, keyword = CASES[name]
    expected = (int(ROWS[name]['power']) + p * active, int(ROWS[name]['toughness']) + t * active)
    before = serialize_match_snapshot(state)
    assert effective_combat_stats(state, card.id) == expected
    if keyword:
        assert (keyword in effective_keywords(state, card.id)) == active
    if name == 'Rakdos Pit Dragon':
        assert 'flying' not in effective_keywords(state, card.id)
    if name == 'Jor Kadeen, the Prevailer':
        own = add(state, 'Grizzly Bears', seat)
        enemy = add(state, 'Grizzly Bears', 3-seat)
        assert effective_combat_stats(state, own.id) == (2 + 3 * active, 2)
        assert effective_combat_stats(state, enemy.id) == (2, 2)
        before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(before)
    assert effective_combat_stats(restored, card.id) == expected
    assert effective_keywords(restored, card.id) == effective_keywords(state, card.id)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(CASES))
def test_resources_can_turn_off_and_back_on_without_cached_results(name, seat):
    state, card, resources = setup(name, seat, True)
    active_stats = effective_combat_stats(state, card.id)
    group = CASES[name][0]
    if group == 'life':
        state.players[seat].life = 29
    elif group == 'hand':
        resources = [add(state, 'Forest', seat, Zone.HAND)]
    else:
        resource = resources[-1]
        getattr(state.players[seat], resource.zone.value).remove(resource.id)
        resource.move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(resource.id)
    _, p, t, keyword = CASES[name]
    # Wild Nacatl loses just the Plains bonus; the Mountain remains.
    remaining = 1 if name == 'Wild Nacatl' else 0
    assert effective_combat_stats(state, card.id) == (
        int(ROWS[name]['power']) + remaining, int(ROWS[name]['toughness']) + remaining)
    if keyword:
        assert keyword not in effective_keywords(state, card.id)
    if group == 'life':
        state.players[seat].life = 30
    elif group == 'hand':
        state.players[seat].hand.remove(resources[0].id)
        resources[0].move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(resources[0].id)
    else:
        state.players[seat].exile.remove(resource.id)
        destination = Zone.GRAVEYARD if group in {'graveyard', 'card_types'} else Zone.BATTLEFIELD
        resource.move_to_zone(destination)
        getattr(state.players[seat], destination.value).append(resource.id)
    assert effective_combat_stats(state, card.id) == active_stats
    if keyword:
        assert keyword in effective_keywords(state, card.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_conditional_ward_uses_live_source_and_recipient_scope(seat):
    from rules_engine.ward import ward_instances
    state = board(seat)
    source = add(state, 'K-9, Mark I', seat)
    own = add(state, 'Iymrith, Desert Doom', seat)
    other = add(state, 'Iymrith, Desert Doom', 3-seat)
    ordinary = add(state, 'Grizzly Bears', seat)
    assert sorted(ward_instances(state, own)) == ['{1}', '{4}']
    assert ward_instances(state, source) == []
    assert ward_instances(state, other) == ['{4}']
    assert ward_instances(state, ordinary) == []
    source.tapped = True
    assert ward_instances(state, own) == ['{4}']
    own.tapped = True
    assert ward_instances(state, own) == []
    source.tapped = False
    assert ward_instances(state, own) == ['{1}']
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert ward_instances(restored, restored.cards[own.id]) == ['{1}']


@pytest.mark.parametrize('seat', [1, 2])
def test_ward_family_removal_and_later_grant_follow_effect_timestamps(seat):
    from rules_engine.ward import ward_instances
    from rules_engine.keyword_effects import add_keyword_effect
    state = board(seat)
    card = add(state, 'Iymrith, Desert Doom', seat)
    assert ward_instances(state, card) == ['{4}']
    add_keyword_effect(state, card.id, ['ward'], operation='remove')
    assert ward_instances(state, card) == []
    add_keyword_effect(state, card.id, ['ward', 'ward {2}'])
    assert ward_instances(state, card) == ['{2}']
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert ward_instances(restored, restored.cards[card.id]) == ['{2}']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('active', [False, True])
def test_delirium_combines_stats_keywords_and_attack_requirement(seat, active):
    from rules_engine.combat_requirements import requirement_weights
    state, card, _ = setup("Dragon's Rage Channeler", seat, active)
    assert requirement_weights(state, [card.id], 'attack')[card.id] == int(active)


@pytest.mark.parametrize('seat', [1, 2])
def test_threshold_does_not_count_tokens_as_cards(seat):
    state, card, _ = setup('Nimble Mongoose', seat, False)
    token = add(state, 'Grizzly Bears', seat, Zone.GRAVEYARD)
    token.is_token = True
    assert effective_combat_stats(state, card.id) == (1, 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_resource_condition_tracks_controller_not_owner(seat):
    state, card, _ = setup('Werebear', seat, True)
    assert effective_combat_stats(state, card.id) == (4, 4)
    state.players[seat].battlefield.remove(card.id)
    card.controller = 3-seat
    state.players[3-seat].battlefield.append(card.id)
    assert effective_combat_stats(state, card.id) == (1, 1)
    for _ in range(7):
        add(state, 'Forest', 3-seat, Zone.GRAVEYARD)
    assert effective_combat_stats(state, card.id) == (4, 4)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(CASES))
def test_ai_entry_projection_uses_live_conditional_resources(seat, name):
    from ai.pending_effects import prospective_creature_stats, decision_projection_scope
    state, card, _ = setup(name, seat, True)
    expected = effective_combat_stats(state, card.id)
    state.players[seat].battlefield.remove(card.id)
    card.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(card.id)
    before = serialize_match_snapshot(state)
    with decision_projection_scope(state, seat):
        assert prospective_creature_stats(state, card, seat) == expected
        assert prospective_creature_stats(state, card, seat) == expected
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nimble Mongoose', 'Auriok Sunchaser', "Dragon's Rage Channeler", 'Iymrith, Desert Doom'])
def test_cached_conditional_card_survives_http_and_sqlite_resume(game, monkeypatch, seat, name):
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from game_state.serializers import serialize_card_view
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
    deck = [{'quantity': 4, 'card_name': name}, {'quantity': 56, 'card_name': 'Forest'}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'seed': 117})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state = controller.state
    card = next(c for c in state.cards.values() if c.name == name and c.owner == seat)
    getattr(state.players[seat], card.zone.value).remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(card.id)
    if name == 'Nimble Mongoose':
        for _ in range(7):
            add(state, 'Forest', seat, Zone.GRAVEYARD)
    elif name == 'Auriok Sunchaser':
        for _ in range(3):
            add(state, 'Darksteel Citadel', seat)
    elif name == "Dragon's Rage Channeler":
        for item in ['Forest', 'Grizzly Bears', 'Counterspell', 'All Is Dust']:
            add(state, item, seat, Zone.GRAVEYARD)
    view = serialize_card_view(state, card.id)
    assert effective_combat_stats(state, card.id) == {'Nimble Mongoose': (3, 3), 'Auriok Sunchaser': (3, 3), "Dragon's Rage Channeler": (3, 3), 'Iymrith, Desert Doom': (5, 5)}[name]
    persist(controller)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id].state
    assert serialize_card_view(restored, card.id) == view
