"""Canonical retained positions; no invented Oracle text, live DB or network."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, decode_action, encode_action
from tests.test_training_environment import keep, resolve
from tests.scheduler_fixture_position import ordinary_position


FIXTURES = Path(__file__).parent / 'fixtures'
FILES = ('cryptic_command.json', 'ineffective_destruction.json', 'variable_spell_costs.json',
         'ward.json', 'permanent_spell_context.json', 'counter_replacements.json',
         'activated_top_selection/impulse.json', 'activated_top_selection/opt.json',
         'activated_top_selection/recruitment-officer.json', 'activated_top_selection/serra-angel.json',
         'activated_top_selection/savannah-lions.json', 'linked_discard.json')


@pytest.fixture(autouse=True)
def forbid_database_and_network(monkeypatch):
    import socket
    import sqlite3
    def forbidden(*args, **kwargs):
        raise AssertionError('Choice qualification cannot open a database or network connection')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(sqlite3, 'connect', forbidden)


def canonical(name):
    for filename in FILES:
        data = json.loads((FIXTURES / filename).read_text())
        rows = data if isinstance(data, list) else [data] if 'name' in data else data.values()
        for row in rows:
            if isinstance(row, dict) and row.get('name') == name:
                assert isinstance(row.get('oracle_text'), str) and row.get('type_line')
                return row
    raise AssertionError('Missing existing canonical fixture: ' + name)


def position(seat=1):
    environment = TrainingEnvironment()
    environment.reset(seed=17)
    keep(environment)
    state = environment._state
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    ordinary_position(state)
    state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    return environment


def card(environment, name, seat, zone=Zone.HAND):
    raw = canonical(name)
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=17)
    instance = deepcopy(next(iter(sample.cards.values())))
    state = environment._state
    instance.id = state.allocate_object_id()
    instance.owner = instance.controller = seat
    instance.move_to_zone(zone)
    state.cards[instance.id] = instance
    getattr(state.players[seat], zone.value).append(instance.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, instance.id)
    assert instance.name == raw['name'] and instance.oracle_text == raw['oracle_text']
    assert instance.mana_cost == raw['mana_cost'] and instance.type_line == raw['type_line']
    return instance.id


def cast(environment, cid, targets=None, **extra):
    move = next(p['hint'] for p in environment.prompts()
                if p['hint']['type'] == 'cast_spell' and p['hint']['card_id'] == cid)
    return {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {},
            'cost_choice': {'id': move['cost_options'][0]['id']}, **extra}


def replay(environment, action, invalid=None):
    """Every actual boundary replays all root fields, private continuation and RNG."""
    before = environment.snapshot()
    encoded = encode_action(action)
    assert encode_action(decode_action(encoded)) == encoded
    assert environment.lookup(action)['id'] == encoded
    assert environment.snapshot() == before
    if invalid is not None:
        assert environment.action_mask([action, invalid]) == [True, False]
        with pytest.raises(ActionRejected):
            environment.step(invalid)
        assert environment.snapshot() == before
    restored = TrainingEnvironment()
    restored.restore(before)
    assert restored.observe(restored.acting_seat) == environment.observe(environment.acting_seat)
    assert environment.step(encoded) == restored.step(action)
    assert environment.snapshot() == restored.snapshot()


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_modal_per_mode_targets_and_missing_mode_are_not_inferred(seat):
    environment = position(seat)
    cid = card(environment, 'Cryptic Command', seat)
    target = card(environment, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
    modes = ["Return target permanent to its owner's hand", 'Draw a card']
    action = cast(environment, cid, {'mode_texts': modes,
        'mode_targets': {modes[0]: {'target_card_id': target}, modes[1]: {}}})
    replay(environment, action, {**action, 'targets': {}})
    resolve(environment)
    assert target in environment._state.players[3-seat].hand


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x', [0, 2])
def test_actual_variable_x_and_full_discard_count_are_reversible(seat, x):
    environment = position(seat)
    cid = card(environment, 'Sickening Dreams', seat)
    selection = environment.observe(seat)['players'][str(seat)]['hand'][:x]
    action = cast(environment, cid, {'x_value': x})
    action['cost_choice']['discard_card_ids'] = selection
    replay(environment, action, {**action, 'targets': {}})
    assert set(selection).issubset(environment._state.players[seat].graveyard)
    resolve(environment)
    assert [environment._state.players[p].life for p in (1, 2)] == [20-x, 20-x]


@pytest.mark.parametrize('name', ['Opt', 'Impulse'])
@pytest.mark.parametrize('seat', [1, 2])
def test_actual_private_top_partition_and_order_restore_without_continuation_leak(name, seat):
    environment = position(seat)
    cid = card(environment, name, seat)
    environment.step(cast(environment, cid))
    resolve(environment)
    prompt = environment.prompts()[0]
    observed = environment.observe(seat)
    assert observed['pending_choice']['prompts'] == environment.prompts()
    assert 'prompts' not in environment.observe(3-seat)['pending_choice']
    assert environment.prompts(3-seat) == []
    assert 'card_ids' in prompt['required_choices'][0]
    options = prompt['hint']['options']
    assert set(options).issubset(observed['known_cards'])
    pending_json = json.dumps(observed['pending_choice'])
    assert not any(field in pending_json for field in ('continuation', 'effect_key', 'starting_decks', 'rng_state'))
    selected = [] if name == 'Opt' else options[:1]
    replay(environment, {'type': 'choose_mechanic', 'card_ids': selected},
           {'type': 'choose_mechanic', 'choice_id': options[0]})
    if name == 'Impulse':
        prompt = environment.prompts()[0]
        assert prompt['hint']['kind'] == 'topdeck_bottom_order'
        ordered = list(reversed(prompt['hint']['options']))
        replay(environment, {'type': 'choose_mechanic', 'card_ids': ordered},
               {'type': 'choose_mechanic', 'card_ids': ordered[:-1]})
        assert environment._state.players[seat].library[:len(ordered)] == ordered
    assert environment._state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
def test_private_officer_inspected_misses_visible_only_to_actor_and_aliasable(seat):
    environment = position(seat)
    cid = card(environment, 'Recruitment Officer', seat, Zone.BATTLEFIELD)
    top = [card(environment, name, seat, Zone.LIBRARY) for name in
           ('Serra Angel', 'Opt', 'Savannah Lions', 'Serra Angel')]
    environment.step({'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})
    resolve(environment)
    observation = environment.observe(seat)
    assert set(top).issubset(observation['known_cards'])
    assert not set(top).intersection(environment.observe(3-seat)['known_cards'])
    assert len(observation['pending_choice']['prompts'][0]['hint']['inspected_cards']) == 4
    from training.dataset import EpisodeAliases, canonical as dataset_json
    assert all(cid not in dataset_json(EpisodeAliases().observation(observation)) for cid in top)
    replay(environment, {'type': 'choose_mechanic', 'card_ids': ['__none__']},
           {'type': 'choose_mechanic', 'card_ids': [top[0]]})
    assert not environment._state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_trigger_order_target_optional_boundaries_replay(seat):
    environment = position(seat)
    card(environment, 'Soul Warden', seat, Zone.BATTLEFIELD)
    target = card(environment, 'Sol Ring', 3-seat, Zone.BATTLEFIELD)
    cid = card(environment, 'Reclamation Sage', seat)
    environment.step(cast(environment, cid))
    resolve(environment)
    prompt = environment.prompts()[0]
    assert prompt['hint']['type'] == 'choose_trigger_order'
    ordered = list(reversed(prompt['hint']['trigger_order']))
    replay(environment, {'type': 'choose_trigger_order', 'trigger_order': ordered},
           {'type': 'choose_trigger_order', 'trigger_order': ordered[:-1]})
    hint = next(p['hint'] for p in environment.prompts() if p['hint'].get('target_card_id') == target)
    replay(environment, {'type': 'choose_trigger_target', 'stack_id': hint['stack_id'], 'target_card_id': target},
           {'type': 'choose_trigger_target', 'stack_id': hint['stack_id'], 'target_player': 3-seat})
    # Resolve the untargeted Warden trigger first if the chosen order put it on top.
    for _ in range(2):
        if environment._state.pending_trigger_order:
            break
        resolve(environment)
    hint = environment.prompts()[0]['hint']
    assert hint['type'] == 'choose_optional_effect'
    replay(environment, {'type': 'choose_optional_effect', 'stack_id': hint['stack_id'], 'accept': True},
           {'type': 'choose_optional_effect', 'stack_id': hint['stack_id']})
    assert target in environment._state.players[3-seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ward_payment_and_discard_continuation_replay(seat):
    environment = position(seat)
    target = card(environment, 'Graveyard Trespasser', 3-seat, Zone.BATTLEFIELD)
    # Canonical Bolt comes from the builtin red seat (or canonical ward fixture).
    cid = card(environment, 'Lightning Bolt', seat)
    environment.step(cast(environment, cid, {'target_card_id': target}))
    resolve(environment)
    assert environment.prompts()[0]['hint']['kind'] == 'ward_payment'
    replay(environment, {'type': 'choose_mechanic', 'card_ids': ['pay']},
           {'type': 'choose_mechanic', 'card_ids': []})
    assert environment.prompts()[0]['hint']['kind'] == 'ward_cost_cards'
    selection = environment.prompts()[0]['hint']['options'][-1:]
    replay(environment, {'type': 'choose_mechanic', 'card_ids': selection},
           {'type': 'choose_mechanic', 'card_ids': selection * 2})
    assert selection[0] in environment._state.players[seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_counter_replacement_order_is_actual_and_replayable(seat):
    from effects.handlers import add_counters
    environment = position(seat)
    target = card(environment, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    card(environment, 'Hardened Scales', seat, Zone.BATTLEFIELD)
    card(environment, 'Doubling Season', seat, Zone.BATTLEFIELD)
    # Trusted retained effect boundary; Oracle metadata is never replaced.
    add_counters(environment._state, seat, {'target_card_id': target, 'amount': 1})
    assert environment._state.pending_replacement_choice
    prompt = environment.prompts()[0]
    assert prompt['required_choices'] == ['replacement_source_id']
    source = next(p['hint']['replacement_source_id'] for p in environment.prompts()
                  if p['hint']['replacement_name'] == 'Hardened Scales')
    replay(environment, {'type': 'choose_replacement', 'replacement_source_id': source},
           {'type': 'choose_replacement', 'replacement_source_id': 'missing'})
    assert environment._state.cards[target].counters['+1/+1'] == 4


def test_shared_consumer_intent_contract_filters_display_only_and_remains_atomic():
    environment = position()
    cid = card(environment, 'Lightning Bolt', 1)
    action = cast(environment, cid, {'target_player': 2})
    intent = {**action, 'card_name': 'Lightning Bolt', 'mana_cost': '{R}',
              'cost_options': [{'id': 'DO NOT INFER THIS'}], 'target_hints': {'PRIVATE': True}}
    before = environment.snapshot()
    assert environment.lookup_intent(intent) == environment.lookup(action)
    assert environment.snapshot() == before
    with pytest.raises(ActionRejected):
        environment.lookup(intent)  # Strict serialized/executable boundary stays strict.
    for invalid in ({**intent, '_invalid_ai_choice': True},
                    {**intent, 'cost_choice': None}, {**intent, 'targets': {}}):
        with pytest.raises(ActionRejected):
            environment.lookup_intent(invalid)
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_private_observation_and_prompts_ignore_unauthorized_hidden_identity_permutations(seat):
    environment = position(seat)
    cid = card(environment, 'Impulse', seat)
    environment.step(cast(environment, cid))
    resolve(environment)
    before = environment.observe(seat)
    prompts = environment.prompts()
    original = environment.snapshot()
    environment.observe(seat)
    environment.prompts()
    environment.action_mask([{'type': 'choose_mechanic', 'card_ids': []}])
    assert environment.snapshot() == original
    state = environment._state
    authorized = set(state.pending_mechanic_choice['options'])
    for ids in (state.players[3-seat].hand, state.players[3-seat].library,
                [cid for cid in state.players[seat].library if cid not in authorized]):
        a, b = ids[:2]
        one, two = deepcopy(state.cards[a]), deepcopy(state.cards[b])
        one.id, two.id = b, a
        state.cards[a], state.cards[b] = two, one
    state.players[3-seat].library.reverse()
    state.starting_decks[3-seat] = deepcopy(state.starting_decks[seat])
    state.log.append('PRIVATE future identity'); state.rng.random()
    assert environment.observe(seat) == before and environment.prompts() == prompts


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_counter_and_return_modes_preserve_distinct_stack_and_card_targets(seat):
    environment = position(seat)
    environment._state.players[3-seat].mana_pool = {'R': 1}
    bolt = card(environment, 'Lightning Bolt', 3-seat)
    environment._state.priority_player = 3-seat
    environment.step(cast(environment, bolt, {'target_player': seat}))
    environment.step({'type': 'pass_priority'})
    cid = card(environment, 'Cryptic Command', seat)
    target = card(environment, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
    stack_id = environment.observe(seat)['stack'][0]['id']
    modes = ['Counter target spell', "Return target permanent to its owner's hand"]
    action = cast(environment, cid, {'mode_texts': modes, 'mode_targets': {
        modes[0]: {'target_stack_id': stack_id}, modes[1]: {'target_card_id': target}}})
    replay(environment, action, {**action, 'targets': {'mode_texts': modes,
           'mode_targets': {modes[0]: {'target_stack_id': stack_id}}}})
    resolve(environment)
    assert bolt in environment._state.players[3-seat].graveyard
    assert target in environment._state.players[3-seat].hand
    assert environment._state.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_abrade_single_mode_target_is_explicit_and_engine_checked(seat):
    environment = position(seat)
    cid = card(environment, 'Abrade', seat)
    target = card(environment, 'Sol Ring', 3-seat, Zone.BATTLEFIELD)
    mode = 'Destroy target artifact'
    action = cast(environment, cid, {'mode_text': mode, 'target_card_id': target})
    replay(environment, action, {**action, 'targets': {'mode_text': mode}})
    resolve(environment)
    assert target in environment._state.players[3-seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_dredge_draw_replacement_requires_choice_id_not_a_card_list(seat):
    environment = position(seat)
    imp = card(environment, 'Stinkweed Imp', seat, Zone.GRAVEYARD)
    opt = card(environment, 'Opt', seat)
    environment.step(cast(environment, opt))
    resolve(environment)
    replay(environment, {'type': 'choose_mechanic', 'card_ids': []})
    hint = environment.prompts()[0]['hint']
    assert hint['kind'] == 'draw' and imp in hint['options']
    assert environment.prompts()[0]['required_choices'][0].startswith('choice_id ')
    library_count = len(environment._state.players[seat].library)
    replay(environment, {'type': 'choose_mechanic', 'choice_id': imp},
           {'type': 'choose_mechanic', 'card_ids': [imp]})
    assert imp in environment._state.players[seat].hand
    assert len(environment._state.players[seat].library) == library_count - 5


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_cleanup_exact_count_discard_is_not_defaulted(seat):
    environment = position(seat)
    card(environment, 'Lightning Bolt', seat)
    card(environment, 'Opt', seat)
    environment._state.step = Step.END_STEP
    ordinary_position(environment._state)
    resolve(environment)
    hint = environment.prompts()[0]['hint']
    assert hint['kind'] == 'cleanup_discard' and hint['count'] == 2
    selected = list(reversed(hint['options'][:2]))
    replay(environment, {'type': 'choose_mechanic', 'card_ids': selected},
           {'type': 'choose_mechanic', 'card_ids': selected[:1]})
    assert set(selected).issubset(environment._state.players[seat].graveyard)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ward_decline_counters_original_spell_after_boundary_replay(seat):
    environment = position(seat)
    target = card(environment, 'Tolarian Terror', 3-seat, Zone.BATTLEFIELD)
    cid = card(environment, 'Lightning Bolt', seat)
    environment.step(cast(environment, cid, {'target_card_id': target}))
    resolve(environment)
    assert 'decline' in environment.prompts()[0]['hint']['options']
    replay(environment, {'type': 'choose_mechanic', 'card_ids': ['decline']},
           {'type': 'choose_mechanic', 'choice_id': 'decline'})
    assert cid in environment._state.players[seat].graveyard
    assert target in environment._state.players[3-seat].battlefield
    assert not environment._state.stack
