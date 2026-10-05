"""Separate AI move-display metadata from complete engine action parameters."""
from typing import get_args

from pydantic import ValidationError

from api_contracts import Action
from rules_engine.action_validation import ActionRejected


_MODELS = {
    kind: model for model in get_args(get_args(Action)[0])
    for kind in get_args(model.model_fields["type"].annotation)
}


def complete_action(intent):
    """Validate chosen parameters; never select targets, costs or cards here."""
    if not isinstance(intent, dict) or not isinstance(intent.get("type"), str):
        raise ActionRejected("AI did not return an action object with a type")
    if intent.get("_invalid_ai_choice"):
        raise ActionRejected("AI could not complete the required choices")
    model = _MODELS.get(intent["type"])
    if model is None:
        raise ActionRejected("AI returned an unknown action type")
    try:
        return model.model_validate({key: value for key, value in intent.items()
                                     if key in model.model_fields}).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise ActionRejected("AI returned malformed action parameters") from exc
