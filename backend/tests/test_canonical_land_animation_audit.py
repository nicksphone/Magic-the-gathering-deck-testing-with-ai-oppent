"""Two canonical families, constructed positions; ordinary desired failures.

Later lifecycle assertions never manufacture an animation to bypass admission.
If activation fails, those assertions remain explicitly prerequisite-blocked.
"""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from knowledge.mechanic_metadata import mechanic_metadata
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_ability_spec
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.costs import activated_cost_available, parse_activated_cost
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.type_effects import effective_types
from tests.test_linked_damage_targets import raw_card

D = Path(__file__).parent / 'fixtures/canonical_land_animation_audit'
ROWS = {}
for entry in json.loads((D / 'provenance.json').read_text())['cards']:
    raw = (D / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['object'] == 'card' and row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row
FAMILIES = ['Mutavault', 'Celestial Colonnade']


def snapshot(state):
    return json.loads(json.dumps(serialize_match_snapshot(state)))


def record(request, state, **detail):
    directory = os.environ.get('MTG_LAND_ANIMATION_EVIDENCE')
    if directory:
        path = Path(directory) / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
        with path.open('x') as f:
            json.dump({'node': request.node.nodeid, 'snapshot': snapshot(state), **detail}, f, indent=2, sort_keys=True)


def position(seat, name, newly_played=False):
    deck = [{**ROWS['Island'], 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=7627)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    land = raw_card(state, ROWS[name], seat, Zone.HAND if newly_played else Zone.BATTLEFIELD)
    if newly_played:
        state = checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': land.id})
        land = state.cards[land.id]
    else:
        assign_static_order_on_battlefield_entry(state, land.id)
    state.players[seat].mana_pool = {'C': 1} if name == 'Mutavault' else {'C': 3, 'W': 1, 'U': 1}
    return state, land


def ability(land):
    abilities = extract_activated_abilities(land)
    assert len(abilities) == 1, abilities
    return abilities[0]


def action(land):
    return {'type': 'activate_ability', 'card_id': land.id, 'ability_index': ability(land)['index'], 'targets': {}}


def activate(request, state, seat, land):
    before = snapshot(state)
    try:
        candidate = checked_action(state, RulesEngine(), seat, action(land))
    except ActionRejected as error:
        assert snapshot(state) == before
        record(request, state, phase='activation', prerequisite_blocked=True,
               rejection=str(error), root_and_rng_unchanged=True)
        raise
    assert snapshot(state) == before
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    assert len(candidate.stack) == 1
    assert candidate.stack[0].source_card_id == land.id
    assert candidate.stack[0].effect_key != 'noop'
    return candidate


def resolve(state):
    for _ in range(8):
        if not state.stack:
            return state
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Eight native priority passes did not resolve the real stack')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_observed_extraction_cost_payability_and_metadata_are_separate(request, seat, name):
    state, land = position(seat, name)
    before = snapshot(state)
    parsed = ability(land)
    expected = '{1}' if name == 'Mutavault' else '{3}{W}{U}'
    assert parsed['index'] == 1 and parsed['mana_cost'] == expected
    assert parse_activated_cost(expected).supported
    assert activated_cost_available(state, seat, land.id, expected, ability_index=1)
    metadata = mechanic_metadata(ROWS[name])
    assert all(value['execution_support'] == 'unknown' for value in metadata['coverage'].values())
    assert snapshot(state) == before
    record(request, state, phase='extraction_cost', ability=parsed, payable=True,
           metadata=metadata, classifier_gaps=known_unsupported_mechanics(land.oracle_text, card_name=land.name),
           note='No classifier gap is not evidence of executable animation')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_animation_clause_compiles_to_non_noop(request, seat, name):
    state, land = position(seat, name)
    parsed = ability(land)
    proxy = SimpleNamespace(id=land.id, name=land.name, oracle_text=parsed['text'], mana_cost='',
                            source_oracle_text=land.oracle_text)
    before = snapshot(state)
    spec = build_ability_spec(state, proxy, seat, report_unsupported=False)
    assert snapshot(state) == before
    record(request, state, phase='compiler', ability=parsed,
           effect_key=spec.effect.key, payload=spec.effect.payload)
    assert spec.effect.key != 'noop', 'Canonical extracted/payable animation is not executable'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('newly_played', [False, True])
def test_desired_public_animation_available_even_when_non_tap_source_is_sick_or_tapped(request, seat, name, newly_played):
    state, land = position(seat, name, newly_played)
    before = snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert snapshot(state) == before
    record(request, state, phase='public_legal', moves=moves, newly_played=newly_played)
    assert any(m['type'] == 'activate_ability' and m.get('card_id') == land.id
               and m.get('ability_index') == 1 for m in moves)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('newly_played', [False, True])
def test_desired_checked_payment_resolution_types_stats_keywords_and_roundtrip(request, seat, name, newly_played):
    state, land = position(seat, name, newly_played)
    original = snapshot(state)
    candidate = activate(request, state, seat, land)
    candidate = resolve(candidate)
    assert {'Land', 'Creature'} <= set(effective_types(candidate, land.id))
    assert (effective_power(candidate, land.id), effective_toughness(candidate, land.id)) == ((2, 2) if name == 'Mutavault' else (4, 4))
    if name == 'Celestial Colonnade':
        from rules_engine.colors import card_color_symbols
        assert has_keyword(candidate, land.id, 'flying') and has_keyword(candidate, land.id, 'vigilance')
        assert card_color_symbols(candidate.cards[land.id], candidate) == {'W', 'U'}
        assert candidate.cards[land.id].colors == ROWS[name]['colors']
    else:
        # Actual existing subtype consumer, not a fabricated Changeling keyword.
        from rules_engine.affinity import _matches
        assert all(_matches(candidate, candidate.cards[land.id], subtype) for subtype in ['elves', 'goblins'])
    assert candidate.cards[land.id].oracle_text == ROWS[name]['oracle_text']
    assert snapshot(deserialize_match_snapshot(snapshot(candidate))) == snapshot(candidate)
    assert snapshot(state) == original
    record(request, candidate, phase='resolved_layers', prerequisite_blocked=False)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('newly_played', [False, True])
def test_desired_same_turn_attack_mana_constraints_and_real_cleanup(request, seat, name, newly_played):
    state, land = position(seat, name, newly_played)
    candidate = resolve(activate(request, state, seat, land))
    assert candidate.cards[land.id].summoning_sick == newly_played
    candidate.step = Step.DECLARE_ATTACKERS
    candidate.priority_player = seat
    before = snapshot(candidate)
    attack = {'type': 'attack', 'attackers': [land.id], 'attack_targets': {land.id: f'player:{3-seat}'}}
    if newly_played:
        with pytest.raises(ActionRejected):
            checked_action(candidate, RulesEngine(), seat, attack)
        attacked = None
    else:
        attacked = checked_action(candidate, RulesEngine(), seat, attack)
        assert land.id in attacked.attackers
    assert snapshot(candidate) == before
    if name == 'Celestial Colonnade' and not newly_played:
        assert not attacked.cards[land.id].tapped  # Vigilance is not an untap effect.
    tap = {'type': 'tap_land_for_mana', 'card_id': land.id,
           'color': 'C' if name == 'Mutavault' else 'U'}
    if newly_played:
        with pytest.raises(ActionRejected):
            checked_action(candidate, RulesEngine(), seat, tap)
    else:
        mana = checked_action(candidate, RulesEngine(), seat, tap)
        assert mana.cards[land.id].tapped
        assert mana.players[seat].mana_pool[tap['color']] == 1
    assert snapshot(candidate) == before
    candidate.step = Step.END_STEP
    candidate.priority_player = seat
    candidate.passed_priority.clear()
    for _ in range(10):
        if candidate.turn != state.turn:
            break
        candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
    assert candidate.turn != state.turn
    assert 'Creature' not in effective_types(candidate, land.id)
    assert 'Land' in effective_types(candidate, land.id)
    assert not has_keyword(candidate, land.id, 'flying') and not has_keyword(candidate, land.id, 'vigilance')
    record(request, candidate, phase='cleanup', prerequisite_blocked=False)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_animation_does_not_follow_source_through_actual_flicker(request, seat, name):
    state, land = position(seat, name)
    candidate = resolve(activate(request, state, seat, land))
    previous = object_incarnation(candidate.cards[land.id])
    spell = raw_card(candidate, ROWS['Flicker'], seat, Zone.HAND)
    candidate.active_player = candidate.priority_player = seat
    candidate.step = Step.PRECOMBAT_MAIN
    candidate.players[seat].mana_pool = {'C': 2, 'W': 1}
    candidate = checked_action(candidate, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': land.id}})
    candidate = resolve(candidate)
    assert candidate.cards[land.id].zone == Zone.BATTLEFIELD
    assert object_incarnation(candidate.cards[land.id]) != previous
    assert 'Creature' not in effective_types(candidate, land.id)
    assert not has_keyword(candidate, land.id, 'flying') and not has_keyword(candidate, land.id, 'vigilance')
    assert candidate.cards[land.id].owner == candidate.cards[land.id].controller == seat
    assert snapshot(deserialize_match_snapshot(snapshot(candidate))) == snapshot(candidate)
    record(request, candidate, phase='incarnation', prerequisite_blocked=False)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_land_play_retains_tapped_entry_and_same_turn_tracking(request, seat, name):
    state, land = position(seat, name, True)
    assert land.zone == Zone.BATTLEFIELD and land.summoning_sick
    assert land.tapped == (name == 'Celestial Colonnade')
    assert state.players[seat].lands_played_this_turn == 1
    assert 'Creature' not in effective_types(state, land.id)
    record(request, state, phase='native_land_entry')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('reason', ['unfunded', 'wrong_priority', 'wrong_actor'])
def test_atomic_safety_rejection_without_animation_or_mana_loss(request, seat, name, reason):
    state, land = position(seat, name)
    if reason == 'unfunded':
        state.players[seat].mana_pool = {}
    elif reason == 'wrong_priority':
        state.priority_player = 3-seat
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat if reason == 'wrong_actor' else seat, action(land))
    assert snapshot(state) == before
    record(request, state, phase='negative_control', reason=reason,
           note='Atomic rejection only; unsupported effect can mask later eligibility checks')


@pytest.fixture
def isolated_api(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine
    from persistence.repository import Repository
    import persistence.db as db
    import main
    root = Path(__file__).resolve().parents[2]
    assert Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve() == root
    assert (root / '.private').read_text() == str(root)
    assert not (root / '.git').exists() and not root.is_symlink()
    assert Path(main.__file__).resolve().parent == root / 'backend'
    default = root / 'backend/mtg_lab.db'
    assert not default.is_symlink()
    default_before = default.read_bytes() if default.exists() else None
    memory = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(memory)
    monkeypatch.setattr(db, 'engine', memory)
    monkeypatch.setattr(main, 'engine', memory)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})
    def repository():
        with Session(memory) as session:
            yield Repository(session)
    assert main.get_repo not in main.app.dependency_overrides
    main.app.dependency_overrides[main.get_repo] = repository
    client = TestClient(main.app)  # No application lifespan, seed sync, or live server.
    try:
        yield main, memory, client
    finally:
        client.close()
        del main.app.dependency_overrides[main.get_repo]
        memory.dispose()
        assert (default.read_bytes() if default.exists() else None) == default_before


def db_dump(engine):
    connection = engine.raw_connection()
    try:
        return tuple(connection.driver_connection.iterdump())
    finally:
        connection.close()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('funded', [True, False])
def test_desired_private_http_activation_atomic_sql_and_native_restore(isolated_api, request, seat, name, funded):
    from sqlmodel import Session
    from persistence.repository import Repository
    main, memory, client = isolated_api
    state, land = position(seat, name)
    hidden = raw_card(state, ROWS['Flicker'], 3-seat, Zone.HAND)
    if not funded:
        state.players[seat].mana_pool = {}
    controller = main.MatchController(state=state, rules=RulesEngine(), controllers={seat: 'human', 3-seat: 'ai'},
        ai={}, mode='human_vs_ai', deck_ids=(None, None), mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=1)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(memory) as session:
        main._persist_active_match(Repository(session), controller)
    before = snapshot(state)
    sql_before = db_dump(memory)
    view = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}')
    assert view.status_code == 200 and hidden.id not in json.dumps(view.json())
    assert snapshot(state) == before and db_dump(memory) == sql_before
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action(land)})
    if response.status_code == 422:
        assert snapshot(controller.state) == before and db_dump(memory) == sql_before
    else:
        assert response.status_code == 200, response.text
        assert sum(controller.state.players[seat].mana_pool.values()) == 0
    after = snapshot(controller.state)
    assert hidden.id not in json.dumps(response.json())
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(memory) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id].state) == after
    record(request, main.ACTIVE_MATCHES[state.id].state, phase='http', status=response.status_code,
           funded=funded, legal_view=view.json(), response=response.json(), before=before,
           root_sql_unchanged=response.status_code == 422, restart_equal=True,
           transport='Actual ASGI HTTP; memory SQLite; no lifespan; in-process native persistence restore')
    assert response.status_code == (200 if funded else 422)
