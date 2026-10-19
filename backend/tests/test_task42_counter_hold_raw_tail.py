"""Unknown parenthetical RAW tails must not become reminder-stripped coverage."""
import pytest

from tests import test_task42_counter_hold_body_guard as body


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['pool', 'paid_lands'])
def test_unknown_parenthetical_raw_body_keeps_legacy(seat, context, monkeypatch):
    monkeypatch.setitem(body.BODY_CASES, 'unknown_parenthetical', [
        '{T}: Add {G}. (UNKNOWN)',
        '{T}: Add {G}. (You win the game.)',
    ])
    body.test_full_method_only_vanilla_or_complete_free_fixed_tap_mana_holds(
        seat, context, 'unknown_parenthetical')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['pool', 'paid_lands'])
def test_raw_only_parenthetical_is_not_empty_vanilla(seat, context, monkeypatch):
    monkeypatch.setitem(body.BODY_CASES, 'raw_only_parenthetical', [
        '(UNKNOWN)', '(You win the game.)',
    ])
    body.test_full_method_only_vanilla_or_complete_free_fixed_tap_mana_holds(
        seat, context, 'raw_only_parenthetical')
