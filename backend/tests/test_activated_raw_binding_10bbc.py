"""Actual RAW occurrence binding; adversarial strings are protocol-only inputs."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ai.selection_activation import _schema
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.type_effects import effective_types
from tests.test_temporary_artifact_type import raw, place, act
from tests.rings_activation_native_support_5763 import raw_card as rings_raw


EFFECT = 'Target permanent becomes an artifact in addition to its other types until end of turn.'


def extract(text):
    return extract_activated_abilities(SimpleNamespace(name='Protocol', oracle_text=text))


def observed(state):
    value = deepcopy(vars(state))
    value['rng'] = state.rng.getstate()
    return value


@pytest.mark.parametrize('bodies', [
    [EFFECT, EFFECT],
    [EFFECT + ' (first reminder)', EFFECT + ' (second reminder)'],
    ['(leading (nested) reminder) ' + EFFECT, EFFECT + ' (tail)'],
])
def test_equal_normalized_keys_bind_their_own_occurrences_without_rejecting_duplicates(bodies):
    abilities = extract('\n'.join('{T}: ' + text for text in bodies))
    assert [item['index'] for item in abilities] == [0, 1]
    assert [item['raw_body'] for item in abilities] == bodies
    assert [item['raw_effect_text'] for item in abilities] == bodies
    assert [item['text'] for item in abilities] == [EFFECT, EFFECT]


@pytest.mark.parametrize('prefix,index', [
    ('(Reminder (nested {1}: Draw a card.) only.)\n', 0),
    ('"{1}: Draw a card."\n', 1),
    ('\u201c{1}: Draw a card.\u201d\n', 1),
])
def test_fake_reminder_or_quoted_costs_never_bind_as_top_level_abilities(prefix, index):
    abilities = extract(prefix + '{T}: ' + EFFECT)
    assert len(abilities) == 1 and abilities[0]['index'] == index
    assert abilities[0]['raw_body'] == EFFECT


def test_reminder_colon_and_quoted_inner_cost_do_not_replace_actual_separator():
    body = '(Reminder: "{2}: Draw a card." (nested).) ' + EFFECT + ' (tail: reminder)'
    ability, = extract('{T}: ' + body)
    assert ability['raw_body'] == ability['raw_effect_text'] == body
    assert ability['mana_cost'] == '{T}' and ability['text'] == EFFECT


@pytest.mark.parametrize('text', [
    '{T}: ' + EFFECT + ' (unclosed',
    '{T}: ' + EFFECT + ' unmatched)',
    '"{T}: ' + EFFECT,
    '{T}: Create a token with "{1}: Draw a card.',
])
def test_genuinely_malformed_spans_fail_closed(text):
    assert extract(text) == []


def test_supported_modifier_retains_raw_partition_and_every_legacy_field():
    body = 'Draw a card. (drawing reminder) This ability costs {1} less to activate during your turn.'
    ability, = extract('{3}: ' + body)
    assert ability['raw_body'] == body
    assert ability['raw_effect_text'] == 'Draw a card. (drawing reminder)'
    assert {key: value for key, value in ability.items() if key not in {'raw_body', 'raw_effect_text'}} == {
        'index': 0, 'mana_cost': '{3}', 'text': 'Draw a card.', 'activation_zone': 'battlefield',
        'cost_modifier': {'amount': 1, 'basis': 'controller_turn', 'effect_text': 'Draw a card.'},
        'label': '{3}: Draw a card.  This ability costs {1} less to activate during your turn.',
    }


@pytest.mark.parametrize('body', [
    'Draw a card. This ability costs {1} less to activate during your turn. (unknown executable tail)',
    'Draw a card. This ability costs {1} less to activate during (if you control a Plains) your turn.',
    'Draw a card. (This ability costs {1} less to activate during your turn.)',
])
def test_modifier_cannot_be_inferred_from_only_the_normalized_partition(body):
    assert extract('{3}: ' + body) == []


def board(seat, suffix=''):
    names = ['Liquimetal Coating', 'Rings of Brighthearth', 'Forest']
    deck = []
    for name in names:
        data = deepcopy(rings_raw(name) if name == 'Rings of Brighthearth' else raw(name))
        if name == 'Liquimetal Coating':
            data['oracle_text'] += suffix  # Explicit protocol at birth, not a canonical RAW claim.
        deck.append({**data, 'card_name': name, 'quantity': 1})
    deck.append({**raw('Island'), 'card_name': 'Island', 'quantity': 57})
    state = MatchFactory.from_decks(deck, deck, seed=937)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    source = place(state, 'Liquimetal Coating', seat)
    target = place(state, 'Forest', 3-seat)
    return state, source, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' (then draw a card)', '(if you control a Plains)'])
@pytest.mark.parametrize('consumer', ['checked', 'producer'])
def test_unknown_coating_raw_is_not_offered_and_actual_activation_rejects_before_tap(seat, suffix, consumer):
    state, source, target = board(seat, suffix)
    before = observed(state)
    action = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
              'targets': {'target_card_id': target}}
    with pytest.raises(ActionRejected):
        if consumer == 'checked':
            act(state, seat, 'activate_ability', card_id=source, ability_index=0,
                targets={'target_card_id': target})
        else:
            RulesEngine().take_action(state, seat, action, reject_invalid=True)
    moves = RulesEngine().legal_moves(state, seat)
    assert not any(move['type'] == 'activate_ability' and move['card_id'] == source for move in moves)
    assert observed(state) == before and not state.cards[source].tapped and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_real_canonical_tap_and_rings_payment_copy_keep_public_shape_and_actual_frame(seat):
    state, source, target = board(seat)
    rings = place(state, 'Rings of Brighthearth', seat)
    state.players[seat].mana_pool = {'C': 2}
    move, = [move for move in RulesEngine().legal_moves(state, seat)
             if move['type'] == 'activate_ability' and move['card_id'] == source]
    assert move['mana_cost'] == '{T}' and move['ability_index'] == 0
    assert move['ability_label'] == '{T}: ' + EFFECT
    assert 'raw_body' not in move and 'raw_effect_text' not in move
    state = act(state, seat, 'activate_ability', card_id=source, ability_index=0,
                targets={'target_card_id': target})
    original = state.stack[0]
    assert original.source_card_id == source and state.cards[source].tapped
    assert original.payload['__ability_target_text'] == EFFECT
    assert state.stack[-1].source_card_id == rings
    assert resolve_top_of_stack(state) is False
    assert state.pending_trigger_order['phase'] == 'optional'
    state = act(state, seat, 'choose_optional_effect', stack_id=state.stack[-1].id, accept=True)
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = act(state, seat, 'choose_mechanic', card_ids=['keep'])
    assert len(state.stack) == 2 and state.stack[-1].payload['__copied_from_stack_id'] == original.id
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert 'Artifact' in effective_types(state, target) and not state.stack


def test_selection_schema_uses_raw_effect_not_normalized_surrogate():
    body = ('Look at the top four cards of your library. You may reveal a creature card '
            'with mana value 3 or less from among them and put it into your hand. '
            'Put the rest on the bottom of your library in a random order.')
    ability, = extract('{3}{W}: ' + body + ' (then draw a card)')
    assert _schema(ability) is None
    complete, = extract('{3}{W}: ' + body)
    assert _schema(complete)['top_n'] == 4


def test_actual_agent_activated_divide_proxy_receives_same_raw_without_running_policy(monkeypatch):
    from ai.agent import AIAgent
    from rules_engine import cast_choice
    state, source, target = board(1, ' (protocol tail)')
    agent = object.__new__(AIAgent)
    monkeypatch.setattr(agent, '_spell_tags', lambda card: set())
    seen = []

    class Captured(Exception):
        pass

    def capture(card, targets):
        seen.append(card.oracle_text)
        raise Captured

    monkeypatch.setattr(cast_choice, 'enrich_divide_total', capture)
    move = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
            'target_hints': {'supports_divide': True},
            'targets': {'target_distribution': {target: 1}}}
    with pytest.raises(Captured):
        agent._materialize_action_without_resources(state, move, 1)
    assert seen == [EFFECT + ' (protocol tail)']
