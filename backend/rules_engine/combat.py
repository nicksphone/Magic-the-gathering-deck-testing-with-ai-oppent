from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from game_state.state import MatchState, Step, Zone, object_incarnation
from rules_engine.colors import card_color_names
from rules_engine.continuous import KNOWN_KEYWORDS, effective_power, effective_toughness, has_keyword
from rules_engine.events import emit_event, emit_event_batch
from rules_engine.query_context import rule_query_scope
from rules_engine.prevention import consume_card_prevention_shield, consume_player_prevention_shield
from rules_engine.protection import protected_from_source
from rules_engine.replacement import damage_cant_be_prevented, replace_die_zone, apply_permanent_damage_replacements, apply_damage_replacements
from rules_engine.restrictions import (
    card_cant_attack,
    card_cant_attack_alone,
    card_cant_block,
    card_cant_block_alone,
)

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"
BLOCK_ONLY_KEYWORD_RE = re.compile(r"\bcan block only creatures with ([a-z][a-z ]*?)(?:[.\n]|$)", re.IGNORECASE)


def bind_attack_target(state, attacker, target):
    """Retain the permanent object, its defending player and relevant types."""
    state.combat_target_context.pop(attacker, None)
    if not target.startswith(('battle:', 'planeswalker:')):
        return
    cid = target.split(':', 1)[1]
    card = state.cards.get(cid)
    if card is None or card.zone != Zone.BATTLEFIELD:
        state.attack_targets[attacker] = ''
        return
    state.combat_target_context[attacker] = {
        'target_card_id': cid, 'incarnation': object_incarnation(card),
        'zone_change_sequence': card.zone_change_sequence,
        'controller': card.controller, 'protector': card.battle_protector,
        'types': sorted(set(effective_types(state, card)) & {'Battle', 'Planeswalker'}),
        'removed': False}


def remove_permanent_from_combat(state, card_id):
    """A genuine departure/control transition cannot be undone by returning."""
    state.attackers = [cid for cid in state.attackers if cid != card_id]
    state.attack_targets.pop(card_id, None)
    state.combat_target_context.pop(card_id, None)
    state.blocks = {aid: [bid for bid in bids if bid != card_id]
                    for aid, bids in state.blocks.items() if aid != card_id}
    for aid, context in state.combat_target_context.items():
        if context['target_card_id'] == card_id:
            context['removed'] = True
            state.attack_targets[aid] = ''


def reconcile_combat_targets(state):
    """Latch rule506.4 removal; retain the conditional mixed-type exceptions."""
    for aid in list(state.combat_target_context):
        if aid not in state.attackers:
            del state.combat_target_context[aid]
            continue
        context = state.combat_target_context[aid]
        card = state.cards.get(context['target_card_id'])
        previous = set(context['types'])
        current = set(effective_types(state, card)) & {'Battle', 'Planeswalker'} if card else set()
        removed = (context['removed'] or card is None or card.zone != Zone.BATTLEFIELD
                   or object_incarnation(card) != context['incarnation']
                   or card.zone_change_sequence != context['zone_change_sequence']
                   or card.controller != context['controller']
                   or ('Battle' in previous and card.battle_protector != context['protector'])
                   or not current)
        if not removed and not previous.issubset(current):
            removed = not (previous == {'Battle', 'Planeswalker'}
                           and (current == {'Battle'} or current == {'Planeswalker'}
                                and card.controller == context['protector']))
        if removed:
            context['removed'] = True
            state.attack_targets[aid] = ''
        else:
            context['types'] = sorted(current)
            key = 'battle:' if 'Battle' in current else 'planeswalker:'
            state.attack_targets[aid] = key + card.id


def is_being_attacked(state, card_id):
    reconcile_combat_targets(state)
    return any(aid in state.attackers and not context['removed']
               and context['target_card_id'] == card_id
               for aid, context in state.combat_target_context.items())


def restore_combat_targets(state, raw):
    """Legacy player and planeswalker destinations retain their prior behavior."""
    from copy import deepcopy
    if type(raw) is not dict:
        raise ValueError('Invalid combat target context')
    keys = {'target_card_id', 'incarnation', 'zone_change_sequence', 'controller', 'protector', 'types', 'removed'}
    for aid, row in raw.items():
        if (type(aid) is not str or aid not in state.attackers or type(row) is not dict
                or set(row) != keys or type(row['target_card_id']) is not str
                or row['target_card_id'] not in state.cards
                or any(type(row[key]) is not int or row[key] < 0 for key in ('incarnation', 'zone_change_sequence'))
                or type(row['controller']) is not int or row['controller'] not in state.players
                or not (row['protector'] is None or type(row['protector']) is int and row['protector'] in state.players)
                or type(row['removed']) is not bool or type(row['types']) is not list
                or not row['types'] or any(type(kind) is not str for kind in row['types'])
                or row['types'] != sorted(set(row['types']))
                or not set(row['types']).issubset({'Battle', 'Planeswalker'})
                or (state.attack_targets.get(aid) != '' if row['removed'] else
                    state.attack_targets.get(aid) not in {'battle:' + row['target_card_id'], 'planeswalker:' + row['target_card_id']})):
            raise ValueError('Invalid retained combat destination')
    state.combat_target_context = deepcopy(raw)
    for aid, key in state.attack_targets.items():
        if aid not in raw and key.startswith('battle:'):
            state.attack_targets[aid] = ''
    reconcile_combat_targets(state)


def remove_noncreatures_from_combat(state):
    """A type transition removes combatants; returning to creature doesn't rejoin."""
    if not (state.attackers or state.attack_targets or state.blocks or state.combat_target_context):
        return

    def remains(cid):
        card = state.cards.get(cid)
        if card is None or card.zone != Zone.BATTLEFIELD:
            return False
        types = effective_types(state, card)
        return 'Creature' in types and 'Battle' not in types

    with rule_query_scope(state):
        attackers = [cid for cid in state.attackers if remains(cid)]
        # Preserve an empty block entry: the attacker remains blocked (rule 509.1h).
        blocks = {cid: [bid for bid in bids if remains(bid)]
                  for cid, bids in state.blocks.items() if cid in attackers}
    state.attackers = attackers
    state.attack_targets = {cid: target for cid, target in state.attack_targets.items() if cid in attackers}
    state.blocks = blocks
    reconcile_combat_targets(state)
    # Announced bands persist; block assignment filters out departed members.


def valid_attack_bands(state: MatchState, attackers: list[str], targets: dict[str, str], bands: list[list[str]]) -> bool:
    defender = 1 if state.active_player == 2 else 2
    seen: set[str] = set()
    for band in bands:
        if len(band) < 2 or len(set(band)) != len(band):
            return False
        if any(cid not in attackers or cid in seen or cid not in state.cards for cid in band):
            return False
        seen.update(band)
        if sum(not has_keyword(state, cid, "banding") for cid in band) > 1:
            return False
        if len({targets.get(cid, f"player:{defender}") for cid in band}) != 1:
            return False
    return True


def declare_attackers(state: MatchState, attacker_ids: list[str], attack_targets: dict[str, str] | None = None, bands: list[list[str]] | None = None, hybrid_choices: list[str] | None = None) -> None:
    attack_targets = attack_targets or {}
    bands = bands or []
    if not valid_attack_bands(state, attacker_ids, attack_targets, bands):
        raise ValueError("Invalid attacking band")
    legal: list[str] = []
    legal_targets: dict[str, str] = {}
    defender = 1 if state.active_player == 2 else 2
    valid_defenders = _valid_defenders(state, defender)
    requested = list(attacker_ids)

    for cid in requested:
        if cid not in state.cards:
            continue
        card = state.cards[cid]
        if card.controller != state.active_player:
            continue
        if card.zone != Zone.BATTLEFIELD:
            continue
        types = effective_types(state, card)
        if 'Creature' not in types or 'Battle' in types:
            continue
        if card.tapped:
            continue
        if card.summoning_sick and not has_keyword(state, cid, "haste"):
            continue
        if has_keyword(state, cid, "defender"):
            continue
        if card_cant_attack(state, cid):
            continue
        legal.append(cid)
        desired = attack_targets.get(cid, f"player:{defender}")
        if desired not in valid_defenders:
            raise ValueError('Invalid attack destination')
        legal_targets[cid] = desired
    if len(legal) == 1 and card_cant_attack_alone(state, legal[0]):
        lone = legal[0]
        state.log.append(f"{state.cards[lone].name} can't attack alone.")
        legal = []
        legal_targets = {}
    from rules_engine.declaration_limits import attackers_within_limits
    from rules_engine.combat_requirements import best_required_attack, attack_requirement_score
    if not attackers_within_limits(state, legal, legal_targets):
        raise ValueError('Attacker declaration exceeds a static combat limit')
    optimum = best_required_attack(state)
    if optimum and attack_requirement_score(state, legal) < attack_requirement_score(state, optimum[0]):
        completion = best_required_attack(state, legal, legal_targets)
        if completion is None or attack_requirement_score(state, completion[0]) < attack_requirement_score(state, optimum[0]):
            raise ValueError('Attacker declaration must satisfy the maximum possible requirements')
        legal, legal_targets = completion
    from rules_engine.combat_payments import attack_payment_state
    paid = attack_payment_state(state, legal, legal_targets, hybrid_choices)
    if paid is None:
        raise ValueError('Cannot pay the declared attack costs')
    staged_here = not state.trigger_staging
    if paid is not state:
        state.__dict__.update(paid.__dict__)
    if staged_here:
        state.trigger_staging = True
        state.trigger_staging_event = 'declare_attackers'
    # Chosen creatures sacrificed during mana activation never become attackers.
    legal = [cid for cid in legal if state.cards[cid].zone == Zone.BATTLEFIELD
             and state.cards[cid].controller == state.active_player and 'Creature' in effective_types(state, state.cards[cid])]
    legal_targets = {cid: target for cid, target in legal_targets.items() if cid in legal}
    from rules_engine.resource_events import tap_permanents
    tap_permanents(state, [cid for cid in legal if not has_keyword(state, cid, 'vigilance')])
    state.attackers = legal
    state.declared_attackers_this_turn[state.active_player] += len(legal)
    state.attack_bands = [list(band) for band in bands if all(cid in legal for cid in band)]
    state.combat_damage_resolved = False
    state.combat_damage_stage = "none"
    state.first_strike_damage_ids = set()
    state.attack_targets = legal_targets
    state.combat_target_context = {}
    for cid, target in legal_targets.items():
        bind_attack_target(state, cid, target)
    if legal:
        names = ", ".join(
            f"{state.cards[c].name} -> {_defender_label(state, state.attack_targets.get(c, f'player:{defender}'))}"
            for c in legal
        )
        state.log.append(f"Attackers declared: {names}")
        for index, cid in enumerate(legal):
            emit_event(
                state,
                "attack_declared",
                {
                    "card_id": cid,
                    "controller": state.cards[cid].controller,
                    "attack_target": state.attack_targets.get(cid, f"player:{defender}"),
                    "attack_group_first": index == 0,
                },
            )


    if staged_here:
        from rules_engine.events import flush_staged_triggers
        flush_staged_triggers(state)


def declare_blockers(state: MatchState, blocks: dict[str, str | list[str]], hybrid_choices: list[str] | None = None,
                     *, declaration_details: dict | None = None) -> None:
    defender = 1 if state.active_player == 2 else 2
    legal: dict[str, list[str]] = {}
    blocker_assignments: dict[str, int] = {}
    with rule_query_scope(state):
        for attacker, blockers in blocks.items():
            if attacker not in state.attackers:
                continue
            blocker_list = list(dict.fromkeys(blockers)) if isinstance(blockers, list) else [blockers]
            picked: list[str] = []
            for blocker in blocker_list:
                if blocker not in state.cards:
                    continue
                block_card = state.cards[blocker]
                assigned = int(blocker_assignments.get(blocker, 0))
                block_cap = _max_attackers_blockable_by_creature(state, block_card)
                if assigned >= block_cap:
                    continue
                if block_card.zone != Zone.BATTLEFIELD or block_card.controller != defender:
                    continue
                if block_card.tapped:
                    continue
                types = effective_types(state, block_card)
                if 'Creature' not in types or 'Battle' in types:
                    continue
                if card_cant_block(state, blocker):
                    continue
                atk_card = state.cards[attacker]
                if not _can_block_attacker(state, atk_card, block_card):
                    continue
                picked.append(blocker)
                blocker_assignments[blocker] = assigned + 1
            if picked:
                legal[attacker] = picked
        # Menace: must be blocked by two or more creatures.
        for attacker in list(legal.keys()):
            atk_card = state.cards.get(attacker)
            min_blockers = _minimum_blockers_required(state, attacker) if atk_card else 1
            if atk_card and len(legal[attacker]) < min_blockers:
                legal.pop(attacker, None)

    from rules_engine.declaration_limits import blockers_within_limits
    from rules_engine.combat_requirements import best_required_blocks, block_requirement_score
    if not blockers_within_limits(state, legal):
        raise ValueError('Blocker declaration exceeds a static combat limit')
    chosen = {bid for bids in legal.values() for bid in bids}
    optimum = best_required_blocks(state, volunteered=chosen)
    if optimum is not None and block_requirement_score(state, legal) < block_requirement_score(state, optimum):
        completion = best_required_blocks(state, legal)
        if completion is None or block_requirement_score(state, completion) < block_requirement_score(state, optimum):
            raise ValueError('Blocker declaration must satisfy the maximum possible requirements')
        legal = completion
    blocking_ids = {bid for bids in legal.values() for bid in bids}
    if len(blocking_ids) == 1 and card_cant_block_alone(state, next(iter(blocking_ids))):
        legal = {}
    from rules_engine.combat_payments import block_payment_state
    chosen = sorted({bid for bids in legal.values() for bid in bids})
    paid = block_payment_state(state, chosen, hybrid_choices)
    if paid is None:
        raise ValueError('Cannot pay the declared block costs')
    if declaration_details is not None:
        # Direct intent is distinct from post-payment departures and band
        # propagation. AI must resubmit the former, not resolved block pairs.
        declaration_details['direct_blocks'] = {aid: list(ids) for aid, ids in legal.items()}
    if paid is not state:
        state.__dict__.update(paid.__dict__)
    # Eligibility/restrictions were checked before locked costs. Tapping a
    # chosen blocker for mana does not prevent it from becoming a blocker.
    legal = {aid: [bid for bid in bids if state.cards[bid].zone == Zone.BATTLEFIELD
                  and state.cards[bid].controller == defender and 'Creature' in effective_types(state, state.cards[bid])]
             for aid, bids in legal.items()}
    legal = {aid: bids for aid, bids in legal.items() if bids}
    # A legal direct block of one band member blocks every member, regardless
    # of whether the blocker could have blocked those other members directly.
    for band in state.attack_bands:
        members = [cid for cid in band if cid in state.attackers and state.cards[cid].zone == Zone.BATTLEFIELD]
        shared = list(dict.fromkeys(bid for cid in members for bid in legal.get(cid, [])))
        for cid in members:
            if shared:
                legal[cid] = list(shared)
    state.blocks = legal
    from rules_engine.combat_requirements import target_block_requirements, targeted_block_score
    targeted = targeted_block_score(target_block_requirements(state), legal)
    if targeted:
        state.log.append(f'Targeted block requirements satisfied: {targeted}.')
    events = []
    seen_blockers = set()
    for attacker_id, blocker_ids in legal.items():
        for index, blocker_id in enumerate(blocker_ids):
            events.append({
                    "attacker_id": attacker_id,
                    "blocker_id": blocker_id,
                    "controller": state.cards[blocker_id].controller,
                    'attacker_first_block': index == 0,
                    'blocker_first_block': blocker_id not in seen_blockers,
                })
            seen_blockers.add(blocker_id)
    emit_event_batch(state, 'block_declared', events)


def combat_damage(state: MatchState) -> None:
    """Resolve both substeps for direct callers that do not manage priority."""
    if state.combat_damage_resolved:
        return
    if state.combat_damage_stage != "first":
        begin_combat_damage(state)
    if state.combat_damage_stage == "first" and not state.pending_mechanic_choice and not state.pending_replacement_choice and not state.pending_trigger_order:
        finish_combat_damage(state)


def _assigns_damage(state: MatchState, cid: str, first_only: bool) -> bool:
    if 'Creature' not in effective_types(state, cid):
        return False
    return cid in state.first_strike_damage_ids if first_only else cid not in state.first_strike_damage_ids or has_keyword(state, cid, "double strike")


def _assignment_options(state: MatchState, cid: str, first_only: bool) -> list[str]:
    card = state.cards.get(cid)
    if not card or card.zone != Zone.BATTLEFIELD or not _assigns_damage(state, cid, first_only):
        return []
    if cid in state.attackers:
        blockers = [bid for bid in state.blocks.get(cid, []) if bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD]
        defender = 1 if state.active_player == 2 else 2
        target = state.attack_targets.get(cid, f'player:{defender}')
        overflow = bool(target) and has_keyword(state, cid, 'trample')
        if len(blockers) > 1 or (blockers and overflow):
            return blockers + ([target] if overflow else [])
        return []
    attackers = [aid for aid in state.attackers if cid in state.blocks.get(aid, []) and aid in state.cards and state.cards[aid].zone == Zone.BATTLEFIELD]
    return attackers if len(attackers) > 1 else []


def _assignment_controller(state: MatchState, cid: str) -> int:
    source = state.cards[cid]
    if cid in state.attackers:
        blockers = state.blocks.get(cid, [])
        if any(bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD and has_keyword(state, bid, "banding") for bid in blockers):
            return 1 if state.active_player == 2 else 2
    elif any(aid in state.cards and state.cards[aid].zone == Zone.BATTLEFIELD and has_keyword(state, aid, "banding")
             for aid in state.attackers if cid in state.blocks.get(aid, [])):
        return state.active_player
    return source.controller


def _offer_damage_assignment(state: MatchState) -> None:
    source = state.combat_assignment_queue[0]
    card = state.cards[source]
    with rule_query_scope(state):
        chooser = _assignment_controller(state, source)
        options = _assignment_options(state, source, state.combat_damage_stage == "first")
        labels = {cid: state.cards[cid].name if cid in state.cards else _defender_label(state, cid) for cid in options}
        pending = {
            "kind": "combat_damage", "player_id": chooser, "source_id": source,
            "source_name": card.name, "stage": state.combat_damage_stage,
            "options": options, "option_labels": labels,
            "count": max(0, effective_power(state, source)),
            "can_restart": any(_assignment_controller(state, cid) == chooser for cid in state.combat_damage_assignments),
            "label": f"Assign {card.name}'s combat damage",
        }
    state.pending_mechanic_choice = pending
    state.priority_player = state.pending_mechanic_choice["player_id"]
    state.passed_priority = set()


def _resolve_damage_step(state: MatchState) -> None:
    state.trigger_staging = True
    state.trigger_staging_event = "combat_damage_step"
    first_only = state.combat_damage_stage == "first"
    defender = 1 if state.active_player == 2 else 2
    _combat_damage_step(state, defender, state.first_strike_damage_ids, first_strike_only=first_only)
    if not first_only:
        state.combat_damage_resolved = True
    if state.pending_replacement_choice or state.pending_mechanic_choice:
        (state.pending_replacement_choice or state.pending_mechanic_choice)["combat_damage_needs_sba"] = True
        return
    _remove_dead_creatures(state)
    if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
        state.priority_player = state.active_player
        state.passed_priority = set()


def _prepare_damage_step(state: MatchState) -> None:
    state.combat_damage_assignments = {}
    remove_noncreatures_from_combat(state)
    first_only = state.combat_damage_stage == "first"
    # Reuse board queries only while constructing the immutable assignment list.
    with rule_query_scope(state):
        blockers = list(dict.fromkeys(bid for bids in state.blocks.values() for bid in bids))
        sources = list(state.attackers) + blockers
        queue = [
            cid for cid in sources
            if cid in state.cards and _assignment_controller(state, cid) in state.mechanic_choice_players
            and effective_power(state, cid) > 0 and _assignment_options(state, cid, first_only)
        ]
    state.combat_assignment_queue = queue
    if state.combat_assignment_queue:
        _offer_damage_assignment(state)
    else:
        _resolve_damage_step(state)


def _trample_assignments_legal(state: MatchState, assignments: dict[str, dict[str, int]]) -> bool:
    first_only = state.combat_damage_stage == "first"
    assigned_to_blocker: dict[str, int] = {}
    deathtouch_blockers: set[str] = set()
    for attacker in state.attackers:
        if attacker not in state.cards or state.cards[attacker].zone != Zone.BATTLEFIELD or not _assigns_damage(state, attacker, first_only):
            continue
        amounts = assignments.get(attacker)
        if amounts is None:
            blockers = [bid for bid in state.blocks.get(attacker, []) if bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD]
            defender = state.attack_targets.get(attacker, f'player:{3-state.active_player}')
            overflow = bool(defender) and has_keyword(state, attacker, 'trample')
            amounts = {blockers[0]: max(0, effective_power(state, attacker))} if len(blockers) == 1 and not overflow else {}
        for blocker_id in state.blocks.get(attacker, []):
            dealt = amounts.get(blocker_id, 0)
            assigned_to_blocker[blocker_id] = assigned_to_blocker.get(blocker_id, 0) + dealt
            if dealt > 0 and has_keyword(state, attacker, "deathtouch"):
                deathtouch_blockers.add(blocker_id)
    for attacker, amounts in assignments.items():
        if attacker not in state.attackers or not has_keyword(state, attacker, "trample"):
            continue
        blockers = [bid for bid in state.blocks.get(attacker, []) if bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD]
        defender = state.attack_targets.get(attacker, f"player:{2 if state.active_player == 1 else 1}")
        if amounts.get(defender, 0) <= 0:
            continue
        for blocker_id in blockers:
            card = state.cards[blocker_id]
            lethal = max(0, effective_toughness(state, blocker_id) - int(card.counters.get(DMG_MARK_KEY, 0)))
            if blocker_id not in deathtouch_blockers and assigned_to_blocker.get(blocker_id, 0) < lethal:
                return False
    return True


def valid_damage_assignment(state: MatchState, player_id: int, action: dict) -> bool:
    pending = state.pending_mechanic_choice
    if not pending or pending.get("kind") != "combat_damage" or pending.get("player_id") != player_id:
        return False
    if state.step != Step.COMBAT_DAMAGE or state.combat_damage_stage != pending.get("stage"):
        return False
    if action.get("choice_id") == "restart":
        return bool(pending.get("can_restart")) and action.get("damage_assignment") is None
    amounts = action.get("damage_assignment")
    source = pending.get("source_id")
    if source not in state.cards or state.cards[source].zone != Zone.BATTLEFIELD:
        return False
    options = _assignment_options(state, source, state.combat_damage_stage == "first")
    if not isinstance(amounts, dict) or set(amounts) != set(options):
        return False
    if any(type(amount) is not int or amount < 0 for amount in amounts.values()):
        return False
    power = max(0, effective_power(state, source))
    if sum(amounts.values()) != power or power != pending.get("count"):
        return False
    if source in state.attackers and not any(cid in state.attackers for cid in state.combat_assignment_queue[1:]):
        projected = {**state.combat_damage_assignments, source: amounts}
        if not _trample_assignments_legal(state, projected):
            return False
    return True


def finish_damage_assignment(state: MatchState, player_id: int, action: dict) -> bool:
    if not valid_damage_assignment(state, player_id, action):
        return False
    if action.get("choice_id") == "restart":
        state.combat_damage_assignments = {
            cid: amounts for cid, amounts in state.combat_damage_assignments.items()
            if _assignment_controller(state, cid) != player_id
        }
        blockers = list(dict.fromkeys(bid for bids in state.blocks.values() for bid in bids))
        first_only = state.combat_damage_stage == "first"
        state.combat_assignment_queue = [
            cid for cid in list(state.attackers) + blockers
            if cid in state.cards and cid not in state.combat_damage_assignments
            and _assignment_controller(state, cid) in state.mechanic_choice_players
            and effective_power(state, cid) > 0 and _assignment_options(state, cid, first_only)
        ]
        _offer_damage_assignment(state)
        return True
    amounts = action["damage_assignment"]
    source = state.pending_mechanic_choice["source_id"]
    state.combat_damage_assignments[source] = dict(amounts)
    state.combat_assignment_queue.pop(0)
    state.pending_mechanic_choice = None
    if state.combat_assignment_queue:
        _offer_damage_assignment(state)
    else:
        _resolve_damage_step(state)
    return True


def begin_combat_damage(state: MatchState) -> None:
    if state.combat_damage_stage != "none" or state.combat_damage_resolved:
        return
    combatants = set(state.attackers)
    combatants.update(blocker for blockers in state.blocks.values() for blocker in blockers)
    with rule_query_scope(state):
        first_ids = {
            cid for cid in combatants
            if cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
            and (has_keyword(state, cid, "first strike") or has_keyword(state, cid, "double strike"))
        }
    state.first_strike_damage_ids = first_ids
    if first_ids:
        state.combat_damage_stage = "first"
    else:
        state.combat_damage_stage = "regular"
    _prepare_damage_step(state)


def finish_combat_damage(state: MatchState) -> None:
    if state.combat_damage_stage != "first" or state.combat_damage_resolved:
        return
    state.combat_damage_stage = "regular"
    _prepare_damage_step(state)


def _combat_damage_step(state: MatchState, default_defender: int, first_ids: set[str], first_strike_only: bool) -> None:
    from rules_engine.damage_results import collect_damage_counters, flush_damage_counters
    from effects.registry import resolve_effect
    from rules_engine.named_counters import shield_damage_event

    with collect_damage_counters(state) as packets, shield_damage_event(state):
        damage_events, gain_effects = _combat_damage_results(state, default_defender, first_ids, first_strike_only)
    flush_damage_counters(state, packets)
    pending = state.pending_replacement_choice or state.pending_mechanic_choice
    if pending:
        pending.setdefault('continuation_effects', []).extend([
            {'effect_key': 'emit_combat_damage_events', 'payload': {'events': damage_events}},
            *gain_effects,
        ])
    else:
        emit_event_batch(state, 'combat_damage_dealt', damage_events)
        if gain_effects:
            resolve_effect(state, state.active_player, 'effect_sequence', {'effects': gain_effects})


def _combat_damage_results(state: MatchState, default_defender: int, first_ids: set[str], first_strike_only: bool):
    def assigns_damage(cid: str) -> bool:
        return _assigns_damage(state, cid, first_strike_only)

    damage_events: list[dict] = []
    lifelink_gains: dict[str, tuple[int, int]] = {}

    def record_lifelink(source_id: str, controller: int, amount: int) -> None:
        if amount <= 0 or not has_keyword(state, source_id, "lifelink"):
            return
        previous = lifelink_gains.get(source_id, (controller, 0))[1]
        lifelink_gains[source_id] = (controller, previous + amount)

    def record_destination(source_id: str, target: str, amount: int) -> None:
        kind, identity = target.split(':', 1)
        event = {'source_card_id': source_id, 'target_key': target, 'amount': amount,
                 'target_player': int(identity) if kind == 'player' else None}
        if kind != 'player':
            event['target_card_id'] = identity
        damage_events.append(event)
    reconcile_combat_targets(state)
    # All sources assign damage from the same pre-damage game state.
    with rule_query_scope(state):
        attacker_power = {
            cid: max(0, effective_power(state, cid))
            for cid in state.attackers
            if cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
        }
        blocker_damage_remaining = {
            cid: max(0, effective_power(state, cid))
            for blockers in state.blocks.values() for cid in blockers
            if cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
        }
    for attacker in list(state.attackers):
        if attacker not in state.cards:
            continue
        atk = state.cards[attacker]
        if atk.zone != Zone.BATTLEFIELD:
            continue

        blocks = [b for b in state.blocks.get(attacker, []) if b in state.cards and state.cards[b].zone == Zone.BATTLEFIELD]
        defender_key = state.attack_targets.get(attacker, f"player:{default_defender}")
        can_trample = bool(defender_key) and has_keyword(state, attacker, 'trample')
        if not blocks:
            if not assigns_damage(attacker):
                continue
            # A blocked creature stays blocked when its blockers leave combat.
            if attacker in state.blocks and not has_keyword(state, attacker, "trample"):
                continue
            dealt = _deal_unblocked_damage(state, defender_key, attacker_power[attacker], source_id=attacker)
            record_lifelink(attacker, atk.controller, dealt)
            if dealt > 0:
                record_destination(attacker, defender_key, dealt)
            continue

        if assigns_damage(attacker):
            remaining = attacker_power[attacker]
            atk_has_deathtouch = has_keyword(state, attacker, "deathtouch")
            allocation = state.combat_damage_assignments.get(attacker)
            if allocation is None:
                allocation = {}
                for blocker_id in blocks:
                    lethal = _remaining_lethal_damage(state, blocker_id)
                    dealt = min(remaining, min(1, lethal) if atk_has_deathtouch else lethal)
                    allocation[blocker_id] = dealt
                    remaining -= dealt
                if can_trample:
                    allocation[defender_key] = remaining
                elif blocks and remaining > 0:
                    allocation[blocks[0]] += remaining
            for blocker_id in blocks:
                dealt = allocation.get(blocker_id, 0)
                if dealt <= 0 or _damage_prevented_by_protection(state, attacker, blocker_id):
                    continue
                actual = _mark_creature_damage(state, blocker_id, dealt, deathtouch=atk_has_deathtouch, source_id=attacker)
                record_lifelink(attacker, atk.controller, actual)
                if actual > 0:
                    damage_events.append({"source_card_id": attacker, "target_card_id": blocker_id, "amount": actual})
            if can_trample and allocation.get(defender_key, 0) > 0:
                dealt = _deal_unblocked_damage(state, defender_key, allocation[defender_key], source_id=attacker)
                record_lifelink(attacker, atk.controller, dealt)
                if dealt > 0:
                    record_destination(attacker, defender_key, dealt)

        for blocker_id in blocks:
            blk = state.cards[blocker_id]
            if not assigns_damage(blocker_id):
                continue
            assigned = state.combat_damage_assignments.get(blocker_id)
            blk_power = assigned.get(attacker, 0) if assigned is not None else blocker_damage_remaining.get(blocker_id, 0)
            blocker_damage_remaining[blocker_id] = max(0, blocker_damage_remaining.get(blocker_id, 0) - blk_power)
            if blk_power <= 0:
                continue
            if _damage_prevented_by_protection(state, blocker_id, attacker):
                continue
            actual = _mark_creature_damage(state, attacker, blk_power, deathtouch=has_keyword(state, blocker_id, "deathtouch"), source_id=blocker_id)
            record_lifelink(blocker_id, blk.controller, actual)
            if actual > 0:
                damage_events.append({"source_card_id": blocker_id, "target_card_id": attacker, "amount": actual})
    gain_effects = []
    for source_id, (controller, amount) in lifelink_gains.items():
        gain_effects.append({"effect_key": "gain_life", "payload": {
            "target_player": controller, "amount": amount, "__source_card_id": source_id,
        }})
    return damage_events, gain_effects


def _remove_dead_creatures(state: MatchState) -> None:
    from rules_engine.state_based_actions import apply_state_based_actions

    apply_state_based_actions(state)


def resume_combat_die_replacement(state: MatchState, card_id: str, replacement_source_id: str) -> None:
    """Resume a combat death after a human replacement choice."""
    card = state.cards.get(card_id)
    if not card or card.zone != Zone.BATTLEFIELD:
        return
    battlefield_owner = state.players[card.controller]
    zone_owner = state.players[getattr(card, "owner", card.controller)]
    if card_id not in battlefield_owner.battlefield:
        return
    emit_event(state, "leaves_battlefield", {"card_id": card_id, "controller": card.controller})
    battlefield_owner.battlefield.remove(card_id)
    destination = replace_die_zone(state, card.controller, card_id, replacement_source_id)
    if destination == "exile":
        zone_owner.exile.append(card_id)
        card.move_to_zone(Zone.EXILE)
        state.log.append(f"{card.name} is exiled instead of dying in combat.")
        return
    zone_owner.graveyard.append(card_id)
    card.zone = Zone.GRAVEYARD
    state.log.append(f"{card.name} dies in combat.")
    emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
    emit_event(state, "creature_dies", {"card_id": card_id, "controller": card.controller})


def _can_block_attacker(state: MatchState, attacker, blocker) -> bool:
    if 'Battle' in effective_types(state, blocker):
        return False
    from rules_engine.combat_constraints import combat_rule_text
    attacker_text = combat_rule_text(state, attacker.id)
    blocker_text = combat_rule_text(state, blocker.id)
    if any(re.fullmatch(r"(?:can't|cannot) be blocked", line) for line in attacker_text.splitlines()):
        return False
    for line in attacker_text.splitlines():
        power_limit = re.fullmatch(r"(?:can't|cannot) be blocked by creatures with power (\d+) or (less|greater)", line)
        if power_limit:
            power = effective_power(state, blocker.id)
            if power_limit[2] == 'less' and power <= int(power_limit[1]) or power_limit[2] == 'greater' and power >= int(power_limit[1]):
                return False
    if re.search(r"(?:can't|cannot) block artifact creatures", blocker_text) and 'Artifact' in effective_types(state, attacker):
        return False
    only_keyword = BLOCK_ONLY_KEYWORD_RE.search(blocker_text)
    if only_keyword:
        required = only_keyword.group(1).strip().lower()
        if required in KNOWN_KEYWORDS and not has_keyword(state, attacker.id, required):
            return False
    # Flying can only be blocked by flying or reach.
    if has_keyword(state, attacker.id, "flying"):
        if not (has_keyword(state, blocker.id, "flying") or has_keyword(state, blocker.id, "reach")):
            return False
    # Shadow creatures can only block or be blocked by other shadow creatures.
    attacker_has_shadow = has_keyword(state, attacker.id, "shadow")
    blocker_has_shadow = has_keyword(state, blocker.id, "shadow")
    if attacker_has_shadow != blocker_has_shadow:
        return False
    # Fear: blocked only by artifact creatures and/or black creatures.
    if has_keyword(state, attacker.id, "fear"):
        blocker_colors = card_color_names(state.cards.get(blocker.id))
        if "Artifact" not in (effective_types(state, blocker) or []) and "black" not in blocker_colors:
            return False
    # Intimidate: blocked only by artifact creatures and/or creatures sharing a color.
    if has_keyword(state, attacker.id, "intimidate"):
        blocker_colors = card_color_names(state.cards.get(blocker.id))
        attacker_colors = card_color_names(state.cards.get(attacker.id))
        shares_color = bool(attacker_colors & blocker_colors)
        if "Artifact" not in (effective_types(state, blocker) or []) and not shares_color:
            return False
    # Landwalk: unblockable if defending player controls relevant land type.
    if _attacker_has_active_landwalk_with_state(state, attacker, blocker.controller):
        return False
    # Protection prevents blocking from protected qualities.
    if protected_from_source(state, attacker.id, blocker):
        return False
    return True


def _damage_prevented_by_protection(state: MatchState, source_id: str, target_id: str) -> bool:
    if damage_cant_be_prevented(state, source_card_id=source_id, target_card_id=target_id, combat=True):
        return False
    source = state.cards[source_id]
    return protected_from_source(state, target_id, source)


def _minimum_blockers_required(state: MatchState, attacker_id: str) -> int:
    attacker = state.cards[attacker_id]
    min_blockers = 2 if has_keyword(state, attacker_id, "menace") else 1
    if has_keyword(state, attacker_id, "menace"):
        min_blockers = max(min_blockers, 2)
    from rules_engine.combat_constraints import combat_rule_text
    text = combat_rule_text(state, attacker_id)
    from rules_engine.combat_constraints import number
    for token in re.findall(r"(?:can't|cannot) be blocked except by (\w+) or more creatures", text):
        min_blockers = max(min_blockers, number(token) or 1)
    return min_blockers


def _max_attackers_blockable_by_creature(state, blocker) -> int | float:
    from rules_engine.combat_constraints import combat_rule_text
    text = combat_rule_text(state, blocker.id)
    if "can block any number of creatures" in text:
        return float('inf')
    extra = text.splitlines().count("can block an additional creature each combat")
    from rules_engine.combat_constraints import number
    extra += sum(number(token) or 0 for token in re.findall(r"can block (\w+) additional creatures each combat", text))
    return 1 + extra


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _attacker_has_active_landwalk_with_state(state: MatchState, attacker, defending_player_id: int) -> bool:
    walks = [
        "islandwalk", "swampwalk", "mountainwalk", "forestwalk", "plainswalk",
        "nonbasic landwalk", "snow landwalk", "desertwalk", "wasteswalk", "legendary landwalk",
    ]
    active_walks = [w for w in walks if has_keyword(state, attacker.id, w)]
    if not active_walks:
        return False
    defender_bf = state.players[defending_player_id].battlefield
    for cid in defender_bf:
        card = state.cards[cid]
        if 'Land' not in effective_types(state, card):
            continue
        from rules_engine.land_types import effective_type_line, has_land_type
        tl = effective_type_line(state, card).lower()
        for walk in active_walks:
            if walk == "nonbasic landwalk" and "land" in tl and "basic" not in tl:
                return True
            if walk == "snow landwalk" and "snow" in tl and "land" in tl:
                return True
            if walk == "legendary landwalk" and "legendary" in tl and "land" in tl:
                return True
            subtype = walk.replace(" landwalk", "").replace("walk", "")
            if has_land_type(state, card, subtype):
                return True
    return False


def _defender_keys(state: MatchState, defending_player: int) -> list[str]:
    planeswalkers = []
    battles = []
    with rule_query_scope(state):
        for controller, player in state.players.items():
            for cid in player.battlefield:
                card = state.cards.get(cid)
                if card is None or card.zone != Zone.BATTLEFIELD or card.controller != controller:
                    continue
                types = effective_types(state, card)
                is_battle = 'Battle' in types
                protected = type(card.battle_protector) is int and card.battle_protector == defending_player
                if is_battle and protected:
                    battles.append('battle:' + cid)
                if controller == defending_player and 'Planeswalker' in types and (not is_battle or protected):
                    planeswalkers.append('planeswalker:' + cid)
    return [f'player:{defending_player}', *planeswalkers, *battles]


def _valid_defenders(state: MatchState, defending_player: int) -> set[str]:
    return set(_defender_keys(state, defending_player))


def _defender_label(state: MatchState, key: str) -> str:
    if key.startswith(("planeswalker:", 'battle:')):
        cid = key.split(":", 1)[1]
        card = state.cards.get(cid)
        if card:
            return card.name
    if key.startswith("player:"):
        pid = int(key.split(":", 1)[1])
        return state.players[pid].name
    return key


def _deal_unblocked_damage(state: MatchState, defender_key: str, amount: int, source_id: str | None = None) -> int:
    if amount <= 0:
        return 0
    if defender_key.startswith(("planeswalker:", 'battle:')):
        cid = defender_key.split(":", 1)[1]
        card = state.cards.get(cid)
        kind = 'Battle' if defender_key.startswith('battle:') else 'Planeswalker'
        if card and kind in effective_types(state, card) and card.zone == Zone.BATTLEFIELD:
            prevention_locked = damage_cant_be_prevented(state, source_card_id=source_id,
                                                        target_card_id=cid, combat=True)
            if not prevention_locked and source_id is not None and source_id in state.cards and _damage_prevented_by_protection(state, source_id, cid):
                state.log.append(f"{card.name} prevents {amount} damage.")
                return 0
            amount = apply_permanent_damage_replacements(state, cid, amount, prevention_locked=prevention_locked)
            if not prevention_locked:
                amount, _ = consume_card_prevention_shield(card, amount, state=state)
            from rules_engine.damage_results import apply_permanent_damage
            apply_permanent_damage(state, cid, amount, source_id)
            return amount
        # PW left battlefield — damage disappears, does NOT redirect to player
        return 0
    if not defender_key.startswith('player:'):
        return 0
    raw_player = defender_key.split(':', 1)[1]
    if raw_player not in {'1', '2'}:
        return 0
    pid = int(raw_player)
    prevention_locked = source_id is not None and source_id in state.cards and damage_cant_be_prevented(
        state,
        source_card_id=source_id,
        target_player=pid,
        combat=True,
    )
    amount = apply_damage_replacements(state, pid, amount, prevention_locked=prevention_locked,
                                       source_card_id=source_id)
    post, prevented = (amount, 0) if prevention_locked else consume_player_prevention_shield(state, pid, amount)
    if prevented > 0:
        state.log.append(f"{state.players[pid].name} prevents {prevented} damage.")
    if post <= 0:
        return 0
    from rules_engine.damage_results import apply_player_damage
    apply_player_damage(state, pid, post, source_id, combat=True)
    return post


def _mark_creature_damage(
    state: MatchState,
    card_id: str,
    amount: int,
    deathtouch: bool = False,
    source_id: str | None = None,
) -> int:
    if amount <= 0:
        return 0
    card = state.cards[card_id]
    prevention_locked = source_id is not None and source_id in state.cards and damage_cant_be_prevented(
        state,
        source_card_id=source_id,
        target_card_id=card_id,
        combat=True,
    )
    amount = apply_permanent_damage_replacements(state, card_id, amount, prevention_locked=prevention_locked)
    post, prevented = (amount, 0) if prevention_locked else consume_card_prevention_shield(card, amount, state=state)
    if prevented > 0:
        state.log.append(f"{card.name} prevents {prevented} damage.")
    if post <= 0:
        return 0
    from rules_engine.damage_results import apply_permanent_damage
    apply_permanent_damage(state, card_id, int(post), source_id)
    if deathtouch:
        card.counters[DEATHTOUCH_MARK_KEY] = 1
    return int(post)


def _remaining_lethal_damage(state: MatchState, card_id: str) -> int:
    card = state.cards[card_id]
    toughness = effective_toughness(state, card_id)
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    return max(0, toughness - marked)
