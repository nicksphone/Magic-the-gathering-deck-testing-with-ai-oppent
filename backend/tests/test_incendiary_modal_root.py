"""Public full Oracle intake, paid modal contracts, and adversarial parser probes."""
import itertools
import json
from pathlib import Path
import pickle

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.ability_model import build_spell_spec
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import _extract_modes, _infer_closed_damage_instruction
from rules_engine.stack_engine import resolve_top_of_stack


FIXTURE = Path(__file__).parent / 'fixtures' / 'wheel_draw.json'
RAW = next(row for row in json.loads(FIXTURE.read_text())
           if row['name'] == 'Incendiary Command')
MODES = _extract_modes(RAW['oracle_text'])
PAIRS = list(itertools.combinations(range(4), 2))
EXPECTED_KEYS = ['deal_damage', 'damage_each_creature', 'destroy_permanent',
                 'each_player_discard']


def position(seat):
    deck = [{'card_name': 'Mountain', 'quantity': 32, 'type_line': 'Basic Land - Mountain',
             'oracle_text': ''}]
    state = MatchFactory.from_decks(deck, deck, seed=7134)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].mana_pool = {'R': 2, 'C': 3}
    sample = MatchFactory.from_decks([{**RAW, 'card_name': RAW['name'], 'quantity': 1}],
                                     [], seed=7135)
    source = next(iter(sample.cards.values()))
    source.id = state.allocate_object_id()
    source.owner = source.controller = seat
    source.move_to_zone(Zone.HAND)
    state.cards[source.id] = source
    state.players[seat].hand.append(source.id)
    # Declared synthetic test subjects, not canonical card payloads.
    for pid in (1, 2):
        creature = CardInstance(f'creature-{pid}', f'Declared creature {pid}', pid, pid,
                                Zone.BATTLEFIELD, ['Creature'], power=3, toughness=3,
                                type_line='Creature', oracle_text='')
        state.cards[creature.id] = creature
        state.players[pid].battlefield.append(creature.id)
    land = CardInstance('nonbasic', 'Declared nonbasic land', 3-seat, 3-seat,
                        Zone.BATTLEFIELD, ['Land'], type_line='Land', oracle_text='')
    state.cards[land.id] = land
    state.players[3-seat].battlefield.append(land.id)
    return state, source


def announced(seat, pair):
    return {'mode_texts': [MODES[index] for index in reversed(pair)],
            'mode_targets': {MODES[index]: {'target_player': 3-seat} if index == 0
                             else {'target_card_id': 'nonbasic'} if index == 2
                             else {} for index in pair}}


def reload(state):
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(state)
    return restored


def test_full_inherited_oracle_intake_is_not_shortened():
    assert RAW['id'] == '925d6ae9-deb8-41a4-99de-fd6fc6924d3b'
    assert RAW['oracle_id'] == 'd45a4924-daa0-4ac3-afd7-b66f636ce870'
    assert RAW['mana_cost'] == '{3}{R}{R}' and RAW['type_line'] == 'Sorcery'
    assert len(MODES) == 4 and len(RAW['oracle_text'].splitlines()) == 5
    state, source = position(1)
    assert source.oracle_text == RAW['oracle_text']
    assert source.name == RAW['name'] and source.mana_cost == RAW['mana_cost']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pair', PAIRS)
def test_full_canonical_selected_pairs_compile_every_branch_without_root_mutation(seat, pair):
    state, source = position(seat)
    before = pickle.dumps(state)
    spec = build_spell_spec(state, source, seat, announced(seat, pair),
                            report_unsupported=False)
    assert pickle.dumps(state) == before
    assert not spec.unsupported_resolution
    assert spec.effect.key == 'effect_sequence'
    assert [effect['effect_key'] for effect in spec.effect.payload['effects']] == [
        EXPECTED_KEYS[index] for index in pair]
    assert [effect['mode_text'] for effect in spec.effect.payload['effects']] == [
        MODES[index] for index in pair]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pair', PAIRS)
def test_full_canonical_paid_modes_restore_and_resolve_only_selected_effects(seat, pair):
    state, source = position(seat)
    before = pickle.dumps(state)
    original_discards = dict(state.discards_this_turn)
    assert original_discards == {1: 0, 2: 0}
    original_hands = {pid: set(player.hand) - {source.id}
                      for pid, player in state.players.items()}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': source.id,
                            'targets': announced(seat, pair)})
    assert state.cards[source.id].zone == Zone.STACK
    assert len(state.stack) == 1 and state.stack[-1].source_card_id == source.id
    assert all(value == 0 for value in state.players[seat].mana_pool.values())
    assert state.stack[-1].effect_key == 'effect_sequence'
    assert [effect['effect_key'] for effect in state.stack[-1].payload['effects']] == [
        EXPECTED_KEYS[index] for index in pair]
    assert pickle.dumps(state) != before
    state = reload(state)
    assert resolve_top_of_stack(state)
    state = reload(state)
    assert not state.stack and not state.pending_mechanic_choice
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert state.cards[source.id].oracle_text == RAW['oracle_text']
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == (16 if 0 in pair else 20)
    assert state.cards['nonbasic'].zone == (Zone.GRAVEYARD if 2 in pair else Zone.BATTLEFIELD)
    for pid in (1, 2):
        assert state.cards[f'creature-{pid}'].counters.get('__damage_marked', 0) == (
            2 if 1 in pair else 0)
        assert len(state.players[pid].hand) == len(original_hands[pid])
        assert all(state.cards[cid].zone == (Zone.GRAVEYARD if 3 in pair else Zone.HAND)
                   for cid in original_hands[pid])
    assert state.discards_this_turn == ({pid: len(cards) for pid, cards in original_hands.items()}
                                       if 3 in pair else original_discards)


@pytest.mark.parametrize('suffix', [' Draw a card.', ' if you control an Island.',
                                    ' and each player.', ' except creatures with flying.'])
@pytest.mark.parametrize('mode_index', [0, 1, 2, 3])
def test_adversarial_unselected_unknown_suffix_cannot_reward_selected_prefix(suffix, mode_index):
    # Explicit malformed parser input only. Never mutate a canonical runtime Oracle.
    lines = RAW['oracle_text'].splitlines()
    lines[mode_index + 1] += suffix
    malformed = '\n'.join(lines)
    selected = [MODES[index] for index in range(4) if index != mode_index][:2]
    key, payload = _infer_closed_damage_instruction(malformed, RAW['name'],
                                                    {'mode_texts': selected})
    assert key == 'noop' and payload['__unsupported_instruction'] == malformed


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['missing_player', 'basic_land', 'unoffered', 'duplicate'])
def test_invalid_canonical_announcements_reject_without_root_mutation(seat, invalid):
    state, source = position(seat)
    targets = announced(seat, (0, 2))
    if invalid == 'missing_player':
        targets['mode_targets'][MODES[0]] = {}
    elif invalid == 'basic_land':
        basic = state.players[3-seat].hand[0]
        state.players[3-seat].hand.remove(basic)
        state.players[3-seat].battlefield.append(basic)
        state.cards[basic].move_to_zone(Zone.BATTLEFIELD)
        targets['mode_targets'][MODES[2]] = {'target_card_id': basic}
    elif invalid == 'unoffered':
        targets['mode_texts'] = [MODES[0], 'Draw a card']
    else:
        targets['mode_texts'] = [MODES[0], MODES[0]]
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
                       {'type': 'cast_spell', 'card_id': source.id, 'targets': targets})
    assert pickle.dumps(state) == before
