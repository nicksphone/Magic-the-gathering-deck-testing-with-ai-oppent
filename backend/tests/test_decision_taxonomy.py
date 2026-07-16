from analytics.decision_taxonomy import has_actionable_move, has_meaningful_move


def test_restricted_placeholders_are_not_actionable() -> None:
    moves = [
        {"type": "declare_attackers_restricted"},
        {"type": "declare_blockers_restricted"},
        {"type": "pass_priority"},
    ]

    assert has_actionable_move(moves) is False
    assert has_meaningful_move(moves) is False


def test_activated_and_cycling_actions_are_meaningful() -> None:
    assert has_actionable_move([{"type": "cycle_card"}]) is True
    assert has_meaningful_move([{"type": "activate_ability"}]) is True
    assert has_meaningful_move([{"type": "equip"}]) is True


def test_unknown_real_action_is_actionable_but_not_meaningful() -> None:
    move = {"type": "choose_mode"}

    assert has_actionable_move([move]) is True
    assert has_meaningful_move([move]) is False
