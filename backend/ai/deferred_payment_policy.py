"""Reserve native deferred payments without exposing unseen card identities.

The forecast assumes unanswered priority passes. Only a completed native loss
can remove a commitment; unavailable or incomplete financing stays uncertain.
"""
import re
import json
from collections import Counter
from types import SimpleNamespace

from ai.pending_effects import (planning_copy,simulation_frontier,UncertainSimulation,
                                combat_expansion_available)
from game_state.state import Step,Zone
from rules_engine.action_validation import ActionRejected,checked_action,validate_action
from rules_engine.engine import RulesEngine


PAYMENT = 'deferred_upkeep_payment'
SCHEDULE = 'schedule_upkeep_payment'
COPY_KEYS = {'copy_spell','copy_ability','copy_referred_ability','spree_copy'}
MANA_ACTIONS = {'tap_land_for_mana','tap_lands_bulk','tap_nonland_for_mana','activate_mana_ability'}
FUNDING_ACTIONS = {'play_land','cast_spell','activate_ability','activate_loyalty'}
UNKNOWN_ERRORS = (UncertainSimulation,ActionRejected,KeyError,TypeError,ValueError,AttributeError)


def _creates_payment(state,key,payload,seen=()):
    if key==SCHEDULE:return True
    if key=='effect_sequence':
        return any(_creates_payment(state,item.get('effect_key'),item.get('payload') or {},seen)
                   for item in payload.get('effects',[]))
    if key in COPY_KEYS:
        target=payload.get('target_stack_id')
        if target in seen:return True
        item=next((item for item in state.stack if item.id==target),None)
        # Some referred-copy instructions bind a retained native occurrence.
        return key=='copy_referred_ability' if item is None else _creates_payment(
            state,item.effect_key,item.payload or {},seen+(target,))
    return False


def _creation_pending(state,player):
    return any(item.controller==player and _creates_payment(state,item.effect_key,item.payload or {})
               for item in state.stack)


def _has_payment(state,player):
    pending=state.pending_mechanic_choice or {}
    return (pending.get('kind')==PAYMENT and pending.get('player_id')==player
        or any(row.get('effect_key')==PAYMENT and row.get('controller')==player
               for row in state.delayed_triggers)
        or any(item.controller==player and item.effect_key==PAYMENT for item in state.stack)
        or _creation_pending(state,player))


def _payment_units(state,player):
    """Count known native commitments, not estimated mana or unseen rewards."""
    def units(key,payload,seen=()):
        if key in {SCHEDULE,PAYMENT}:return 1
        if key=='effect_sequence':
            values=[units(item.get('effect_key'),item.get('payload') or {},seen)
                    for item in payload.get('effects',[])]
            return None if any(value is None for value in values) else sum(values)
        if key in COPY_KEYS:
            target=payload.get('target_stack_id')
            if target in seen:return None
            item=next((item for item in state.stack if item.id==target),None)
            if item is None:return None if key=='copy_referred_ability' else 0
            return units(item.effect_key,item.payload or {},seen+(target,))
        return 0
    values=[units(item.effect_key,item.payload or {}) for item in state.stack if item.controller==player]
    if any(value is None for value in values):return None
    pending=state.pending_mechanic_choice or {}
    return (sum(values)+sum(row.get('effect_key')==PAYMENT and row.get('controller')==player
                           for row in state.delayed_triggers)
            +int(pending.get('kind')==PAYMENT and pending.get('player_id')==player))


def _action_key(action):
    # Only this decision's declared public action protocol, never a state or
    # hidden-card identity. Native admission precedes reuse of a forecast.
    from ai.action_contract import complete_action
    return json.dumps(complete_action(action),sort_keys=True,separators=(',',':'),allow_nan=False)


def _take(state,player,action):
    if simulation_frontier(state,player,action) is not None:
        raise UncertainSimulation('Deferred-payment continuation crosses an unknown frontier')
    return checked_action(state,RulesEngine(),player,action)


def _pass_owned_forecast(state,before_pass=None):
    """Advance an already-owned copy through the original native admission.

    checked_action adds declaration requirements beyond validate_action. Keep
    that entry at those windows; other passes need no second state copy.
    """
    player=state.priority_player;action={'type':'pass_priority'}
    if (not state.stack and not state.pregame_pending
            and state.step in {Step.DECLARE_ATTACKERS,Step.DECLARE_BLOCKERS}):
        if before_pass is not None:before_pass()
        return _take(state,player,action)
    if simulation_frontier(state,player,action) is not None:
        raise UncertainSimulation('Deferred-payment continuation crosses an unknown frontier')
    engine=RulesEngine()
    from rules_engine.query_context import rule_query_scope
    # Funding and admission query the same immutable position. Share only its
    # native pure-query cache, then leave that scope before the action mutates it.
    with rule_query_scope(state):
        if before_pass is not None:before_pass()
        validate_action(state,engine,player,action)
    engine.take_action(state,player,action,reject_invalid=True)
    return state


def _choose_owned_forecast(state,player,card_ids):
    """Complete a fixed choice on the forecast's private state."""
    action={'type':'choose_mechanic','card_ids':card_ids}
    if simulation_frontier(state,player,action) is not None:
        raise UncertainSimulation('Deferred-payment continuation crosses an unknown frontier')
    engine=RulesEngine()
    from rules_engine.query_context import rule_query_scope
    with rule_query_scope(state):validate_action(state,engine,player,action)
    engine.take_action(state,player,action,reject_invalid=True)
    return state


def _searches(state,player):
    result=[]
    def visit(key,data,seen=()):
        if key=='effect_sequence':
            for item in data.get('effects',[]):visit(item.get('effect_key'),item.get('payload') or {},seen)
        elif key=='search_library':result.append(data)
        elif key in {'draw_cards','look_top_choose','look_top_select_hand'}:result.append(None)
        elif key in COPY_KEYS:
            target=data.get('target_stack_id')
            item=next((item for item in state.stack if item.id==target),None)
            if item is not None and target not in seen:visit(item.effect_key,item.payload or {},seen+(target,))
    for item in state.stack:
        if item.controller==player:visit(item.effect_key,item.payload or {})
    return result


def _acquisition_may_finance(state,player):
    """Own submitted metadata can keep a funding/winning acquisition uncertain.

    It never supplies the identity or order of a hidden instance to a forecast.
    Native visible actions are tested separately, including resource spells and
    counters to an obligation. A vanilla acquisition cannot fund basic sources.
    """
    searches=_searches(state,player)
    if not searches:return False
    from card_data.seed_cards import seed_card_payload
    from rules_engine.card_types import printed_card_types
    from rules_engine.oracle_effects import search_card_matches
    rows=getattr(state,'starting_decks',{}).get(player,[])
    if not rows:return True
    from ai.information import is_unknown
    from rules_engine.card_types import is_token_card
    visible=set(state.players[player].hand)
    for owner in state.players.values():
        visible.update(owner.battlefield);visible.update(owner.graveyard);visible.update(owner.exile)
    visible.update(item.source_card_id for item in state.stack if item.source_card_id)
    observed=Counter()
    for cid in visible:
        card=state.cards.get(cid)
        if (card is not None and card.owner==player and card.zone!=Zone.LIBRARY
                and not is_unknown(card) and not is_token_card(card)):
            observed[card.printed_characteristics.get('name',card.name).casefold()]+=1
    pending=state.pending_mechanic_choice or {}
    due_now=(pending.get('kind')==PAYMENT and pending.get('player_id')==player
             or any(item.controller==player and item.effect_key==PAYMENT for item in state.stack))
    for row in rows:
        name=row.get('card_name','').casefold()
        available=max(0,row.get('quantity',1)-observed[name])
        observed[name]=max(0,observed[name]-row.get('quantity',1))
        if not available:continue
        metadata=row if row.get('type_line') else seed_card_payload(row.get('card_name',''))
        if not metadata:return True
        text=str(metadata.get('oracle_text') or '')
        line=str(metadata.get('type_line') or '')
        card=SimpleNamespace(name=row.get('card_name',metadata.get('name','')),
            type_line=line,types=printed_card_types(line),mana_cost=metadata.get('mana_cost'),
            colors=metadata.get('colors'),oracle_text=text,card_faces=metadata.get('card_faces') or [])
        eligible=any(search is None or search_card_matches(card,search.get('contains'),search.get('mv_max'),
            printed_mana_costs=search.get('printed_mana_costs')) for search in searches)
        if not eligible:continue
        if 'Land' in card.types:
            from rules_engine.mana_abilities import _fixed_only_mana_text
            if text.strip() and not _fixed_only_mana_text(text):return True
            if any(search and search.get('destination')!='hand' for search in searches):return True
            # Native land plays require one's own main phase. A basic drawn
            # during a due upkeep cannot finance that already-waiting payment.
            if not due_now and state.active_player==player:return True
            continue
        if (text.strip() or metadata.get('keywords')
                or any(search and search.get('destination')!='hand' for search in searches)):
            return True
    # An acquired vanilla can change a contextual source or a deployment payoff.
    for cid in state.players[player].battlefield:
        card=state.cards[cid];text=(card.oracle_text or '').strip()
        if not text:continue
        if re.search(r'\b(?:for each|number of|equal to|among|devotion|haste|if you control)\b',text,re.I):
            return True
        if 'Land' not in card.types:
            from rules_engine.mana_abilities import _fixed_only_mana_text
            if not _fixed_only_mana_text(text):return True
    return False


class DeferredPaymentPolicy:
    def __init__(self,agent,state,player_id):
        self.agent=agent;self.state=state;self.player=player_id
        self.existing=_has_payment(state,player_id)
        self._baseline_set=False;self._baseline=None;self._answers={};self._forecasts={}
        self._initial_units=_payment_units(state,player_id)

    def _may_create(self,state,move):
        if move.get('type') in {'cast_spell','activate_ability','activate_loyalty'}:
            from ai.agent import _card_for_move
            from rules_engine.deferred_upkeep_payment import compile_instruction
            card=_card_for_move(state,move)
            if card is None:return False
            text=(move.get('ability_label') or card.oracle_text or '') if move.get('type')!='cast_spell' else card.oracle_text or ''
            instruction=compile_instruction(text)
            return (instruction is not None and '__unsupported_instruction' not in instruction
                    or re.search(r'\bcopy\b',text,re.I) is not None)
        pending=state.pending_mechanic_choice or {}
        return pending.get('kind') in {'effect_cast','suspend_cast'}

    def filter(self,moves):
        if self.existing:
            # Preserve a proved continuation before an uncertain branch can
            # consume the sticky allowance. This never replenishes its work.
            for move in moves:
                if move.get('type')=='pass_priority':self.permits(move)
        return [move for move in moves if self.permits(move)]

    def _cached(self,action):
        return self._forecasts.get(_action_key(action))

    def _evaluate(self,move):
        action=self.agent._materialize_action(self.state,move,self.player)
        if action.get('_invalid_ai_choice'):return None
        proposed=_take(self.state,self.player,action)
        key=_action_key(action)
        if key in self._forecasts:return self._forecasts[key]
        units=_payment_units(proposed,self.player)
        added=(self._initial_units is not None and units is not None and units>self._initial_units)
        outcome=self._forecast(proposed,self.agent._strategic_search_depth(self.state,self.player),
                               lock_creation=added,_owned_start=True)
        result=(outcome,added,action);self._forecasts[key]=result
        return result

    def funded_alternative(self,action,moves):
        """Retain a proved path before another uncertain payment commitment.

        The uncertain action remains permitted. This is a preference between
        checked continuations, not evidence that an incomplete line loses.
        """
        if not self.existing or action.get('type') not in {'cast_spell','activate_ability','activate_loyalty'}:
            return None
        try:
            selected=self._cached(action)
            if selected is None and combat_expansion_available():
                self.permits(action);selected=self._cached(action)
            if selected is None or selected[0] is not None or not selected[1]:return None
            ordered=[move for move in moves if move.get('type')=='pass_priority']
            ordered.extend(move for move in moves if move.get('type')!='pass_priority')
            for move in ordered:
                self.permits(move)
                candidate=self._cached(move)
                if candidate is None and combat_expansion_available():
                    candidate=self._evaluate(move)
                if candidate is not None and candidate[0] is True:return candidate[2]
        except UNKNOWN_ERRORS:
            return None
        return None

    def financing_action(self):
        """Choose a proved rescue instead of leaving an unpaid debt to ranking.

        An incomplete alternative remains legal. It does not displace a native
        financing action which already demonstrates survival of the deadline.
        """
        state=self.state
        if (not self.existing or _creation_pending(state,self.player)
                or state.priority_player!=self.player or state.pending_mechanic_choice
                or state.pending_trigger_order or state.pending_replacement_choice
                or not combat_expansion_available()):return None
        if self._forecast(state,0,allow_financing=False) is not False:return None
        depth=self.agent._strategic_search_depth(state,self.player)
        for move in self._funding_moves(state):
            if not combat_expansion_available(charge=True):return None
            try:
                action=self.agent._materialize_action(state,move,self.player)
                if action.get('_invalid_ai_choice'):continue
                proposed=_take(state,self.player,action)
                if self._forecast(proposed,depth-1,_owned_start=True) is True:return action
            except UNKNOWN_ERRORS:
                continue
        return None

    def permits(self,move):
        key=id(move);cached=self._answers.get(key)
        if cached is not None and cached[0] is move:return cached[1]
        answer=self._permits(move)
        self._answers[key]=(move,answer)
        return answer

    def _permits(self,move):
        creates=self._may_create(self.state,move)
        if not self.existing and not creates:return True
        try:
            result=self._cached(move)
            if result is None:
                if not combat_expansion_available():return True
                result=self._evaluate(move)
            if result is None:return True
            after,added,_=result
            if after is not False:return True
            if added:return False
            if not self._baseline_set:
                self._baseline=(True if any(item[0] is True for item in self._forecasts.values()) else
                    self._forecast(self.state,self.agent._strategic_search_depth(self.state,self.player)))
                self._baseline_set=True
            return self._baseline is not True
        except UNKNOWN_ERRORS:
            return True

    def _funding_moves(self,state):
        moves=RulesEngine().legal_moves(state,self.player)
        result=[];has_nonmana=False
        for move in moves:
            kind=move.get('type')
            if kind not in FUNDING_ACTIONS:continue
            if kind=='cast_spell':
                card=state.cards.get(move.get('card_id'))
                if card is None:continue
                if self._may_create(state,move):
                    # Do not finance a known loan by repeating the same opaque
                    # hand acquisition. Potential financing remains uncertain.
                    continue
                text=(card.oracle_text or '').strip()
                if not text and not card.keywords:continue
            if kind=='cast_spell':
                # Native target hints may legally include one's own debt.
                # The ordinary counter heuristic intentionally prefers enemy
                # objects; supply the explicit legal target for this rescue.
                due={item.id for item in state.stack if item.controller==self.player and item.effect_key==PAYMENT}
                for target in (move.get('target_hints') or {}).get('stack_targets',[]):
                    if target.get('id') in due:
                        result.append({**move,'targets':{**(move.get('targets') or {}),'target_stack_id':target['id']}})
            result.append(move);has_nonmana=True
        # Native automatic payment already considers ordinary mana sources.
        # Keep their sequencing when a nonmana ability/spell can use it.
        if has_nonmana:result.extend(move for move in moves if move.get('type') in MANA_ACTIONS)
        return result

    def _forecast(self,start,depth,*,lock_creation=False,allow_financing=True,_owned_start=False):
        if not combat_expansion_available():return None
        # checked_action already returned a private candidate at these call
        # sites. The caller relinquishes it; immutable roots still get copied.
        state=start if _owned_start else planning_copy(start)
        frontiers=[];unexpanded_financing=False
        possible_acquisition=_acquisition_may_finance(state,self.player)
        outcome=None
        try:
            for _ in range(128):
                if state.winner is not None:
                    outcome=state.winner==self.player;break
                # Delayed abilities may already be waiting in trigger groups,
                # outside the stack/list inspected by _has_payment.
                if state.pending_trigger_order or state.pending_replacement_choice:return None
                if not _has_payment(state,self.player):return True
                if lock_creation and not _creation_pending(state,self.player):lock_creation=False
                pending=state.pending_mechanic_choice
                if pending:
                    if pending.get('kind')==PAYMENT and pending.get('player_id')==self.player:
                        option='pay' if 'pay' in pending['options'] else 'decline'
                        state=_choose_owned_forecast(state,self.player,[option])
                        continue
                    if (pending.get('kind')=='search_library' and pending.get('player_id')==self.player
                            and pending.get('min_count',0)==0):
                        # A legal fail-to-find values the unconditional debt,
                        # never a fabricated identity for the unknown result.
                        state=_choose_owned_forecast(state,self.player,[])
                        continue
                    return None
                def remember_funding():
                    nonlocal unexpanded_financing
                    moves=self._funding_moves(state)
                    if moves:
                        if depth<=0:unexpanded_financing=True
                        else:frontiers.append((planning_copy(state),moves))
                remember=(remember_funding if allow_financing and not lock_creation
                          and state.priority_player==self.player
                          and (depth>0 or not unexpanded_financing) else None)
                state=_pass_owned_forecast(state,remember)
            else:return None
        except UNKNOWN_ERRORS:
            return None
        if outcome is not False:return outcome
        unknown=possible_acquisition
        if depth<=0:return None if unexpanded_financing or unknown else False
        for frontier,moves in reversed(frontiers):
            for move in moves:
                if not combat_expansion_available(charge=True):return None
                try:
                    action=self.agent._materialize_action(frontier,move,self.player)
                    if action.get('_invalid_ai_choice'):
                        unknown=True;continue
                    candidate=_take(frontier,self.player,action)
                    result=self._forecast(candidate,depth-1,lock_creation=self._may_create(frontier,move),_owned_start=True)
                except UNKNOWN_ERRORS:
                    unknown=True;continue
                if result is True:return True
                if result is None:unknown=True
        return None if unknown else False
