"""Order-aware v3 boundary checks layered over unchanged v2 handler checks."""
import json

from scripts.archetype_matrix_api_check import HandlerChecks as PreviousHandlerChecks
from scripts.archetype_matrix_game import TraceDivergence
from scripts.archetype_trace_v3 import digest


class HandlerChecks(PreviousHandlerChecks):
    def __call__(self, initial, row):
        from persistence.repository import Repository
        from sqlmodel import Session
        step = row['step']
        expected_before = row['before_cards_order_sha256']
        expected_after = row['after_cards_order_sha256']
        original = self.main.checked_action

        def checked(state, *args, **kwargs):
            if digest(list(state.cards)) != expected_before:
                raise TraceDivergence(step, ['handler_initial_cards_order'])
            result = original(state, *args, **kwargs)
            if digest(list(result.cards)) != expected_after:
                raise TraceDivergence(step, ['handler_transition_cards_order'])
            return result

        self.main.checked_action = checked
        try:
            result = super().__call__(initial, row)
        finally:
            self.main.checked_action = original
        match_id = row['before']['id']
        with Session(self.engine) as session:
            stored = Repository(session).get_active_match(match_id)
            if digest(list(json.loads(stored.state_json)['cards'])) != expected_after:
                raise TraceDivergence(step, ['handler_sqlite_cards_order'])
        if digest(list(self.main.ACTIVE_MATCHES[match_id].state.cards)) != expected_after:
            raise TraceDivergence(step, ['handler_restored_cards_order'])
        return {**result, 'cards_order_transition_equal':True,
                'cards_order_sqlite_roundtrip':True, 'cards_order_restored':True}
