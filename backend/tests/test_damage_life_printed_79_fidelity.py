"""Full facts at existing first consumers; later declared mutations are separate."""
import ast
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, Zone, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_faces import apply_transform_face
from rules_engine.card_types import printed_card_types
from tests.damage_life_printed_79 import raw_card

KONDA = 'The Fall of Lord Konda // Fragment of Konda'
PRINTED = ('name', 'oracle_text', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
    'printed_power', 'printed_toughness', 'loyalty', 'colors', 'keywords', 'layout',
    'card_faces', 'selected_face_index', 'printed_characteristics', 'image_uri')
SUBJECTS = (
    ('test_life_total_lock', 'test_life_total_lock_blocks_changes_and_nonzero_payments_but_not_zero_payment', 'player_cant_gain_life', 'Platinum Emperion'),
    ('test_life_total_lock', 'test_life_total_lock_blocks_changes_and_nonzero_payments_but_not_zero_payment', 'player_cant_gain_life', 'Island'),
    ('test_life_total_lock', 'test_locked_life_prevents_conditional_land_payment', 'land_entry_options', 'Sacred Foundry'),
    ('test_life_total_lock', 'test_damage_is_still_dealt_and_opponent_lifelink_still_gains_life', '_combat_damage_step', 'Vampire Nighthawk'),
    ('test_life_total_lock', 'test_infect_damage_still_grants_poison_under_life_total_lock', 'apply_player_damage', 'Glistener Elf'),
    ('test_life_total_lock', 'test_life_payment_cost_can_use_exact_remaining_life_without_lock', 'activated_cost_available', 'Cruel Sadist'),
    ('test_life_total_lock', 'test_font_of_agonies_triggers_after_cruel_sadist_life_payment', 'RulesEngine.legal_moves', 'Font of Agonies'),
    ('test_life_total_lock', 'test_withering_boon_additional_life_cost_triggers_font_above_spell', 'checked_action', 'Withering Boon'),
    ('test_life_total_lock', 'test_withering_boon_additional_life_cost_triggers_font_above_spell', 'checked_action', 'Grizzly Bears'),
    ('test_life_total_lock', 'test_additional_cost_uses_the_same_life_payment_legality', 'check_cost_option_available', 'Lightning Bolt'),
    ('test_lifelink_gain_events', 'test_noncombat_lifelink_uses_damage_after_prevention', 'deal_damage', "Ajani's Pridemate"),
    ('test_lifelink_gain_events', 'test_lifelink_gain_uses_alhammarrets_archive_replacement', 'combat.combat_damage', "Alhammarret's Archive"),
    ('test_lifelink_gain_events', 'test_human_lifelink_replacement_choice_survives_snapshot_before_sba', 'combat.combat_damage', 'Boon Reflection'),
    ('test_lifelink_gain_events', 'test_lifelink_source_death_waits_for_gain_choice', 'combat.combat_damage', 'Centaur Courser'),
    ('test_lifelink_gain_events', 'test_lifelink_gain_replaced_by_draw_resumes_remaining_source', 'combat.combat_damage', 'Nefarious Lich'),
    ('test_divided_damage_resolution', 'test_one_illegal_target_keeps_original_damage_split', 'checked_action', 'Pyrotechnics'),
    ('test_divided_damage_resolution', 'test_one_illegal_target_keeps_original_damage_split', 'checked_action', 'Wall of Omens'),
    ('test_divided_damage_resolution', 'test_divided_damage_requires_a_recipient_when_players_have_shroud', 'RulesEngine.legal_moves', 'Ivory Mask'),
    ('test_divided_damage_resolution', 'test_divided_damage_replacement_choice_preserves_first_share_after_snapshot', 'checked_action', 'Protection of the Hekma'),
    ('test_departed_damage_sources', 'test_departed_source_uses_granted_lifelink_and_infect_after_snapshot', 'RulesEngine.take_action', 'Prodigal Pyromancer'),
    ('test_departed_damage_sources', 'test_self_sacrifice_damage_ability_keeps_granted_lifelink', 'RulesEngine.take_action', 'Fanatical Firebrand'),
    ('test_departed_damage_sources', 'test_departed_batch_source_uses_one_last_known_lifelink_gain', 'add_to_stack', 'Crypt Rats'),
    ('test_damage_trigger_targets', 'test_human_mayhem_devil_can_target_creature_after_snapshot', 'sacrifice', 'Mayhem Devil'),
    ('test_damage_trigger_targets', 'test_havoc_jester_uses_the_same_printed_sacrifice_damage_path', 'sacrifice', 'Havoc Jester'),
    ('test_damage_trigger_targets', 'test_human_mayhem_devil_can_target_creature_after_snapshot', 'sacrifice', 'Everflowing Chalice'),
    ('test_damage_trigger_targets', 'test_human_mayhem_devil_can_target_creature_after_snapshot', 'sacrifice', 'Llanowar Elves'),
    ('test_damage_trigger_targets', 'test_human_mayhem_devil_can_target_planeswalker_loyalty', 'RulesEngine.legal_moves', 'Teferi, Hero of Dominaria'),
    ('test_sacrifice_drain', 'test_sacrifice_trigger_loses_and_gains_life', 'sacrifice', 'Popular Egotist'),
    ('test_sacrifice_drain', 'test_hexproof_opponent_prevents_targeted_sacrifice_drain', 'sacrifice', 'Leyline of Sanctity'),
    ('test_combat_damage_windows', 'test_first_strike_attacker_kills_blocker_before_regular_step', 'RulesEngine.take_action', 'Youthful Knight'),
    ('test_combat_damage_windows', 'test_double_strike_uses_two_priority_windows_and_snapshot_resume', 'RulesEngine.take_action', 'Boros Swiftblade'),
    ('test_combat_damage_windows', 'test_instant_can_be_cast_after_first_damage_before_regular_damage', 'RulesEngine.take_action', 'Shock'),
    ('test_death_last_known', 'test_single_death_uses_effective_power_before_exit_and_survives_snapshot', 'effective_power', 'Heartfire Hero'),
    ('test_death_last_known', 'test_single_death_uses_effective_power_before_exit_and_survives_snapshot', 'effective_power', 'Glorious Anthem'),
    ('test_death_last_known', 'test_single_death_uses_effective_power_before_exit_and_survives_snapshot', 'effective_power', 'Forest'),
    ('test_death_last_known', 'test_wipe_preserves_power_granted_by_a_simultaneously_dying_lord', 'effective_power', 'Cacophony Scamp'),
    ('test_death_last_known', 'test_wipe_preserves_power_granted_by_a_simultaneously_dying_lord', 'effective_power', 'Goblin Chieftain'),
    ('test_death_last_known', 'test_transformed_back_face_self_death_trigger_survives_front_face_reset', 'apply_transform_face', KONDA),
)


def expected_card(name, face_index=0):
    raw = raw_card(name)
    data = ScryfallSyncService._normalize_payload(raw, None)
    types = printed_card_types(data['type_line'])
    card = CardInstance(id='expectation-only', owner=1, controller=1, zone=Zone.HAND,
        name=data['name'], types=types, oracle_text=data['oracle_text'],
        mana_cost=data['mana_cost'], type_line=data['type_line'],
        power=_infer_power(data['name'], data['power'], types),
        toughness=_infer_toughness(data['name'], data['toughness'], types),
        printed_power=data['power'], printed_toughness=data['toughness'],
        loyalty=int(data['loyalty']) if data['loyalty'] is not None else None,
        colors=data['colors'].split(',') if data['colors'] else [],
        keywords=_infer_keywords(data['oracle_text']), layout=data['layout'],
        card_faces=json.loads(data['card_faces_json']), image_uri=data['image_uri'])
    if card.card_faces and card.layout in {'transform', 'modal_dfc'}:
        apply_transform_face(card, face_index)
    return card


def printed(card):
    return {key: deepcopy(getattr(card, key)) for key in PRINTED}


def capture(monkeypatch, module_name, test_name, boundary, raw_name):
    module = importlib.import_module('tests.' + module_name)
    owner = module
    parts = boundary.split('.')
    for part in parts[:-1]:
        owner = getattr(owner, part)
    attribute = parts[-1]
    delegate = getattr(owner, attribute)
    raw = raw_card(raw_name)
    identities = {raw['name'], *(face['name'] for face in raw.get('card_faces', []))}
    found = []

    class BeforeConsumer(BaseException):
        pass

    def observe(*args, **kwargs):
        cards = [arg for arg in args if isinstance(arg, CardInstance)]
        for arg in args:
            if hasattr(arg, 'cards') and hasattr(arg, 'players'):
                cards.extend(arg.cards.values())
        unique = {id(card): card for card in cards if card.name in identities}
        if not unique:
            return delegate(*args, **kwargs)
        found.append([deepcopy(card) for card in unique.values()])
        raise BeforeConsumer

    with monkeypatch.context() as patch:
        patch.setattr(owner, attribute, observe)
        with pytest.raises(BeforeConsumer):
            getattr(module, test_name)()
    assert len(found) == 1
    return found[0]


@pytest.mark.parametrize('module_name,test_name,boundary,name', SUBJECTS,
    ids=[m + '.' + t + ':' + n for m, t, b, n in SUBJECTS])
def test_original_first_consumer_has_full_printed_facts(monkeypatch, module_name, test_name, boundary, name):
    cards = capture(monkeypatch, module_name, test_name, boundary, name)
    expected = printed(expected_card(name))
    assert cards
    for card in cards:
        assert printed(card) == expected


def test_all_exact_sources_are_full_fresh_and_independent():
    from tests.damage_life_printed_79 import SOURCES
    assert {row[3] for row in SUBJECTS} == set(SOURCES)
    assert len(SOURCES) == 38
    for name in SOURCES:
        first, second = raw_card(name), raw_card(name)
        assert first == second and first is not second
        assert first['object'] == 'card' and first['name'] == name
        assert all(key in first for key in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'legalities',
            'type_line', 'layout', 'color_identity', 'cmc', 'lang', 'set', 'collector_number'))
        first['legalities'].clear()
        assert raw_card(name)['legalities'] == second['legalities']
    assert raw_card('Centaur Courser')['oracle_text'] == ''


def test_konda_is_one_genuine_parent_with_ordered_independent_faces():
    from tests.damage_life_printed_79 import canonical_card
    parent = raw_card(KONDA)
    assert parent['layout'] == 'transform'
    assert [face['name'] for face in parent['card_faces']] == ['The Fall of Lord Konda', 'Fragment of Konda']
    first = canonical_card(KONDA, id='same-physical', owner=1, controller=1, zone=Zone.BATTLEFIELD)
    second = canonical_card(KONDA, id='other-physical', owner=2, controller=2, zone=Zone.HAND)
    assert printed(first) == printed(second) == printed(expected_card(KONDA))
    assert first.card_faces is not second.card_faces and first.card_faces[0] is not second.card_faces[0]
    apply_transform_face(first, 1)
    assert first.id == 'same-physical' and first.owner == first.controller == 1 and first.zone == Zone.BATTLEFIELD
    assert printed(first) == printed(expected_card(KONDA, 1))
    first.card_faces[0]['name'] = 'local-mutation'
    first.colors.append('local-mutation')
    first.counters['local-mutation'] = 1
    assert printed(second) == printed(expected_card(KONDA)) and second.counters == {}
    assert raw_card(KONDA) == parent


@pytest.mark.parametrize('module_name,test_name,boundary,name,changed', (
    ('test_divided_damage_resolution', 'test_hexproof_after_cast_does_not_redirect_damage_after_snapshot', 'resolve_top_of_stack', 'Wall of Omens', {'first': {'keywords': ['defender', 'hexproof']}}),
    ('test_divided_damage_resolution', 'test_divided_damage_lifelink_counts_only_unprevented_damage_once', 'checked_action', 'Pyrotechnics', {'pyrotechnics': {'keywords': ['lifelink']}}),
    ('test_lifelink_gain_events', 'test_double_strike_lifelink_replaces_each_damage_window_once', 'RulesEngine.take_action', 'Vampire Nighthawk', {}),
))
def test_declared_grants_are_not_claimed_as_pristine(monkeypatch, module_name, test_name, boundary, name, changed):
    cards = capture(monkeypatch, module_name, test_name, boundary, name)
    expected = printed(expected_card(name))
    for card in cards:
        actual = printed(card)
        allowed = changed.get(card.id, {})
        if module_name == 'test_lifelink_gain_events':
            allowed = {'keywords': expected['keywords'] + ['double strike']}
        assert actual == {**expected, **allowed}
        if allowed:
            assert actual != expected


def test_original_names_decorators_and_all_assertions_are_protected():
    root = Path(__file__).parent
    contracts = json.loads((root / 'fixtures/damage_life_printed_79/ORIGINAL_ASSERT_CONTRACTS.json').read_bytes())
    total = 0
    for name, contract in contracts.items():
        tree = ast.parse((root / name).read_bytes())
        functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        assert [node.name for node in functions] == contract['names']
        assert [[ast.dump(d, include_attributes=False) for d in node.decorator_list] for node in functions] == contract['decorators']
        assertions = [hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                      for node in ast.walk(tree) if isinstance(node, ast.Assert)]
        assert assertions == contract['assertions']
        total += len(assertions)
    assert total == 274


def test_intake_is_byte_exact_bounded_and_completed_before_offline_tests():
    root = Path(__file__).parent / 'fixtures/damage_life_printed_79'
    proof = json.loads((root / 'PROVENANCE.json').read_bytes())
    assert proof['complete'] and proof['request_count'] == len(proof['requests']) == 15
    assert not proof['oracle_modified'] and not proof['automatic_retry']
    assert proof['elapsed_seconds'] < 120 and proof['all_NFS_bytes_readback']
    assert proof['source_admission_finished_before_offline_tests_utc']
    for before, after in zip(proof['requests'], proof['requests'][1:]):
        assert after['start_monotonic'] - before['start_monotonic'] >= .3
    for record in proof['requests']:
        data = (root / record['file']).read_bytes()
        assert record['status'] == 200 and record['full_raw_preserved'] and record['identity_verified']
        assert record['response_headers'] and record['response_url'] == record['url']
        assert len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256']
        assert json.loads(data)['name'] == record['canonical_name']


def test_materializer_rejects_printed_overrides():
    from tests.damage_life_printed_79 import canonical_card
    for field, value in [('oracle_text', ''), ('types', []), ('colors', []), ('mana_cost', ''), ('power', 19), ('card_faces', [])]:
        with pytest.raises(AssertionError):
            canonical_card('Lightning Bolt', id='strict', owner=1, controller=1, zone=Zone.HAND, **{field: value})
