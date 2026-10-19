"""Pure first-boundary witnesses; the original HTTP test is NOT executed here."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, Zone, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_faces import apply_transform_face
from rules_engine.card_types import printed_card_types
from tests import test_stack_copies as original
from tests.stack_copy_printed_b720 import (
    PRINTED_FIELDS, SOURCES, canonical_stack_card, raw_card,
)


SUBJECTS = (
    ('test_copied_spell_uses_stack_and_countering_copy_preserves_original', 'copy_spell', 'Lightning Bolt'),
    ('test_memory_deluge_copy_has_zero_mana_spent_to_cast', 'copy_spell', 'Memory Deluge'),
    ('test_copied_ability_resolves_after_a_response_window', 'copy_ability', 'Soul Warden'),
    ('test_copied_spell_fizzles_when_its_only_target_becomes_illegal', 'copy_spell', 'Grizzly Bears'),
    ('test_copied_permanent_spell_enters_as_token_without_moving_card', 'copy_spell', 'Grizzly Bears'),
    ('test_twincast_cast_resolves_copy_before_original_after_priority_passes', 'checked_action', 'Twincast'),
    ('test_twincast_cast_resolves_copy_before_original_after_priority_passes', 'checked_action', 'Lightning Bolt'),
    ('test_counterspell_copy_cannot_target_itself', 'copy_spell', 'Counterspell'),
    ('test_counterspell_copy_cannot_target_itself', 'copy_spell', 'Lightning Bolt'),
    ('test_creature_spell_copy_offers_only_legal_new_creature_targets', 'copy_spell', 'Murder'),
    ('test_activated_ability_copy_can_choose_a_new_target', 'copy_ability', 'Prodigal Pyromancer'),
    ('test_activated_ability_copy_fizzles_when_new_target_becomes_illegal', 'copy_ability', 'Prodigal Pyromancer'),
    ('test_activated_ability_copy_fizzles_when_new_target_becomes_illegal', 'copy_ability', 'Grizzly Bears'),
    ('test_lithoform_activation_copies_targeted_ability_with_human_choice', 'checked_action', 'Prodigal Pyromancer'),
    ('test_lithoform_activation_copies_targeted_ability_with_human_choice', 'checked_action', 'Lithoform Engine'),
    ('test_lithoform_cannot_copy_an_opponents_ability', 'checked_action', 'Prodigal Pyromancer'),
    ('test_lithoform_cannot_copy_an_opponents_ability', 'checked_action', 'Lithoform Engine'),
    ('test_lithoform_permanent_spell_copy_enters_as_token', 'checked_action', 'Lithoform Engine'),
    ('test_lithoform_permanent_spell_copy_enters_as_token', 'checked_action', 'Grizzly Bears'),
    ('test_lithoform_permanent_spell_copy_enters_as_token', 'checked_action', 'Lightning Bolt'),
    ('test_divided_copy_retargets_slots_without_reallocating_damage', 'copy_spell', 'Pyrotechnics'),
    ('test_divided_copy_retargets_slots_without_reallocating_damage', 'copy_spell', 'Grizzly Bears'),
    ('test_twincast_divided_copy_finishes_only_after_all_target_choices', 'checked_action', 'Pyrotechnics'),
    ('test_twincast_divided_copy_finishes_only_after_all_target_choices', 'checked_action', 'Grizzly Bears'),
    ('test_twincast_divided_copy_finishes_only_after_all_target_choices', 'checked_action', 'Twincast'),
    ('test_copied_spell_uses_stack_and_countering_copy_preserves_original', 'copy_spell', 'Island'),
    ('test_triggered_ability_copy_uses_trigger_clause_for_legal_targets', 'copy_ability', 'Goblin Arsonist'),
)


def _main_binding_snapshot():
    return 'main' in sys.modules, sys.modules.get('main')


def _assert_main_binding(previous):
    present, module = previous
    assert ('main' in sys.modules) == present, 'main module presence changed within fidelity body'
    if present:
        assert sys.modules['main'] is module, 'main module identity changed within fidelity body'


def expected_printed(name):
    # Independent of the new materializer's CardInstance construction.
    data = ScryfallSyncService._normalize_payload(raw_card(name), None)
    types = printed_card_types(data['type_line'])
    card = CardInstance(id='expectation-only', owner=1, controller=1, zone=Zone.HAND,
        name=data['name'], oracle_text=data['oracle_text'], type_line=data['type_line'],
        types=types, mana_cost=data['mana_cost'], power=_infer_power(name, data['power'], types),
        toughness=_infer_toughness(name, data['toughness'], types),
        printed_power=data['power'], printed_toughness=data['toughness'],
        loyalty=int(data['loyalty']) if data['loyalty'] is not None else None,
        colors=data['colors'].split(',') if data['colors'] else [],
        keywords=_infer_keywords(data['oracle_text']), image_uri=data['image_uri'],
        layout=data['layout'], card_faces=json.loads(data['card_faces_json']))
    if card.card_faces and card.layout in {'transform', 'modal_dfc'}:
        apply_transform_face(card, 0)
    return {key: deepcopy(getattr(card, key)) for key in PRINTED_FIELDS}


@pytest.mark.parametrize('test_name,boundary,name', SUBJECTS,
    ids=[test + ':' + name for test, boundary, name in SUBJECTS])
def test_original_first_consumer_receives_complete_printed_card(monkeypatch, test_name, boundary, name):
    main_before = _main_binding_snapshot()
    assert not test_name.startswith('test_http_')
    delegate = getattr(original, boundary)
    captured = []

    class BeforeConsumer(BaseException):
        pass

    def observe(state, *args, **kwargs):
        _assert_main_binding(main_before)
        found = [deepcopy(card) for card in state.cards.values() if card.name == name]
        if not found:
            return delegate(state, *args, **kwargs)
        captured.extend(found)
        raise BeforeConsumer

    with monkeypatch.context() as patch:
        patch.setattr(original, boundary, observe)
        with pytest.raises(BeforeConsumer):
            getattr(original, test_name)()
    assert captured
    expected = expected_printed(name)
    for card in captured:
        assert {key: getattr(card, key) for key in PRINTED_FIELDS} == expected
    _assert_main_binding(main_before)


@pytest.mark.parametrize('name', sorted(SOURCES))
def test_materializer_preserves_full_facts_and_physical_identity_without_aliases(name):
    raw_before = raw_card(name)
    first = canonical_stack_card(name, id='one', owner=1, controller=2, zone=Zone.STACK)
    second = canonical_stack_card(name, id='two', owner=2, controller=1, zone=Zone.HAND)
    assert {key: getattr(first, key) for key in PRINTED_FIELDS} == expected_printed(name)
    assert {key: getattr(second, key) for key in PRINTED_FIELDS} == expected_printed(name)
    assert (first.id, first.owner, first.controller, first.zone) == ('one', 1, 2, Zone.STACK)
    assert (second.id, second.owner, second.controller, second.zone) == ('two', 2, 1, Zone.HAND)
    first.colors.append('local-probe')
    first.keywords.append('local-probe')
    first.card_faces.append({'name': 'local-probe'})
    first.printed_characteristics['local-probe'] = True
    assert {key: getattr(second, key) for key in PRINTED_FIELDS} == expected_printed(name)
    assert raw_card(name) == raw_before


def test_original_28_names_145_assertions_frames_and_engine_actions_are_protected():
    tree = ast.parse(Path(original.__file__).read_bytes())
    contract = json.loads((Path(__file__).parent / 'fixtures/stack_copy_printed_b720/ORIGINAL_CONTRACT.json').read_bytes())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    assert len(functions) == 28
    assert [n.name for n in functions] == contract['functions']
    assert [[ast.dump(d, include_attributes=False) for d in n.decorator_list] for n in functions] == contract['decorators']
    assertions = [hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                  for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    assert len(assertions) == 145 and assertions == contract['assertions']
    frames = [ast.dump(n, include_attributes=False) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'StackItem']
    actions = [ast.dump(n, include_attributes=False) for n in ast.walk(tree)
               if isinstance(n, ast.Call) and (isinstance(n.func, ast.Name) and n.func.id == 'checked_action'
                   or isinstance(n.func, ast.Attribute) and n.func.attr == 'take_action')]
    assert frames == contract['StackItem_AST']
    assert actions == contract['engine_action_AST']


def test_full_raw_roles_and_remaining_uncaptured_boundaries_are_explicit():
    main_before = _main_binding_snapshot()
    assert {name for test, boundary, name in SUBJECTS} == set(SOURCES)
    assert len(SOURCES) == 12
    assert 'Flashback' in raw_card('Memory Deluge')['oracle_text']
    assert len(raw_card('Lithoform Engine')['oracle_text'].splitlines()) == 3
    assert raw_card('Murder')['mana_cost'] == '{1}{B}{B}'
    assert raw_card('Goblin Arsonist')['name'] == 'Goblin Arsonist'
    assert raw_card('Island')['name'] == 'Island'
    _assert_main_binding(main_before)


def test_ordinary_canonical_birth_preserves_controlled_physical_resources_and_rng():
    main_before = _main_binding_snapshot()
    ordinary = original._state()
    protocol = original._state(controlled=True)
    assert ordinary.players == protocol.players
    assert ordinary.rng.getstate() == protocol.rng.getstate()
    assert ordinary.log == protocol.log
    assert len(ordinary.cards) == len(protocol.cards) == 120
    assert set(ordinary.cards) == set(protocol.cards)
    for card_id, card in ordinary.cards.items():
        assert {k: v for k, v in vars(card).items() if k not in PRINTED_FIELDS} == {
            k: v for k, v in vars(protocol.cards[card_id]).items() if k not in PRINTED_FIELDS}
    for field in ('pregame_pending', 'kept_hands', 'priority_player', 'turn',
                  'active_player', 'step', 'stack'):
        assert getattr(ordinary, field) == getattr(protocol, field)
    _assert_main_binding(main_before)


def test_state_change_is_only_the_declared_printed_deck_data_expression():
    path = Path(__file__).parent / 'fixtures/stack_copy_printed_b720/STATE_FIXTURE_PREIMAGE.json'
    contract = json.loads(path.read_bytes())
    tree = ast.parse(Path(original.__file__).read_bytes())
    state = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_state')
    deck = state.body[0]
    assert isinstance(deck, ast.Assign) and [n.id for n in deck.targets] == ['deck']
    assert ast.dump(deck.value, include_attributes=False) in {
        contract['deck_value_AST'], contract['canonical_deck_value_AST']}
    inverse = deepcopy(state)
    inverse.body[0].value = ast.parse(contract['old_deck_expression'], mode='eval').body
    assert ast.dump(inverse, include_attributes=False) == contract['function_AST']
    helper = Path(__file__).parent / 'controlled_basic_game_support.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == contract['controlled_helper_sha256']


def test_full_canonical_arsonist_preserves_the_original_trigger_copy_sequence():
    main_before = _main_binding_snapshot()
    original.test_triggered_ability_copy_uses_trigger_clause_for_legal_targets()
    _assert_main_binding(main_before)
