"""First real consumer inputs, not a claim that structural poses are printed cards."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import _infer_keywords
from rules_engine.card_types import printed_card_types


FIXTURES = Path(__file__).parent / 'fixtures'
PROVENANCE_SHA = '2c2750acb82ff6746cfbb4cb49c6118f276e9129fd2c819cbc2b5187e0b22f76'
NAMES = (
    'Realmwalker', 'Llanowar Elves', 'Expressive Iteration', 'Forest', 'Island',
    'Memory Deluge', 'Negate', 'Counterspell', 'Sheoldred, the Apocalypse',
    'Entomb', 'Demonic Tutor', 'Buried Alive', 'Rest in Peace', 'Swamp',
    'Griselbrand', 'Reanimate', 'Cultivate', 'Migration Path', 'Collected Company',
    'Plains', 'Storm the Festival', 'Thought-Knot Seer', "Cartographer's Survey",
    'Grizzly Bears', 'Recruitment Officer', 'Militia Bugler',
    'Adeline, Resplendent Cathar', 'Topiary Stomper', 'Mountain', 'Lightning Bolt',
)


def provenance():
    data = (FIXTURES / 'library_canonical_88/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == PROVENANCE_SHA
    return json.loads(data)


def official(name):
    record = provenance()['objects'][name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    if record['file'].endswith('.jsonl'):
        raw = json.loads(data.splitlines()[record['source_line'] - 1])
    else:
        raw = json.loads(data)
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()
    assert digest == record['object_sha256']
    assert raw['name'] == name and raw['object'] == 'card'
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


# module, original function, first consumer, actual named operand
SUBJECTS = (
    ('library_search_rules', 'test_entomb_searches_any_card_into_graveyard', 'spec', 'Entomb'),
    ('library_search_rules', 'test_demonic_tutor_does_not_reveal_hidden_hand_selection_in_log', 'spec', 'Demonic Tutor'),
    ('library_search_rules', 'test_buried_alive_searches_three_creatures_into_graveyard_with_replacement', 'spec', 'Buried Alive'),
    ('library_search_rules', 'test_http_entomb_choice_moves_selected_card_to_graveyard', 'spec', 'Entomb'),
    ('library_search_rules', 'test_cultivate_inference_splits_canonical_land_destinations', 'spec', 'Cultivate'),
    ('library_search_rules', 'test_migration_path_puts_basic_lands_onto_battlefield_tapped', 'spec', 'Migration Path'),
    ('library_search_rules', 'test_library_search_hides_candidates_until_resolution_and_honors_choice', 'hints', 'Cultivate'),
    ('library_search_rules', 'test_library_search_rejects_nonmatching_explicit_selection', 'hints', 'Cultivate'),
    ('library_search_rules', 'test_topdeck_battlefield_tutor_chooses_only_at_resolution', 'hints', 'Collected Company'),
    ('library_search_rules', 'test_topdeck_battlefield_tutor_rejects_nonmatching_selection', 'hints', 'Collected Company'),
    ('library_search_rules', 'test_company_bottom_order_keeps_spell_unresolved_until_second_choice', 'spec', 'Collected Company'),
    ('library_search_rules', 'test_topdeck_put_uses_resolution_library_and_resumes_stack_after_snapshot', 'spec', 'Storm the Festival'),
    ('library_search_rules', 'test_library_search_uses_resolution_library_and_resumes_stack_after_snapshot', 'spec', 'Cultivate'),
    ('top_card_choices', 'test_top_three_hand_exile_bottom_choice_has_temporary_play_permission', 'spec', 'Expressive Iteration'),
    ('top_card_choices', 'test_top_three_choice_accepts_explicit_human_order', 'hints', 'Expressive Iteration'),
    ('top_card_choices', 'test_expressive_iteration_wording_with_exile_verb_is_structured', 'spec', 'Expressive Iteration'),
    ('top_card_choices', 'test_top_three_choice_rejects_duplicate_or_missing_cards', 'hints', 'Expressive Iteration'),
    ('top_card_choices', 'test_iteration_uses_resolution_library_and_turn_after_stack_resume', 'spec', 'Expressive Iteration'),
    ('look_top_select_hand', 'test_mana_spent_top_card_selection_is_not_a_draw', 'spec', 'Memory Deluge'),
    ('look_top_select_hand', 'test_paid_memory_deluge_pauses_for_two_cards_and_resumes_after_snapshot', 'take', 'Memory Deluge'),
    ('look_top_select_hand', 'test_flashback_memory_deluge_looks_at_seven_and_exiles_after_resolution', 'legal', 'Memory Deluge'),
    ('look_top_select_hand', 'test_countered_flashback_spell_is_exiled', 'take', 'Memory Deluge'),
    ('library_permissions', 'test_realmwalker_exposes_only_matching_top_creature_as_library_cast', 'library', 'Realmwalker'),
    ('library_permissions', 'test_realmwalker_choice_is_persisted_when_it_enters', 'stack', 'Realmwalker'),
    ('topdeck_reveal_creature', 'test_recruitment_officer_uses_mana_value_and_reveals_a_qualifying_creature', 'reveal', 'Recruitment Officer'),
    ('topdeck_reveal_creature', 'test_ai_creature_reveal_chooses_at_resolution', 'reveal', 'Recruitment Officer'),
    ('topdeck_reveal_creature', 'test_power_threshold_remains_distinct_and_human_may_decline_after_restart', 'reveal', 'Militia Bugler'),
    ('topdeck_reveal_creature', 'test_human_recruitment_officer_choice_resumes_activated_stack_after_snapshot', 'legal', 'Recruitment Officer'),
    ('topdeck_reveal_creature', 'test_http_human_topdeck_choice_exposes_options_and_accepts_selection', 'reveal', 'Militia Bugler'),
    ('topdeck_lands', 'test_survey_chooses_only_lands_at_resolution_and_forces_tapped_entry', 'spec', "Cartographer's Survey"),
    ('topdeck_lands', 'test_survey_ai_uses_the_same_legal_choice_window', 'spec', "Cartographer's Survey"),
)
SUPPORT_SUBJECTS = (
    ('library_search_rules', 'test_reanimator_ai_entombs_creature_instead_of_mana_fixing_land', 'ai', 'Griselbrand'),
    ('library_search_rules', 'test_reanimator_ai_entombs_creature_instead_of_mana_fixing_land', 'ai', 'Reanimate'),
    ('library_search_rules', 'test_buried_alive_searches_three_creatures_into_graveyard_with_replacement', 'effect', 'Rest in Peace'),
    ('look_top_select_hand', 'test_paid_memory_deluge_pauses_for_two_cards_and_resumes_after_snapshot', 'take', 'Negate'),
    ('look_top_select_hand', 'test_paid_memory_deluge_pauses_for_two_cards_and_resumes_after_snapshot', 'take', 'Counterspell'),
    ('look_top_select_hand', 'test_paid_memory_deluge_pauses_for_two_cards_and_resumes_after_snapshot', 'take', 'Sheoldred, the Apocalypse'),
    ('topdeck_reveal_creature', 'test_recruitment_officer_uses_mana_value_and_reveals_a_qualifying_creature', 'reveal', 'Topiary Stomper'),
    ('topdeck_lands', 'test_survey_chooses_only_lands_at_resolution_and_forces_tapped_entry', 'spec', 'Grizzly Bears'),
)
# These are strict failures, not xfails or exceptions to printed fidelity.
CONFLICT_SUBJECTS = (
    ('library_permissions', 'test_realmwalker_exposes_only_matching_top_creature_as_library_cast', 'library', 'Llanowar Elves'),
    ('topdeck_reveal_creature', 'test_power_threshold_remains_distinct_and_human_may_decline_after_restart', 'reveal', 'Adeline, Resplendent Cathar'),
)


def actual_input(monkeypatch, subject):
    module, test_name, boundary, name = subject
    original = importlib.import_module('tests.test_' + module)
    if boundary in ('legal', 'take'):
        owner = original.RulesEngine
        attribute = 'legal_moves' if boundary == 'legal' else 'take_action'
    elif boundary == 'ai':
        owner, attribute = original.AIAgent, 'choose_action'
    elif boundary == 'stack':
        owner = importlib.import_module('rules_engine.stack_engine')
        attribute = 'resolve_top_of_stack'
    else:
        owner = original
        attribute = {'spec': 'build_ability_spec', 'hints': 'build_cast_hints',
                     'reveal': 'infer_effect_from_oracle', 'library': 'top_library_creature_for_type',
                     'effect': 'resolve_effect'}[boundary]
    delegate = getattr(owner, attribute)
    captured = []

    class BeforeConsumer(BaseException):
        pass

    def capture(*args, **kwargs):
        state = args[1] if boundary in ('legal', 'take', 'ai') else args[0]
        if boundary in ('spec', 'hints', 'reveal') and args[1].name == name:
            card = args[1]
        else:
            matches = [card for card in state.cards.values() if card.name == name]
            if not matches:
                return delegate(*args, **kwargs)
            assert len(matches) == 1
            card = matches[0]
        captured.append((state, card))
        raise BeforeConsumer

    with monkeypatch.context() as patch:
        patch.setattr(owner, attribute, capture)
        with pytest.raises(BeforeConsumer):
            getattr(original, test_name)()
    assert len(captured) == 1
    return captured[0]


def assert_printed(card, raw):
    keys = ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout')
    assert {key: getattr(card, key) for key in keys} == {key: raw[key] for key in keys}
    assert card.types == printed_card_types(raw['type_line'])
    assert card.keywords == _infer_keywords(raw['oracle_text'])
    assert card.card_faces == raw.get('card_faces', [])
    assert card.printed_power == raw.get('power')
    assert card.printed_toughness == raw.get('toughness')
    assert card.loyalty == (int(raw['loyalty']) if raw.get('loyalty') is not None else None)
    assert card.selected_face_index is None


@pytest.mark.parametrize('name', NAMES)
def test_complete_raw_and_provenance_are_pinned_and_independent(name):
    first, second = official(name), official(name)
    assert first == second and first is not second
    assert first['uri'].startswith('https://api.scryfall.com/cards/')
    assert first['legalities'] and len(first) > 50
    first['legalities'].clear()
    assert second == official(name) and second['legalities']


@pytest.mark.parametrize('subject', SUBJECTS + SUPPORT_SUBJECTS,
                         ids=['-'.join((row[0], row[1], row[3])) for row in SUBJECTS + SUPPORT_SUBJECTS])
def test_actual_first_consumer_receives_complete_printed_facts(monkeypatch, subject):
    _, card = actual_input(monkeypatch, subject)
    assert_printed(card, official(subject[3]))


@pytest.mark.parametrize('subject', CONFLICT_SUBJECTS,
                         ids=['HOLD-printed-conflict-' + row[3] for row in CONFLICT_SUBJECTS])
def test_named_structural_conflicts_are_not_reported_as_printed_fidelity(monkeypatch, subject):
    _, card = actual_input(monkeypatch, subject)
    assert_printed(card, official(subject[3]))


@pytest.mark.parametrize('module,test_name,kind', (
    ('top_card_choices', 'test_ai_top_three_choice_uses_resolution_time_cards', 'Sorcery'),
    ('library_search_rules', 'test_ai_topdeck_put_chooses_stronger_creature_at_resolution', 'Creature'),
))
def test_structural_forest_operands_are_not_reported_as_printed_fidelity(monkeypatch, module, test_name, kind):
    from tests.library_canonical_fixtures import ranking_raw_card

    original = importlib.import_module('tests.test_' + module)
    captured = []
    expected_names = (('Tidings', 'Preordain', 'Explore') if kind == 'Sorcery' else
                      ('Deathbloom Gardener', 'Brindle Boar', 'Wayward Swordtooth'))
    delegate = original.resolve_effect

    def capture(state, *args, **kwargs):
        ids = (state.players[1].library[-3:] if kind == 'Sorcery' else
               state.players[1].library[-6:][::2])
        assert len(ids) == len(set(ids)) == 3
        captured.extend(state.cards[cid] for cid in ids)
        for cid, card, name in zip(ids, captured, expected_names):
            assert card.id == cid and card.types == [kind]
            assert_printed(card, ranking_raw_card(name))
        return delegate(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(original, 'resolve_effect', capture)
        getattr(original, test_name)()
    assert len(captured) == 3
    for card, name in zip(captured, expected_names):
        assert_printed(card, ranking_raw_card(name))


@pytest.mark.parametrize('index', (13, 19, 22, 29))
def test_actual_source_printed_facts_survive_snapshot(monkeypatch, index):
    state, card = actual_input(monkeypatch, SUBJECTS[index])
    raw = official(SUBJECTS[index][3])
    assert_printed(card, raw)
    assert state.cards[card.id] is card
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert_printed(restored.cards[card.id], raw)


def test_original_inputs_do_not_share_mutable_printed_metadata(monkeypatch):
    _, first = actual_input(monkeypatch, SUBJECTS[22])
    _, second = actual_input(monkeypatch, SUBJECTS[22])
    assert_printed(first, official('Realmwalker'))
    assert_printed(second, official('Realmwalker'))
    assert first is not second and first.colors is not second.colors
    first.colors.clear()
    first.counters['fidelity-independence'] = 1
    assert second.colors == official('Realmwalker')['colors'] and second.counters == {}


def test_all_raw_source_provenance_is_bound_without_network_intake():
    proof = provenance()
    assert set(proof['objects']) == set(NAMES) and proof['complete_object_count'] == 30
    assert proof['network_requests'] == 0 and proof['oracle_modified'] is False
    for path, digest in proof['source_provenance'].items():
        assert hashlib.sha256((FIXTURES / path).read_bytes()).hexdigest() == digest
    seed = json.loads((FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert seed['snapshot_sha256'] == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
    assert seed['oracle_modified'] is False and seed['response_statuses'] == [200, 200, 200]
    bulk = FIXTURES.parents[1] / 'card_data/mh3_catalog_seed_provenance.json'
    assert hashlib.sha256(bulk.read_bytes()).hexdigest() == proof['bulk_provenance_sha256']
    bulk_pin = json.loads(bulk.read_bytes())['canonical_source']['source_bulk_sha256']
    for record in proof['objects'].values():
        if 'source_file_sha256' in record:
            assert record['source_file_sha256'] == bulk_pin
            assert record['original_HTTP_wire_body_claim'] is False
            assert not (FIXTURES / record['file']).read_bytes().endswith(b'\n')
