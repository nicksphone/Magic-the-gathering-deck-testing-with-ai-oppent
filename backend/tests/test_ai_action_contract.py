from copy import deepcopy

import pytest

from ai.action_contract import complete_action
from rules_engine.action_validation import ActionRejected


def test_ai_display_hints_are_not_action_parameters_and_intent_is_unchanged():
    intent = {"type": "cast_spell", "card_id": "bolt", "card_name": "Lightning Bolt",
              "mana_cost": "{R}", "cost_options": [{"id": "base"}],
              "target_hints": {"player_targets": [{"id": 2}]},
              "targets": {"target_player": 2}, "cost_choice": {"id": "base"}}
    before = deepcopy(intent)
    action = complete_action(intent)
    assert intent == before
    assert action["targets"] == {"target_player": 2}
    assert action["cost_choice"] == {"id": "base"}
    assert not {"card_name", "mana_cost", "cost_options", "target_hints"} & action.keys()


@pytest.mark.parametrize("intent", [None, {}, {"type": "unknown"},
    {"type": "cast_spell"}, {"type": "cast_spell", "card_id": "bolt", "targets": []},
    {"type": "cast_spell", "card_id": "bolt", "targets": {"x_value": -1}},
    {"type": "pass_priority", "_invalid_ai_choice": True}])
def test_incomplete_or_malformed_intent_is_not_replaced_with_a_pass(intent):
    with pytest.raises(ActionRejected):
        complete_action(intent)


def test_presentation_options_do_not_infer_a_target_or_x_value():
    action = complete_action({"type": "cast_spell", "card_id": "source",
        "target_hints": {"requires_x_value": True, "player_targets": [{"id": 2}]}})
    assert action["targets"] == {}


@pytest.mark.parametrize("kind, fields", [
    ("attack", {"attackers": ["one", "two"], "bands": [["one", "two"]],
                "attack_targets": {"one": "player:2", "two": "player:2"}}),
    ("block", {"blocks": {"one": ["three", "four"]}}),
    ("choose_mechanic", {"card_ids": ["four", "three"]}),
    ("activate_ability", {"card_id": "one", "ability_index": 1,
                          "targets": {"x_value": 4}}),
])
def test_ordered_complete_choices_survive_metadata_separation(kind, fields):
    action = complete_action({"type": kind, **fields, "label": "display only"})
    for key, value in fields.items():
        assert action[key] == value
