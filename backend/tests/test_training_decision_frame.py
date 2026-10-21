"""V2 decision-frame regressions; field vectors below are codec protocols, not games."""
from copy import deepcopy
import importlib
import importlib.util
import json

import pytest

from training import TrainingEnvironment
from training.dataset import episode_records, model_input
from tests.test_training_environment import cast, position


def api():
    assert importlib.util.find_spec('training.decision_frame') is not None, (
        'Missing versioned decision frame and reference-bound feature encoder')
    return importlib.import_module('training.decision_frame')


@pytest.fixture(scope='module')
def native_decision():
    environment, cid = position(1)
    environment.step(cast(environment, cid, target_player=2))
    return environment.observe(1), environment.prompts(1)


def protocol_decision(native_decision):
    """Explicit public protocol descriptors, never injected into an engine state."""
    observation, prompts = deepcopy(native_decision)
    cards = list(observation['known_cards'])[:3]
    assert len(cards) == 3 and observation['stack']
    stack = observation['stack'][0]['id']
    prompts.extend([
        {'hint': {'type': 'choose_mechanic', 'kind': 'library_search',
                  'options': ['protocol-library-option'],
                  'option_labels': {'protocol-library-option': 'Public offered choice'},
                  'option_type_lines': {'protocol-library-option': 'Creature'}},
         'required_choices': ['card_ids']},
        {'hint': {'type': 'cast_spell', 'card_id': cards[0],
                  'cost_options': [{'id': 'protocol-cost', 'mana_cost': '{1}{R}'}]},
         'required_choices': ['cost_choice.id']},
        {'hint': {'type': 'play_land', 'card_id': cards[0],
                  'graveyard_permission_key': 'protocol-permission'},
         'required_choices': []},
        {'hint': {'type': 'choose_replacement',
                  'replacement_source_id': 'protocol-replacement',
                  'replacement_name': 'Public replacement'},
         'required_choices': ['replacement_source_id']},
        {'hint': {'type': 'choose_optional_effect', 'stack_id': stack,
                  'accept': True}, 'required_choices': ['accept']},
        {'hint': {'type': 'choose_mechanic', 'kind': 'draw',
                  'options': ['protocol-choice'],
                  'option_labels': {'protocol-choice': 'Draw the offered card'}},
         'required_choices': ['choice_id']},
    ])
    return observation, prompts, cards, stack


@pytest.mark.parametrize('seat', [1, 2])
def test_v2_records_real_observation_and_prompts_before_chooser(seat):
    environment = TrainingEnvironment()
    environment.reset(seed=17)
    if seat == 2:
        environment.step({'type': 'keep_hand'})
    observation, prompts = environment.observe(seat), environment.prompts(seat)
    before = environment.snapshot()
    seen = []

    def choose(current):
        seen.append((current.observe(seat), current.prompts(seat)))
        return {'type': 'keep_hand'}

    rows = list(episode_records(environment, choose, episode='episode-0000',
                               groups=['family:' + 'a' * 64], tick_budget=1,
                               decision_frame=True))
    assert seen == [(observation, prompts)]
    assert before != environment.snapshot()
    assert all(row['version'] == 'mtg.dataset.v2' for row in rows)
    transition = rows[1]
    frame = model_input(transition)
    assert set(frame) == {'version', 'observation', 'prompts'}
    assert frame['version'] == 'mtg.decision.v1'
    assert frame['observation']['seat'] == seat
    assert frame['observation']['pregame_pending'] == observation['pregame_pending']
    assert frame['prompts'] == prompts
    assert transition['accepted'] is True and transition['action']['type'] == 'keep_hand'
    assert rows[-1]['complete'] is False and rows[-1]['terminal_rewards'] is None


def test_default_and_explicit_false_retain_v1_bytes():
    def collect(**kwargs):
        environment = TrainingEnvironment()
        environment.reset(seed=17)
        return list(episode_records(environment, lambda current: {'type': 'keep_hand'},
                                   episode='episode-0000', groups=['family:' + 'b' * 64],
                                   tick_budget=2, **kwargs))
    default = collect()
    explicit = collect(decision_frame=False)
    assert json.dumps(default, sort_keys=True) == json.dumps(explicit, sort_keys=True)
    assert all(row['version'] == 'mtg.dataset.v1' for row in default)
    assert model_input(default[1]) == default[1]['input']


def test_frame_detaches_and_private_reverse_bindings_never_serialize(native_decision):
    observation, prompts = deepcopy(native_decision)
    original = deepcopy((observation, prompts))
    frame, bindings = api().build_decision_frame(observation, prompts)
    assert (observation, prompts) == original
    assert set(frame) == {'version', 'observation', 'prompts'}
    frame['observation']['players']['1']['hand'].clear()
    frame['prompts'].clear()
    assert (observation, prompts) == original
    assert not {'bindings', 'reverse', 'snapshot', 'seed', 'provenance'}.intersection(frame)
    assert bindings is not frame


def test_prompt_only_reference_joins_descriptor_and_round_trips(native_decision):
    observation, prompts, _, _ = protocol_decision(native_decision)
    frame, bindings = api().build_decision_frame(observation, prompts)
    action = {'type': 'choose_mechanic', 'card_ids': ['protocol-library-option']}
    aliased = bindings.action(action)
    assert aliased['card_ids'] != action['card_ids']
    assert bindings.actual_action(aliased) == action
    encoded = api().encode_action(frame, aliased)
    rendered = json.dumps(encoded, sort_keys=True)
    assert 'Public offered choice' in rendered
    assert 'protocol-library-option' not in rendered
    assert 'Creature' in rendered


def _replace(value, mapping):
    if isinstance(value, dict):
        return {_replace(key, mapping): _replace(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item, mapping) for item in value]
    if isinstance(value, str):
        if value in mapping:
            return mapping[value]
        for old, new in mapping.items():
            value = value.replace('planeswalker:' + old, 'planeswalker:' + new)
    return value


def test_complete_consistent_id_renaming_does_not_change_features(native_decision):
    observation, prompts, cards, _ = protocol_decision(native_decision)
    mapping = {cid: 'renamed-public-' + str(index)
               for index, cid in enumerate(observation['known_cards'])}
    mapping.update({item['id']: 'renamed-stack-' + str(index)
                    for index, item in enumerate(observation['stack'])})
    mapping['protocol-library-option'] = 'renamed-prompt-only'
    first, one = api().build_decision_frame(observation, prompts)
    second, two = api().build_decision_frame(_replace(observation, mapping),
                                            _replace(prompts, mapping))
    action = {'type': 'choose_mechanic', 'card_ids': cards[:2]}
    assert api().encode_state(first) == api().encode_state(second)
    assert api().encode_action(first, one.action(action)) == api().encode_action(
        second, two.action(_replace(action, mapping)))


def test_known_card_mapping_insertion_order_is_not_a_feature(native_decision):
    observation, prompts = deepcopy(native_decision)
    first, _ = api().build_decision_frame(observation, prompts)
    observation['known_cards'] = dict(reversed(list(observation['known_cards'].items())))
    second, _ = api().build_decision_frame(observation, prompts)
    assert api().encode_state(first) == api().encode_state(second)


def test_ordered_selection_is_distinct_and_unknown_reference_fails(native_decision):
    observation, prompts, cards, _ = protocol_decision(native_decision)
    frame, bindings = api().build_decision_frame(observation, prompts)
    forward = {'type': 'choose_mechanic', 'card_ids': cards[:2]}
    reverse = {'type': 'choose_mechanic', 'card_ids': list(reversed(cards[:2]))}
    assert api().encode_action(frame, bindings.action(forward)) != api().encode_action(
        frame, bindings.action(reverse))
    with pytest.raises(ValueError):
        bindings.action({'type': 'choose_mechanic', 'card_ids': ['not-authorized']})


@pytest.mark.parametrize('forbidden', ['seed', 'snapshot', 'provenance', 'rng_state', 'log'])
def test_private_observation_additions_are_rejected(native_decision, forbidden):
    observation, prompts = deepcopy(native_decision)
    observation[forbidden] = 'PRIVATE-MUST-NOT-APPEAR'
    with pytest.raises(ValueError):
        api().build_decision_frame(observation, prompts)


@pytest.mark.parametrize('seat', [1, 2])
def test_nonacting_hidden_information_is_never_added(seat):
    environment = TrainingEnvironment()
    environment.reset(seed=17)
    if seat == 2:
        environment.step({'type': 'keep_hand'})
    observation = environment.observe(seat)
    frame, _ = api().build_decision_frame(observation, environment.prompts(seat))
    assert 'hand' not in frame['observation']['players'][str(3-seat)]
    assert all('library' not in player for player in frame['observation']['players'].values())
    assert not {'starting_decks', 'rng_state', 'log'}.intersection(frame['observation'])


def test_model_input_copies_frame_not_labels_or_future(native_decision):
    frame, _ = api().build_decision_frame(*deepcopy(native_decision))
    record = {'version': 'mtg.dataset.v2', 'kind': 'transition', 'accepted': True,
              'input': frame, 'action': {'type': 'pass_priority'},
              'terminal_rewards': {'1': 1, '2': -1}, 'next_observation': 'FORBIDDEN'}
    value = model_input(record)
    assert value == frame
    assert not {'action', 'terminal_rewards', 'next_observation'}.intersection(value)
    value['prompts'].clear()
    assert record['input'] == frame


def test_unknown_action_field_is_not_silently_dropped(native_decision):
    frame, bindings = api().build_decision_frame(*deepcopy(native_decision))
    with pytest.raises(ValueError):
        api().encode_action(frame, {'type': 'pass_priority', 'future_choice': 1})
    with pytest.raises(ValueError):
        bindings.action({'type': 'pass_priority', 'future_choice': 1})


def _field_names(value, parent=None):
    if isinstance(value, dict):
        keys = set() if parent in {'target_distribution', 'blocks', 'attack_targets', 'damage_assignment'} else set(value)
        return keys.union(*(_field_names(item, key) for key, item in value.items()))
    if isinstance(value, list):
        return set().union(*(_field_names(item, parent) for item in value))
    return set()


def _text_nodes(node):
    kind = node['kind']
    assert kind in {'null', 'bool', 'number', 'text', 'list', 'map', 'set', 'ref'}
    if kind == 'text':
        return {node['value']}
    if kind == 'map':
        return set().union(*(_text_nodes(item) for pair in node['items'] for item in pair))
    if kind in {'list', 'set'}:
        return set().union(*(_text_nodes(item) for item in node['items']))
    return set()


ACTION_KINDS = [
    'pass_priority', 'mulligan', 'keep_hand', 'play_land', 'foretell', 'suspend',
    'cast_spell', 'cycle_card', 'activate_ability', 'activate_loyalty', 'crew',
    'ninjutsu', 'equip', 'tap_land_for_mana', 'tap_nonland_for_mana',
    'activate_mana_ability', 'tap_lands_bulk', 'attack', 'block',
    'choose_mechanic_cards', 'choose_mechanic_option', 'choose_mechanic_damage',
    'choose_replacement', 'choose_trigger_order', 'choose_trigger_target',
    'choose_optional_effect',
]


def protocol_action(kind, cards, stack):
    a, b, c = cards
    targets = {
        'target_player': 2, 'target_card_id': b, 'target_card_ids': [b, c],
        'target_stack_id': stack, 'target_distribution': {b: 2, '2': 1},
        'x_value': 3, 'selected_face_index': 0, 'mode_text': 'Public mode A',
        'mode_texts': ['Public mode B', 'Public mode A'],
        'mode_targets': {'Public mode A': {'target_player': 2,
                                         'target_card_id': c, 'target_stack_id': stack}},
        'search_card_ids': ['protocol-library-option'], 'topdeck_card_ids': [c, b],
        'top_choice_hand_id': b, 'top_choice_exile_id': c,
        'top_choice_bottom_ids': [c, b], 'pay_unless_counter': False,
        'replacement_source_id': 'protocol-replacement',
    }
    payments = {'discard_card_ids': [b], 'sacrifice_card_ids': [c]}
    values = {
        'pass_priority': {}, 'mulligan': {}, 'keep_hand': {'bottom_card_ids': [c, b]},
        'play_land': {'card_id': a, 'from_exile': True, 'from_graveyard': True,
                      'graveyard_permission_key': 'protocol-permission',
                      'selected_face_index': 0, 'entry_choice': 'pay_two_life'},
        'foretell': {'card_id': a}, 'suspend': {'card_id': a, 'x_value': 3},
        'cast_spell': {'card_id': a, 'targets': targets,
                       'cost_choice': {'id': 'protocol-cost', **payments, 'exile_card_ids': [b]},
                       'hybrid_choices': ['W', 'P'], 'selected_face_index': 0,
                       'from_exile': True, 'from_library': True, 'from_graveyard': True,
                       'escape_exile_ids': [c], 'resource_payment': {
                           'delve': [a], 'convoke': [{'card_id': b, 'pay_as': 'W'}],
                           'improvise': [c]}},
        'cycle_card': {'card_id': a, 'x_value': 2},
        'activate_ability': {'card_id': a, 'ability_index': 0, 'targets': targets,
                             'hybrid_choices': ['U', '2'], 'payment_choices': payments},
        'activate_loyalty': {'card_id': a, 'ability_index': 1, 'targets': targets},
        'crew': {'card_id': a, 'crew_card_ids': [b, c]},
        'ninjutsu': {'card_id': a, 'return_card_id': b},
        'equip': {'card_id': a, 'target_card_id': b},
        'tap_land_for_mana': {'card_id': a, 'color': 'R'},
        'tap_nonland_for_mana': {'card_id': a, 'color': 'U'},
        'activate_mana_ability': {'card_id': a, 'ability_index': 0, 'color': 'R',
                                  'payment_choices': payments, 'hybrid_choices': ['P'],
                                  'output_bundle': {'R': 2, 'C': 1}},
        'tap_lands_bulk': {'land_name': 'Mountain', 'count': 2, 'color': 'R'},
        'attack': {'attackers': [a, b], 'attack_targets': {a: 'player:2', b: 'planeswalker:' + c},
                   'bands': [[a, b]], 'hybrid_choices': ['R', '2']},
        'block': {'blocks': {a: [b, c]}, 'hybrid_choices': ['W', 'P']},
        'choose_mechanic_cards': {'card_ids': [b, c]},
        'choose_mechanic_option': {'choice_id': 'protocol-choice'},
        'choose_mechanic_damage': {'damage_assignment': {b: 2, '2': 1}},
        'choose_replacement': {'replacement_source_id': 'protocol-replacement'},
        'choose_trigger_order': {'trigger_order': [stack]},
        'choose_trigger_target': {'stack_id': stack, 'target_player': 2},
        'choose_optional_effect': {'stack_id': stack, 'accept': False},
    }
    return {'type': 'choose_mechanic' if kind.startswith('choose_mechanic_') else kind,
            **values[kind]}


@pytest.mark.parametrize('kind', ACTION_KINDS)
def test_all_typed_action_fields_have_reference_bound_feature_nodes(native_decision, kind):
    observation, prompts, cards, stack = protocol_decision(native_decision)
    frame, bindings = api().build_decision_frame(observation, prompts)
    action = protocol_action(kind, cards, stack)
    aliased = bindings.action(action)
    assert bindings.actual_action(aliased) == action
    features = api().encode_action(frame, aliased)
    assert set(features) == {'version', 'root', 'entities'}
    assert features['version'] == 'mtg.features.v1'
    assert _field_names(action).issubset(_text_nodes(features['root']))
    rendered = json.dumps(features, sort_keys=True)
    assert not any(value in rendered for value in cards + [stack, 'protocol-cost',
                    'protocol-permission', 'protocol-replacement', 'protocol-choice',
                    'protocol-library-option'])


def test_v2_immutable_shard_and_manifest_use_explicit_version(tmp_path):
    from training.dataset import DatasetRun, digest, validate_episode
    environment = TrainingEnvironment()
    environment.reset(seed=17)
    metadata = {'configuration_hash': digest('v2-protocol'), 'engine_hash': digest('engine'),
                'deck_hashes': [digest('a'), digest('b')], 'policy_hash': digest('script'),
                'origin': 'scripted'}
    run = DatasetRun(tmp_path / 'v2', metadata, dataset_version='mtg.dataset.v2')
    try:
        end = run.write_episode(episode_records(
            environment, lambda current: {'type': 'keep_hand'}, episode='episode-0000',
            groups=['family:' + 'c' * 64], tick_budget=1, origin='scripted',
            decision_frame=True))
    finally:
        run.close()
    assert end['steps'] == 1 and end['terminal_rewards'] is None
    assert json.loads((tmp_path / 'v2/manifest.json').read_text())['version'] == 'mtg.dataset.v2'
    assert validate_episode(tmp_path / 'v2/episode-0000.jsonl', 'episode-0000',
                            dataset_version='mtg.dataset.v2') == end
    with pytest.raises(ValueError):
        validate_episode(tmp_path / 'v2/episode-0000.jsonl', 'episode-0000')


def test_feature_schema_binds_cpu_pool_revision():
    assert api().FEATURE_VERSION == 'mtg.features.v1'
    assert api().DECISION_VERSION == 'mtg.decision.v1'
    assert api().FEATURE_SCHEMA_SHA256 == (
        '0b3aadfead9f66999c8b6c3ddc13699ad7dc5dd1c76179e95585042ba0339ed5')


@pytest.mark.parametrize('limit', ['depth', 'text', 'nodes', 'total_text'])
def test_oversized_decision_rejected_without_truncating_input(native_decision, limit):
    observation, prompts = deepcopy(native_decision)
    if limit == 'depth':
        nested = 1
        for _ in range(66):
            nested = {'next': nested}
        prompts.append({'hint': {'type': 'pass_priority', 'target_hints': nested},
                        'required_choices': []})
    elif limit == 'text':
        prompts.append({'hint': {'type': 'pass_priority', 'label': 'x' * 65537},
                        'required_choices': []})
    elif limit == 'nodes':
        prompts.append({'hint': {'type': 'choose_mechanic', 'kind': 'library_search',
                                 'options': [None] * 262145},
                        'required_choices': ['card_ids']})
    else:
        prompts.append({'hint': {'type': 'choose_mechanic', 'kind': 'library_search',
                                 'option_labels': {str(i): 'x' * 65536 for i in range(17)}},
                        'required_choices': ['card_ids']})
    before = json.dumps([observation, prompts], sort_keys=True)
    with pytest.raises(ValueError, match='limit|budget|oversiz|depth'):
        api().build_decision_frame(observation, prompts)
    assert json.dumps([observation, prompts], sort_keys=True) == before


def test_feature_bank_references_are_gathers_into_earlier_entities(native_decision):
    frame, _ = api().build_decision_frame(*deepcopy(native_decision))
    pack = api().encode_state(frame)

    def check(node, available):
        if node['kind'] == 'ref':
            assert type(node['index']) is int and 0 <= node['index'] < available
        elif node['kind'] == 'map':
            for pair in node['items']:
                assert len(pair) == 2
                for child in pair:
                    check(child, available)
        elif node['kind'] in {'list', 'set'}:
            for child in node['items']:
                check(child, available)
    for index, entity in enumerate(pack['entities']):
        check(entity, index)
    check(pack['root'], len(pack['entities']))
