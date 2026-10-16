"""Authentic counter preparation restores the original effective target pose."""
from copy import deepcopy

from rules_engine import entry_counters, graveyard_batch_entry
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from tests import test_ai_allocation_contracts as original
from tests.test_allocation_fixture_fidelity7f import raw_card, expected_card


def test_original_ready_target_has_printed_zero_seven_counters_and_effective_seven():
    state = original.state_with_targets()
    card = state.cards['friendly']
    raw = raw_card('Phantom Nishoba')
    assert raw['power'] == raw['toughness'] == '0'
    assert (card.power, card.toughness, card.printed_power, card.printed_toughness) == (0, 0, '0', '0')
    assert card.counters == {'+1/+1': 7}
    assert (effective_power(state, card.id), effective_toughness(state, card.id)) == (7, 7)
    assert card.counter_timestamps == {'+1/+1': 1}
    assert card.owner == card.controller == 1 and not card.summoning_sick
    assert card.id in state.players[1].battlefield
    bear = state.cards['enemy']
    assert bear.counters == {} and bear.counter_timestamps == {}
    assert (effective_power(state, bear.id), effective_toughness(state, bear.id)) == (2, 2)


def test_actual_existing_seed_prepare_commit_producers_initialize_without_other_mutation(monkeypatch):
    real_seed = graveyard_batch_entry._entry_seeds
    real_prepare = entry_counters.prepare_entry_counters
    real_commit = entry_counters.commit_entry_counters
    calls = []

    def protected(state):
        return deepcopy((state.rng.getstate(), state.starting_decks, state.sideboard_facts,
                         [(pid, player.life, player.mana_pool, player.hand,
                           player.library, player.battlefield, player.graveyard)
                          for pid, player in state.players.items()], state.stack,
                         state.pending_mechanic_choice, state.pending_replacement_choice))

    def seed(state, cards, **kwargs):
        before = protected(state)
        result = real_seed(state, cards, **kwargs)
        assert protected(state) == before
        assert len(cards) == 1 and state.cards[cards[0].id] is cards[0]
        calls.append(('seed', cards[0].id, deepcopy(result[cards[0].id]['counters'])))
        return result

    def prepare(state, controller, data, card, resume_effect):
        before = protected(state)
        result = real_prepare(state, controller, data, card, resume_effect)
        assert protected(state) == before
        assert state.cards[card.id] is card and result is True
        assert card.counters == {}
        calls.append(('prepare', card.id, deepcopy(data['entry_payload']['__entry_counters_ready'])))
        return result

    def commit(state, card, payload, **kwargs):
        before = protected(state)
        assert state.cards[card.id] is card
        result = real_commit(state, card, payload, **kwargs)
        assert protected(state) == before
        calls.append(('commit', card.id, deepcopy(card.counters)))
        return result

    monkeypatch.setattr(graveyard_batch_entry, '_entry_seeds', seed)
    monkeypatch.setattr(entry_counters, 'prepare_entry_counters', prepare)
    monkeypatch.setattr(entry_counters, 'commit_entry_counters', commit)
    original.state_with_targets()
    assert calls == [('seed', 'friendly', {'+1/+1': 7}),
                     ('prepare', 'friendly', {'+1/+1': 7}),
                     ('commit', 'friendly', {'+1/+1': 7}),
                     ('seed', 'enemy', {}), ('prepare', 'enemy', {}), ('commit', 'enemy', {})]


def test_original_allocation_action_observes_ready_seven_power_target(monkeypatch):
    real = RulesEngine.legal_moves
    observed = []

    def observe(self, state, *args, **kwargs):
        if 'friendly' in state.cards and state.cards['friendly'].name == 'Phantom Nishoba':
            card = state.cards['friendly']
            assert card.counters == {'+1/+1': 7}
            assert (effective_power(state, card.id), effective_toughness(state, card.id)) == (7, 7)
            observed.append(card.id)
        return real(self, state, *args, **kwargs)

    monkeypatch.setattr(RulesEngine, 'legal_moves', observe)
    original.test_ai_uses_the_fixed_damage_budget_and_an_enemy_recipient()
    assert observed


def test_full_raw_and_all_replacement_instruction_text_survive_counter_initialization():
    state = original.state_with_targets()
    card = state.cards['friendly']
    raw = raw_card('Phantom Nishoba')
    expected = expected_card('Phantom Nishoba')
    assert len(raw) > 40 and raw['object'] == 'card'
    assert card.oracle_text.splitlines() == raw['oracle_text'].splitlines()
    assert len(card.oracle_text.splitlines()) == 4
    assert card.characteristic_record == expected.characteristic_record
    assert card.keywords == expected.keywords and card.type_line == raw['type_line']
