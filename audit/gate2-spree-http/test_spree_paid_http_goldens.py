"""NEW whole12: actual paid Spree, private actors, mandatory/optional choices, cold lifespans."""
import pytest
from spree_paid_http_support import SpreeCase
from card_data.fallback_cards import fallback_card_payload
import main
from game_state.state import Zone


@pytest.fixture
def offline_decks(monkeypatch):
    monkeypatch.setattr(main, '_hydrate_deck_cards',
        lambda repo, deck: [{**fallback_card_payload(item['card_name']), **item} for item in deck])


CASES = [(actor, mode, copy) for actor in (1, 2) for mode in (0, 1, 2)
         for copy in (('keep', 'new') if mode in (0, 2) else ('none',))]


@pytest.mark.parametrize('actor,mode,copy', CASES,
    ids=[f'actor{a}-mode{m}-copy-{c}' for a, m, c in CASES])
def test_real_paid_private_actor_choices_and_cold_lifespan(offline_decks, actor, mode, copy):
    with SpreeCase(actor, mode, copy) as case:
        case.cast()
        case.advance(lambda s: s.pending_mechanic_choice is not None)
        assert case.state.pending_mechanic_choice['kind'] == ('copy_target' if mode in (0, 2) else 'spree_target_change')
        case.emit('pending')
        case.cold()
        if mode in (0, 2):
            copies = [i for i in case.state.stack if i.payload.get('__copied_from_stack_id') == case.original]
            assert len(copies) == 1 and copies[0].controller == actor
            old_target = copies[0].payload['target_card_id']
            old_targets = list(copies[0].targets)
            assert old_target == case.old_target
            token = case.choice('copy_target', keep=copy == 'keep')
            retained = next(i for i in case.state.stack if i.id == copies[0].id)
            assert (retained.payload['target_card_id'] == old_target) is (copy == 'keep')
            assert retained.payload['target_card_id'] == (old_target if copy == 'keep' else token.split(':', 1)[1])
            assert retained.controller == actor
            assert retained.targets == (old_targets if copy == 'keep' else [retained.payload['target_card_id']])
            case.emit('copy-choice')
        if mode in (1, 2):
            case.advance(lambda s: s.pending_mechanic_choice is not None)
            old_target = next(i for i in case.state.stack if i.id == case.original).payload['target_card_id']
            assert old_target == case.old_target
            token = case.choice('spree_target_change')
            frame = next(i for i in case.state.stack if i.id == case.original)
            assert frame.controller == 3-actor and frame.payload['target_card_id'] != old_target
            assert frame.payload['target_card_id'] == token.split(':', 1)[1]
            assert frame.targets == [frame.payload['target_card_id']]
            case.emit('change-choice')
        assert case.state.pending_mechanic_choice is None
        case.privacy()
        assert case.state.cards[case.favor].zone == Zone.GRAVEYARD
        case.emit('terminal')


@pytest.mark.parametrize('actor', [1, 2], ids=['actor1-no-alternative', 'actor2-no-alternative'])
def test_real_paid_response_removes_last_alternative_without_pending(offline_decks, actor):
    with SpreeCase(actor, 1, no_alternative=True) as case:
        case.cast()
        initial_targets = list(next(i for i in case.state.stack if i.id == case.original).targets)
        case.advance(lambda s: s.priority_player == actor)
        before = sum(case.state.players[actor].mana_pool.values())
        case.submit({'type': 'cast_spell', 'card_id': case.bolt, 'cost_choice': {'id': 'base'},
                     'targets': {'target_card_id': case.alternate}})
        assert before - sum(case.state.players[actor].mana_pool.values()) == 1
        case.advance(lambda s: s.cards[case.bolt].zone == Zone.GRAVEYARD)
        assert case.state.cards[case.alternate].zone == Zone.GRAVEYARD
        case.emit('removed-alt')
        case.advance(lambda s: s.cards[case.favor].zone == Zone.GRAVEYARD)
        assert case.state.pending_mechanic_choice is None
        original = next(i for i in case.state.stack if i.id == case.original)
        assert original.payload['target_card_id'] == case.old_target and original.controller == 3-actor
        assert original.targets == initial_targets
        case.cold()
        assert case.state.pending_mechanic_choice is None
        case.privacy()
        case.emit('terminal')
