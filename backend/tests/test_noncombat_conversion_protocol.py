"""Pure query/application controls supplement, not replace, real paid goldens."""
import pytest

from effects.handlers import deal_damage
from rules_engine.action_validation import ActionRejected
from rules_engine.replacement import replacement_options, apply_permanent_damage_replacements
from game_state.serializers import serialize_match_snapshot as snap
from tests.test_soulscar_preflight_rules_audit import position, add


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', ['protection', 'conversion'])
def test_actual_paid_nontargeted_black_damage_offers_matching_protection_order(
        seat, selected, monkeypatch):
    from game_state.state import Zone
    from tests import test_soulscar_affected_order_goldens as ordered
    from tests.test_generic_protection_damage import position as protected_position, CANONICAL
    from tests.test_linked_damage_targets import raw_card
    from tests.test_batch_graveyard_publication_audit import assert_private
    from effects import handlers
    state, target = protected_position(seat, 'White Knight')
    mage = add(state, 'Soul-Scar Mage', seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    spell = raw_card(state, CANONICAL['Sickening Dreams'], seat, Zone.HAND).id
    discarded = next(cid for cid in state.players[seat].hand if cid != spell)
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    events = []
    emit = handlers.emit_event

    def observe(current, event, payload):
        if event == 'damage_dealt':
            events.append(dict(payload))
        return emit(current, event, payload)

    monkeypatch.setattr(handlers, 'emit_event', observe)
    state = ordered.act(state, seat, {'type': 'cast_spell', 'card_id': spell,
        'targets': {'x_value': 1},
        'cost_choice': {'id': 'base', 'discard_card_ids': [discarded]}})
    frame_id = next(item.id for item in state.stack if item.source_card_id == spell)
    assert not sum(state.players[seat].mana_pool.values())
    assert state.cards[discarded].zone == Zone.GRAVEYARD
    state = ordered.base.finish(ordered.reload_exact(state))
    pending = state.pending_replacement_choice
    assert pending['resume_kind'] == 'damage_batch'
    assert pending['player_id'] == 3-seat and pending['target_card_id'] == target
    assert pending['resolving_item']['id'] == frame_id
    assert pending['resolving_item']['source_card_id'] == spell
    assert {mage, 'protection:' + target} <= {option['source_id'] for option in pending['options']}
    assert_private(state)
    state = ordered.choose(state, 3-seat, 'protection:' + target if selected == 'protection' else mage)
    assert not state.pending_replacement_choice and not state.pending_mechanic_choice
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].counters.get('-1/-1', 0) == (selected == 'conversion')
    assert state.cards[target].counters.get('__damage_marked', 0) == 0
    assert not any(event.get('target_card_id') == target for event in events)
    assert state.players[1].life == state.players[2].life == 19
    assert_private(ordered.reload_exact(state))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first, expected', [('Doubling Season', 7), ('Winding Constrictor', 8)])
def test_actual_paid_conversion_retains_nested_counter_choice_and_real_frame(seat, first, expected):
    from game_state.state import Zone
    from tests import test_soulscar_preflight_rules_audit as base
    from tests import test_soulscar_affected_order_goldens as ordered
    from tests.test_counter_replacements import source as counter_source
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    sources = {name: counter_source(state, name, 3-seat).id
               for name in ('Doubling Season', 'Winding Constrictor')}
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    state, spell = base.cast(state, 'Lightning Bolt', seat, target)
    item_id = next(item.id for item in state.stack if item.source_card_id == spell)
    state = base.finish(ordered.reload_exact(state))
    pending = state.pending_replacement_choice
    assert pending['resume_kind'] == 'counter_event'
    assert pending['resolving_item']['id'] == item_id
    assert pending['resolving_item']['source_card_id'] == spell
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert {option['source_card_id'] for option in pending['options']} == set(sources.values())
    choice = next(option['source_id'] for option in pending['options']
                  if option['source_card_id'] == sources[first])
    state = ordered.choose(state, 3-seat, choice)
    # The counter replacement protocol automatically applies its sole remaining effect.
    assert not state.pending_replacement_choice
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert state.cards[target].last_known_battlefield['counters']['-1/-1'] == expected
    assert state.players[1].life == state.players[2].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', ['protection', 'conversion'])
def test_virtual_protection_component_choice_is_not_a_fabricated_paid_episode(seat, selected):
    from tests.test_soulscar_protection_boundaries import setup
    state, mage, target = setup(seat)
    source = add(state, 'Prodigal Pyromancer', seat)
    before = snap(state)
    options = replacement_options(state, 'damage_to_permanent', source_card_id=source,
                                  target_card_id=target, amount=1)
    assert {mage, 'protection:' + target} <= {entry['source_id'] for entry in options}
    assert snap(state) == before
    # Core replacement calculation only. A red targeted activation against this
    # creature would be illegal; no such action or synthetic StackItem is executed.
    choice = 'protection:' + target if selected == 'protection' else mage
    assert apply_permanent_damage_replacements(
        state, target, 1, replacement_source_id=choice, source_card_id=source,
        combat=False) == 0
    assert state.cards[target].counters.get('-1/-1', 0) == (selected == 'conversion')
    assert state.cards[target].counters.get('__damage_marked', 0) == 0
    assert state.players[1].life == state.players[2].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('amount', [None, 0, -1, 3])
def test_readonly_known_zero_and_legacy_unknown_amounts(seat, amount):
    state = position(seat)
    mage = add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    source = add(state, 'Prodigal Pyromancer', seat)
    before = snap(state)
    ids = {entry['source_id'] for entry in replacement_options(
        state, 'damage_to_permanent', source_card_id=source,
        target_card_id=target, amount=amount)}
    assert (mage in ids) == (amount is None or amount > 0)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_combat_never_acquires_conversion_and_missing_context_does_not_guess_active(seat):
    state = position(seat)
    mage = add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    source = add(state, 'Prodigal Pyromancer', seat)
    before = snap(state)
    combat = replacement_options(state, 'damage_to_permanent', source_card_id=source,
                                 target_card_id=target, amount=2, combat=True)
    absent = replacement_options(state, 'damage_to_permanent', source_card_id='absent',
                                 source_lki={'colors': ['R']}, target_card_id=target, amount=2)
    assert mage not in {entry['source_id'] for entry in combat + absent}
    assert snap(state) == before
    assert apply_permanent_damage_replacements(state, target, 2) == 2
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_unoffered_source_rejects_before_log_counters_or_zones(seat):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    source = add(state, 'Prodigal Pyromancer', seat)
    before = snap(state)
    with pytest.raises(ActionRejected, match='no longer applicable'):
        apply_permanent_damage_replacements(state, target, 2, replacement_source_id='unoffered',
                                            source_card_id=source, combat=False)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_core_damage_uses_real_source_controller_not_unrelated_handler_actor(seat):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    source = add(state, 'Prodigal Pyromancer', seat)
    # Explicit existing core operation, not an invented Pyromancer activation.
    assert deal_damage(state, 3-seat, {'__source_card_id': source,
                                      'target_card_id': target, 'amount': 2}) == 0
    assert state.cards[target].counters.get('-1/-1') == 2
    assert state.players[seat].life == state.players[3-seat].life == 20
