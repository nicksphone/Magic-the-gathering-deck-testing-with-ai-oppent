from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ai.agent import AIAgent
from analytics.schemas import AIDiagnosticsRequest, BatchSimulationRequest
from main import StartMatchRequest


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
@pytest.mark.parametrize('human_seat', [1, 2])
def test_start_preserves_offered_difficulty_and_human_seat(difficulty, human_seat):
    deck = [{'card_name': 'Island', 'quantity': 60}]
    request = StartMatchRequest.model_validate({
        'deck_a': deck, 'deck_b': deck, 'ai_difficulty': difficulty,
        'controller_a': 'human' if human_seat == 1 else 'ai',
        'controller_b': 'human' if human_seat == 2 else 'ai',
    })
    restored = StartMatchRequest.model_validate_json(request.model_dump_json())
    assert restored == request
    assert restored.ai_difficulty == difficulty
    assert (restored.controller_a, restored.controller_b) == (
        ('human', 'ai') if human_seat == 1 else ('ai', 'human'))


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_diagnostics_and_batch_accept_the_same_offered_difficulties(difficulty):
    deck = [{'card_name': 'Island', 'quantity': 60}]
    diagnostics = AIDiagnosticsRequest(difficulty=difficulty)
    batch = BatchSimulationRequest(deck_a=deck, deck_b=deck, difficulty=difficulty)
    assert diagnostics.difficulty == batch.difficulty == difficulty
    assert AIDiagnosticsRequest.model_validate_json(diagnostics.model_dump_json()) == diagnostics


@pytest.mark.parametrize('difficulty', ['', 'MASTER_PLUS', 'invented', None, True, 4])
def test_unknown_difficulties_are_not_downgraded(difficulty):
    deck = [{'card_name': 'Island', 'quantity': 60}]
    for model, fields in [
        (StartMatchRequest, {'deck_a': deck, 'deck_b': deck, 'ai_difficulty': difficulty}),
        (AIDiagnosticsRequest, {'difficulty': difficulty}),
        (BatchSimulationRequest, {'deck_a': deck, 'deck_b': deck, 'difficulty': difficulty}),
    ]:
        with pytest.raises(ValidationError):
            model.model_validate(fields)


def test_master_plus_retains_its_distinct_existing_policy():
    state = SimpleNamespace(turn=8, players={
        1: SimpleNamespace(battlefield=list(range(5))),
        2: SimpleNamespace(battlefield=list(range(5))),
    })
    assert AIAgent(difficulty='master_plus')._strategic_search_depth(state, 1) == 3
    assert AIAgent(difficulty='strong')._strategic_search_depth(state, 1) == 1
