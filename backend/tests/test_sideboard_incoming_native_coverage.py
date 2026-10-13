"""Whole printed incoming coverage; trusted paid rules poses, not natural BO3."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ai import sideboard_policy as policy
from card_data.hydration import hydrate_deck_cards
from knowledge.profiles import derive_profile, merge_profile_payload
from knowledge.service import tags_for
from rules_engine.ability_model import build_spell_spec
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.test_sideboard_finished_transition import MetadataRows
from tests.test_task23_checked_removal_baseline import add_profiled
from tests.vraska_full import test_full_vraska as rules


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Negate', 'Go for the Throat'])
def test_paid_native_whole_answer_is_not_blanket_rejected_as_incoming(seat, name):
    state = rules.bare(seat)
    for player in state.players.values():
        player.mana_pool = {}
    source = add_profiled(state, RAW[name], seat, rules.Zone.HAND)
    if name == 'Negate':
        opposing = add_profiled(state, RAW['Lightning Bolt'], 3-seat, rules.Zone.HAND)
        state.active_player = state.priority_player = 3-seat
        state.players[3-seat].mana_pool = {'R': 1}
        state = rules.act(state, 3-seat, {'type': 'cast_spell', 'card_id': opposing.id,
                                        'targets': {'target_player': seat}})
        assert state.stack[-1].payload['mana_spent'] == 1
        state = rules.act(state, 3-seat, {'type': 'pass_priority'})
        assert state.priority_player == seat
        targets = {'target_stack_id': state.stack[-1].id}
        state.players[seat].mana_pool = {'U': 1, 'C': 1}
        want = 'counter_spell'
    else:
        opposing = add_profiled(state, RAW['Llanowar Elves'], 3-seat, rules.Zone.BATTLEFIELD)
        state.players[seat].mana_pool = {'B': 1, 'C': 1}
        targets = {'target_card_id': opposing.id}
        want = 'destroy_permanent'
    source = state.cards[source.id]
    spec = build_spell_spec(state, source, seat, targets)
    assert spec.effect.key == want and not spec.used_fallback and not spec.unsupported_resolution
    assert source.oracle_text == RAW[name]['oracle_text']
    result = rules.act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': targets})
    assert result.stack[-1].source_card_id == source.id
    assert result.stack[-1].payload['mana_spent'] == 2
    assert sum(result.players[seat].mana_pool.values()) == 0
    result = rules.settle(result)
    assert not result.stack and result.winner is None
    assert result.cards[source.id].zone == result.cards[opposing.id].zone == rules.Zone.GRAVEYARD
    assert result.players[seat].life == 20
    row = hydrate_deck_cards(MetadataRows(), [{'card_name': name, 'quantity': 1}])[0]
    assert tags_for(policy._view(row)).source == 'persisted'
    admitted = policy._profile(row)
    assert admitted is not None, 'Complete paid native body lacks incoming policy coverage'
    assert want in {effect['effect_key'] for clause in admitted.ability_specs for effect in clause['effects']}
    printed = next(effect for clause in admitted.ability_specs for effect in clause['effects']
                   if effect['effect_key'] == want)
    assert not {'target_card_id', 'target_stack_id', 'source_card_id'} & set(printed['payload'])
    if name == 'Negate':
        assert printed['payload'] == {'target_kind': spec.effect.payload['target_kind']}
    else:
        assert printed['payload']['exclude_types'] == ['Artifact']
        assert opposing.id in {target['id'] for target in spec.target_hints['creature_targets']}


def fault_row(name, oracle):
    raw = deepcopy(RAW[name])
    raw['oracle_text'] = oracle  # Explicit synthetic fault, not official Oracle.
    profile = merge_profile_payload({'card_data': raw}, derive_profile(raw))
    descriptor = SimpleNamespace(name=name, scryfall_id=raw['id'], oracle_source='scryfall',
                                 profiles_json=json.dumps(profile))
    class FaultRows:
        def get_cached_cards_by_names(self, names):
            return {}
        def get_card_knowledge_by_names(self, names):
            return {name.casefold(): descriptor}
    return hydrate_deck_cards(FaultRows(), [{'card_name': name, 'quantity': 1}])[0]


@pytest.mark.parametrize('name', ['Negate', 'Go for the Throat'])
@pytest.mark.parametrize('fault', ['win-tail', 'parenthetic-tail', 'conditional', 'activated', 'extra-dot', 'truncated'])
def test_whole_answer_unknown_tail_condition_and_malformed_surface_stay_rejected(name, fault):
    body = RAW[name]['oracle_text']
    changed = {
        'win-tail': body + ' You win the game.',
        'parenthetic-tail': body + ' (You win the game.)',
        'conditional': 'If you control a creature, ' + body[0].lower() + body[1:],
        'activated': '{1}: ' + body,
        'extra-dot': body + '.',
        'truncated': body.removesuffix('.'),
    }[fault]
    assert policy._profile(fault_row(name, changed)) is None
