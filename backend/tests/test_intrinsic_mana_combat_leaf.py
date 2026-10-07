"""SQL/network-free intrinsic-mana leaf qualification, not natural-game evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.card_faces import apply_transform_face
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.mana_abilities import tap_only_outputs
from tests.test_empty_hand_attack_witness import ROWS, position, finish_combat
from tests.test_linked_damage_targets import raw_card
from tests.test_public_combat_boundary_audit import LANDS, response_window


FIXTURES = Path(__file__).parent / 'fixtures'


def official(file):
    path = FIXTURES / file
    data = path.read_bytes()
    provenance = json.loads(Path(str(path) + '.provenance.json').read_text())
    assert hashlib.sha256(data).hexdigest() == provenance['sha256']
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['oracle_id'] and raw['id']
    return raw


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
@pytest.mark.parametrize('land', ['Underground Sea', 'Tropical Island'])
@pytest.mark.parametrize('tapped', [False, True])
def test_full_raw_dual_tapped_or_ready_checked_decision_and_restore(seat, family, land, tapped):
    state, source = position(seat, family, counter=True)
    card = raw_card(state, LANDS[land], 3-seat, Zone.BATTLEFIELD)
    card.tapped = tapped
    assert card.colors == [] and card.oracle_text == LANDS[land]['oracle_text']
    assert set(tap_only_outputs(state, card, ignore_readiness=True)) == (
        {'U', 'B'} if land == 'Underground Sea' else {'U', 'G'})
    before = serialize_match_snapshot(state)
    announced, _, _ = response_window(state, seat, source)
    agent = AIAgent(difficulty='master', archetype='Control')
    leaf = agent._complete_strategic_combat_leaf(announced, seat)
    assert leaf is not None and leaf.players[3-seat].life == 20-int(ROWS[family]['power'])
    restored = deserialize_match_snapshot(serialize_match_snapshot(announced))
    restored_leaf = agent._complete_strategic_combat_leaf(restored, seat)
    assert serialize_match_snapshot(restored_leaf) == serialize_match_snapshot(leaf)
    decision = agent.choose_action(state, agent.engine.legal_moves(state, seat), seat)
    assert decision.action['type'] == 'attack' and source in decision.action['attackers']
    actual = finish_combat(checked_action(state, agent.engine, seat, decision.action))
    assert actual.players[3-seat].life == leaf.players[3-seat].life
    assert actual.cards[card.id].tapped == tapped
    assert actual.players[seat].hand == state.players[seat].hand
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['functional', 'creature-land', 'modal-front', 'modal-back'])
def test_real_functional_or_nonland_faces_are_not_intrinsic_empty_land(seat, case):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    raw = (ROWS['Mutavault'] if case == 'functional' else official(
        'graveyard_permissions/dryad-arbor.json' if case == 'creature-land'
        else 'graveyard_permissions/bala-ged-recovery.json'))
    card = raw_card(state, raw, 3-seat, Zone.BATTLEFIELD)
    if case.startswith('modal-'):
        apply_transform_face(card, int(case == 'modal-back'))
        assert card.oracle_text == raw['card_faces'][int(case == 'modal-back')]['oracle_text']
    announced, _, _ = response_window(state, seat, source)
    before = serialize_match_snapshot(announced)
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    assert serialize_match_snapshot(announced) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['missing-text', 'missing-type-line', 'effective-creature',
                                  'nonland', 'suppressed'])
def test_trusted_metadata_and_layer_receipt_probes_fail_closed(seat, case):
    # Not claimed as a paid spell: metadata damage / supported resolved-layer receipt.
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, LANDS['Tropical Island'], 3-seat, Zone.BATTLEFIELD)
    announced, _, _ = response_window(state, seat, source)
    card = announced.cards[card.id]
    if case == 'missing-text':
        card.oracle_text = None
    elif case == 'missing-type-line':
        card.type_line = ''
    elif case == 'effective-creature':
        card.types.append('Creature')
    elif case == 'nonland':
        card.types = []
        card.type_line = ''
    else:
        add_keyword_effect(announced, card.id, ['all abilities'], operation='remove')
        assert tap_only_outputs(announced, card, ignore_readiness=True) == {}
    before = serialize_match_snapshot(announced)
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    assert serialize_match_snapshot(announced) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_card_color_metadata_does_not_fabricate_mana_output(seat):
    # Trusted color-metadata probe, not an invented canonical color-changing spell.
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, LANDS['Tropical Island'], 3-seat, Zone.BATTLEFIELD)
    card.colors = ['R']
    assert tap_only_outputs(state, card) == {'U': 1, 'G': 1}
    announced, _, _ = response_window(state, seat, source)
    before = serialize_match_snapshot(announced)
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is not None
    assert serialize_match_snapshot(announced) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', [Zone.HAND, Zone.EXILE])
def test_unexpanded_hidden_or_exile_inventory_remains_unknown(seat, zone):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    raw_card(state, ROWS['Lightning Bolt'], 3-seat, zone)
    raw_card(state, LANDS['Underground Sea'], 3-seat, Zone.BATTLEFIELD)
    announced, _, _ = response_window(state, seat, source)
    before = serialize_match_snapshot(announced)
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    assert serialize_match_snapshot(announced) == before
