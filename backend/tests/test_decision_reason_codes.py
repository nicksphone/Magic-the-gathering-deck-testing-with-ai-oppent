from analytics.decision_taxonomy import decision_reason_code


def _reason(action: dict, text: str, *, legal: bool = True, meaningful: bool = True, step: str = "PRECOMBAT_MAIN") -> str:
    return decision_reason_code(
        action,
        text,
        legal_non_pass=legal,
        meaningful_non_pass=meaningful,
        active_player=1,
        player_id=1,
        step=step,
        stack_empty=True,
    )


def test_main_phase_hold_up_is_distinguished_from_unexplained_pass() -> None:
    assert _reason({"type": "pass_priority"}, "Hold up interaction") == "hold_up_interaction"
    assert _reason({"type": "pass_priority"}, "Control plan selected best-scoring move") == "pass_with_meaningful_option"


def test_pass_labels_cover_no_action_and_response_windows() -> None:
    assert _reason({"type": "pass_priority"}, "No legal action", legal=False, meaningful=False) == "pass_no_action"
    assert _reason({"type": "pass_priority"}, "Pass", meaningful=False) == "pass_nonmeaningful_option"
    assert _reason({"type": "pass_priority"}, "Pass", step="DECLARE_BLOCKERS") == "pass_response_window"


def test_common_ai_reasons_are_stable_labels() -> None:
    assert _reason({"type": "play_land"}, "Prioritize reliable land development") == "land_development"
    assert _reason({"type": "cast_spell"}, "Answer threatening stack item with available interaction") == "stack_interaction"
    assert _reason({"type": "attack"}, "Combat plan selected") == "combat_plan"
