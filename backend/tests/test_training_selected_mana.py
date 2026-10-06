"""Actual selected immediate mana; requires the composed executor dependency."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.action_contract import complete_action
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from training.dataset import EpisodeAliases
from training.environment import encode_action, decode_action
from tests.test_linked_damage_targets import raw_card
from tests.test_training_choice_coverage import position, replay, card as existing_card, forbid_database_and_network
from tests.test_training_mana_choice_coverage import card, mana
from tests.test_training_environment import resolve


def mana_position(seat):
    env = position(seat)
    player = env._state.players[seat]
    retained = next((cid for cid in player.hand if 'Land' in env._state.cards[cid].type_line), None)
    # A bounded retained decision, not a full built-in-hand planning benchmark.
    for cid in list(player.hand):
        if cid != retained:
            player.hand.remove(cid)
            env._state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
    return env


def selected_position(seat, name='Phyrexian Tower'):
    env = mana_position(seat)
    if name == 'Phyrexian Tower':
        source = card(env, name, seat)
        choices = [existing_card(env, 'Grizzly Bears', seat, Zone.BATTLEFIELD) for _ in range(2)]
        action = mana(source, 'B', 1)
    else:
        rows = json.loads((Path(__file__).parent / 'fixtures/mana_resources.json').read_text())
        raw = next(row for row in rows if row['name'] == 'Skirk Prospector')
        source = raw_card(env._state, raw, seat, Zone.BATTLEFIELD).id
        choices = [raw_card(env._state, raw, seat, Zone.BATTLEFIELD).id for _ in range(2)]
        action = mana(source, 'R')
    env._state.players[seat].mana_pool = {}
    return env, choices, action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,amount', [('Phyrexian Tower', 2), ('Skirk Prospector', 1)])
@pytest.mark.parametrize('index', [0, 1])
def test_actual_selected_other_resource_roundtrip_alias_and_intent(seat, name, amount, index):
    env, choices, action = selected_position(seat, name)
    selected = choices[index]
    action['payment_choices'] = {'sacrifice_card_ids': [selected]}
    before = env.snapshot()
    prompt = next(p for p in env.prompts() if p['hint'].get('card_id') == action['card_id']
                  and p['hint']['type'] == 'activate_mana_ability'
                  and p['hint']['ability_index'] == action['ability_index'])
    assert prompt['encoding_supported'] and not prompt['unsupported_choices']
    assert selected in prompt['hint']['activation_costs']['sacrifice_card_ids']
    assert 'payment_choices.sacrifice_card_ids' in prompt['required_choices']
    intent = {**action, 'card_name': name, 'cost_options': [], 'target_hints': {}}
    assert complete_action(intent) == action
    assert env.lookup_intent(intent) == env.lookup(action)
    assert decode_action(encode_action(action)) == action
    aliases = EpisodeAliases()
    aliases.observation(env.observe(seat))
    mapped = aliases.action(action, seat)
    assert mapped['payment_choices']['sacrifice_card_ids'][0].startswith('card:')
    assert aliases.actual_action(mapped, seat) == action
    assert env.snapshot() == before
    replay(env, action, {**action, 'payment_choices': {'sacrifice_card_ids': []}})
    assert selected in env._state.players[seat].graveyard
    assert choices[1-index] in env._state.players[seat].battlefield
    assert env._state.players[seat].mana_pool[action['color']] == amount
    assert not env._state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['omitted', 'partial', 'extra', 'duplicate', 'foreign', 'wrong_zone',
                                 'noncreature', 'wrong_source', 'wrong_index', 'wrong_color', 'discard'])
def test_selected_resource_rejections_are_atomic_all_root_fields(seat, bad):
    env, choices, action = selected_position(seat)
    action['payment_choices'] = {'sacrifice_card_ids': [choices[0]]}
    if bad == 'omitted':
        action.pop('payment_choices')
    elif bad == 'partial':
        action['payment_choices'] = {}
    elif bad in {'extra', 'duplicate'}:
        action['payment_choices']['sacrifice_card_ids'] = choices if bad == 'extra' else [choices[0]] * 2
    elif bad in {'foreign', 'wrong_zone', 'noncreature'}:
        selected = (existing_card(env, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD) if bad == 'foreign' else
                    existing_card(env, 'Grizzly Bears', seat, Zone.HAND) if bad == 'wrong_zone' else
                    card(env, 'Sol Ring', seat))
        action['payment_choices']['sacrifice_card_ids'] = [selected]
    elif bad == 'wrong_source':
        action['card_id'] = card(env, 'Phyrexian Tower', 3-seat)
    elif bad == 'wrong_index':
        action['ability_index'] = 99
    elif bad == 'wrong_color':
        action['color'] = 'U'
    else:
        action['payment_choices']['discard_card_ids'] = [existing_card(env, 'Grizzly Bears', seat, Zone.HAND)]
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        checked_action(env._state, env._rules, seat, action)
    for boundary in (env.lookup, env.lookup_intent, env.step):
        with pytest.raises(ActionRejected):
            boundary(action)
        assert env.snapshot() == before
    assert env.action_mask([action]) == [False]
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_resources_do_not_reveal_opposing_hidden_identity(seat):
    env, choices, action = selected_position(seat)
    action['payment_choices'] = {'sacrifice_card_ids': [choices[1]]}
    aliases = EpisodeAliases()
    def inputs():
        return json.dumps({'observation': aliases.observation(env.observe(seat)),
                           'prompts': env.prompts(seat)}, sort_keys=True).encode()
    before = inputs()
    for ids in (env._state.players[3-seat].hand, env._state.players[3-seat].library):
        first, second = ids[:2]
        a, b = deepcopy(env._state.cards[first]), deepcopy(env._state.cards[second])
        a.id, b.id = second, first
        env._state.cards[first], env._state.cards[second] = b, a
        ids.reverse()
    assert inputs() == before
    assert env.prompts(3-seat) == []
    assert env.lookup_intent(action) == env.lookup(action)


@pytest.mark.parametrize('field,value', [('targets', {'x_value': 2}), ('x_value', 2),
                                      ('unknown_choice', ['a'])])
def test_requested_unsupported_intent_fields_are_not_silently_dropped(field, value):
    env, choices, action = selected_position(1)
    action['payment_choices'] = {'sacrifice_card_ids': [choices[0]]}
    before = env.snapshot()
    with pytest.raises(ActionRejected, match='cannot carry'):
        env.lookup_intent({**action, field: value})
    assert env.snapshot() == before


def filter_position(seat, name, branch):
    env = mana_position(seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/training_selected_mana' / (name + '.json')).read_text())
    source = raw_card(env._state, raw, seat, Zone.BATTLEFIELD)
    env._state.players[seat].mana_pool = {branch: 1}
    for field in ('oracle_text', 'mana_cost', 'type_line'):
        assert getattr(source, field) == raw[field]
    return env, source.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,branch,color,bundle', [
    (name, branch, color, bundle)
    for name, colors in [('graven-cairns', 'BR'), ('flooded-grove', 'GU')]
    for branch in colors
    for color, bundle in [(colors[0], {colors[0]: 2}), (colors[1], {colors[1]: 2}),
                          (colors[0], dict.fromkeys(colors, 1)), (colors[1], dict.fromkeys(colors, 1))]
])
def test_actual_canonical_hybrid_branch_and_complete_output_vector_are_selected(seat, name, branch, color, bundle):
    env, cid = filter_position(seat, name, branch)
    action = {**mana(cid, color, 1), 'hybrid_choices': [branch], 'output_bundle': bundle}
    before = env.snapshot()
    prompt = next(p for p in env.prompts() if p['hint']['type'] == 'activate_mana_ability'
                  and p['hint'].get('card_id') == cid and p['hint']['ability_index'] == 1)
    assert prompt['encoding_supported'] and not prompt['unsupported_choices']
    assert prompt['hint']['hybrid_symbols'][0]['choices'] == list('BR' if name == 'graven-cairns' else 'GU')
    assert {'color': color, 'output_bundle': bundle} in prompt['hint']['output_options']
    assert bundle in prompt['hint']['base_output_bundles']
    assert complete_action(action) == action
    assert env.lookup_intent({**action, 'card_name': name}) == env.lookup(action)
    assert env.snapshot() == before
    replay(env, action, mana(cid, color, 1))
    assert all(env._state.players[seat].mana_pool.get(key, 0) == amount for key, amount in bundle.items())
    assert sum(env._state.players[seat].mana_pool.values()) == 2
    assert env._state.cards[cid].tapped and not env._state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choices', [None, [], ['G'], ['B', 'R'], ['R']])
def test_canonical_hybrid_missing_invalid_partial_or_unaffordable_branch_is_atomic(seat, choices):
    env, cid = filter_position(seat, 'graven-cairns', 'B')
    action = {**mana(cid, 'B', 1), 'output_bundle': {'B': 2}}
    if choices is not None:
        action['hybrid_choices'] = choices
    before = env.snapshot()
    for boundary in (env.lookup, env.lookup_intent, env.step):
        with pytest.raises(ActionRejected):
            boundary(action)
        assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_hybrid_source_cannot_fund_its_own_activation(seat):
    env, cid = filter_position(seat, 'graven-cairns', 'B')
    env._state.players[seat].mana_pool = {}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.step({**mana(cid, 'B', 1), 'hybrid_choices': ['B'], 'output_bundle': {'B': 2}})
    assert env.snapshot() == before and not env._state.cards[cid].tapped


@pytest.mark.parametrize('bundle', [None, {}, {'B': 0}, {'B': -1}, {'B': True}, {'B': '2'},
                                  {'B': 3}, {'B': 1, 'G': 1}, {'R': 2}, {'B': 100001}])
def test_missing_malformed_or_non_offered_vectors_cannot_be_normalized_away(bundle):
    env, cid = filter_position(1, 'graven-cairns', 'B')
    action = {**mana(cid, 'B', 1), 'hybrid_choices': ['B']}
    action['output_bundle'] = bundle
    before = env.snapshot()
    for boundary in (env.lookup, env.lookup_intent, env.step):
        with pytest.raises(ActionRejected):
            boundary(action)
        assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_subtype_resource_rejects_non_goblin_but_can_select_the_source(seat):
    env, choices, action = selected_position(seat, 'Skirk Prospector')
    wrong = existing_card(env, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup({**action, 'payment_choices': {'sacrifice_card_ids': [wrong]}})
    assert env.snapshot() == before
    action['payment_choices'] = {'sacrifice_card_ids': [action['card_id']]}
    replay(env, action)
    assert action['card_id'] in env._state.players[seat].graveyard
    assert set(choices).issubset(env._state.players[seat].battlefield)
    assert env._state.players[seat].mana_pool['R'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_selected_sacrifice_death_draw_pending_restore_privacy_and_replay(seat):
    env, choices, action = selected_position(seat)
    rows = json.loads((Path(__file__).parent / 'fixtures/recurring_engines.json').read_text())
    raw = next(row for row in rows if row['name'] == 'Grim Haruspex')
    raw_card(env._state, raw, seat, Zone.BATTLEFIELD)
    existing_card(env, 'Stinkweed Imp', seat, Zone.GRAVEYARD)
    action['payment_choices'] = {'sacrifice_card_ids': [choices[1]]}
    replay(env, action)
    assert env._state.players[seat].mana_pool['B'] == 2
    assert len(env._state.stack) == 1
    resolve(env)
    assert env._state.pending_mechanic_choice['kind'] == 'draw'
    assert 'prompts' not in env.observe(3-seat)['pending_choice']
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(action)
    assert env.snapshot() == before
    replay(env, {'type': 'choose_mechanic', 'choice_id': 'draw'},
           {'type': 'choose_mechanic', 'card_ids': []})
    assert not env._state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Phyrexian Tower', 'Skirk Prospector'])
def test_actual_ai_spell_payment_preserves_declared_resource_reservation(seat, name):
    from ai.agent import AIAgent
    env, choices, source_action = selected_position(seat, name)
    rows = json.loads((Path(__file__).parent / 'fixtures/spell_additional_costs.json').read_text())
    raw = next(row for row in rows if row['name'] == ('Deadly Dispute' if name == 'Phyrexian Tower' else 'Goblin Grenade'))
    spell = raw_card(env._state, raw, seat, Zone.HAND)
    before = env.snapshot()
    view, moves = env._view(seat)
    move = next(move for move in moves if move['type'] == 'cast_spell' and move['card_id'] == spell.id)
    intent = AIAgent(archetype='Midrange')._materialize_action(view, move, seat)
    selected = complete_action(intent)['cost_choice']['sacrifice_card_ids']
    assert len(selected) == 1
    assert env.snapshot() == before
    action = env.lookup_intent(intent)['action']
    replay(env, action)
    assert selected[0] in env._state.players[seat].graveyard
    assert len(env._state.stack) == 1
    assert env._state.stack[0].source_card_id == spell.id
    # Distinct mana/resource sacrifices are required; double-spending the
    # additional-cost selection would fail authoritative trial execution.
    assert len(set(env._state.players[seat].graveyard) & set(choices + [source_action['card_id']])) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_bog_witch_paid_discard_selection_is_complete_and_not_inferred(seat):
    env = mana_position(seat)
    rows = json.loads((Path(__file__).parent / 'fixtures/mana_executor_choices.json').read_text())
    raw = next(row for row in rows if row['name'] == 'Bog Witch')
    source = raw_card(env._state, raw, seat, Zone.BATTLEFIELD)
    source.summoning_sick = False
    choices = [existing_card(env, 'Grizzly Bears', seat, Zone.HAND) for _ in range(2)]
    env._state.players[seat].mana_pool = {'B': 1}
    action = {**mana(source.id, 'B'), 'payment_choices': {'discard_card_ids': [choices[1]]}}
    before = env.snapshot()
    aliases = EpisodeAliases()
    aliases.observation(env.observe(seat))
    assert aliases.actual_action(aliases.action(action, seat), seat) == action
    assert env.lookup_intent({**action, 'card_name': source.name}) == env.lookup(action)
    assert env.snapshot() == before
    replay(env, action, mana(source.id, 'B'))
    assert choices[1] in env._state.players[seat].graveyard
    assert choices[0] in env._state.players[seat].hand
    assert env._state.players[seat].mana_pool['B'] == 3
    assert env._state.cards[source.id].tapped and not env._state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('replacement,expected', [('Mana Reflection', {'B': 2, 'R': 2}),
                                               ('Damping Sphere', {'C': 1})])
def test_explicit_base_anchor_and_whole_vector_survive_actual_replacement(seat, replacement, expected):
    env, cid = filter_position(seat, 'graven-cairns', 'B')
    card(env, replacement, seat)
    action = {**mana(cid, 'B', 1), 'hybrid_choices': ['B'], 'output_bundle': {'B': 1, 'R': 1}}
    replay(env, action, {**action, 'color': 'C'})
    assert all(env._state.players[seat].mana_pool.get(color, 0) == amount for color, amount in expected.items())
    assert sum(env._state.players[seat].mana_pool.values()) == sum(expected.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_omitted_bundle_preserves_existing_legacy_final_sphere_color(seat):
    env = mana_position(seat)
    source = card(env, 'Forest', seat)
    card(env, 'Mana Reflection', seat)
    card(env, 'Damping Sphere', seat)
    env._state.players[seat].mana_pool = {}
    replay(env, mana(source, 'C'))
    assert env._state.players[seat].mana_pool == {'C': 1}
