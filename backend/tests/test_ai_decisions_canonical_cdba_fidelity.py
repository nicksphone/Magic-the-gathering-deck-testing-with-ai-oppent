"""Capture real original-test inputs before the actual AI consumer executes."""
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, Zone, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_faces import apply_transform_face
from rules_engine.card_types import printed_card_types
from tests import canonical_positive_fixtures as shared
from tests import test_ai_decisions as original


EXTRA = {'Opt': {'file': 'global_flash_timing_audit/opt.json', 'sha256': '4c1d4b713ae2884e8475dad6c93239d564eb3edfacec3969615df623d40fa3db'}, 'Divination': {'file': 'global_flash_timing_audit/divination.json', 'sha256': 'b4027892ddae4183a1107d169a27a6197bf338dec1ce71283575e1d3618036f2'}, 'Disenchant': {'file': 'shuffle_observer_fix/canonical.jsonl', 'sha256': 'b2940c590f40c0377c5e6abdf5e2459abd4e1c45fdc75fd300b0e450b4e15e71'}, 'Merfolk Looter': {'file': 'ai_decisions_canonical_cdba/merfolk-looter-scryfall-raw.json', 'sha256': 'c896efbb4ed3088cce6f0c811c45d78f64a193a4e34c4a17625a2d055a4b4f62'}, 'Dream Trawler': {'file': 'ai_decisions_canonical_cdba/dream-trawler-scryfall-raw.json', 'sha256': 'b8e6ac8d14c0de9f6053ec6ca803bd7ae83f411f1396cc3c1b96493aaf32a07a'}, 'Runeclaw Bear': {'file': 'ai_decisions_canonical_cdba/runeclaw-bear-scryfall-raw.json', 'sha256': 'f8b88dbd8f0ba783b974472488baf04d04753772a8d6e196eab470b192cce29e'}, 'Rhystic Study': {'file': 'ai_decisions_canonical_cdba/rhystic-study-scryfall-raw.json', 'sha256': 'fd71db57f2d28040ab3c64b949422e8edda5a6f92d9790160043f5c81473e85d'}, 'Explore': {'file': 'ai_decisions_canonical_cdba/explore-scryfall-raw.json', 'sha256': 'eecf27130f92e54ca15fbc8931daee4db1f801905fa8dd0560cd5008f8d512c0'}, 'Grim Haruspex': {'file': 'ai_decisions_canonical_cdba/grim-haruspex-scryfall-raw.json', 'sha256': '5efbfd06276f3bdc9f81f43e58342604f4573cf024852b0e872d96854277d47e'}}
CASES = ['test_ai_materializes_land_only_target_without_creature_target', 'test_ai_casts_non_x_permanent_with_x_in_later_loyalty_ability', 'test_ai_uses_board_value_to_choose_x_loyalty_sweep', 'test_ai_does_not_force_x_sweep_for_a_single_low_value_threat', 'test_ai_announces_only_one_target_for_any_target_damage', 'test_master_ai_prefers_lethal_line', 'test_master_plus_ai_prefers_lethal_line', 'test_control_ai_prefers_card_draw_over_creature_on_empty_stack', 'test_control_ai_prefers_value_draw_over_idle_hold_up_when_stable', 'test_matchup_profile_boosts_counterspell_score_against_aggro', 'test_ramp_ai_prefers_ramp_spell_over_card_draw_on_early_turn', 'test_control_ai_prefers_sweeper_over_draw_when_stabilizing', 'test_board_role_adjusts_pass_bias_for_control_and_aggro_lines', 'test_control_ai_holds_small_attacker_back_into_larger_blocker_when_not_pressing', 'test_ai_does_not_counter_its_only_own_spell_on_the_stack', 'test_control_ai_holds_counter_for_low_impact_creature_but_stops_planeswalker', 'test_control_ai_does_not_double_counter_same_pending_spell', 'test_control_ai_targets_most_threatening_stack_spell_with_counter', 'test_control_ai_mulligans_missing_primary_color_access', 'test_hybrid_spells_do_not_create_false_opening_color_miss', 'test_control_ai_keeps_borderline_two_land_hand_with_real_action', 'test_ramp_ai_keeps_two_land_hand_with_acceleration', 'test_aggro_ai_mulligans_hand_without_early_pressure', 'test_master_ai_casts_big_creature_when_castable', 'test_control_ai_casts_big_creature_on_clear_turn_four_board', 'test_master_ai_uses_deeper_planner_on_complex_midgame_board', 'test_ai_targets_highest_threat_creature_not_just_highest_toughness', 'test_control_ai_more_proactive_when_opponent_tapped_down', 'test_control_ai_casts_big_finisher_on_clear_main_phase', 'test_ai_materializes_x_value_for_x_spells', 'test_ai_x_value_accounts_for_opponent_static_spell_tax', 'test_ai_avoids_casting_x_spells_when_only_x_zero_is_possible', 'test_ai_avoids_low_value_secure_the_wastes_early', 'test_ai_rejects_low_impact_x_value_for_token_spells', 'test_ai_prefers_positive_x_for_interactive_x_removal', 'test_control_ai_prefers_moderate_x_value_over_max_on_stable_board', 'test_ai_uses_log_priors_to_delay_historically_late_noncreature_spells', 'test_ai_uses_role_specific_log_priors_when_board_is_stable', 'test_ai_materialize_sets_default_cost_choice_when_options_present', 'test_ai_forces_land_drop_on_own_main_phase', 'test_ai_prefers_blue_source_for_counterspell_setup', 'test_ai_does_not_invent_land_drop_when_legal_moves_omit_it', 'test_ai_forces_legal_land_drop_even_if_land_counter_is_desynced', 'test_control_ai_mulligan_counts_land_with_missing_types_from_oracle', 'test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic', 'test_tokens_ai_prioritizes_token_enchantment_engine', 'test_control_ai_breaks_late_game_main_phase_pass_loop_with_proactive_spell', 'test_control_ai_deploys_major_threat_instead_of_holding_counter_late', 'test_ai_prefers_preserving_mana_creature_when_other_good_block_exists', 'test_ai_blocks_with_mana_creature_when_it_is_the_only_profitable_assignment', 'test_tribal_ai_prefers_collected_company_style_spell_over_pass', 'test_control_inevitability_planner_prefers_draw_over_pass', 'test_control_inevitability_planner_avoids_counter_on_empty_stack', 'test_ai_targets_high_threat_enchantment_when_available', 'test_counter_target_prefers_high_impact_artifact_stack_spell', 'test_early_turn_cheap_proactive_cast_over_pass_when_opponent_tapped_low', 'test_control_cast_bias_engine_tag_path_does_not_crash', 'test_control_selects_counter_mode_when_stack_is_live', 'test_control_prefers_removal_mode_over_draw_when_opponent_has_board_pressure', 'test_strategic_planner_considers_beyond_top_four_moves_on_complex_boards', 'test_aggro_selects_token_mode_when_board_is_empty']
ALIASES = {'Wedding Announcement': 'Wedding Announcement // Wedding Festivity',
           'Delver of Secrets': 'Delver of Secrets // Insectile Aberration'}
PRINTED = ('name', 'oracle_text', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
           'printed_power', 'printed_toughness', 'loyalty', 'colors', 'keywords', 'layout',
           'card_faces', 'selected_face_index')
NEGATIVE_INPUTS = {
    ('test_ai_does_not_invent_land_drop_when_legal_moves_omit_it', 'Forest'),
    ('test_control_ai_mulligan_counts_land_with_missing_types_from_oracle', 'Island'),
    ('test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic', 'Llanowar Elves'),
}


def archived(name):
    name = ALIASES.get(name, name)
    if name in EXTRA:
        source = EXTRA[name]
        data = (shared.FIXTURES / source['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == source['sha256']
        rows = list(map(json.loads, data.splitlines())) if source['file'].endswith('.jsonl') else [json.loads(data)]
        return next(row for row in rows if row.get('name') == name and row.get('object') == 'card')
    if name == 'Grizzly Bears':
        return shared.raw_card(name)
    data = (shared.FIXTURES / shared.SEED).read_bytes()
    assert hashlib.sha256(data).hexdigest() == shared.PINS[shared.SEED]
    return next(row for row in map(json.loads, data.splitlines()) if row['name'] == name)


def expected(raw):
    cached = ScryfallSyncService._normalize_payload(raw, shared.CACHED_IMAGE_URI)
    types = printed_card_types(cached['type_line'])
    card = CardInstance('projection-only', cached['name'], 1, 1, Zone.HAND,
        types=types, oracle_text=cached['oracle_text'], mana_cost=cached['mana_cost'],
        type_line=cached['type_line'], power=_infer_power(cached['name'], cached['power'], types),
        toughness=_infer_toughness(cached['name'], cached['toughness'], types),
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        loyalty=int(cached['loyalty']) if cached['loyalty'] is not None else None,
        colors=cached['colors'].split(',') if cached['colors'] else [],
        keywords=_infer_keywords(cached['oracle_text']), layout=cached['layout'],
        card_faces=json.loads(cached['card_faces_json']))
    if card.card_faces and card.layout in {'transform', 'modal_dfc'}:
        apply_transform_face(card, 0)
    return card


def capture(monkeypatch, test_name):
    seen = []

    class BeforeConsumer(BaseException):
        pass

    def boundary(agent, state, *args, **kwargs):
        seen.append((state, args, kwargs))
        raise BeforeConsumer

    with monkeypatch.context() as patch:
        for method in ('choose_action', 'choose_mulligan_action', '_materialize_action',
                       '_choose_x_value', '_historical_cast_timing_bias', '_pass_bias',
                       '_cast_bias', '_attack_bias', '_matchup_move_adjustment',
                       '_strategic_plan_action', '_tactical_loyalty_action', '_opening_hand_profile',
                       '_select_mode_text'):
            patch.setattr(original.AIAgent, method, boundary)
        with pytest.raises(BeforeConsumer):
            getattr(original, test_name)()
    assert len(seen) == 1
    return seen[0]


@pytest.mark.parametrize('test_name', CASES)
def test_actual_original_ai_inputs_retain_complete_official_printed_facts(monkeypatch, test_name):
    state, _, _ = capture(monkeypatch, test_name)
    cards = state if isinstance(state, list) else state.cards.values()
    checked = []
    for card in cards:
        name = getattr(card, 'name', '')
        try:
            raw = archived(name)
        except StopIteration:
            continue  # Explicit synthetic/ambiguous identities are separately inventoried, not guessed.
        want = expected(raw)
        fields = {key: getattr(want, key) for key in PRINTED}
        if (test_name, name) in NEGATIVE_INPUTS:
            fields.update(types=[], type_line='')
        actual = {key: getattr(card, key, None) for key in PRINTED}
        differences = [key for key in PRINTED if actual[key] != fields[key]]
        assert not differences, (test_name, name, 'printed fields differ', differences)
        checked.append(name)
    assert checked, (test_name, 'no actual canonical positive card at consumer boundary')


def test_five_official_intakes_are_full_exact_objects_and_preserved_http200():
    source = shared.FIXTURES / 'ai_decisions_canonical_cdba/PROVENANCE.json'
    proof = json.loads(source.read_bytes())
    assert proof['oracle_modified'] is False and proof['minimum_request_spacing_seconds'] >= .25
    successful = [r for r in proof['requests'] if r['status'] == 200]
    assert len(successful) == 5
    for row in successful:
        raw = archived(row['name'])
        assert raw['object'] == 'card' and raw['name'] == row['name']
        assert raw['id'] == row['scryfall_id'] and raw['oracle_id'] == row['oracle_id']
        assert raw['legalities'] and raw['uri'].startswith('https://api.scryfall.com/cards/')
        assert row['response_headers'] and row['complete_raw_response_preserved']


def test_actual_inputs_are_fresh_and_immutable_raw_survives_runtime_mutation(monkeypatch):
    name = 'test_tokens_ai_prioritizes_token_enchantment_engine'
    first, _, _ = capture(monkeypatch, name)
    second, _, _ = capture(monkeypatch, name)
    a, b = first.cards['adeline-1'], second.cards['adeline-1']
    raw = archived('Adeline, Resplendent Cathar')
    assert raw['power'] == '*' and a.printed_power == b.printed_power == '*'
    assert a is not b and a.colors is not b.colors
    a.colors.clear()
    assert b.colors == raw['colors'] and archived(raw['name']) == raw
    assert [face['name'] for face in first.cards['wedding-1'].card_faces] == [
        'Wedding Announcement', 'Wedding Festivity']


@pytest.mark.parametrize('test_name,difficulty', [
    ('test_master_ai_prefers_lethal_line', 'master'),
    ('test_master_plus_ai_prefers_lethal_line', 'master_plus'),
])
def test_original_pooled_mana_pose_chosen_bolt_has_checked_payment_and_real_damage(
        monkeypatch, test_name, difficulty):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine

    state, args, kwargs = capture(monkeypatch, test_name)
    assert state.players[1].mana_pool.get('R') == 1  # Initial policy pose, not naturally tapped mana.
    assert state.players[2].life == 3 and not state.players[1].battlefield
    bolt_id = state.players[1].hand[0]
    assert state.cards[bolt_id].mana_cost == '{R}'
    chosen = original.AIAgent(difficulty=difficulty, archetype='Burn').choose_action(
        state, *args, **kwargs).action
    assert chosen['type'] == 'cast_spell' and chosen['card_id'] == bolt_id
    rules = RulesEngine()
    # Do not move to another phase or bypass engine legality to manufacture a witness.
    paid = checked_action(state, rules, 1, chosen)
    assert state.players[1].mana_pool['R'] == 1 and state.players[2].life == 3
    assert paid.players[1].mana_pool.get('R', 0) == 0
    assert paid.cards[bolt_id].zone == Zone.STACK and bolt_id not in paid.players[1].hand
    for _ in range(8):
        if not paid.stack:
            break
        paid = checked_action(paid, rules, paid.priority_player, {'type': 'pass_priority'})
    assert not paid.stack and paid.players[2].life == 0 and paid.winner == 1
    assert paid.cards[bolt_id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('test_name,card_id,full_name,owner,zone', [
    ('test_ai_x_value_accounts_for_opponent_static_spell_tax', 'tax',
     'Thalia, Guardian of Thraben', 2, Zone.BATTLEFIELD),
    ('test_control_ai_mulligan_counts_land_with_missing_types_from_oracle', 's3',
     'March of Otherworldly Light', 1, Zone.HAND),
])
def test_parent_declared_identity_has_full_facts_at_the_actual_consumer(
        monkeypatch, test_name, card_id, full_name, owner, zone):
    state, _, _ = capture(monkeypatch, test_name)
    card = state.cards[card_id]
    raw = archived(full_name)
    want = expected(raw)
    assert {field: getattr(card, field) for field in PRINTED} == {
        field: getattr(want, field) for field in PRINTED}
    assert card.id == card_id and card.owner == card.controller == owner and card.zone == zone
    assert card.oracle_text == raw['oracle_text'] and card.name == raw['name']
    if card_id == 's3':
        assert state.cards['l1'].types == [] and state.cards['l1'].type_line == ''


def test_grim_haruspex_intake_is_exact_full_http200_and_fresh():
    proof = json.loads((shared.FIXTURES / 'ai_decisions_canonical_cdba/grim-haruspex-PROVENANCE.json').read_bytes())
    assert proof['oracle_modified'] is False and len(proof['requests']) == 1
    record = proof['requests'][0]
    assert record['status'] == 200 and record['response_headers'] and record['complete_raw_response_preserved']
    a, b = archived('Grim Haruspex'), archived('Grim Haruspex')
    assert a == b and a is not b and len(a) > 10
    assert a['object'] == 'card' and a['name'] == record['name'] == 'Grim Haruspex'
    assert a['id'] == record['scryfall_id'] and a['oracle_id'] == record['oracle_id']
    assert a['legalities'] and a['uri'].startswith('https://api.scryfall.com/cards/')


@pytest.mark.parametrize('test_name,difficulty', [
    ('test_master_ai_prefers_lethal_line', 'master'),
    ('test_master_plus_ai_prefers_lethal_line', 'master_plus'),
])
def test_funded_bolt_still_cannot_cast_during_untap(monkeypatch, test_name, difficulty):
    from game_state.state import Step
    from rules_engine.action_validation import ActionRejected, checked_action
    from rules_engine.engine import RulesEngine

    state, args, kwargs = capture(monkeypatch, test_name)
    state.step = Step.UNTAP
    untap_moves = RulesEngine().legal_moves(state, 1)
    bolt_id = state.players[1].hand[0]
    assert state.players[1].mana_pool['R'] == 1 and state.players[2].life == 3
    assert not any(move['type'] == 'cast_spell' for move in untap_moves)
    chosen = original.AIAgent(difficulty=difficulty, archetype='Burn').choose_action(
        state, untap_moves, 1).action
    assert chosen['type'] == 'pass_priority'
    with pytest.raises(ActionRejected, match='^Action is not currently legal$'):
        checked_action(state, RulesEngine(), 1, {
            'type': 'cast_spell', 'card_id': bolt_id, 'targets': {'target_player': 2}})
    assert state.players[1].mana_pool['R'] == 1 and state.players[2].life == 3
    assert not state.stack and state.cards[bolt_id].zone == Zone.HAND


@pytest.mark.parametrize('test_name', [
    'test_master_ai_prefers_lethal_line',
    'test_master_plus_ai_prefers_lethal_line',
])
def test_original_two_offer_fixture_uses_actual_matching_engine_cast(monkeypatch, test_name):
    from rules_engine.engine import RulesEngine

    observed = []
    actual_legal_moves = RulesEngine.legal_moves
    def record_offers(engine, state, player_id):
        offers = actual_legal_moves(engine, state, player_id)
        observed.append((state, player_id, offers))
        return offers

    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine, 'legal_moves', record_offers)
        state, args, kwargs = capture(patch, test_name)
    moves, player_id = args
    assert not kwargs and player_id == 1 and len(moves) == 2
    assert moves[0] == {'type': 'pass_priority'}
    bolt_id = state.players[1].hand[0]
    assert moves[1]['type'] == 'cast_spell' and moves[1]['card_id'] == bolt_id
    assert moves[1]['card_name'] == 'Lightning Bolt'
    assert len(observed) == 1 and observed[0][0] is state and observed[0][1] == 1
    matching = [offer for offer in observed[0][2]
                if offer.get('type') == 'cast_spell' and offer.get('card_id') == bolt_id]
    assert len(matching) == 1 and moves[1] == matching[0]
    assert moves[1]['mana_cost'] == state.cards[bolt_id].mana_cost == '{R}'
    assert any(target['id'] == 2 for target in moves[1]['target_hints']['player_targets'])
    assert any(option['id'] == 'base' and option['mana_cost'] == '{R}'
               for option in moves[1]['cost_options'])
    # Malformed protocol offer, not a natural-game policy regression.
    minimal = {'type': 'cast_spell', 'card_id': bolt_id, 'card_name': 'Lightning Bolt'}
    agent = original.AIAgent(difficulty='master', archetype='Burn')
    assert agent._burn_has_only_friendly_targets(state, minimal, 1)
    assert not agent._burn_has_only_friendly_targets(state, moves[1], 1)
