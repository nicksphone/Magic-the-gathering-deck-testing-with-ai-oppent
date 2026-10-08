import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { selectAttackers, toggleAttacker, type CombatDraft } from "./combat-selection";
import type { DeckItem, DeckRecord, LegalMove, MatchState } from "../types";
import { CardArt } from "./CardArt";

// Includes engine-supported generic selections not yet listed in LegalMove.kind.
const supportedMechanicControls = new Set<string>([
  "effect_cast", "suspend_cast", "scry", "scry_top_order", "surveil", "surveil_top_order", "hand_top_order",
  "proliferate", "ward_payment", "ward_cost_cards", "counter_payment", "optional_search",
  "graveyard_return", "optional_reveal", "discard", "each_player_discard", "cleanup_discard", "mulligan_bottom",
  "opening_hand", "opening_hand_exile", "sacrifice", "draw", "land_entry", "land_from_hand", "saga_entry", "note_creature_type",
  "attacking_token_target", "topdeck_reveal_creature", "topdeck_put", "topdeck_bottom_order",
  "look_top_choose", "look_top_select_hand", "search_library", "combat_damage", "copy_target",
  "foretell_from_hand", "choose_revealed_discard", "choose_revealed_exile", "linked_exile_copy",
]);

type Props = {
  decks: DeckRecord[];
  selectedA: number | null;
  selectedB: number | null;
  setSelectedA: (id: number) => void;
  setSelectedB: (id: number) => void;
  startMode: NonNullable<MatchState["mode"]>;
  setStartMode: (mode: NonNullable<MatchState["mode"]>) => void;
  difficulty: string;
  setDifficulty: (d: string) => void;
  bestOf: number;
  setBestOf: (bestOf: number) => void;
  onStart: () => void;
  startDisabled: boolean;
  onPassPriority: () => void;
  onKeepHand: (bottomCardIds: string[]) => void;
  actingPlayerId?: number;
  onMulligan: () => void;
  onNextStep: () => void;
  onAutoplayTick: (ticks: number) => void;
  autoplayDelayMs: number;
  setAutoplayDelayMs: (ms: number) => void;
  onSubmitBlocks: (blocks: Record<string, string[]>, hybridChoices?: string[]) => void;
  onSubmitAttack: (attackers: string[], attackTargets: Record<string, string>, bands: string[][], hybridChoices?: string[]) => void;
  onApplySideboard: (playerId: number, outCards: DeckItem[], inCards: DeckItem[]) => void;
  onNextGame: (playFirst?: boolean) => void;
  onSetPriorityStops: (playerId: number, stops: string[]) => void;
  onChooseReplacement: (sourceId: string) => void;
  onChooseTriggerOrder: (order: string[]) => void;
  onChooseTriggerTarget: (stackId: string, targetCardId?: string, targetPlayer?: number) => void;
  onChooseOptionalEffect: (stackId: string, accept: boolean) => void;
  onChooseMechanic: (playerId: number, action: Record<string, unknown>) => void;
  responseCountdown: number | null;
  autoResponsePaused: boolean;
  onToggleAutoResponsePause: () => void;
  legalMoves: LegalMove[];
  match: MatchState | null;
  combatDraft?: CombatDraft;
  onCombatDraftChange?: Dispatch<SetStateAction<CombatDraft>>;
};

function parseDeckLines(text: string): DeckItem[] {
  return text
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean)
    .map((line) => {
      const m = line.match(/^(\d+)\s+(.+)$/);
      if (!m) return null;
      return { quantity: Number(m[1]), card_name: m[2].trim() };
    })
    .filter((x): x is DeckItem => Boolean(x));
}

export function Controls(props: Props) {
  const pregameActor = props.actingPlayerId ?? props.match?.priority_player ?? 1;
  const bottomCount = Math.max(0, (props.match?.mulligan_count?.[String(pregameActor)] ?? 0) - (props.match?.mulligan_bottomed?.[String(pregameActor)] ?? 0));
  const [bottomCards, setBottomCards] = useState<string[]>([]);
  useEffect(() => setBottomCards([]), [props.match?.id, pregameActor, bottomCount]);
  const mechanicMove = props.legalMoves.find((move) => move.type === "choose_mechanic");
  const variableDiscard = ["discard", "land_from_hand"].includes(mechanicMove?.kind ?? "") && mechanicMove?.min_count === 0;
  const [mechanicSelections, setMechanicSelections] = useState<string[]>([]);
  const [damageAmounts, setDamageAmounts] = useState<Record<string, number>>({});
  const mechanicKey = `${mechanicMove?.kind}:${mechanicMove?.player_id}:${mechanicMove?.stage}:${mechanicMove?.source_id}:${mechanicMove?.target_slot_number}:${mechanicMove?.min_count}:${mechanicMove?.count}:${mechanicMove?.options?.join(",")}:${mechanicMove?.inspected_cards?.map(card => card.id).join(",")}`;
  useEffect(() => setMechanicSelections([]), [mechanicKey]);
  useEffect(() => setDamageAmounts({}), [mechanicKey]);
  const mechanicPaused = Boolean(mechanicMove || props.match?.pending_mechanic_choice);
  const pendingChoicePlayer = props.match?.pending_mechanic_choice?.player_id
    ?? props.match?.pending_replacement_choice?.player_id
    ?? props.match?.pending_trigger_order?.current_controller;
  const aiChoicePending = pendingChoicePlayer !== undefined
    && props.match?.controllers?.[String(pendingChoicePlayer)] === "ai";
  const stepOptions = [
    "untap",
    "upkeep",
    "draw",
    "precombat_main",
    "begin_combat",
    "declare_attackers",
    "declare_blockers",
    "combat_damage",
    "end_combat",
    "postcombat_main",
    "end_step",
    "cleanup",
  ];
  const blockMove = useMemo(() => props.legalMoves.find((m) => m.type === "block"), [props.legalMoves]);
  const attackMove = useMemo(() => props.legalMoves.find((m) => m.type === "attack"), [props.legalMoves]);
  const attackRestrictions = useMemo(() => props.legalMoves.filter((m) => m.type === "attack_restricted"), [props.legalMoves]);
  const replacementMoves = useMemo(
    () => props.legalMoves.filter((m) => m.type === "choose_replacement"),
    [props.legalMoves],
  );
  const triggerOrderMoves = useMemo(
    () => props.legalMoves.filter((m) => m.type === "choose_trigger_order"),
    [props.legalMoves],
  );
  const triggerTargetMoves = useMemo(
    () => props.legalMoves.filter((m) => m.type === "choose_trigger_target"),
    [props.legalMoves],
  );
  const optionalEffectMoves = useMemo(
    () => props.legalMoves.filter((m) => m.type === "choose_optional_effect"),
    [props.legalMoves],
  );
  const [localBlockMap, setBlockMap] = useState<Record<string, string[]>>({});
  const blockMap = props.combatDraft?.blocks ?? localBlockMap;
  const [blockPaymentChoices, setBlockPaymentChoices] = useState<Record<string, string>>({});
  const selectedBlockers = [...new Set(Object.values(blockMap).flat())].sort();
  const [localAttackTargets, setAttackTargets] = useState<Record<string, string>>({});
  const attackTargets = props.combatDraft?.attackTargets ?? localAttackTargets;
  const [attackPaymentChoices, setAttackPaymentChoices] = useState<Record<string, string>>({});
  const [localExcludedAttackers, setExcludedAttackers] = useState<string[]>([]);
  const excludedAttackers = props.combatDraft ? (attackMove?.options ?? []).filter(id => !props.combatDraft?.attackers.includes(id)) : localExcludedAttackers;
  const [attackBandNumbers, setAttackBandNumbers] = useState<Record<string, number>>({});
  const [attackReviewRequired, setAttackReviewRequired] = useState(false);
  const selectedAttackers = (attackMove?.options ?? []).filter(id => !excludedAttackers.includes(id));
  const attackNeedsPayment = selectedAttackers.some(id => {
    const defender = attackTargets[id] || `player:${3 - (props.match?.active_player ?? 1)}`;
    const cost = attackMove?.attack_costs?.[id]?.[defender];
    return cost?.hybrid_symbols.some((_, index) => !attackPaymentChoices[`${id}:${defender}:${cost.mana_cost}:${index}`]);
  });
  const blockNeedsPayment = selectedBlockers.some(id => {
    const cost = blockMove?.block_costs?.[id];
    return cost?.hybrid_symbols.some((_, index) => !blockPaymentChoices[`${id}:${cost.mana_cost}:${index}`]);
  });
  useEffect(() => {
    setAttackTargets({});
    setBlockMap({});
    setBlockPaymentChoices({});
    setAttackPaymentChoices({});
    setExcludedAttackers([]);
    setAttackBandNumbers({});
    setAttackReviewRequired(false);
  }, [props.match?.id, props.match?.game_number, props.match?.turn, props.match?.step]);
  const [sbPlayer, setSbPlayer] = useState(1);
  const [sbOut, setSbOut] = useState("");
  const [sbIn, setSbIn] = useState("");
  useEffect(() => { setSbOut(""); setSbIn(""); }, [props.match?.id, props.match?.game_number]);
  const [stopPlayer, setStopPlayer] = useState(1);
  const matchComplete = Boolean(props.match?.match_complete);
  const betweenGames = props.match?.winner != null && !matchComplete;
  const humanSeats = [1, 2].filter((pid) => props.match?.controllers?.[String(pid)] === "human");
  const selectedSbPlayer = humanSeats.includes(sbPlayer) ? sbPlayer : humanSeats[0];
  const sideboardInventory = props.match?.sideboarding?.[String(selectedSbPlayer)];
  const unfinishedSideboardPlayers = humanSeats.filter((pid) => props.match?.sideboarding?.[String(pid)]?.applied !== true);
  useEffect(() => { setSbOut(""); setSbIn(""); }, [selectedSbPlayer]);
  const gamesNeeded = props.match?.games_needed ?? Math.floor((props.match?.best_of ?? 3) / 2) + 1;
  const p1Score = props.match?.score?.["1"] ?? 0;
  const p2Score = props.match?.score?.["2"] ?? 0;
  const scoreText = props.match ? `${p1Score}-${p2Score}` : "0-0";
  const sideboardStatus = betweenGames ? (humanSeats.length ? "Sideboarding open" : "No human sideboarding") : matchComplete ? "Match complete" : "Sideboarding locked";
  const stackSize = props.match?.stack?.length ?? 0;
  const currentController = props.match?.controllers?.[String(props.actingPlayerId ?? props.match?.priority_player ?? 1)] ?? "human";
  const interruptWindowLive = props.responseCountdown !== null;
  const replacementPaused = replacementMoves.length > 0 || Boolean(props.match?.pending_replacement_choice);
  const triggerOrderPaused = triggerOrderMoves.length > 0 || Boolean(props.match?.pending_trigger_order);
  const aiSeries = props.match?.mode === 'ai_vs_ai'
    || (props.match?.controllers?.['1'] === 'ai' && props.match?.controllers?.['2'] === 'ai');
  const aiTickDisabled = !props.match || matchComplete || (props.match.winner != null && !aiSeries)
    || ((replacementPaused || triggerOrderPaused || mechanicPaused) && !aiChoicePending);
  const interruptWindowLabel = interruptWindowLive
    ? "Response window open"
    : props.autoResponsePaused
      ? "Response timer paused"
      : stackSize > 0 && currentController === "human"
        ? "Priority held for human response"
        : stackSize > 0
          ? "Stack open"
          : "No pending response window";
  const interruptWindowSeat = props.match ? `P${props.match.priority_player} • ${currentController.toUpperCase()}` : "";
  const interruptWindowDetail = interruptWindowLive
    ? `Auto-pass in ${props.responseCountdown}s unless you respond.`
    : props.autoResponsePaused
      ? "Auto-response is paused on a human interrupt window."
      : stackSize > 0 && currentController !== "human"
        ? `Priority is with ${props.match ? `P${props.match.priority_player}` : "the active player"} and the current controller is AI.`
        : stackSize > 0
          ? "A response window exists, but auto-response is not currently counting down."
          : "No stack item or interruptible window is currently waiting.";

  return (
    <section className="panel controls">
      <h2>{props.match ? "Command the turn" : "Choose your matchup"}</h2>
      <details className="match-setup" open={!props.match}><summary>Match setup</summary>
      <div className="row">
        <label className="setup-seat"><span>Seat 01 <small>Your opening list</small></span><select aria-label="Deck A" value={props.selectedA ?? ""} onChange={(e) => props.setSelectedA(Number(e.target.value))}>
          <option value="">Deck A</option>
          {props.decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select></label>
        <label className="setup-seat"><span>Seat 02 <small>The other side of the table</small></span><select aria-label="Deck B" value={props.selectedB ?? ""} onChange={(e) => props.setSelectedB(Number(e.target.value))}>
          <option value="">Deck B</option>
          {props.decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select></label>
      </div>
      <div className="row">
        <label className="setup-setting">Seats<select aria-label="Match mode" value={props.startMode} onChange={(e) => {
          const mode = e.currentTarget.value;
          if (mode === "player_vs_ai" || mode === "ai_vs_ai" || mode === "human_vs_human") {
            props.setStartMode(mode);
          }
        }}>
          <option value="player_vs_ai">Player vs AI</option>
          <option value="ai_vs_ai">AI vs AI</option>
          <option value="human_vs_human">Human vs Human</option>
        </select></label>
        <label className="setup-setting">AI difficulty<select aria-label="AI difficulty" value={props.difficulty} onChange={(e) => props.setDifficulty(e.target.value)}>
          <option value="casual">Casual</option>
          <option value="strong">Strong</option>
          <option value="master">Master</option>
          <option value="master_plus">Master+</option>
        </select></label>
        <label className="setup-setting">Match length<select aria-label="Match length" value={props.bestOf} onChange={(e) => props.setBestOf(Number(e.target.value))}>
          <option value={3}>Best-of-3</option>
          <option value={5}>Best-of-5</option>
          <option value={7}>Best-of-7</option>
          <option value={9}>Best-of-9</option>
        </select></label>
      </div>
      <button disabled={props.startDisabled} onClick={props.onStart}>Start Best-of-{props.bestOf} Match</button>
      {!props.match && (!props.selectedA || !props.selectedB) ? <p className="setup-hint">Choose a deck for each seat to take the table.</p> : null}
      </details>
      {props.match ? (
        <div className="match-status-grid">
          <div className="status-card">
            <span className="status-label">Score</span>
            <strong>{scoreText}</strong>
          </div>
          <div className="status-card">
            <span className="status-label">Game</span>
            <strong>
              {props.match.game_number ?? 1} / {props.match.best_of ?? 3}
            </strong>
          </div>
          <div className="status-card">
            <span className="status-label">To Win</span>
            <strong>{gamesNeeded}</strong>
          </div>
          <div className="status-card">
            <span className="status-label">Sideboard</span>
            <strong>{sideboardStatus}</strong>
          </div>
          <div className="status-card priority-active">
            <span className="status-label">Priority</span>
            <strong>P{props.match.priority_player}</strong>
          </div>
        </div>
      ) : null}
      {mechanicMove ? (
        <div className="block-panel">
          <h3>{mechanicMove.label ?? "Choose a draw replacement"} (P{mechanicMove.player_id})</h3>
          {mechanicMove.inspected_cards?.length ? <section aria-label="Privately inspected cards">
            <p>{mechanicMove.kind === "optional_reveal" ? "This card remains on top. You may reveal it, even if it will not transform the source, or decline without revealing it." : "Inspected cards. Only qualifying cards below can be selected."}</p>
            {mechanicMove.inspected_cards.map((card) => <details key={card.id} className="cast-card-box">
              <summary>{card.name} {card.mana_cost} {mechanicMove.kind === "optional_reveal" ? "(privately inspected)" : mechanicMove.options?.includes(card.id) ? "(selectable)" : "(not selectable)"}</summary>
              <div style={{ maxWidth: 180 }}><CardArt uri={card.image_uri} name={card.name} /></div>
              <p>{card.type_line}</p><p>{card.oracle_text}</p>
            </details>)}
          </section> : null}
          {!supportedMechanicControls.has(mechanicMove.kind ?? "") ? <p role="alert">
            Unsupported mechanic choice: {typeof mechanicMove.kind === "string" && mechanicMove.kind ? mechanicMove.kind : "(missing or invalid kind)"}. No control is implemented
            for this choice. Do not advance while this action is required.
          </p> : mechanicMove.kind === "combat_damage" ? <>
            <p>Assign exactly {mechanicMove.count} damage in the {mechanicMove.stage} damage step.</p>
            {(mechanicMove.options ?? []).map((target) => <label key={target}>
              {mechanicMove.option_labels?.[target] ?? target} ({target})
              <input
                type="number" min={0} max={mechanicMove.count ?? 0}
                aria-label={`Damage to ${mechanicMove.option_labels?.[target] ?? target} ${target}`}
                value={damageAmounts[target] ?? 0}
                onChange={(event) => setDamageAmounts((current) => ({
                  ...current,
                  [target]: Math.max(0, Math.min(mechanicMove.count ?? 0, Number(event.target.value) || 0)),
                }))}
              />
            </label>)}
            <p>{Object.values(damageAmounts).reduce((sum, amount) => sum + amount, 0)} / {mechanicMove.count} assigned</p>
            <button
              disabled={Object.values(damageAmounts).reduce((sum, amount) => sum + amount, 0) !== mechanicMove.count}
              onClick={() => props.onChooseMechanic(mechanicMove.player_id!, {
                type: "choose_mechanic",
                damage_assignment: Object.fromEntries((mechanicMove.options ?? []).map((target) => [target, damageAmounts[target] ?? 0])),
              })}
            >Assign Damage</button>
            {mechanicMove.can_restart ? <button onClick={() => props.onChooseMechanic(mechanicMove.player_id!, {
              type: "choose_mechanic", choice_id: "restart",
            })}>Restart Damage Assignments</button> : null}
          </> : mechanicMove.kind === "optional_reveal" || mechanicMove.kind === "effect_cast" || mechanicMove.kind === "ward_payment" || mechanicMove.kind === "counter_payment" || mechanicMove.kind === "optional_search" || (mechanicMove.options?.length === 1 && mechanicMove.options[0] === "__none__") ? (mechanicMove.options ?? []).map((cid) => (
            <button key={cid} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", card_ids: [cid] })}>{mechanicMove.option_labels?.[cid] ?? cid}</button>
          )) : mechanicMove.kind === "attacking_token_target" ? (mechanicMove.options ?? []).map((cid) => (
            <button key={cid} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", card_ids: [cid] })}>Attack {mechanicMove.option_labels?.[cid] ?? cid}</button>
          )) : mechanicMove.kind === "draw" || mechanicMove.kind === "land_entry" || mechanicMove.kind === "saga_entry" || mechanicMove.kind === "note_creature_type" ? (mechanicMove.options ?? []).map((cid) => (
            <button key={cid} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", choice_id: cid })}>{mechanicMove.option_labels?.[cid] ?? cid}</button>
          )) : mechanicMove.kind === "look_top_choose" || mechanicMove.kind === "topdeck_bottom_order" || ["scry_top_order", "surveil_top_order", "hand_top_order"].includes(mechanicMove.kind ?? "") ? <>
            <p>{mechanicMove.kind === "look_top_choose" ? "Pick a hand card, then an exile card, then the bottom cards in order." : ["scry_top_order", "surveil_top_order", "hand_top_order"].includes(mechanicMove.kind ?? "") ? "Pick the remaining cards in order, topmost first." : "Pick the bottom cards in order, bottommost first."}</p>
            {(mechanicMove.options ?? []).map((cid) => (
              <button key={cid} disabled={mechanicSelections.includes(cid)} onClick={() => setMechanicSelections((selected) => [...selected, cid])}>{mechanicMove.option_labels?.[cid] ?? cid}</button>
            ))}
            <p>{mechanicSelections.map((cid, index) => `${mechanicMove.kind === "look_top_choose" ? index === 0 ? "Hand" : index === 1 ? "Exile" : `Bottom ${index - 1}` : `${["scry_top_order", "surveil_top_order", "hand_top_order"].includes(mechanicMove.kind ?? "") ? "Top" : "Bottom"} ${index + 1}`}: ${mechanicMove.option_labels?.[cid] ?? cid}`).join(" | ")}</p>
            <button onClick={() => setMechanicSelections([])}>Reset Order</button>
            <button disabled={mechanicSelections.length !== mechanicMove.count} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", card_ids: mechanicSelections })}>Confirm Order</button>
          </> : <>
            <p>{mechanicMove.kind === "surveil" ? "Choose any cards for your graveyard, bottommost first. Choose none to keep all." : mechanicMove.kind === "scry" ? "Choose any cards to put on the bottom, bottommost first. Choose none to keep all." : mechanicMove.kind === "proliferate" ? "Choose any number of permanents or players, including none. Each gets another counter of every kind it already has." : mechanicMove.min_count === mechanicMove.count && mechanicMove.count ? `Select exactly ${mechanicMove.count} card(s).` : variableDiscard || mechanicMove.kind === "topdeck_put" || mechanicMove.kind === "search_library" ? `Select up to ${mechanicMove.count} card(s).` : `Select exactly ${mechanicMove.count} card(s).`}</p>
            {(mechanicMove.options ?? []).map((cid) => <label key={cid}>
              <input type="checkbox" checked={mechanicSelections.includes(cid)} onChange={(event) => setMechanicSelections((selected) => event.target.checked ? [...selected, cid] : selected.filter((id) => id !== cid))} />
              {mechanicMove.option_labels?.[cid] ?? cid}
              {mechanicMove.option_type_lines?.[cid] ? <small> ({mechanicMove.option_type_lines[cid]})</small> : null}
            </label>)}
            {(mechanicMove.kind === "search_library" || mechanicMove.kind === "mulligan_bottom" || ["scry", "surveil"].includes(mechanicMove.kind ?? "")) && mechanicSelections.length > 0 ? <p>Selection order{mechanicMove.kind === "mulligan_bottom" || ["scry", "surveil"].includes(mechanicMove.kind ?? "") ? " (bottom-most first)" : ""}: {mechanicSelections.map((cid) => mechanicMove.option_labels?.[cid] ?? cid).join(" then ")}</p> : null}
            <button disabled={mechanicSelections.length < (mechanicMove.min_count ?? 0) || (variableDiscard || ["topdeck_put", "search_library", "proliferate", "scry", "surveil"].includes(mechanicMove.kind ?? "") ? mechanicSelections.length > (mechanicMove.count ?? 0) : mechanicSelections.length !== mechanicMove.count)} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", card_ids: mechanicSelections })}>Confirm Selection</button>
          </>}
        </div>
      ) : null}
      {replacementPaused ? (
        <div className="block-panel replacement-choice-panel">
          <h3>Replacement Choice Required</h3>
          <p>
            Choose which replacement effect applies to the pending event
            {props.match?.pending_replacement_choice?.event
              ? ` (${props.match.pending_replacement_choice.event.replace(/_/g, " ")})`
              : ""}.
          </p>
          <div className="row">
            {replacementMoves.map((move) => (
              <button
                key={move.replacement_source_id}
                onClick={() => props.onChooseReplacement(move.replacement_source_id ?? "")}
              >
                {move.replacement_name ?? move.replacement_source_id ?? "Choose replacement"}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {triggerOrderMoves.length > 0 ? (
        <div className="block-panel trigger-order-panel">
          <h3>Order Simultaneous Triggers</h3>
          <p>
            Choose the order for the simultaneous triggered abilities
            {props.match?.pending_trigger_order?.event
              ? ` (${props.match.pending_trigger_order.event.replace(/_/g, " ")})`
              : ""}.
          </p>
          <div className="row">
            {triggerOrderMoves.map((move, index) => (
              <button
                key={`trigger-order-${index}-${(move.trigger_order ?? []).join("-")}`}
                onClick={() => props.onChooseTriggerOrder(move.trigger_order ?? [])}
              >
                {(move.trigger_labels ?? move.trigger_order ?? []).join(" -> ") || "Use trigger order"}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {triggerTargetMoves.length > 0 ? (
        <div className="block-panel trigger-target-panel">
          <h3>Choose Trigger Target</h3>
          <p>Select a legal target before players receive priority.</p>
          <div className="row">
            {triggerTargetMoves.map((move) => (
              <button
                key={`${move.stack_id}-${move.target_card_id ?? move.target_player}`}
                onClick={() => props.onChooseTriggerTarget(move.stack_id ?? "", move.target_card_id, move.target_player)}
              >
                {move.target_name ?? move.target_card_id ?? `Player ${move.target_player}`}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {optionalEffectMoves.length > 0 ? (
        <div className="block-panel optional-effect-panel">
          <h3>Optional Trigger</h3>
          <p>Choose whether to apply this ability as it resolves.</p>
          <div className="row">
            {optionalEffectMoves.map((move) => (
              <button
                key={`${move.stack_id}-${move.accept}`}
                onClick={() => props.onChooseOptionalEffect(move.stack_id ?? "", move.accept === true)}
              >
                {move.accept ? "Apply effect" : "Decline effect"}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <details className="block-panel"><summary>AI Playback Speed</summary>
        <p>{(props.autoplayDelayMs / 1000).toFixed(1)}s per AI beat</p>
        <input
          aria-label="AI playback delay"
          type="range"
          min={600}
          max={3500}
          step={100}
          value={props.autoplayDelayMs}
          onChange={(e) => props.setAutoplayDelayMs(Number(e.target.value))}
        />
      </details>
      {props.match ? (
        <div className={`block-panel interrupt-window ${interruptWindowLive ? "interrupt-window-live" : ""}`}>
          <h3>Interrupt Window</h3>
          <div className="status-card interrupt-status-card">
            <span className="status-label">State</span>
            <strong>{interruptWindowLabel}</strong>
          </div>
          {interruptWindowSeat ? <p className="interrupt-seat-note">{interruptWindowSeat}</p> : null}
          <p>{interruptWindowDetail}</p>
          {stackSize > 0 ? (
            <p className="interrupt-stack-note">
              Stack objects: {stackSize} | Priority: P{props.match.priority_player}
            </p>
          ) : null}
          <button onClick={props.onToggleAutoResponsePause}>
            {props.autoResponsePaused ? "Resume Auto Response Timer" : "Hold Priority Timer"}
          </button>
        </div>
      ) : null}
      {props.match?.mode === "player_vs_ai" ? <p className="muted">Empty priority windows advance automatically. Playable cards, abilities and required choices stop play. Use Pause automatic play to inspect any step. Spend end-of-turn mana in the end step; untap has no response window.</p> : null}
      {props.match && props.match.mode !== "player_vs_ai" ? (
        <details className="block-panel"><summary>Priority Stops</summary>
          <div className="row">
            <select aria-label="Priority stop player" value={stopPlayer} onChange={(e) => setStopPlayer(Number(e.target.value))}>
              <option value={1}>Player 1</option>
              <option value={2}>Player 2</option>
            </select>
          </div>
          <div className="priority-stop-grid">
            {stepOptions.map((step) => {
              const current = new Set(props.match?.priority_stops?.[String(stopPlayer)] ?? []);
              const checked = current.has(step);
              return (
                <label key={`stop-${stopPlayer}-${step}`} className="priority-stop-item">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const next = new Set(current);
                      if (e.target.checked) next.add(step);
                      else next.delete(step);
                      props.onSetPriorityStops(stopPlayer, Array.from(next));
                    }}
                  />
                  {" "}
                  {step}
                </label>
              );
            })}
          </div>
        </details>
      ) : null}
      <div className="grid-actions">
        <button onClick={props.onPassPriority} disabled={!props.match || currentController !== "human" || !props.legalMoves.some(move => move.type === "pass_priority") || replacementPaused || triggerOrderPaused || mechanicPaused}>
          Pass Priority
        </button>
        <button onClick={props.onNextStep} title="Pass priority toward the next step. Both players must pass; stack objects resolve first."
          disabled={!props.match || props.match.winner !== null || replacementPaused || triggerOrderPaused || mechanicPaused || (currentController === "human" && !props.legalMoves.some(move => move.type === "pass_priority"))}>
          Next Step
        </button>
        <button onClick={() => props.onAutoplayTick(1)} disabled={aiTickDisabled}>
          Auto-pass Until Response
        </button>
        <button onClick={() => props.onAutoplayTick(30)} disabled={aiTickDisabled}>
          AI Step x30
        </button>
      </div>
      {props.match?.pregame_pending && !mechanicMove && props.match.controllers?.[String(pregameActor)] !== "ai" ? (
        <div className="block-panel">
          <h3>London Mulligan</h3>
          <p>Player {pregameActor} declares next. Redraws wait until all players declare.</p>
          <p>
            P1 mulligans: {props.match.mulligan_count?.["1"] ?? 0} | P2 mulligans: {props.match.mulligan_count?.["2"] ?? 0}
          </p>
          {bottomCount > 0 ? <fieldset>
            <legend>Choose {bottomCount} cards to bottom for player {pregameActor}</legend>
            <small>Selection order is bottom-most first.</small>
            {props.match.players[String(pregameActor)].hand.map((card) => <label key={card.id}>
              <input type="checkbox" aria-label={`Bottom ${card.name} ${card.id}`} checked={bottomCards.includes(card.id)} onChange={(event) => setBottomCards((selected) => event.target.checked ? [...selected, card.id] : selected.filter((cid) => cid !== card.id))} />{card.name} {card.mana_cost}
            </label>)}
          </fieldset> : null}
          <div className="row">
            <button disabled={bottomCards.length !== bottomCount || !props.legalMoves.some((move) => move.type === "keep_hand")} onClick={() => props.onKeepHand(bottomCards)}>Keep Hand</button>
            <button disabled={!props.legalMoves.some((move) => move.type === "mulligan")} onClick={props.onMulligan}>Mulligan</button>
          </div>
        </div>
      ) : null}

      {blockMove ? (
        <form id="block-declaration" className="block-panel" onSubmit={event => {
          event.preventDefault();
          if (blockNeedsPayment) return;
          const choices = selectedBlockers.flatMap(id => {
            const cost = blockMove.block_costs?.[id];
            return cost?.hybrid_symbols.map((_, index) => blockPaymentChoices[`${id}:${cost.mana_cost}:${index}`]) ?? [];
          });
          props.onSubmitBlocks(Object.fromEntries(Object.entries(blockMap).filter(([, ids]) => ids.length > 0)), choices.length ? choices : undefined);
        }}>
          <h3>Declare Blockers</h3>
          {props.combatDraft ? <p>Click a blocker, then its attacker, or drag the blocker onto an attacker. Confirm the assignments together.</p> : null}
          {props.onCombatDraftChange ? <button type="button" onClick={() => props.onCombatDraftChange?.(draft => ({ ...draft, blocks: {}, selectedBlocker: null }))}>Clear blocks</button> : null}
          <details open={props.combatDraft ? undefined : true}>
          <summary>Advanced block assignments</summary>
          {blockMove.attackers?.map((atk) => (
            <div className="row" key={atk.id}>
              <span>{atk.name}</span>
              <select
                multiple
                value={blockMap[atk.id] ?? []}
                aria-label={`Block assignments for ${atk.name}`}
                onChange={e => {
                  const ids = Array.from(e.target.selectedOptions).map(option => option.value);
                  if (props.onCombatDraftChange) props.onCombatDraftChange(draft => ({ ...draft, blocks: { ...draft.blocks, [atk.id]: ids } }));
                  else setBlockMap(previous => ({ ...previous, [atk.id]: ids }));
                }}
              >
                {blockMove.blockers?.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          ))}
          </details>
          {selectedBlockers.map((id) => {
            const cost = blockMove.block_costs?.[id];
            const name = blockMove.blockers?.find((card) => card.id === id)?.name ?? id;
            return cost?.mana_cost ? <div key={`block-cost-${id}`}>Block cost for {name}: {cost.mana_cost}
              {cost.hybrid_symbols.map((symbol, index) => {
                const key = `${id}:${cost.mana_cost}:${index}`;
                return <label key={key}>Pay {`{${symbol.symbol}}`} <select
                  aria-label={`Block payment ${index + 1} for ${name}`} value={blockPaymentChoices[key] ?? ""}
                  required
                  onChange={(e) => setBlockPaymentChoices((prev) => ({ ...prev, [key]: e.target.value }))}>
                  <option value="">Choose payment</option>
                  {symbol.choices.map((branch) => <option key={branch} value={branch}>{branch === "P" ? "2 life" : `{${branch}} mana`}</option>)}
                </select></label>;
              })}
            </div> : null;
          })}
          <button type="submit" disabled={blockNeedsPayment}>
            Submit Blocks
          </button>
        </form>
      ) : null}

      {attackMove ? (
        <form id="attack-declaration" className="block-panel" onSubmit={event => {
          event.preventDefault();
          if (attackNeedsPayment) return;
          const attackers = selectedAttackers;
          const targets = Object.fromEntries(Object.entries(attackTargets).filter(([id, target]) => attackers.includes(id) && target));
          const grouped = new Map<number, string[]>();
          for (const id of attackers) {
            const number = attackBandNumbers[id] ?? 0;
            if (number > 0) grouped.set(number, [...(grouped.get(number) ?? []), id]);
          }
          const choices = attackers.flatMap(id => {
            const defender = targets[id] || `player:${3 - (props.match?.active_player ?? 1)}`;
            const cost = attackMove.attack_costs?.[id]?.[defender];
            return cost?.hybrid_symbols.map((_, index) => attackPaymentChoices[`${id}:${defender}:${cost.mana_cost}:${index}`]) ?? [];
          });
          const bands = props.combatDraft?.bands.map(band => band.filter(id => attackers.includes(id))).filter(band => band.length > 1) ?? [...grouped.values()];
          props.onSubmitAttack(attackers, targets, bands, choices.length ? choices : undefined);
        }}>
          <h3>Declare Attackers</h3>
          <p>{props.combatDraft ? "Click creatures on the battlefield to select them. Drag an eligible attacker onto another to form a legal band. Confirm when ready." : "Select attackers. To form a band, give its members the same band number; a band needs at least one creature with banding and at most one without."}</p>
          <div className="row">
            <button type="button" disabled={!attackMove.options?.length} onClick={() => {
              const eligible = attackMove.options ?? [];
              const defaultDefender = `player:${3 - (props.match?.active_player ?? 1)}`;
              const needsReview = Object.values(attackMove.attack_costs ?? {}).some(costs => Object.keys(costs).length > 0)
                || eligible.some(id => attackTargets[id] && attackTargets[id] !== defaultDefender)
                || (props.combatDraft?.bands.some(band => band.filter(id => eligible.includes(id)).length > 1) ?? eligible.some(id => (attackBandNumbers[id] ?? 0) > 0));
              if (needsReview) {
                if (props.onCombatDraftChange) props.onCombatDraftChange(draft => selectAttackers(draft, eligible));
                else setExcludedAttackers([]);
                setAttackReviewRequired(true);
                return;
              }
              // Submit this snapshot, not the asynchronously updated selection draft.
              props.onSubmitAttack(eligible, {}, []);
            }}>Attack all eligible</button>
            <button type="button" onClick={() => {
              if (props.onCombatDraftChange) props.onCombatDraftChange(draft => selectAttackers(draft, attackMove.options ?? []));
              else setExcludedAttackers([]);
            }}>Select all</button>
            <button type="button" onClick={() => {
              if (props.onCombatDraftChange) props.onCombatDraftChange(draft => selectAttackers(draft, []));
              else setExcludedAttackers(attackMove.options ?? []);
            }}>Clear attackers</button>
            {props.onCombatDraftChange ? <button type="button" onClick={() => props.onCombatDraftChange?.(draft => ({ ...draft, bands: [] }))}>Separate bands</button> : null}
          </div>
          {attackReviewRequired ? <p role="status">All eligible attackers selected. Review defenders, bands and attack costs, choose any required payments, then click Submit Attackers to confirm. No attack has been declared.</p> : null}
          <details open={attackReviewRequired || !props.combatDraft || selectedAttackers.some(id => attackMove.attack_costs?.[id]?.[attackTargets[id] || `player:${3 - (props.match?.active_player ?? 1)}`]?.mana_cost) ? true : undefined}>
          <summary>Advanced attackers, defenders and payments</summary>
          {(attackMove.options ?? []).map((attackerId) => {
            const defender = attackTargets[attackerId] || `player:${3 - (props.match?.active_player ?? 1)}`;
            const payment = attackMove.attack_costs?.[attackerId]?.[defender];
            const attacker = props.match?.players?.["1"]?.battlefield?.find((c) => c.id === attackerId)
              || props.match?.players?.["2"]?.battlefield?.find((c) => c.id === attackerId);
            return (
              <div className="row" key={`atk-${attackerId}`}>
                <input type="checkbox" aria-label={`Attack with ${attacker?.name ?? attackerId}`} checked={!excludedAttackers.includes(attackerId)} onChange={e => {
                  if (props.onCombatDraftChange) props.onCombatDraftChange(draft => toggleAttacker(draft, attackerId));
                  else setExcludedAttackers(previous => e.target.checked ? previous.filter(id => id !== attackerId) : [...previous, attackerId]);
                }} />
                <span>{attacker?.name ?? attackerId}</span>
                {!props.combatDraft ? <label>Band <input type="number" min="0" max="125" aria-label={`Band number for ${attacker?.name ?? attackerId}`} value={attackBandNumbers[attackerId] ?? 0} onChange={(e) => setAttackBandNumbers((prev) => ({ ...prev, [attackerId]: Number(e.target.value) || 0 }))} /></label> : null}
                <select
                  value={attackTargets[attackerId] ?? ""}
                  aria-label={`Defender for ${attacker?.name ?? attackerId}`}
                  onChange={e => {
                    const target = e.target.value;
                    if (props.onCombatDraftChange) props.onCombatDraftChange(draft => {
                      const targets = { ...draft.attackTargets, [attackerId]: target };
                      return { ...draft, attackTargets: targets, bands: draft.bands.filter(band => new Set(band.map(id => targets[id] || `player:${3 - (props.match?.active_player ?? 1)}`)).size === 1) };
                    });
                    else setAttackTargets(previous => ({ ...previous, [attackerId]: target }));
                  }}
                >
                  <option value="">Default Defender</option>
                  {attackMove.defenders?.map((d) => (
                    <option key={`${attackerId}-def-${d.id}`} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
                {!excludedAttackers.includes(attackerId) && payment?.mana_cost ? <span>Attack cost: {payment.mana_cost}</span> : null}
                {!excludedAttackers.includes(attackerId) ? payment?.hybrid_symbols.map((symbol, index) => {
                  const key = `${attackerId}:${defender}:${payment.mana_cost}:${index}`;
                  return <label key={key}>Pay {`{${symbol.symbol}}`} <select
                    aria-label={`Attack payment ${index + 1} for ${attacker?.name ?? attackerId}`}
                    required
                    value={attackPaymentChoices[key] ?? ""}
                    onChange={(e) => setAttackPaymentChoices((prev) => ({ ...prev, [key]: e.target.value }))}>
                    <option value="">Choose payment</option>
                    {symbol.choices.map((branch) => <option key={branch} value={branch}>{branch === "P" ? "2 life" : `{${branch}} mana`}</option>)}
                  </select></label>;
                }) : null}
              </div>
            );
          })}
          </details>
          <button type="submit" disabled={attackNeedsPayment}>
            Submit Attackers
          </button>
        </form>
      ) : null}
      {attackRestrictions.length ? (
        <div className="block-panel">
          <h3>Attack Restrictions</h3>
          {attackRestrictions.map((r, i) => (
            <p key={`atk-res-${r.card_id ?? i}`}>
              {r.card_name}: {r.reason}
            </p>
          ))}
        </div>
      ) : null}

      {betweenGames ? (
        <div className="sideboard-panel">
          <h3>Between Games</h3>
          <p className="status-line">Each human seat must submit sideboard swaps or confirm no swaps before the next game.</p>
          {unfinishedSideboardPlayers.length > 0 ? <p className="status-line" role="status">
            Waiting for {unfinishedSideboardPlayers.map((pid) => `P${pid}`).join(", ")} to finish sideboarding.
          </p> : null}
          <div className="row">
            {humanSeats.length > 0 ? <>
              <select aria-label="Sideboarding player" value={selectedSbPlayer} onChange={(e) => setSbPlayer(Number(e.target.value))}>
                {humanSeats.map((pid) => <option key={pid} value={pid}>Player {pid}</option>)}
              </select>
              <button disabled={sideboardInventory?.applied} onClick={() => props.onApplySideboard(selectedSbPlayer, parseDeckLines(sbOut), parseDeckLines(sbIn))}>
                {sideboardInventory?.applied ? "Sideboard Applied" : "Apply Sideboard Swaps"}
              </button>
              <button disabled={sideboardInventory?.applied} onClick={() => props.onApplySideboard(selectedSbPlayer, [], [])}>
                Confirm No Swaps
              </button>
            </> : <span className="status-line">AI sideboarding is handled automatically.</span>}
            {props.match?.next_play_draw_chooser && props.match.controllers?.[String(props.match.next_play_draw_chooser)] === "human" ? <>
              <button disabled={unfinishedSideboardPlayers.length > 0} onClick={() => props.onNextGame(true)}>P{props.match.next_play_draw_chooser} Play First</button>
              <button disabled={unfinishedSideboardPlayers.length > 0} onClick={() => props.onNextGame(false)}>P{props.match.next_play_draw_chooser} Draw First</button>
            </> : <button disabled={unfinishedSideboardPlayers.length > 0} onClick={() => props.onNextGame()}>Start Next Game (AI chooses play)</button>}
          </div>
          {sideboardInventory ? <div className="sideboard-inventory">
            <details><summary>Current mainboard ({sideboardInventory.mainboard.reduce((n, card) => n + card.quantity, 0)})</summary>
              <ul>{sideboardInventory.mainboard.map((card) => <li key={card.card_name}>{card.quantity} {card.card_name}</li>)}</ul>
            </details>
            <details open><summary>Available sideboard ({sideboardInventory.sideboard.reduce((n, card) => n + card.quantity, 0)})</summary>
              <ul>{sideboardInventory.sideboard.map((card) => <li key={card.card_name}>{card.quantity} {card.card_name}</li>)}</ul>
            </details>
          </div> : null}
          {humanSeats.length > 0 ? <>
            <textarea aria-label="Cards out" rows={3} disabled={sideboardInventory?.applied} value={sbOut} onChange={(e) => setSbOut(e.target.value)} placeholder="Cards out: e.g. 2 Shock" />
            <textarea aria-label="Cards in" rows={3} disabled={sideboardInventory?.applied} value={sbIn} onChange={(e) => setSbIn(e.target.value)} placeholder="Cards in: e.g. 2 Negate" />
          </> : null}
        </div>
      ) : props.match?.winner != null && matchComplete ? (
        <div className="sideboard-panel">
          <h3>Match Complete</h3>
          <p className="status-line">The match is finished. Start a new match to sideboard again.</p>
        </div>
      ) : null}
    </section>
  );
}
