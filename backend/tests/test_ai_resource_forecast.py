"""Known-composition draws are priors, never peeks at library instances."""
from copy import deepcopy
from math import comb

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
from rules_engine.cast_choice import build_cast_hints
from tests.test_discard_history import ROWS
from tests.test_linked_discard import ROWS as LINKED_ROWS
from tests.test_legendary_channels import resolve_to_choice


def position(seat=1, lands=48, board_lands=5, remaining_spell='Lightning Bolt',
             source_name='Cathartic Pyre', cast=True):
    source_data = {**ROWS, **LINKED_ROWS}[source_name]
    deck = [{**fallback_card_payload('Mountain'), 'card_name': 'Mountain', 'quantity': lands},
            {**fallback_card_payload('Ugin, the Spirit Dragon'), 'card_name': 'Ugin, the Spirit Dragon', 'quantity': 2},
            {**fallback_card_payload(remaining_spell), 'card_name': remaining_spell, 'quantity': 57-lands},
            {**source_data, 'card_name': source_name, 'quantity': 1}]
    state = MatchFactory.from_decks(deck, deck, seed=1992)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    player = state.players[seat]
    player.library.extend(player.hand)
    for cid in player.hand:
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    player.hand.clear()
    for name, zone, count in [('Mountain', Zone.BATTLEFIELD, board_lands),
                             ('Ugin, the Spirit Dragon', Zone.HAND, 2), (source_name, Zone.HAND, 1)]:
        for _ in range(count):
            cid = next(cid for cid in player.library if state.cards[cid].name == name)
            player.library.remove(cid)
            state.cards[cid].move_to_zone(zone)
            if zone != Zone.STACK:
                getattr(player, zone.value).append(cid)
    spell = next(state.cards[cid] for cid in player.hand if state.cards[cid].name == source_name)
    targets = {}
    if source_name == 'Cathartic Pyre':
        targets['mode_text'] = next(mode for mode in build_cast_hints(state, spell, seat)['modes'] if mode.startswith('Discard'))
    player.mana_pool = {'R': 2, 'U': 1, 'C': 2}
    state.mechanic_choice_players = {1, 2}
    if not cast:
        return state
    return resolve_to_choice(checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets}))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Ramp', 'Aggro', 'Tokens', 'Drain'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_actual_rummage_retains_spells_against_land_heavy_remaining_composition(seat, style, difficulty):
    state = position(seat)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty=difficulty, archetype=style)
    action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert action['card_ids'] == []
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_land_light_board_can_recycle_expensive_cards_to_find_resources(seat, difficulty):
    state = position(seat, board_lands=2)
    agent = AIAgent(difficulty=difficulty, archetype='Ramp')
    action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert len(action['card_ids']) == 2
    resolved = checked_action(state, RulesEngine(), seat, action)
    assert len(resolved.players[seat].hand) == 2
    assert not resolved.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('draws', [0, 1, 2, 5])
def test_hypergeometric_prior_and_hidden_identity_invariance(seat, draws):
    from ai.information import draw_resource_forecast
    state = position(seat, lands=24)
    view, _ = decision_view(state, seat, [])
    before = serialize_match_snapshot(state)
    result = draw_resource_forecast(view, seat, draws)
    assert result['expected_lands'] == pytest.approx(draws * 19/52)
    assert result['probability_land'] == pytest.approx(1-comb(33, draws)/comb(52, draws))
    for pid, player in state.players.items():
        player.library.reverse()
        for cid in player.library:
            state.cards[cid].name = 'Counterspell'
            state.cards[cid].oracle_text = 'Counter target spell.'
            state.cards[cid].types = ['Instant']
    changed, _ = decision_view(state, seat, [])
    assert draw_resource_forecast(changed, seat, draws) == result
    restored, _ = decision_view(deserialize_match_snapshot(before), seat, [])
    assert draw_resource_forecast(restored, seat, draws) == result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('gap', ['legacy', 'unknown_exile', 'missing_metadata', 'inconsistent_count'])
def test_unreconciled_inventory_is_explicitly_unknown(seat, gap):
    from ai.information import draw_resource_forecast
    state = position(seat)
    if gap == 'legacy':
        state.starting_decks.clear()
    elif gap == 'unknown_exile':
        cid = state.players[seat].library.pop()
        state.players[seat].exile.append(cid)
        state.cards[cid].move_to_zone(Zone.EXILE)
        state.cards[cid].exile_face_down = True
        state.cards[cid].foretell_owner = 3-seat
    elif gap == 'missing_metadata':
        state.starting_decks[seat][0] = {'card_name': 'Unresolved metadata fixture', 'quantity': 48}
    else:
        state.players[seat].library.pop()
    view, _ = decision_view(state, seat, [])
    assert draw_resource_forecast(view, seat, 2) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_owned_stolen_land_and_token_copy_do_not_change_inventory(seat):
    from ai.information import draw_resource_forecast
    state = position(seat)
    view, _ = decision_view(state, seat, [])
    expected = draw_resource_forecast(view, seat, 2)
    cid = state.players[seat].battlefield.pop()
    state.players[3-seat].battlefield.append(cid)
    state.cards[cid].controller = 3-seat
    token = deepcopy(state.cards[cid])
    token.id = 'land-copy-token'
    token.is_token = True
    state.cards[token.id] = token
    state.players[seat].battlefield.append(token.id)
    view, _ = decision_view(state, seat, [])
    assert draw_resource_forecast(view, seat, 2) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_spell_heavy_remaining_composition_can_improve_expensive_hand(seat, difficulty):
    state = position(seat, lands=6)
    agent = AIAgent(difficulty=difficulty, archetype='Tempo')
    action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert len(action['card_ids']) == 2
    resolved = checked_action(state, RulesEngine(), seat, action)
    assert len(resolved.players[seat].hand) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_equal_expensive_draws_do_not_get_fictitious_five_point_credit(seat):
    state = position(seat, lands=5, remaining_spell='Ugin, the Spirit Dragon')
    agent = AIAgent(archetype='Ramp')
    action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert action['card_ids'] == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name', ['Tolarian Winds', 'Dangerous Wager'])
@pytest.mark.parametrize('lands', [6, 48])
def test_whole_hand_draw_admission_uses_same_prior(seat, source_name, lands):
    state = position(seat, lands=lands, source_name=source_name, cast=False)
    view, _ = decision_view(state, seat, [])
    source = next(view.cards[cid] for cid in view.players[seat].hand if view.cards[cid].name == source_name)
    agent = AIAgent(archetype='Tempo')
    assert agent._bad_shared_draw_cast(view, {'type': 'cast_spell', 'card_id': source.id}, seat) == (lands == 48)


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_resolution_source_remains_public_and_resume_keeps_prior(seat):
    from ai.information import draw_resource_forecast
    state = position(seat)
    assert not state.stack
    source = state.pending_mechanic_choice['resolving_item']['source_card_id']
    view, _ = decision_view(state, seat, [])
    assert view.cards[source].name == 'Cathartic Pyre'
    restored, _ = decision_view(deserialize_match_snapshot(serialize_match_snapshot(state)), seat, [])
    assert draw_resource_forecast(view, seat, 2) == draw_resource_forecast(restored, seat, 2)


@pytest.mark.parametrize('seat', [1, 2])
def test_forecast_requires_private_matching_actor_and_exchangeable_library(seat):
    from ai.information import draw_resource_forecast
    state = position(seat)
    assert draw_resource_forecast(state, seat, 2) is None
    cid = state.players[seat].library[-1]
    view, _ = decision_view(state, seat, [{'type': 'cast_spell', 'card_id': cid}])
    assert draw_resource_forecast(view, seat, 2) is None
    assert draw_resource_forecast(view, 3-seat, 2) is None


@pytest.mark.parametrize('draws', [-1, 53])
def test_out_of_bounds_draws_are_unknown_not_probabilities(draws):
    from ai.information import draw_resource_forecast
    state, _ = decision_view(position(), 1, [])
    assert draw_resource_forecast(state, 1, draws) is None
