"""Paid native casts first; feature joins never use fixture/private payloads."""
from copy import deepcopy
import json

import pytest

from card_data.seed_cards import seed_card_payload
from game_state.state import Zone
from tests.scheduler_fixture_position import ordinary_position
from tests.test_training_environment import cast, position
from training import TrainingEnvironment, encode_action
from training import decision_frame as features
from training.dataset import episode_groups, episode_records, model_input


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _expanded(pack):
    """Expand only reachable gathers; unused bank/index differences are not evidence."""
    assert pack['version'] == 'mtg.features.v2'
    bank = pack['entities']
    context_kinds = {'card_context', 'stack_context'}
    kinds = [_field(entry, 'entity_kind')['value'] for entry in bank]
    context_start = next((index for index, kind in enumerate(kinds) if kind in context_kinds), len(bank))
    assert context_start < len(bank), 'Missing public-reference context bank'
    assert all(kind in context_kinds for kind in kinds[context_start:])

    def walk(node, available):
        kind = node['kind']
        if kind == 'ref':
            index = node['index']
            assert type(index) is int and 0 <= index < available
            return walk(bank[index], index)
        if kind == 'map':
            pairs = [[walk(key, available), walk(value, available)]
                     for key, value in node['items']]
            return {'kind': kind, 'items': sorted(pairs, key=lambda row: _canonical(row[0]))}
        if kind in {'list', 'set'}:
            items = [walk(item, available) for item in node['items']]
            return {'kind': kind, 'items': sorted(items, key=_canonical) if kind == 'set' else items}
        return deepcopy(node)

    for index, entry in enumerate(bank):
        # Even a preceding context record is forbidden as a context dependency.
        walk(entry, min(index, context_start))
    return walk(pack['root'], len(bank))


def _field(node, name):
    assert node['kind'] == 'map'
    matches = [value for key, value in node['items']
               if key == {'kind': 'text', 'value': name}]
    assert len(matches) == 1
    return matches[0]


def _named_values(node, name):
    if node['kind'] == 'map':
        result = [value for key, value in node['items']
                  if key == {'kind': 'text', 'value': name}]
        for key, value in node['items']:
            result.extend(_named_values(key, name))
            result.extend(_named_values(value, name))
        return result
    if node['kind'] in {'list', 'set'}:
        return [value for item in node['items'] for value in _named_values(item, name)]
    return []


def _paid_two_bolts(seat, self_first):
    """C2 retained resource/zone pose, not an entire causally played game."""
    environment, counterspell = position(seat, 'Counterspell')
    caster = 3 - seat
    state = environment._state
    state.active_player = state.priority_player = caster
    ordinary_position(state)
    bolts = [card for card in state.cards.values()
             if card.owner == caster and card.name == 'Lightning Bolt'][:2]
    assert len(bolts) == 2 and bolts[0].id != bolts[1].id
    for card in [state.cards[counterspell], *bolts]:
        raw = seed_card_payload(card.name)
        assert card.oracle_text == raw['oracle_text']
        assert card.mana_cost == raw['mana_cost'] and card.type_line == raw['type_line']
    for card in bolts:
        for zone in ('hand', 'library', 'battlefield', 'graveyard', 'exile'):
            ids = getattr(state.players[caster], zone)
            if card.id in ids:
                ids.remove(card.id)
        state.players[caster].hand.append(card.id)
        card.move_to_zone(Zone.HAND)
    state.players[caster].mana_pool = {'R': 2}
    state.players[seat].mana_pool = {'U': 2}
    order = [seat, caster] if self_first else [caster, seat]
    announced = {}
    for card, target in zip(bolts, order):
        action = cast(environment, card.id, target_player=target)
        assert environment.lookup(action)['id'] == encode_action(action)
        environment.step(action, caster)
        view = environment.observe(caster)
        assert view['stack'][-1]['source_card_id'] == card.id
        assert view['stack'][-1]['label'] == 'Lightning Bolt'
        assert view['known_cards'][card.id]['zone'] == 'stack'
        announced[target] = view['stack'][-1]['id']
    assert len(environment.observe(caster)['stack']) == 2
    assert environment.observe(caster)['players'][str(caster)]['mana_pool'].get('R', 0) == 0
    environment.step({'type': 'pass_priority'}, caster)
    assert environment.acting_seat == seat
    snapshot = environment.snapshot()
    actions = {target: cast(environment, counterspell, target_stack_id=stack_id)
               for target, stack_id in announced.items()}
    # Both complete proposals really cast the same Counterspell on independent roots.
    for target, action in actions.items():
        environment.lookup(action, seat)
        assert environment.snapshot() == snapshot
        branch = TrainingEnvironment()
        branch.restore(snapshot)
        branch.step(action, seat)
        public = branch.observe(seat)
        assert len(public['stack']) == 3
        assert public['stack'][-1]['label'] == 'Counterspell'
        assert public['stack'][-1]['source_card_id'] == counterspell
        assert public['players'][str(seat)]['mana_pool'].get('U', 0) == 0
        for _ in range(8):
            if not branch.observe(branch.acting_seat)['stack']:
                break
            branch.step({'type': 'pass_priority'})
        final = branch.observe(branch.acting_seat)
        assert final['stack'] == []
        assert final['players'][str(seat)]['life'] == (20 if target == seat else 17)
        assert final['players'][str(caster)]['life'] == (17 if target == seat else 20)
    assert environment.snapshot() == snapshot
    return environment, actions, announced


def _capture(environment, seat):
    method = getattr(environment, 'decision_context', None)
    assert callable(method), 'Missing opt-in actor-public announcement projection'
    before = environment.snapshot()
    observation, prompts = environment.observe(seat), environment.prompts(seat)
    context = method(seat)
    assert environment.snapshot() == before
    assert set(context) == {'version', 'seat', 'stack'}
    assert context['version'] == 'mtg.public-context.v1' and context['seat'] == seat
    assert [item['stack_id'] for item in context['stack']] == [item['id'] for item in observation['stack']]
    assert all(set(item) == {'stack_id', 'announcement_available', 'announced_targets', 'reference_lifecycle'}
               for item in context['stack'])
    with pytest.raises(ValueError):
        method(3-seat)
    assert environment.snapshot() == before
    return observation, prompts, context


@pytest.mark.parametrize(('seat', 'self_first'), [(1, True), (1, False), (2, True), (2, False)],
                         ids=['seat1-self-first', 'seat1-opponent-first', 'seat2-self-first', 'seat2-opponent-first'])
def test_checked_counterspell_targets_join_real_paid_bolt_targets(seat, self_first):
    environment, actions, announced = _paid_two_bolts(seat, self_first)
    observation, prompts, context = _capture(environment, seat)
    assert observation == environment.observe(seat)
    by_id = {item['stack_id']: item for item in context['stack']}
    for target, stack_id in announced.items():
        assert by_id[stack_id]['announcement_available'] is True
        assert by_id[stack_id]['announced_targets'] == {'target_player': target}
        assert by_id[stack_id]['reference_lifecycle'] == 'unknown'
    frame, bindings = features.build_decision_frame(observation, prompts, public_context=context)
    expanded = {target: _expanded(features.encode_action(frame, bindings.action(action)))
                for target, action in actions.items()}
    assert expanded[seat] != expanded[3-seat], 'Selected stack references collapse distinct public targets'
    for target, label in ((seat, 'self'), (3-seat, 'opponent')):
        selected = _field(_field(expanded[target], 'targets'), 'target_stack_id')
        assert _named_values(selected, 'target_player') == [{'kind': 'text', 'value': label}]


def _rename(value, mapping):
    if isinstance(value, dict):
        return {mapping.get(key, key): _rename(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_rename(item, mapping) for item in value]
    return mapping.get(value, value) if isinstance(value, str) else value


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_context_reference_expansion_is_equivariant_to_opaque_id_renaming(seat, monkeypatch):
    environment, actions, _ = _paid_two_bolts(seat, True)
    observation, prompts, context = _capture(environment, seat)
    mapping = {cid: 'renamed-card-' + str(index)
               for index, cid in enumerate(reversed(list(observation['known_cards'])))}
    mapping.update({item['id']: 'renamed-stack-' + str(index)
                    for index, item in enumerate(reversed(observation['stack']))})
    first, one = features.build_decision_frame(observation, prompts, public_context=context)
    second, two = features.build_decision_frame(
        _rename(observation, mapping), _rename(prompts, mapping),
        public_context=_rename(context, mapping))
    assert _expanded(features.encode_state(first)) == _expanded(features.encode_state(second))
    for action in actions.values():
        before = _expanded(features.encode_action(first, one.action(action)))
        after = _expanded(features.encode_action(second, two.action(_rename(action, mapping))))
        assert before == after
        rendered = _canonical(after)
        assert all(identifier not in rendered for identifier in [*mapping, *mapping.values()])
    events = []
    actual_context = environment.decision_context

    def capture(actor):
        events.append('context')
        return actual_context(actor)

    def choose(current):
        assert current is environment
        events.append('chooser')
        return actions[seat]

    monkeypatch.setattr(environment, 'decision_context', capture)
    groups = episode_groups(17, ['counter-context-fixture'],
                            environment.snapshot()['provenance']['deck_hashes'],
                            position_group='retained-two-paid-bolts')
    rows = list(episode_records(environment, choose, episode='episode-0000', groups=groups,
                               tick_budget=1, decision_frame=True, public_context=True))
    assert events == ['context', 'chooser']
    assert rows[1]['accepted'] is True and model_input(rows[1]) == first
    assert rows[-1]['complete'] is False and rows[-1]['terminal_rewards'] is None
