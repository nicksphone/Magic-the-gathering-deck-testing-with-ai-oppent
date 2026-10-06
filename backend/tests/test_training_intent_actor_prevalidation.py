"""Strict actor boundary precedes every dispatch; real choices stay authoritative."""
from copy import deepcopy

import pytest
from pydantic import TypeAdapter, ValidationError

from api_contracts import PlayerID
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from tests.land_consumer_variant_support import setup
from tests.test_private_choice_intent_boundary import environment, position, selected, owned_disposable_source_only
from tests.test_training_mana_intent_allowlist import simple_intent
from tests.test_training_land_priority_intent_audit import scenario as priority_position
from tests.test_training_foretell_intent_audit import scenario as foretell_position
from tests.test_training_ninjutsu_intent_audit import scenario as ninja_position
from tests.test_nonmana_intent_audit import scenario as nonmana_position
from tests.test_training_combat_intent_audit import scenario as combat_position


KINDS = (
    'activate_mana_ability', 'tap_land_for_mana', 'tap_nonland_for_mana', 'tap_lands_bulk',
    'cast_spell', 'activate_ability', 'activate_loyalty', 'equip', 'crew', 'cycle_card',
    'choose_mechanic', 'choose_optional_effect', 'choose_trigger_order', 'choose_replacement',
    'choose_trigger_target', 'attack', 'block', 'foretell', 'ninjutsu', 'play_land', 'pass_priority',
)
BAD = (True, False, '1', '2', 1.0, 2.0, 0, 3, [], {})
IDS = ('true', 'false', 'str1', 'str2', 'float1', 'float2', 'zero', 'three', 'list', 'dict')


def watch_helpers(monkeypatch, env):
    calls = []
    import ai.action_contract
    import training.environment
    for owner, name in ((ai.action_contract, 'complete_action'),
                        (env._rules, 'legal_moves'),
                        (training.environment, 'serialize_card_view')):
        original = getattr(owner, name)
        def observed(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(owner, name, observed)
    return calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', KINDS + ('unrecognized',))
@pytest.mark.parametrize('actor', BAD, ids=IDS)
def test_every_dispatch_envelope_rejects_invalid_explicit_actor_before_helpers(seat, kind, actor, monkeypatch):
    env, _, _, _ = setup('shock_tapped', seat)
    # Deliberately partial dispatch envelopes: no invented card/target choices.
    packet = {'type': kind}
    before, original = env.snapshot(), deepcopy(packet)
    calls = watch_helpers(monkeypatch, env)
    with pytest.raises(ValidationError):
        TypeAdapter(PlayerID).validate_python(actor)
    with pytest.raises(ActionRejected, match='Seat must be integer 1 or 2'):
        env.lookup_intent(packet, actor)
    assert not calls and env.snapshot() == before and packet == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('actor', BAD + (None,), ids=IDS + ('terminal-none',))
@pytest.mark.parametrize('omitted', [False, True])
def test_null_or_omitted_actor_validates_authoritative_current_actor(seat, actor, omitted, monkeypatch):
    env, action, hint, _ = setup('shock_tapped', seat)
    if actor is None:
        env._state.winner = seat
    else:
        env._state.priority_player = deepcopy(actor)
    before = env.snapshot()
    calls = watch_helpers(monkeypatch, env)
    with pytest.raises(ActionRejected, match='Seat must be integer 1 or 2'):
        if omitted:
            env.lookup_intent({**hint, **action})
        else:
            env.lookup_intent({**hint, **action}, None)
    assert not calls and env.snapshot() == before


FAMILIES = ('shock_tapped', 'shock_pay', 'crucible', 'ramunap', 'mana',
            'pass', 'delver', 'officer', 'foretell', 'ninjutsu', 'spell', 'ability', 'attack', 'block')


def real_position(family, seat):
    if family in ('shock_tapped', 'shock_pay', 'crucible', 'ramunap'):
        env, action, hint, _ = setup(family, seat)
    elif family == 'mana':
        env, action = simple_intent(seat, 'activate_mana_ability')
        hint = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat)
                    if m['type'] == action['type'] and m['card_id'] == action['card_id'])
    elif family == 'pass':
        env, action, hint, _ = priority_position('pass_priority', seat)
    elif family in ('delver', 'officer'):
        state, _, _ = position(family, seat)
        env = environment(state)
        action = selected(state, family, False)
        hint = next(m for m in env._rules.legal_moves(deepcopy(state), seat) if m['type'] == 'choose_mechanic')
    elif family == 'foretell':
        env, _, action, hint = foretell_position(seat)
    elif family == 'ninjutsu':
        env, action, hint, _ = ninja_position(seat)
    elif family in ('spell', 'ability'):
        env, action, hint, _, _ = nonmana_position(seat, family)
    else:
        env, action, hint, _ = combat_position(seat, family, 'ordinary')
    return env, action, {**hint, **action}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_real_whole_views_null_default_explicit_actor_equivalence_and_wrong_seat(seat, family):
    env, action, packet = real_position(family, seat)
    before, original = env.snapshot(), deepcopy(packet)
    expected = env.lookup(action, seat)
    assert env.lookup_intent(packet) == env.lookup_intent(packet, None) == env.lookup_intent(packet, seat) == expected
    with pytest.raises(ActionRejected):
        env.lookup_intent(packet, 3-seat)
    assert env.snapshot() == before and packet == original
    replay = deepcopy(env)
    replay._state = deserialize_match_snapshot(serialize_match_snapshot(env._state))
    assert env.step(expected['action'], seat) == replay.step(action, seat)
    assert env.snapshot() == replay.snapshot()
