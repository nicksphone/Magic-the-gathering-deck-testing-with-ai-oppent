"""Canonical facts at the actual consumers, not just unused helper builders."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.copiable_values import FIELDS, PHYSICAL
from rules_engine.engine import RulesEngine
from tests import test_ai_information_boundary as information
from tests import test_ai_minimax as minimax
from tests import test_ai_opaque_draw_horizon as opaque
from tests import test_ai_pending_deployment as deployment
from tests import test_ai_search_prefix as search
from tests import test_ai_symmetric_draw as symmetric
from tests import ai_information76_canonical as canonical

NAMES = ('Lightning Bolt', 'Counterspell', 'Divination', 'Vision Skeins', 'Prosperity', 'Island')


def assert_printed(card, name):
    raw = canonical.raw_card(name)
    expected = canonical.canonical_card(name, id=card.id, owner=card.owner,
                                        controller=card.controller, zone=card.zone)
    assert raw['object'] == 'card' and len(raw) >= 30
    for field in PHYSICAL:
        assert getattr(card, field) == getattr(expected, field), field
    assert card.characteristic_record == expected.characteristic_record
    assert card.characteristic_record['physical'] == {key: getattr(card, key) for key in PHYSICAL}
    assert card.characteristic_record['values'] == {key: getattr(card, key) for key in FIELDS}


class Captured(Exception):
    pass


def first_state(monkeypatch, module, hook, function, *args):
    found = []
    def capture(state, *_args, **_kwargs):
        found.append(state)
        raise Captured
    with monkeypatch.context() as patch:
        patch.setattr(module, hook, capture)
        with pytest.raises(Captured):
            function(*args)
    assert len(found) == 1
    return found[0]


@pytest.mark.parametrize('seat', [1, 2])
def test_bare_factory_stock_and_rng_are_canonical_at_birth(seat):
    state = search.bare_state(seat)
    rng = random.Random(6781)
    rng.shuffle(list(range(60)))
    rng.shuffle(list(range(60)))
    assert state.rng.getstate() == rng.getstate()
    assert set(state.cards) == {f'p{pid}-{i:03d}' for pid in (1, 2) for i in range(1, 61)}
    for pid, player in state.players.items():
        assert player.library == [f'p{pid}-{i:03d}' for i in range(1, 54)] + [f'p{pid}-{i:03d}' for i in range(60, 53, -1)]
        assert player.hand == [] and player.mana_pool == dict.fromkeys(('W', 'U', 'B', 'R', 'G', 'C'), 0)
        for cid in player.library:
            assert_printed(state.cards[cid], 'Island')
    assert all(v['stock_key'] == 'Island' for v in state.sideboard_facts['inventory'].values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('card_id,name', [('bolt', 'Lightning Bolt'), ('counter', 'Counterspell')])
def test_counter_setup_full_facts_before_any_decision(seat, card_id, name):
    state, _, _ = information.counter_position(seat)
    assert_printed(state.cards[card_id], name)


@pytest.mark.parametrize('seat', [1, 2])
def test_information_body_reaches_observer_with_full_named_inputs(monkeypatch, seat):
    state = first_state(monkeypatch, information, 'serialize_match_snapshot',
                        information.test_all_agent_paths_receive_only_their_allowed_information,
                        seat, 'Control', 'casual')
    assert_printed(state.cards['own'], 'Lightning Bolt')
    assert_printed(state.cards['hidden'], 'Counterspell')


@pytest.mark.parametrize('seat', [1, 2])
def test_divination_first_legal_move_consumer_has_full_facts(monkeypatch, seat):
    found = []
    original = RulesEngine.legal_moves
    def observe(engine, state, actor, *args, **kwargs):
        found.append(deepcopy(state.cards['draw']))
        return original(engine, state, actor, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine, 'legal_moves', observe)
        state, _, _ = opaque.draw_position(seat)
    assert found
    assert_printed(found[0], 'Divination')
    assert_printed(state.cards['draw'], 'Divination')


@pytest.mark.parametrize('seat', [1, 2])
def test_opaque_counter_is_canonical_before_actual_announcement(monkeypatch, seat):
    found = []
    original = RulesEngine.take_action
    def observe(engine, state, actor, move, **kwargs):
        if move.get('card_id') == 'counter':
            found.append(deepcopy(state.cards['counter']))
        return original(engine, state, actor, move, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine, 'take_action', observe)
        opaque.test_actual_announced_counterspell_prevents_projected_draw(seat)
    assert len(found) == 1
    assert_printed(found[0], 'Counterspell')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['counter', 'draw'])
def test_pending_inputs_are_canonical_before_action(monkeypatch, seat, kind):
    found = []
    def capture(_engine, state, *_args, **_kwargs):
        found.append(state)
        raise Captured
    function = (deployment.test_horizon_keeps_actual_counter_response_value_and_original_stack
                if kind == 'counter' else deployment.test_pending_hidden_library_change_is_not_a_known_forecast)
    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine, 'take_action', capture)
        with pytest.raises(Captured):
            function(seat)
    assert len(found) == 1
    assert_printed(found[0].cards[kind], 'Counterspell' if kind == 'counter' else 'Divination')


@pytest.mark.parametrize('seat', [1, 2])
def test_search_stack_consumer_gets_full_real_facts(monkeypatch, seat):
    state = first_state(monkeypatch, search, 'add_to_stack',
                        search.test_real_counter_response_matches_actor_correct_reference,
                        seat, 0, 'Control')
    assert_printed(state.cards['bolt'], 'Lightning Bolt')
    assert_printed(state.cards['counter'], 'Counterspell')


def test_minimax_stack_consumer_gets_full_facts(monkeypatch):
    state = first_state(monkeypatch, minimax, 'add_to_stack',
                        minimax.test_strategic_search_rejects_unpayable_cast_instead_of_scoring_noop,
                        monkeypatch)
    assert_printed(state.cards['threat'], 'Lightning Bolt')
    assert_printed(state.cards['counter'], 'Counterspell')


@pytest.mark.parametrize('name', ['Vision Skeins', 'Prosperity'])
def test_symmetric_actual_factory_birth_not_stock_repair(monkeypatch, name):
    found = []
    original = MatchFactory.from_decks
    def observe(deck_a, deck_b, *args, **kwargs):
        state = original(deck_a, deck_b, *args, **kwargs)
        if kwargs.get('seed') == 318:
            found.append((deepcopy(state), deepcopy(deck_a), deepcopy(deck_b)))
        return state
    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', observe)
        if name == 'Vision Skeins':
            state, _ = symmetric._position()
        else:
            symmetric.test_ai_checks_x_draw_against_both_library_sizes()
    assert len(found) == 1
    birth, deck_a, deck_b = found[0]
    cid = birth.players[1].hand[0]
    assert cid == 'p1-060'
    assert_printed(birth.cards[cid], name)
    assert birth.sideboard_facts['inventory'][cid]['stock_key'] == name
    assert sum(item['quantity'] for item in deck_a) == 60
    assert sum(item['quantity'] for item in deck_b) == 60
    assert all(item.get('oracle_text') == canonical.raw_card(item['card_name']).get('oracle_text', '')
               for item in deck_a + deck_b)
    rng = random.Random(318)
    rng.shuffle(list(range(60))); rng.shuffle(list(range(60)))
    assert birth.rng.getstate() == rng.getstate()
    for pid, player in birth.players.items():
        assert player.hand == [f'p{pid}-{i:03d}' for i in range(60, 53, -1)]
        assert player.library == [f'p{pid}-{i:03d}' for i in range(1, 54)]
    if name == 'Vision Skeins':
        assert_printed(state.cards[cid], name)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_hidden_replacement_is_full_canonical_not_partial_retag(monkeypatch, seat):
    seen = []
    original = AIAgent.choose_action
    def observe(ai, state, moves, actor):
        seen.append(deepcopy(state.cards['counter']))
        return original(ai, state, moves, actor)
    with monkeypatch.context() as patch:
        patch.setattr(AIAgent, 'choose_action', observe)
        information.test_real_decisions_ignore_unexposed_hand_and_library_identity(seat, 'Control', 'casual')
    assert len(seen) == 2
    assert_printed(seen[0], 'Counterspell')
    assert_printed(seen[1], 'Island')


@pytest.mark.parametrize('seat', [1, 2])
def test_distinct_real_hidden_identities_and_order_are_observationally_equal(seat):
    state, bolt, counter = information.counter_position(seat)
    first, _ = decision_view(state, seat, [])
    alternate = deepcopy(state)
    hidden = canonical.canonical_card('Island', id=counter.id, owner=counter.owner,
                                      controller=counter.controller, zone=counter.zone)
    alternate.cards[counter.id] = hidden
    for player in alternate.players.values():
        player.library.reverse()
    second, _ = decision_view(alternate, seat, [])
    assert {cid: card.__dict__ for cid, card in first.cards.items()} == {
        cid: card.__dict__ for cid, card in second.cards.items()}
    assert first.players[3-seat].hand == second.players[3-seat].hand
    assert all(not first.cards[cid].name and not second.cards[cid].name
               for player in first.players.values() for cid in player.library)
    assert_printed(state.cards[counter.id], 'Counterspell')
    assert_printed(alternate.cards[counter.id], 'Island')


@pytest.mark.parametrize('name', NAMES)
def test_full_raw_materializer_and_snapshot_preserve_all_printed_fields(name):
    card = canonical.canonical_card(name, id='printed', owner=1, controller=1, zone=Zone.HAND)
    state = search.bare_state()
    state.cards[card.id] = card
    state.players[1].hand.append(card.id)
    assert_printed(card, name)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert_printed(restored.cards[card.id], name)


@pytest.mark.parametrize('field', ['oracle_text', 'colors', 'characteristic_record'])
def test_consumer_fidelity_rejects_printed_tamper(field):
    card = canonical.canonical_card('Lightning Bolt', id='tamper', owner=1, controller=1, zone=Zone.HAND)
    setattr(card, field, {'oracle_text': '', 'colors': ['U'], 'characteristic_record': None}[field])
    with pytest.raises(AssertionError):
        assert_printed(card, 'Lightning Bolt')


@pytest.mark.parametrize('field', ['oracle_text', 'colors', 'characteristic_record'])
def test_runtime_pose_cannot_override_printed_facts(field):
    with pytest.raises(ValueError):
        canonical.canonical_card('Lightning Bolt', **{field: None})


def test_source_tamper_is_rejected_before_materialization(monkeypatch):
    original = Path.read_bytes
    def changed(path):
        data = original(path)
        if path.name == 'seed155-scryfall.jsonl':
            return data + b' '
        return data
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_bytes', changed)
        with pytest.raises(AssertionError):
            canonical.raw_card('Island')


@pytest.mark.parametrize('seat', [1, 2])
def test_retained_foretell_body_reaches_real_checked_action_without_HTTP_imports(monkeypatch, seat):
    from rules_engine import action_validation
    seen = []
    original = action_validation.checked_action
    def observe(state, engine, actor, action, *args, **kwargs):
        seen.append(deepcopy(state))
        return original(state, engine, actor, action, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(action_validation, 'checked_action', observe)
        information.test_foretold_owner_can_still_inspect_their_real_card_and_cast_cost(seat)
    assert len(seen) == 1
    state = seen[0]
    source = state.cards[state.players[seat].hand[0]]
    assert source.id == '00000000-0000-0000-0000-000000000001'
    assert_printed(source, 'Behold the Multiverse')
    assert state.players[seat].mana_pool == {'C': 2}
    assert state.turn == 5 and state.active_player == state.priority_player == seat
    rng = random.Random(941)
    rng.shuffle(list(range(60))); rng.shuffle(list(range(60)))
    assert state.rng.getstate() == rng.getstate()
    assert len(state.sideboard_facts['inventory']) == 120
    for cid, binding in state.sideboard_facts['inventory'].items():
        assert binding['stock_key'] == 'Swamp'
        assert_printed(state.cards[cid], 'Swamp')


@pytest.mark.parametrize('seat', [1, 2])
def test_retained_restriction_body_uses_canonical_static_entry_without_HTTP_imports(monkeypatch, seat):
    found = []
    original = RulesEngine.take_action
    def observe(engine, state, actor, action, **kwargs):
        found.extend(deepcopy(state.cards[cid]) for player in state.players.values()
                     for cid in player.battlefield if state.cards[cid].name == 'Spirit of the Labyrinth')
        return original(engine, state, actor, action, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine, 'take_action', observe)
        opaque.test_public_count_uses_real_draw_restrictions(seat, 0, 1)
    assert found
    for card in found:
        assert_printed(card, 'Spirit of the Labyrinth')
        assert card.owner == card.controller == 3-seat
        assert card.battlefield_incarnation == card.effect_timestamp > 0
