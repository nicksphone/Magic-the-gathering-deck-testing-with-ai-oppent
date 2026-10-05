"""Project declared actions and stack effects without guessing opponents."""
from __future__ import annotations
from rules_engine.type_effects import effective_types

from copy import copy, deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import json
import pickle
import re

from game_state.state import CardInstance, MatchState, Zone
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.oracle_text import without_reminder_text
from rules_engine.continuous import effective_combat_stats, has_keyword


SECONDARY_EFFECT_RE = re.compile(
    r"\b(draw|gain|gains|lose|loses|create|scry|surveil|discard|mill|search|deals?|cast|play|put|add|untap|sacrifice)\b", re.I,
)

_decision_projection = ContextVar("ai_decision_projection", default=None)
_immutable_card_types = frozenset((str, int, float, bool, type(None), Zone))
POSITION_SCORE_CACHE_BYTES = 16 * 1024 * 1024
POSITION_SCORE_CACHE_ENTRIES = 256


def reuse_position_score(state, player_id, owner, compute):
    """Reuse exact states only within one synchronous, fixed-profile decision."""
    scope = _decision_projection.get()
    if scope is None:
        return compute()
    cache = scope[2].setdefault('position_scores', {'values': {}, 'bytes': 0, 'owners': {}})
    try:
        # Include every gameplay/AI field, including RNG and opaque information.
        # planning_copy excludes only diagnostic history unused by search.
        encoded = pickle.dumps(planning_copy(state), protocol=5)
    except (pickle.PicklingError, TypeError, AttributeError):
        return compute()
    key = (id(owner), player_id, encoded)
    if key in cache['values']:
        return cache['values'][key]
    result = compute()
    if (len(cache['values']) < POSITION_SCORE_CACHE_ENTRIES
            and cache['bytes'] + len(encoded) <= POSITION_SCORE_CACHE_BYTES):
        cache['values'][key] = result
        cache['bytes'] += len(encoded)
        cache['owners'][id(owner)] = owner
    return result


@contextmanager
def decision_projection_scope(state, player_id):
    """Memoize only the immutable root of one synchronous AI decision."""
    token = _decision_projection.set((state, player_id, {}))
    try:
        from rules_engine.query_context import rule_query_scope
        with rule_query_scope(state):
            yield
    finally:
        _decision_projection.reset(token)


def planning_copy(state, *, memo=None):
    """Copy all gameplay state, but not diagnostic history unused by search."""
    log = getattr(state, "log", None)
    memo = {} if memo is None else dict(memo)
    if isinstance(log, list):
        memo.setdefault(id(log), [])
    # Avoid deepcopy's reconstruction/dispatch overhead for every immutable
    # scalar of every card. Mutable metadata still shares one deepcopy memo.
    cards = [card for card in getattr(state, "cards", {}).values()
             if type(card) is CardInstance and id(card) not in memo]
    for card in cards:
        memo[id(card)] = object.__new__(CardInstance)
        memo[id(card.__dict__)] = {}
        memo[id(card)].__dict__ = memo[id(card.__dict__)]
    for card in cards:
        memo[id(card)].__dict__.update({
            key: value if type(value) in _immutable_card_types
            else _copy_card_field(value, memo)
            for key, value in card.__dict__.items()
        })
    return deepcopy(state, memo)


def _copy_card_field(value, memo):
    """Copy common flat containers without deepcopy's per-scalar dispatch."""
    if id(value) in memo:
        return memo[id(value)]
    kind = type(value)
    if ((kind in (list, dict, set) and not value)
            or (kind in (list, set) and all(type(item) in _immutable_card_types for item in value))
            or (kind is dict and all(type(key) in _immutable_card_types and type(item) in _immutable_card_types
                                     for key, item in value.items()))):
        result = value.copy()
        memo[id(value)] = result
        return result
    return deepcopy(value, memo)


def prospective_creature_stats(state, card, player_id):
    """Evaluate static entry stats, not costs, entry choices or responses."""
    if not isinstance(card, CardInstance) or not isinstance(state, MatchState):
        return getattr(card, "power", None), getattr(card, "toughness", None)
    if card.zone == Zone.BATTLEFIELD and card is state.cards.get(card.id):
        return effective_combat_stats(state, card.id)
    context = _decision_projection.get()
    key = ("entry_stats", id(card), player_id)
    cache = context[2] if context and context[0] is state else None
    if cache is not None and key in cache:
        return cache[key][1]
    projected = planning_copy(state)
    entrant = deepcopy(card)
    entrant.move_to_zone(Zone.BATTLEFIELD)
    entrant.controller = player_id
    projected.cards[entrant.id] = entrant
    for player in projected.players.values():
        for zone in (Zone.HAND, Zone.LIBRARY, Zone.GRAVEYARD, Zone.EXILE, Zone.BATTLEFIELD):
            cards = getattr(player, zone.value)
            cards[:] = [cid for cid in cards if cid != entrant.id]
    projected.players[player_id].battlefield.append(entrant.id)
    result = effective_combat_stats(projected, entrant.id)
    if cache is not None:
        # Retain the proxy so its identity cannot be reused within this decision.
        cache[key] = (card, result)
    return result


def negative_pt_would_be_lethal(state, card_id, power, toughness):
    """Project one public target through actual stat layers, without departures."""
    from effects.registry import resolve_effect
    from rules_engine.state_based_actions import creature_has_lethal_state
    projected = copy(state)
    target = copy(state.cards[card_id])
    target.counters = dict(target.counters)
    projected.cards = {**state.cards, card_id: target}
    projected.log = []
    resolve_effect(projected, target.controller, 'temporary_pt_buff', {
        'target_card_id':card_id,'power':power,'toughness':toughness})
    return creature_has_lethal_state(projected, card_id)


def keyword_target_value(state, card, player_id, targets):
    """Rank known keyword instructions only, without executing later draws."""
    text = (card.oracle_text or '').lower()
    if 'until end of turn' not in text or not re.search(r'\b(?:gains|loses|lose)\b', text):
        return None
    key, payload = infer_effect_from_oracle(state,card,player_id,targets,report_unsupported=False)
    effects = payload.get('effects',[]) if key == 'effect_sequence' else [{'effect_key':key,'payload':payload}]
    if not effects or any(effect['effect_key'] not in {'grant_keyword','temporary_ability_loss','draw_cards'} for effect in effects):
        return None
    changes = [effect for effect in effects if effect['effect_key'] in {'grant_keyword','temporary_ability_loss'}
               and effect['payload'].get('target_card_id') == targets.get('target_card_id')]
    if not changes:
        return None
    from effects.registry import resolve_effect
    from ai.heuristics import evaluate_board
    projected = planning_copy(state)
    for effect in changes:
        resolve_effect(projected,player_id,effect['effect_key'],effect['payload'])
    return evaluate_board(projected,player_id) - evaluate_board(state,player_id)


def unproductive_destroy_targets(state: MatchState, card, player_id: int, targets: dict, *, ability_text: str | None = None,
                                action: dict | None = None, own_choice_action=None, candidates=None) -> set[str]:
    """Conserve pure destruction against indestructible or friendly targets."""
    if ability_text is None and not set(effective_types(state, card)).intersection({"Instant", "Sorcery"}):
        return set()
    text = ability_text or "\n".join(targets.get("mode_texts") or []) or targets.get("mode_text") or card.oracle_text
    text = without_reminder_text(text).strip()
    if SECONDARY_EFFECT_RE.search(text):
        return set()
    proxy = copy(card)
    proxy.oracle_text = text
    if ability_text is not None:
        proxy.types = []
        proxy.card_faces = []
    key, payload = infer_effect_from_oracle(state, proxy, player_id, targets, report_unsupported=False)
    conditional = payload if key == 'conditional_instruction' and payload['effect_key'] == 'destroy_permanent' else None
    if conditional is not None:
        key = conditional['effect_key']
    if key != "destroy_permanent":
        return set()
    excluded = set()
    for player in state.players.values():
        for cid in player.battlefield:
            if candidates is not None and cid not in candidates:
                continue
            if conditional is not None:
                from rules_engine.conditional_instructions import selected_instruction
                if selected_instruction(state, player_id, {**conditional, 'target_card_id': cid})[0] == 'noop':
                    excluded.add(cid)
                    continue
            friendly = state.cards[cid].controller == player_id
            if not friendly and not has_keyword(state, cid, 'indestructible'):
                continue
            if friendly and action is not None:
                profitable = friendly_destruction_profit(state, player_id,
                    {**action, 'targets': {**targets, 'target_card_id': cid}}, own_choice_action=own_choice_action)
                if profitable is not False:
                    continue
            excluded.add(cid)
    return excluded


def friendly_destruction_profit(state, player_id, action, *, own_choice_action=None):
    """Known resolved utility; incomplete/private continuations remain unknown."""
    return _choice_free_projection(state, player_id, 'friendly_destruction', action,
        lambda policy: _friendly_destruction_profit(state, player_id, action, own_choice_action=policy),
        own_choice_action)


def _choice_free_projection(state, player_id, kind, action, compute, policy):
    scope = _decision_projection.get()
    if scope is None or scope[0] is not state or scope[1] != player_id:
        return compute(policy)

    def key():
        try:
            # Bytes remain private in this short-lived scope; never unpickle input.
            # Include RNG, object incarnations, aliases and extra gameplay fields.
            return (pickle.dumps(state, protocol=5),
                    (kind, policy is None,
                     json.dumps(action, sort_keys=True, separators=(',', ':'), allow_nan=False)))
        except (pickle.PicklingError, TypeError, ValueError, AttributeError, RecursionError):
            return None

    announced = key()
    if announced is None:
        return compute(policy)
    memo = scope[2].get('choice_free_outcomes')
    if memo is None or memo[0] != announced[0]:
        # One shared snapshot, not a complete board copy for every target.
        memo = (announced[0], {})
        scope[2]['choice_free_outcomes'] = memo
    if announced[1] in memo[1]:
        return memo[1][announced[1]]
    choice_used = False

    def choice(*args):
        nonlocal choice_used
        choice_used = True
        return policy(*args)

    result = compute(choice if policy is not None else None)
    # A skipped callback must not erase mutable agent/closure side effects.
    if (not choice_used and key() == announced
            and scope[2].get('choice_free_outcomes') is memo):
        memo[1][announced[1]] = result
    return result


def _friendly_destruction_profit(state, player_id, action, *, own_choice_action=None):
    from ai.heuristics import evaluate_board
    from rules_engine.action_validation import ActionRejected, checked_action
    projected = _projection_copy(state)
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    opposing_hand = tuple(state.players[3-player_id].hand)
    try:
        projected = checked_action(projected, RulesEngine(), player_id, action)
    except ActionRejected:
        return False
    if not _settle_announced_stack(projected, player_id=player_id, own_choice_action=own_choice_action):
        return None
    if projected.winner is not None:
        return projected.winner == player_id
    if (any(tuple(player.library) != libraries[pid] for pid, player in projected.players.items())
            or tuple(projected.players[3-player_id].hand) != opposing_hand):
        return None
    status, winner, value = _choice_free_projection(state, player_id, 'destruction_baseline', None,
        lambda policy: _destruction_baseline(state, player_id, policy), own_choice_action)
    if status == 'unknown':
        return None
    if winner is not None:
        return winner != player_id
    return evaluate_board(projected, player_id) > value


def _destruction_baseline(state, player_id, policy):
    from ai.heuristics import evaluate_board
    baseline = _projection_copy(state)
    if not _settle_announced_stack(baseline, player_id=player_id, own_choice_action=policy):
        return ('unknown', None, None)
    if baseline.winner is not None:
        return ('known', baseline.winner, None)
    if (any(tuple(player.library) != tuple(state.players[pid].library)
            for pid, player in baseline.players.items())
            or tuple(baseline.players[3-player_id].hand) != tuple(state.players[3-player_id].hand)):
        return ('unknown', None, None)
    return ('known', None, evaluate_board(baseline, player_id))


def pending_counter_gain(state, player_id, stack_id):
    """Public unanswered prevention value, not a prediction of opponent responses."""
    return _choice_free_projection(state, player_id, 'pending_counter', stack_id,
                                  lambda _policy: _pending_counter_gain(state, player_id, stack_id), None)


def _pending_counter_gain(state, player_id, stack_id):
    from ai.heuristics import evaluate_board
    from effects.registry import resolve_effect
    from rules_engine.targeting import spell_cant_be_countered, stack_object_kind
    item = next((item for item in state.stack if item.id == stack_id), None)
    if item is None or (stack_object_kind(state, item) == 'spell' and spell_cant_be_countered(state, item)):
        return 0.0
    status, winner, value = _choice_free_projection(state, player_id, 'destruction_baseline', None,
        lambda policy: _destruction_baseline(state, player_id, policy), None)
    if status == 'unknown':
        return None
    projected = _projection_copy(state)
    counter = 'counter_spell' if stack_object_kind(state, item) == 'spell' else 'counter_ability'
    resolve_effect(projected, player_id, counter, {'target_stack_id': stack_id, 'target_kind': 'any'})
    if not _settle_announced_stack(projected):
        return None
    if (any(tuple(player.library) != tuple(state.players[pid].library)
            for pid, player in projected.players.items())
            or tuple(projected.players[3-player_id].hand) != tuple(state.players[3-player_id].hand)):
        return None
    if winner is not None or projected.winner is not None:
        outcome = lambda winning: 1000 if winning == player_id else -1000 if winning is not None else 0
        return float(outcome(projected.winner) - outcome(winner))
    return evaluate_board(projected, player_id) - value


def _projection_copy(state: MatchState) -> MatchState:
    # Resolution does not read historical logs; avoid copying growing traces.
    projected = planning_copy(state)
    projected.mechanic_choice_players = {1, 2}
    projected.replacement_choice_players = {1, 2}
    projected.trigger_order_choice_players = {1, 2}
    projected.trigger_order_choice_required = True
    return projected


def _opaque_selection_choice(projected):
    from ai.information import is_unknown
    choice = projected.pending_mechanic_choice or {}
    if choice.get('kind') not in {'look_top_select_hand', 'topdeck_bottom_order'}:
        return None
    options = choice.get('options', [])
    chooser = choice.get('player_id')
    if chooser not in projected.players or any(
            cid not in projected.players[chooser].library or not is_unknown(projected.cards.get(cid))
            for cid in options):
        return None
    count = choice.get('count', 0)
    if not isinstance(count, int) or not 0 <= count <= len(options):
        return None
    # Opaque alternatives have equal count value, never fabricated identities.
    return {'type': 'choose_mechanic', 'card_ids': list(options[:count])}


def _settle_announced_stack(projected: MatchState, *, player_id: int | None = None,
                           own_choice_action=None, opaque_hand_choices=False) -> bool:
    rules = RulesEngine()
    # ponytail: bounded projection; unknown choices/loops keep backup options.
    for _ in range(128):
        choice = projected.pending_mechanic_choice or projected.pending_replacement_choice or projected.pending_trigger_order
        if choice:
            chooser = choice.get("player_id", choice.get("current_controller"))
            action = _opaque_selection_choice(projected) if opaque_hand_choices else None
            if action is None:
                if own_choice_action is None or chooser != player_id:
                    return False
                action = own_choice_action(projected, rules.legal_moves(projected, player_id), player_id)
            if action.get("type") == "pass_priority":
                return False
            rules.take_action(projected, chooser, action, reject_invalid=True)
            continue
        if projected.winner is not None or not projected.stack:
            return True
        rules.take_action(projected, projected.priority_player, {"type": "pass_priority"}, reject_invalid=True)
    return False


def unanswered_action_wins(state: MatchState, player_id: int, action: dict, *, own_choice_action=None) -> bool | None:
    """Evaluate a legal announced line, never optimize from hidden-zone changes."""
    outcome = _unanswered_action_outcome(state, player_id, action, own_choice_action=own_choice_action)
    return None if outcome is None else outcome == "win"


def _opaque_draw_count_changes(state, projected, player_id):
    from ai.information import is_unknown
    if getattr(state, 'ai_information_player', None) != player_id:
        return False
    # Only guaranteed unfiltered hand acquisition, not search or filtered reveals.
    acquisitions = {'draw_cards', 'look_top_select_hand'}
    if (not any(item.effect_key in acquisitions for item in state.stack)
            or any(item.effect_key not in acquisitions | {'counter_spell', 'counter_ability'}
                   for item in state.stack)):
        return False
    may_reorder = any(item.effect_key == 'look_top_select_hand' for item in state.stack)
    for pid, original in state.players.items():
        final = projected.players[pid]
        removed = set(original.library) - set(final.library)
        retained = [cid for cid in original.library if cid not in removed]
        if (final.library != retained and (not may_reorder or len(final.library) != len(retained)
                or set(final.library) != set(retained)
                or any(not is_unknown(state.cards[cid]) or not is_unknown(projected.cards[cid])
                       for cid in original.library))):
            return False
        if final.hand[:len(original.hand)] != original.hand:
            return False
        added = final.hand[len(original.hand):]
        if len(added) != len(removed) or set(added) != removed:
            return False
        if any(not is_unknown(state.cards[cid]) or not is_unknown(projected.cards[cid]) for cid in removed):
            return False
    return True


def settled_public_position(state: MatchState, player_id: int, *, opaque_draw_counts=False) -> MatchState | None:
    """Forecast declared effects; opt-in opaque hand counts never reveal identities."""
    if not state.stack:
        return state
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    opponent = 3 - player_id
    opposing_hand = tuple(state.players[opponent].hand)
    projected = _projection_copy(state)
    opaque_selection = (opaque_draw_counts and getattr(state, 'ai_information_player', None) == player_id
                        and any(item.effect_key == 'look_top_select_hand' for item in state.stack)
                        and all(item.effect_key in {'draw_cards', 'look_top_select_hand', 'counter_spell', 'counter_ability'}
                                for item in state.stack))
    if not _settle_announced_stack(projected, player_id=player_id, opaque_hand_choices=opaque_selection):
        return None
    if (any(tuple(player.library) != libraries[pid] for pid, player in projected.players.items())
            or tuple(projected.players[opponent].hand) != opposing_hand):
        if not opaque_draw_counts or not _opaque_draw_count_changes(state, projected, player_id):
            return None
    return projected


def unanswered_action_loses(state: MatchState, player_id: int, action: dict) -> bool | None:
    """Unknown choices/hidden-zone changes never establish a certain loss."""
    outcome = _unanswered_action_outcome(state, player_id, action)
    return None if outcome is None else outcome == "loss"


def _unanswered_action_outcome(state: MatchState, player_id: int, action: dict, *, own_choice_action=None):
    from rules_engine.action_validation import ActionRejected, checked_action
    projected = _projection_copy(state)
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    opponent = 3 - player_id
    opposing_hand = tuple(state.players[opponent].hand)
    try:
        projected = checked_action(projected, RulesEngine(), player_id, action)
    except ActionRejected:
        return "rejected"
    if not _settle_announced_stack(projected, player_id=player_id, own_choice_action=own_choice_action):
        return None
    if any(tuple(player.library) != libraries[pid] for pid, player in projected.players.items()) or tuple(projected.players[opponent].hand) != opposing_hand:
        return None
    return "win" if projected.winner == player_id else "loss" if projected.winner == opponent else "neutral"


def pending_removal_destinations(state: MatchState, player_id: int) -> dict | None:
    scope = _decision_projection.get()
    if scope is None or scope[0] is not state or scope[1] != player_id:
        return _pending_removal_destinations(state, player_id)
    memo = scope[2]
    if "destinations" not in memo:
        memo["destinations"] = _pending_removal_destinations(state, player_id)
    result = memo["destinations"]
    return dict(result) if result is not None else None


def _pending_removal_destinations(state: MatchState, player_id: int) -> dict | None:
    """Project destinations of opposing permanents with own effects pending."""
    candidates = set(state.players[3 - player_id].battlefield)
    if not candidates or not any(item.controller == player_id for item in state.stack):
        return {}
    projected = _projection_copy(state)
    if _settle_announced_stack(projected) and projected.winner is None:
        remaining = set().union(*(set(player.battlefield) for player in projected.players.values()))
        return {cid: projected.cards[cid].zone for cid in candidates - remaining if cid in projected.cards}
    return None


def covered_removal_targets(state: MatchState, card, player_id: int, targets: dict) -> set[str] | None:
    """Conserve simple removal, but retain secondary value and zone upgrades."""
    if not state.stack or not set(effective_types(state, card)).intersection({"Instant", "Sorcery"}):
        return set()
    text = "\n".join(targets.get("mode_texts") or []) or targets.get("mode_text") or card.oracle_text
    if SECONDARY_EFFECT_RE.search(without_reminder_text(text)):
        return set()
    key, payload = infer_effect_from_oracle(state, card, player_id, targets, report_unsupported=False)
    if key == 'conditional_instruction':
        key = payload['effect_key']
    if key not in {"destroy_permanent", "exile", "return_permanent_to_hand"}:
        return set()
    destinations = pending_removal_destinations(state, player_id)
    if destinations is None:
        return None
    return {
        cid for cid, destination in destinations.items()
        if (destination in {Zone.GRAVEYARD, Zone.EXILE, Zone.CEASED}
            and not (key == "exile" and destination == Zone.GRAVEYARD))
        or (key == "return_permanent_to_hand" and destination == Zone.HAND)
    }
