"""Whole HTTP views and typed inputs: retained context is public, never actor authority."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from api_contracts import MechanicChoice, ReplacementChoice
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from training.environment import TrainingEnvironment
from tests import test_human_legend_keeper_audit as audit
from tests.test_combat_graveyard_caller_audit import receipts, client, base_client, repo
from tests.test_self_graveyard_replacement_audit import snap
from tests.test_spell_admission_safety_http import sql_facts


@pytest.mark.parametrize('seat', [1, 2])
def test_whole_http_keeper_views_and_typed_action_replay(repo, client, seat, receipts, tmp_path):
    import main
    h = audit.episode(seat, 'Progenitus', receipts, tmp_path, replacement=True,
                      client=client, repo=repo)
    pending = deepcopy(h.state.pending_mechanic_choice)
    before = (snap(h.state), deepcopy(main._controller_snapshot(h.controller)), sql_facts(repo))
    public = client.get('/matches/' + h.state.id)
    assert public.status_code == 200
    assert public.json()['pending_mechanic_choice'] == pending
    legal = client.get('/matches/' + h.state.id + '/legal-moves', params={'player_id': seat})
    assert legal.status_code == 200 and len(legal.json()['moves']) == 1
    offered = legal.json()['moves'][0]
    assert offered['legend_context'] == pending['legend_context']
    assert offered['legend_group_index'] == pending['legend_group_index']
    wrong = client.get('/matches/' + h.state.id + '/legal-moves', params={'player_id': 3-seat})
    assert wrong.status_code == 200 and wrong.json()['moves'] == []
    log = client.get('/matches/' + h.state.id + '/replay')
    assert log.status_code == 200
    assert (snap(h.state), main._controller_snapshot(h.controller), sql_facts(repo)) == before
    context = offered['legend_context']
    assert set(context) == {'groups', 'keepers', 'plans'}
    assert len(context['groups']) == 1
    group = context['groups'][0]
    assert set(group) == {'player_id', 'name', 'card_ids', 'references'}
    assert group['player_id'] == seat and group['card_ids'] == [h.old, h.new]
    assert all(len(reference) == 3 and all(type(value) is int for value in reference)
               for reference in group['references'].values())
    context_strings = set()
    def strings(value):
        if isinstance(value, dict):
            for key, child in value.items():
                context_strings.add(key)
                strings(child)
        elif isinstance(value, list):
            for child in value:
                strings(child)
        elif isinstance(value, str):
            context_strings.add(value)
    strings(context)
    hidden = {cid for player in h.state.players.values() for cid in player.library + player.hand}
    assert not context_strings & hidden
    with pytest.raises(ValidationError):
        MechanicChoice.model_validate(offered)
    action = MechanicChoice(type='choose_mechanic', card_ids=[h.new]).model_dump(exclude_none=True)
    h.act(seat, action)
    replacement = client.get('/matches/' + h.state.id + '/legal-moves', params={'player_id': seat})
    assert replacement.status_code == 200
    options = replacement.json()['moves']
    assert {option['replacement_source_id'] for option in options} == {h.old, h.rip}
    assert all('legend_context' not in option for option in options)
    chosen = ReplacementChoice(type='choose_replacement', replacement_source_id=h.old).model_dump()
    h.act(seat, chosen)
    assert h.state.cards[h.old].zone.value == 'library'
    assert h.state.cards[h.new].zone.value == 'battlefield'
    (tmp_path / 'actual-whole-public-contract.json').write_text(json.dumps({
        'public_pending': public.json()['pending_mechanic_choice'], 'whole_legal': legal.json(),
        'replacement_legal': replacement.json(), 'replay': log.json(),
        'typed_keeper_action': action, 'typed_replacement_action': chosen}))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_training_whole_view_boundary_and_projected_hint(seat, receipts, tmp_path):
    h = audit.episode(seat, audit.ISAMARU, receipts, tmp_path)
    # Consumer probe of a real captured paid engine position, NOT a reset/built-in episode.
    env = TrainingEnvironment()
    env._state = deepcopy(h.state)
    before = snap(env._state)
    whole = {**RulesEngine().legal_moves(h.state, seat)[0], 'card_ids': [h.new]}
    accepted_whole = env.lookup_intent(whole, seat)
    assert accepted_whole['action'] == {'type': 'choose_mechanic', 'card_ids': [h.new]}
    assert snap(env._state) == before
    observation = env.observe(seat)
    hint = observation['pending_choice']['prompts'][0]['hint']
    assert 'legend_context' not in hint and 'legend_group_index' not in hint
    selected = env.lookup_intent({**hint, 'card_ids': [h.new]}, seat)
    assert selected == accepted_whole
    assert selected['action'] == {'type': 'choose_mechanic', 'card_ids': [h.new]}
    assert snap(env._state) == before
    with pytest.raises(ActionRejected):
        env.lookup_intent({**hint, 'card_ids': [h.new]}, 3-seat)
    assert snap(env._state) == before
    (tmp_path / 'actual-training-contract-boundary.json').write_text(json.dumps({
        'whole_view': whole, 'projected_hint': hint, 'accepted_action': selected,
        'before': before, 'scope': 'Actual captured paid state attached to adapter; no built-in reset claim'}))
