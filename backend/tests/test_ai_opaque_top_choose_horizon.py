"""Count-only forecasts of canonical selection; never legal unknown-card plays."""
from copy import deepcopy
import json
from pathlib import Path
import pickle

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from ai.pending_effects import opaque_exile_opportunities, planning_copy, settled_public_position
from effects.handlers import copy_spell
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_strategic_pass import STYLES
from tests.test_static_ability_suppression import add as add_static


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / 'card_data/builtin_oracle_seed.json').read_text())['cards']
ROWS = {**SEED, **json.loads((ROOT / 'tests/fixtures/holding_spells/canonical.json').read_text())}
CARDS = {name: {**raw, 'power': raw.get('power'), 'toughness': raw.get('toughness'),
                'keywords': raw.get('keywords', [])} for name, raw in ROWS.items()}
NATURAL = Path('/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/holding-spells/natural-matrix/mtg-natural-matrix-LrSgLt/evidence')


def position(seat):
    state = bare_state(seat)
    state.turn = 16
    spell = add(state, 'Expressive Iteration', seat, Zone.HAND, cards=CARDS)
    state.players[seat].mana_pool.update({'U': 1, 'R': 1})
    return state, spell


def announce(state, spell, seat, perspective=None):
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    return decision_view(state, seat if perspective is None else perspective, [])[0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', STYLES)
def test_live_horizon_retains_only_count_value_and_root_immutability(seat, style):
    state, spell = position(seat)
    view = announce(state, spell, seat)
    before = pickle.dumps(view, protocol=5)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None
    player = projected.players[seat]
    assert len(player.hand) == len(player.exile) == 1
    assert len(player.library) == len(view.players[seat].library) - 2
    assert all(is_unknown(projected.cards[cid]) for cid in player.hand + player.exile + player.library)
    assert opaque_exile_opportunities(projected, seat) == ({
        'controller': seat, 'count': 1, 'expires_turn': view.turn,
        'permission': 'play', 'playability': 'unknown',
    },)
    assert not player.exile_play_until  # Count annotation is not a free spell permission.
    ai = AIAgent(difficulty='master', archetype=style)
    assert ai._strategic_position_score(view, seat) == ai._strategic_position_score(projected, seat)
    moves = RulesEngine().legal_moves(projected, seat)
    assert not any(m.get('card_id') in player.exile for m in moves)
    assert all(ai._materialize_action(projected, m, seat).get('_invalid_ai_choice')
               for m in moves if m.get('card_id') in player.hand)
    assert settled_public_position(view, seat) is None
    assert pickle.dumps(view, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('left,hand,exile', [(0, 0, 0), (1, 1, 0), (2, 1, 1), (3, 1, 1)])
def test_short_library_counts_and_selection_not_draw_failure(seat, left, hand, exile):
    state, spell = position(seat)
    removed = state.players[seat].library[left:]
    state.players[seat].library = state.players[seat].library[:left]
    for cid in removed:
        state.cards[cid].move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(cid)
    view = announce(state, spell, seat)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and projected.winner is None
    assert len(projected.players[seat].hand) == hand
    assert len(projected.players[seat].exile) == exile
    assert sum(r['count'] for r in opaque_exile_opportunities(projected, seat)) == exile


@pytest.mark.parametrize('seat', [1, 2])
def test_public_draw_and_library_cast_prohibitions_do_not_prohibit_selection(seat):
    state, spell = position(seat)
    add_static(state, 'Spirit of the Labyrinth', 3-seat)
    add(state, "Grafdigger's Cage", 3-seat, cards=CARDS)
    state.draws_this_turn[seat] = 1
    view = announce(state, spell, seat)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and len(projected.players[seat].hand) == 1
    assert projected.draws_this_turn[seat] == 1
    assert opaque_exile_opportunities(projected, seat)[0]['playability'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_order_identity_reload_and_wrong_perspective_are_conservative(seat):
    state, spell = position(seat)
    announced = planning_copy(state)
    RulesEngine().take_action(announced, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    assert settled_public_position(announced, seat, opaque_draw_counts=True) is None
    restored = deserialize_match_snapshot(serialize_match_snapshot(announced))
    view, _ = decision_view(restored, seat, [])
    permuted = planning_copy(view)
    for player in permuted.players.values():
        player.library.reverse()
    ai = AIAgent('master', 'Tempo')
    assert ai._strategic_position_score(view, seat) == ai._strategic_position_score(permuted, seat)
    assert settled_public_position(view, 3-seat, opaque_draw_counts=True) is None
    view.cards[view.players[seat].library[-1]] = deepcopy(state.cards[state.players[seat].library[-1]])
    assert settled_public_position(view, seat, opaque_draw_counts=True) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_opposing_selection_exposes_counts_not_opponent_identity(seat):
    state, spell = position(seat)
    view = announce(state, spell, seat, 3-seat)
    projected = settled_public_position(view, 3-seat, opaque_draw_counts=True)
    assert projected is not None
    assert all(is_unknown(projected.cards[cid]) for cid in projected.players[seat].hand + projected.players[seat].exile)
    assert sum(r['count'] for r in opaque_exile_opportunities(projected, seat)) == 1
    assert opaque_exile_opportunities(projected, 3-seat) == ()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('copy_controller', ['same', 'opponent'])
def test_actual_spell_copy_uses_controller_library_not_source_owner(seat, copy_controller):
    state, spell = position(seat)
    announce(state, spell, seat)
    controller = seat if copy_controller == 'same' else 3-seat
    copy_spell(state, controller, {'target_stack_id': state.stack[-1].id})
    state.cards[spell.id].oracle_text = ''  # Copy characteristics survive source changes.
    # Isolate the captured copy; do not forecast the modified original surface.
    original = state.stack.pop(0)
    view, _ = decision_view(state, controller, [])
    projected = settled_public_position(view, controller, opaque_draw_counts=True)
    assert projected is not None
    assert len(projected.players[controller].hand) == 1
    assert len(projected.players[3-controller].hand) == 0
    assert opaque_exile_opportunities(projected, controller)[0]['count'] == 1
    assert original.controller == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('copy_controller', ['same', 'opponent'])
def test_copy_and_original_each_count_their_own_resolution_library(seat, copy_controller):
    state, spell = position(seat)
    announce(state, spell, seat)
    controller = seat if copy_controller == 'same' else 3-seat
    copy_spell(state, controller, {'target_stack_id': state.stack[-1].id})
    view, _ = decision_view(state, seat, [])
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None
    assert len(projected.players[seat].hand) == (2 if controller == seat else 1)
    assert len(projected.players[3-seat].hand) == (0 if controller == seat else 1)
    assert sum(r['count'] for r in opaque_exile_opportunities(projected, seat)) == len(projected.players[seat].hand)


@pytest.mark.parametrize('seat', [1, 2])
def test_announced_real_counterspell_prevents_all_selection_gain(seat):
    state, spell = position(seat)
    counter = add(state, 'Counterspell', 3-seat, Zone.HAND, cards=CARDS)
    state.players[3-seat].mana_pool['U'] = 2
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    target = state.stack[-1].id
    rules.take_action(state, seat, {'type': 'pass_priority'}, reject_invalid=True)
    rules.take_action(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                                   'targets': {'target_stack_id': target}}, reject_invalid=True)
    view, _ = decision_view(state, seat, [])
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and projected.players[seat].hand == []
    assert not projected.players[seat].exile
    assert opaque_exile_opportunities(projected, seat) == ()


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_counter_then_fizzled_original_does_not_create_opportunities(seat):
    state, spell = position(seat)
    counter = add(state, 'Counterspell', 3-seat, Zone.HAND, cards=CARDS)
    state.players[3-seat].mana_pool['U'] = 2
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    target = state.stack[-1].id
    rules.take_action(state, seat, {'type': 'pass_priority'}, reject_invalid=True)
    rules.take_action(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                                   'targets': {'target_stack_id': target}}, reject_invalid=True)
    copy_spell(state, 3-seat, {'target_stack_id': state.stack[-1].id})
    view, _ = decision_view(state, seat, [])
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and projected.players[seat].hand == []
    assert not projected.stack and not projected.players[seat].exile
    assert opaque_exile_opportunities(projected, seat) == ()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['tail', 'duration', 'count', 'filter', 'preselection'])
def test_partial_effect_duration_or_incompatible_schema_does_not_claim_counts(seat, change):
    state, spell = position(seat)
    view = announce(state, spell, seat)
    payload = view.stack[-1].payload
    if change == 'tail':
        view.cards[spell.id].oracle_text += '\n' + SEED['Lightning Bolt']['oracle_text']
    elif change == 'duration':
        payload['play_exiled_until'] = view.turn + 1
    elif change == 'count':
        payload['top_n'] = 4
    elif change == 'filter':
        payload['contains'] = 'creature'
    else:
        payload['top_choice_hand_id'] = view.players[seat].library[-1]
    assert settled_public_position(view, seat, opaque_draw_counts=True) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_permission_count_expiry_and_diagnostic_record_are_not_mutable_authority(seat):
    state, spell = position(seat)
    view = announce(state, spell, seat)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    record = opaque_exile_opportunities(projected, seat)[0]
    record['count'] = 999
    assert opaque_exile_opportunities(projected, seat)[0]['count'] == 1
    projected.turn += 1
    assert opaque_exile_opportunities(projected, seat) == ()


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_resolution_known_choices_and_permissions_survive_snapshot(seat):
    state, spell = position(seat)
    state.mechanic_choice_players = {1, 2}
    rules = RulesEngine()
    rules.take_action(state, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    while state.pending_mechanic_choice is None:
        rules.take_action(state, state.priority_player, {'type': 'pass_priority'}, reject_invalid=True)
    choice = list(state.pending_mechanic_choice['options'])
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules.take_action(state, seat, {'type': 'choose_mechanic', 'card_ids': choice}, reject_invalid=True)
    assert choice[0] in state.players[seat].hand
    assert choice[1] in state.players[seat].exile
    assert state.players[seat].exile_play_until[choice[1]] == state.turn
    assert not is_unknown(state.cards[choice[1]])
    assert not opaque_exile_opportunities(state, seat)  # No forecast annotation in actual game.


@pytest.mark.parametrize('seat', [1, 2])
def test_opaque_paused_choice_keeps_hand_and_exile_count_continuity(seat):
    state, spell = position(seat)
    state.mechanic_choice_players = {1, 2}
    view = announce(state, spell, seat)
    rules = RulesEngine()
    while view.pending_mechanic_choice is None:
        rules.take_action(view, view.priority_player, {'type': 'pass_priority'}, reject_invalid=True)
    assert not view.stack and view.pending_mechanic_choice['kind'] == 'look_top_choose'
    before = pickle.dumps(view, protocol=5)
    projected = settled_public_position(view, seat, opaque_draw_counts=True)
    assert projected is not None and len(projected.players[seat].hand) == 1
    assert opaque_exile_opportunities(projected, seat)[0]['count'] == 1
    assert not projected.pending_mechanic_choice
    assert settled_public_position(view, seat) is None
    assert pickle.dumps(view, protocol=5) == before
    restored = deserialize_match_snapshot(serialize_match_snapshot(view))
    restored, _ = decision_view(restored, seat, [])
    resumed = settled_public_position(restored, seat, opaque_draw_counts=True)
    assert resumed is not None and len(resumed.players[seat].hand) == 1
    assert opaque_exile_opportunities(resumed, seat)[0]['count'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_unsupported_continuation_queue_does_not_turn_into_count_authority(seat):
    state, spell = position(seat)
    state.mechanic_choice_players = {1, 2}
    view = announce(state, spell, seat)
    rules = RulesEngine()
    while view.pending_mechanic_choice is None:
        rules.take_action(view, view.priority_player, {'type': 'pass_priority'}, reject_invalid=True)
    view.pending_mechanic_choice['remaining_draws'] = 1
    assert settled_public_position(view, seat, opaque_draw_counts=True) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_real_sorcery_timing_never_appears_on_opponent_turn(seat):
    state, spell = position(seat)
    state.active_player = 3-seat
    state.step = Step.UPKEEP
    assert not any(m.get('card_id') == spell.id for m in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', STYLES)
def test_actual_agent_legal_choice_and_reservation_are_root_pure_for_both_seats(seat, style):
    state, spell = position(seat)
    before = serialize_match_snapshot(state)
    rules = RulesEngine()
    legal = rules.legal_moves(state, seat)
    ai = AIAgent('master', style)
    choice = ai.choose_action(state, legal, seat)
    assert choice.action['type'] in {'cast_spell', 'pass_priority'}
    accepted = planning_copy(state)
    rules.take_action(accepted, seat, choice.action, reject_invalid=True)
    move = next(m for m in legal if m.get('card_id') == spell.id)
    assert ai._instant_value_reservation(state, move, seat) == 0
    assert serialize_match_snapshot(state) == before


def mirror_snapshot(snapshot):
    """Relabel seats only in known snapshot player-ID fields, never card facts/RNG."""
    maps = {'starting_decks', 'card_observations', 'foretells_this_turn', 'score', 'mulligan_count',
            'mulligan_bottomed', 'mulligan_declarations', 'priority_stops', 'spells_cast_this_turn',
            'kicked_spells_cast_this_turn', 'declared_attackers_this_turn', 'draws_in_current_draw_step',
            'draws_this_turn', 'surveils_this_turn', 'discards_this_turn', 'land_entries_this_turn', 'players'}
    lists = {'passed_priority', 'failed_draw_players', 'kept_hands', 'replacement_choice_players',
             'mechanic_choice_players', 'trigger_order_choice_players', 'turn_cant_gain_life'}
    scalars = {'owner', 'controller', 'active_player', 'priority_player', 'player_id',
               'current_controller', 'winner', 'target_player'}

    def visit(value, field=''):
        if isinstance(value, dict):
            result = {}
            for k, v in value.items():
                if field == 'players':
                    v = {**v, 'id': 3-v['id']}
                result[str(3-int(k)) if field in maps and k in {'1', '2'} else k] = visit(v, k)
            return result
        if isinstance(value, list):
            return [3-v if field in lists and type(v) is int and v in {1, 2} else visit(v) for v in value]
        return 3-value if field in scalars and type(value) is int and value in {1, 2} else value

    return visit(snapshot)


@pytest.mark.skipif(not NATURAL.exists(), reason='Optional archived natural decision fixture')
@pytest.mark.parametrize('tick', [433, 446])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', STYLES)
def test_saved_turn16_live_agent_restored_roots_and_opportunity_count(tick, seat, style):
    snapshot = json.loads((NATURAL / f'Tempo-Dimir_Control-seat2-tick{tick}.snapshot.json').read_text())
    if seat == 1:
        snapshot = mirror_snapshot(snapshot)
        assert mirror_snapshot(snapshot) == json.loads((NATURAL / f'Tempo-Dimir_Control-seat2-tick{tick}.snapshot.json').read_text())
    state = deserialize_match_snapshot(snapshot)
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    ai = AIAgent('master', style, 'Control')
    decision = ai.choose_action(state, legal, seat)
    assert decision.action['type'] in {'cast_spell', 'pass_priority'}
    permuted = planning_copy(state)
    for player in permuted.players.values():
        player.library.reverse()
    repeated = AIAgent('master', style, 'Control').choose_action(permuted, RulesEngine().legal_moves(permuted, seat), seat)
    assert repeated.action == decision.action
    view, moves = decision_view(state, seat, legal)
    move = next(m for m in moves if m.get('card_name') == 'Expressive Iteration')
    assert ai._instant_value_reservation(view, move, seat) == 0
    branch = planning_copy(view)
    RulesEngine().take_action(branch, seat, ai._materialize_action(view, move, seat), reject_invalid=True)
    projected = settled_public_position(branch, seat, opaque_draw_counts=True)
    assert projected is not None and len(projected.players[seat].hand) == 1
    assert sum(r['count'] for r in opaque_exile_opportunities(projected, seat)) == 1
    assert serialize_match_snapshot(state) == before
