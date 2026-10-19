"""Complete official inputs at the two original modules' actual birth boundaries."""
import hashlib
import importlib
import inspect
import json
from dataclasses import replace
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = 'd728f61499dea3e3c03027c5df0c1689d0445c6a66f9240d55a808a48d460c2e'
DISPLAY_ONLY = '/card-images/keyword-zone4f86.jpg'


def raw_card(name):
    proof = (FIXTURES / 'keyword_zone4f86/SOURCES.json').read_bytes()
    assert hashlib.sha256(proof).hexdigest() == SOURCES_SHA
    sources = json.loads(proof)['sources']
    name = 'Delver of Secrets // Insectile Aberration' if name == 'Delver of Secrets' else name
    record = sources[name]
    body = (FIXTURES.parent / record['file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == record['fileSHA']
    value = ([json.loads(line) for line in body.splitlines()]
             if record['file'].endswith('.jsonl') else json.loads(body))
    rows = value if isinstance(value, list) else [value]
    matches = [row for row in rows if row.get('name') == name]
    assert len(matches) == 1
    raw = matches[0]
    assert raw['object'] == 'card'
    assert (raw['id'], raw['oracle_id']) == (record['id'], record['oracle_id'])
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(raw, DISPLAY_ONLY)
    faces = json.loads(normalized.pop('card_faces_json'))
    for face in faces:
        face['image_uri'] = None
    return {**raw, **normalized, 'image_uri': None, 'card_faces': faces,
            'colors': raw.get('colors'), 'card_name': raw['name'], 'quantity': quantity}


def materialize(id, name, owner, controller, zone, *, counters=None,
                summoning_sick=True, selected_face_index=None):
    entry = deck_entry(name, 8)
    if selected_face_index is not None:
        entry['selected_face_index'] = selected_face_index
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=controller, zone=zone,
                   instance_order=0, counters={} if counters is None else counters,
                   summoning_sick=summoning_sick)


def _assert_printed(card, name):
    raw = raw_card(name)
    expected = ScryfallSyncService._normalize_payload(raw, DISPLAY_ONLY)
    front = raw['card_faces'][0] if raw['layout'] == 'transform' else raw
    assert card.name == front['name']
    assert card.oracle_text == front.get('oracle_text', '')
    assert card.mana_cost == front.get('mana_cost', '')
    assert card.type_line == front['type_line']
    assert card.printed_power == front.get('power')
    assert card.printed_toughness == front.get('toughness')
    assert card.layout == raw['layout']
    faces = json.loads(expected['card_faces_json'])
    for face in faces:
        face['image_uri'] = None
    assert card.card_faces == faces
    assert card.image_uri is None
    if front.get('power') is not None:
        assert card.power == int(front['power'])
        assert card.toughness == int(front['toughness'])


BOUNDARIES = [
  [
    "test_expanded_keyword_mechanics",
    "test_infect_combat_gives_poison_and_ten_counters_lose",
    "infect",
    "Blighted Agent",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_noncombat_infect_uses_post_prevention_damage",
    "infect",
    "Blighted Agent",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_counter_damage_can_kill_indestructible_with_zero_toughness",
    "source",
    "Blighted Agent",
    "infect"
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_counter_damage_can_kill_indestructible_with_zero_toughness",
    "source",
    "Blighted Agent",
    "wither"
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_counter_damage_can_kill_indestructible_with_zero_toughness",
    "target",
    "Darksteel Myr",
    "infect"
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_counter_damage_can_kill_indestructible_with_zero_toughness",
    "target",
    "Darksteel Myr",
    "wither"
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_mixed_infect_and_normal_blockers_keep_damage_sources",
    "attacker",
    "Wall of Frost",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_mixed_infect_and_normal_blockers_keep_damage_sources",
    "infect",
    "Blighted Agent",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_mixed_infect_and_normal_blockers_keep_damage_sources",
    "normal",
    "Grizzly Bears",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ninjutsu_is_ability_and_enters_tapped_attacking_same_defender",
    "attacker",
    "Grizzly Bears",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ninjutsu_is_ability_and_enters_tapped_attacking_same_defender",
    "ninja",
    "Ninja of the Deep Hours",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ninjutsu_is_ability_and_enters_tapped_attacking_same_defender",
    "prowess",
    "Monastery Swiftspear",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ninjutsu_rejects_blocked_attacker_before_paying",
    "attacker",
    "Grizzly Bears",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ninjutsu_rejects_blocked_attacker_before_paying",
    "ninja",
    "Ninja of the Deep Hours",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_annihilator_uses_stack_and_defender_choice_survives_snapshot",
    "crusher",
    "Ulamog's Crusher",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_annihilator_uses_stack_and_defender_choice_survives_snapshot",
    "land-a",
    "Island",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_annihilator_uses_stack_and_defender_choice_survives_snapshot",
    "land-b",
    "Forest",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ai_annihilator_keeps_lands_over_expendable_permanents",
    "land-a",
    "Island",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ai_annihilator_keeps_lands_over_expendable_permanents",
    "land-b",
    "Forest",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ai_annihilator_keeps_lands_over_expendable_permanents",
    "small",
    "Elvish Mystic",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ai_annihilator_keeps_lands_over_expendable_permanents",
    "large",
    "Craw Wurm",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_escape_requires_and_exiles_other_graveyard_cards",
    "ox",
    "Ox of Agonas",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_escape_requires_and_exiles_other_graveyard_cards",
    "fuel-0",
    "Mountain",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_invalid_escape_exile_selection_is_rejected_without_payment",
    "ox",
    "Ox of Agonas",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_invalid_escape_exile_selection_is_rejected_without_payment",
    "fuel-0",
    "Mountain",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_prototype_changes_spell_and_permanent_then_restores_on_leaving",
    "prototype",
    "Phyrexian Fleshgorger",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_dredge_is_optional_and_requires_enough_library_cards",
    "imp",
    "Stinkweed Imp",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_dredge_cannot_replace_draw_with_insufficient_library",
    "imp",
    "Stinkweed Imp",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_dredge_spell_continuation_survives_snapshot_and_finishes_once",
    "imp",
    "Stinkweed Imp",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_dredge_spell_continuation_survives_snapshot_and_finishes_once",
    "spell",
    "Revitalize",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_toxic_adds_poison_without_replacing_life_loss",
    "toxic",
    "Skrelv, Defector Mite",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ninjutsu_remains_available_after_damage_without_second_damage",
    "attacker",
    "Ornithopter",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_ninjutsu_remains_available_after_damage_without_second_damage",
    "ninja",
    "Ninja of the Deep Hours",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_nested_draw_sequences_preserve_all_remaining_effects",
    "imp",
    "Stinkweed Imp",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_blocked_attacker_without_trample_does_not_hit_player_when_blocker_leaves",
    "attacker",
    "Grizzly Bears",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_blocked_attacker_without_trample_does_not_hit_player_when_blocker_leaves",
    "blocker",
    "Ornithopter",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_escape_is_available_with_empty_hand",
    "ox",
    "Ox of Agonas",
    None
  ],
  [
    "test_expanded_keyword_mechanics",
    "test_escape_is_available_with_empty_hand",
    "fuel-0",
    "Mountain",
    None
  ],
  [
    "test_zone_object_reset",
    "test_bounced_creature_loses_old_counters_and_damage_on_reentry",
    "bear",
    "Grizzly Bears",
    None
  ],
  [
    "test_zone_object_reset",
    "test_escape_enters_with_only_its_new_counter",
    "ox",
    "Ox of Agonas",
    None
  ],
  [
    "test_zone_object_reset",
    "test_escape_enters_with_only_its_new_counter",
    "fuel-0",
    "Mountain",
    None
  ],
  [
    "test_zone_object_reset",
    "test_oracle_counter_persistence_except_hand_or_library",
    "skullbriar",
    "Skullbriar, the Walking Grave",
    None
  ],
  [
    "test_zone_object_reset",
    "test_transformed_card_returns_to_printed_front_face_after_bounce",
    "delver",
    "Delver of Secrets",
    None
  ],
  [
    "test_zone_object_reset",
    "test_equipment_and_target_leave_break_old_attachment",
    "bear",
    "Grizzly Bears",
    None
  ],
  [
    "test_zone_object_reset",
    "test_equipment_and_target_leave_break_old_attachment",
    "sword",
    "Short Sword",
    None
  ],
  [
    "test_zone_object_reset",
    "test_single_exile_clears_old_counters_and_combat_state",
    "spider",
    "Giant Spider",
    None
  ],
  [
    "test_zone_object_reset",
    "test_batch_exile_collects_old_state_then_resets_new_zone",
    "skullbriar",
    "Skullbriar, the Walking Grave",
    None
  ],
  [
    "test_zone_object_reset",
    "test_batch_exile_collects_old_state_then_resets_new_zone",
    "spider",
    "Giant Spider",
    None
  ],
  [
    "test_zone_object_reset",
    "test_death_triggers_see_old_counters_before_graveyard_reset",
    "spider",
    "Giant Spider",
    None
  ],
  [
    "test_zone_object_reset",
    "test_death_triggers_see_old_counters_before_graveyard_reset",
    "skullbriar",
    "Skullbriar, the Walking Grave",
    None
  ],
  [
    "test_zone_object_reset",
    "test_death_triggers_see_old_counters_before_graveyard_reset",
    "chalice",
    "Everflowing Chalice",
    None
  ],
  [
    "test_zone_object_reset",
    "test_countered_spell_loses_stack_counters_in_graveyard",
    "bolt",
    "Lightning Bolt",
    None
  ],
  [
    "test_zone_object_reset",
    "test_sacrificed_artifact_loses_old_charge_counters",
    "chalice",
    "Everflowing Chalice",
    None
  ],
  [
    "test_zone_object_reset",
    "test_batch_deaths_collect_all_old_counters_before_reset",
    "bear",
    "Grizzly Bears",
    None
  ],
  [
    "test_zone_object_reset",
    "test_batch_deaths_collect_all_old_counters_before_reset",
    "spider",
    "Giant Spider",
    None
  ]
]


class CapturedBirth(BaseException):
    pass


@pytest.mark.parametrize('module_name,function_name,card_id,name,keyword', BOUNDARIES)
def test_actual_original_birth_has_complete_printed_facts(
        module_name, function_name, card_id, name, keyword, monkeypatch):
    module = importlib.import_module('tests.' + module_name)
    state = (module.state.__wrapped__() if module_name == 'test_expanded_keyword_mechanics'
             else module._state())
    captured = []

    class Cards(dict):
        def __setitem__(self, key, value):
            if key == card_id:
                captured.append(value)
                _assert_printed(value, name)
                if keyword == 'wither' and card_id == 'source':
                    assert value.keywords == ['wither']
                raise CapturedBirth
            return super().__setitem__(key, value)

        def update(self, values):
            for key, value in values.items():
                self[key] = value

    state.cards = Cards(state.cards)
    if module_name == 'test_zone_object_reset':
        monkeypatch.setattr(module, '_state', lambda: state)
    function = getattr(module, function_name)
    kwargs = {}
    for arg in inspect.signature(function).parameters:
        kwargs[arg] = {'state': state, 'keyword': keyword, 'monkeypatch': monkeypatch}[arg]
    with pytest.raises(CapturedBirth):
        function(**kwargs)
    assert len(captured) == 1
    assert captured[0].id == card_id


@pytest.mark.parametrize('module_name,name', [
    ('test_expanded_keyword_mechanics', 'Island'), ('test_zone_object_reset', 'Forest')])
def test_actual_deck_factory_receives_complete_card(module_name, name, monkeypatch):
    module = importlib.import_module('tests.' + module_name)
    raw = raw_card(name)
    seen = []

    def capture(deck_a, deck_b, *, seed):
        seen.append(seed)
        for deck in (deck_a, deck_b):
            assert len(deck) == 1 and deck[0]['quantity'] == 60
            for key in ('oracle_text', 'type_line', 'mana_cost', 'colors', 'layout'):
                assert deck[0].get(key) == raw.get(key)
        raise CapturedBirth

    monkeypatch.setattr(module.MatchFactory, 'from_decks', capture)
    with pytest.raises(CapturedBirth):
        (module.state.__wrapped__() if module_name == 'test_expanded_keyword_mechanics'
         else module._state())
    assert seen == ([3] if name == 'Island' else [418])


def test_every_pinned_full_raw_is_independently_fresh():
    sources = json.loads((FIXTURES / 'keyword_zone4f86/SOURCES.json').read_bytes())['sources']
    assert len(sources) == 24
    for name in sources:
        first, second = raw_card(name), raw_card(name)
        assert first == second and first is not second
        assert first['legalities'] == second['legalities']
        first['legalities'].clear()
        assert second['legalities']
        assert raw_card(name) == second
