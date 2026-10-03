"""Canonical conditions/scaling share characteristics, views and AI evaluation."""
import pytest

from ai.heuristics import _creature_value
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.continuous import effective_power, effective_toughness, effective_keywords, attachment_effect_warnings
from tests.test_attached_scaling import add, fixture


def attached(state, name, target, player=1):
    source = add(state, name, player)
    source.attached_to = target.id
    return source


@pytest.mark.parametrize('player', [1, 2])
def test_domain_uses_distinct_basic_types_of_current_source_controller(player):
    state = fixture()
    target = add(state, 'Llanowar Elves', 3 - player)
    source = attached(state, 'Strength of Unity', target, player)
    for name in ['Hallowed Fountain', 'Watery Grave', 'Savai Triome', 'Mountain']:
        add(state, name, player)
    add(state, 'Forest', 3 - player)
    assert effective_power(state, target.id) == 5
    add(state, 'Forest', player)
    assert effective_power(state, target.id) == 6
    assert not attachment_effect_warnings(state, source.id)
    before = serialize_match_snapshot(state)
    assert effective_power(deserialize_match_snapshot(before), target.id) == 6
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('name,stats', [
    ('Llanowar Elves', (2, 2)), ('Ornithopter', (0, 2)),
    ("Tajic, Legion's Edge", (5, 4)),
])
def test_target_colors_not_source_colors_set_scaling(name, stats):
    state = fixture()
    target = add(state, name, 2)
    source = attached(state, 'Blessing of the Nephilim', target)
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == stats
    assert not attachment_effect_warnings(state, source.id)


@pytest.mark.parametrize('player', [1, 2])
def test_attachment_count_includes_both_controllers_and_updates_on_detach(player):
    state = fixture()
    target = add(state, 'Llanowar Elves', player)
    source = attached(state, 'Strong Back', target, player)
    equipment = attached(state, 'Bonesplitter', target, 3 - player)
    attached(state, 'Rancor', target, 3 - player)
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == (11, 7)
    warnings = attachment_effect_warnings(state, source.id)
    assert warnings == []
    equipment.attached_to = None
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == (7, 5)


@pytest.mark.parametrize('name,stats', [('Colossal Dreadmaw', (4, 5)), ("Tajic, Legion's Edge", (4, 4))])
def test_suffix_condition_and_otherwise_choose_one_bonus_without_inventing_color(name, stats):
    state = fixture()
    target = add(state, name)
    source = attached(state, "Serra's Boon", target)
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == stats
    assert not attachment_effect_warnings(state, source.id)


@pytest.mark.parametrize('player', [1, 2])
def test_color_permanent_condition_uses_source_controller_not_target_controller(player):
    state = fixture()
    target = add(state, 'Llanowar Elves', 3 - player)
    source = attached(state, 'Abzan Runemark', target, player)
    assert 'vigilance' not in effective_keywords(state, target.id)
    add(state, 'Whip of Erebos', 3 - player)
    assert 'vigilance' not in effective_keywords(state, target.id)
    add(state, 'Whip of Erebos', player)
    assert 'vigilance' in effective_keywords(state, target.id)
    assert not attachment_effect_warnings(state, source.id)


@pytest.mark.parametrize('name,power', [('Llanowar Elves', 3), ("Tajic, Legion's Edge", 6)])
def test_prefix_subtype_condition_and_additional_bonus(name, power):
    state = fixture()
    target = add(state, name)
    source = attached(state, 'Silver-Inlaid Dagger', target)
    assert effective_power(state, target.id) == power
    assert not attachment_effect_warnings(state, source.id)


@pytest.mark.parametrize('count,expected,keywords', [(3, 4, set()), (4, 5, {'double strike'}), (5, 6, {'double strike'})])
def test_source_counter_condition_ignores_private_counters_and_updates(count, expected, keywords):
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = attached(state, 'Gavel of the Righteous', target)
    source.counters = {'charge': count, '__engine_marker': 99}
    assert effective_power(state, target.id) == expected
    assert ('double strike' in effective_keywords(state, target.id)) == bool(keywords)
    assert not attachment_effect_warnings(state, source.id)


@pytest.mark.parametrize('count,stats', [(6, (8, 4)), (7, (10, 2)), (8, (10, 2))])
def test_threshold_graveyard_counts_and_snapshots_match_views(count, stats):
    state = fixture()
    target = add(state, 'Colossal Dreadmaw')
    source = attached(state, "Patriarch's Desire", target)
    for _ in range(count):
        cid = state.players[1].library.pop()
        state.cards[cid].move_to_zone(Zone.GRAVEYARD)
        state.players[1].graveyard.append(cid)
    before = serialize_match_snapshot(state)
    for candidate in (state, deserialize_match_snapshot(before)):
        assert (effective_power(candidate, target.id), effective_toughness(candidate, target.id)) == stats
        view = next(card for card in serialize_match(candidate)['players'][1]['battlefield'] if card['id'] == target.id)
        assert (view['power'], view['toughness']) == stats
        assert not attachment_effect_warnings(candidate, source.id)
    assert serialize_match_snapshot(state) == before


def test_opponent_color_condition_changes_shared_ai_value_without_mutating_state():
    state = fixture()
    target = add(state, 'Colossal Dreadmaw')
    attached(state, 'Black Scarab', target)
    low = _creature_value(state, target.id)
    add(state, 'Whip of Erebos')
    assert effective_power(state, target.id) == 6
    add(state, 'Whip of Erebos', 2)
    before = serialize_match_snapshot(state)
    assert effective_power(state, target.id) == 8
    assert _creature_value(state, target.id) > low
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('condition', ["it's phased out", "it is goaded", "it's a commander", "it's a madeuptype", "you have more life than an opponent", "this equipment has many counters on it"])
def test_unknown_predicates_are_not_false_and_do_not_select_otherwise(condition):
    from rules_engine.continuous import _attached_condition
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = attached(state, 'Bonesplitter', target)
    assert _attached_condition(state, source, target, condition) is None


@pytest.mark.parametrize('status', ['tapped', 'attacking'])
def test_recipient_status_condition_tracks_live_target(status):
    from rules_engine.continuous import _attached_condition
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = attached(state, 'Bonesplitter', target)
    assert _attached_condition(state, source, target, "it's " + status) is False
    if status == 'tapped':
        target.tapped = True
    else:
        state.attackers = [target.id]
    assert _attached_condition(state, source, target, "it's " + status) is True


def test_unknown_condition_cannot_apply_the_otherwise_branch(monkeypatch):
    state = fixture()
    target = add(state, 'Colossal Dreadmaw')
    source = attached(state, "Serra's Boon", target)
    monkeypatch.setattr('rules_engine.continuous._attached_condition', lambda *_: None)
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == (6, 6)
    assert len(attachment_effect_warnings(state, source.id)) == 2
