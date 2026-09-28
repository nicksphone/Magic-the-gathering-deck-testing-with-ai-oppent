import { useEffect, useMemo, useState } from "react";
import type { DeckItem, DeckRecord, LegalMove, MatchState } from "../types";

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
  onPassPriority: () => void;
  onKeepHand: (bottomCardIds: string[]) => void;
  actingPlayerId?: number;
  onMulligan: () => void;
  onNextStep: () => void;
  onAutoplayTick: (ticks: number) => void;
  autoplayDelayMs: number;
  setAutoplayDelayMs: (ms: number) => void;
  onSubmitBlocks: (blocks: Record<string, string[]>) => void;
  onSubmitAttack: (attackers: string[], attackTargets: Record<string, string>, bands: string[][]) => void;
  onApplySideboard: (playerId: number, outCards: DeckItem[], inCards: DeckItem[]) => void;
  onNextGame: (playFirst?: boolean) => void;
  onSetPriorityStops: (playerId: number, stops: string[]) => void;
  onChooseReplacement: (sourceId: string) => void;
  onChooseTriggerOrder: (order: string[]) => void;
  onChooseTriggerTarget: (stackId: string, targetCardId: string) => void;
  onChooseOptionalEffect: (stackId: string, accept: boolean) => void;
  onChooseMechanic: (playerId: number, action: Record<string, unknown>) => void;
  responseCountdown: number | null;
  autoResponsePaused: boolean;
  onToggleAutoResponsePause: () => void;
  legalMoves: LegalMove[];
  match: MatchState | null;
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
  const bottomCount = props.match?.mulligan_count?.[String(pregameActor)] ?? 0;
  const [bottomCards, setBottomCards] = useState<string[]>([]);
  useEffect(() => setBottomCards([]), [props.match?.id, pregameActor, bottomCount]);
  const mechanicMove = props.legalMoves.find((move) => move.type === "choose_mechanic");
  const [mechanicSelections, setMechanicSelections] = useState<string[]>([]);
  const [damageAmounts, setDamageAmounts] = useState<Record<string, number>>({});
  const mechanicKey = `${mechanicMove?.kind}:${mechanicMove?.stage}:${mechanicMove?.source_id}:${mechanicMove?.count}:${mechanicMove?.options?.join(",")}`;
  useEffect(() => setMechanicSelections([]), [mechanicKey]);
  useEffect(() => setDamageAmounts({}), [mechanicKey]);
  const mechanicPaused = Boolean(mechanicMove || props.match?.pending_mechanic_choice);
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
  const [blockMap, setBlockMap] = useState<Record<string, string[]>>({});
  const [attackTargets, setAttackTargets] = useState<Record<string, string>>({});
  const [excludedAttackers, setExcludedAttackers] = useState<string[]>([]);
  const [attackBandNumbers, setAttackBandNumbers] = useState<Record<string, number>>({});
  useEffect(() => {
    setAttackTargets({});
    setExcludedAttackers([]);
    setAttackBandNumbers({});
  }, [props.match?.id, props.match?.game_number, props.match?.turn, props.match?.step]);
  const [sbPlayer, setSbPlayer] = useState(1);
  const [sbOut, setSbOut] = useState("");
  const [sbIn, setSbIn] = useState("");
  useEffect(() => { setSbOut(""); setSbIn(""); }, [props.match?.id, props.match?.game_number]);
  const [stopPlayer, setStopPlayer] = useState(1);
  const matchComplete = Boolean(props.match?.match_complete);
  const betweenGames = Boolean(props.match?.winner && !matchComplete);
  const humanSeats = [1, 2].filter((pid) => props.match?.controllers?.[String(pid)] === "human");
  const selectedSbPlayer = humanSeats.includes(sbPlayer) ? sbPlayer : humanSeats[0];
  const sideboardInventory = props.match?.sideboarding?.[String(selectedSbPlayer)];
  useEffect(() => { setSbOut(""); setSbIn(""); }, [selectedSbPlayer]);
  const gamesNeeded = props.match?.games_needed ?? Math.floor((props.match?.best_of ?? 3) / 2) + 1;
  const p1Score = props.match?.score?.["1"] ?? 0;
  const p2Score = props.match?.score?.["2"] ?? 0;
  const scoreText = props.match ? `${p1Score}-${p2Score}` : "0-0";
  const sideboardStatus = betweenGames ? (humanSeats.length ? "Sideboarding open" : "No human sideboarding") : matchComplete ? "Match complete" : "Sideboarding locked";
  const stackSize = props.match?.stack?.length ?? 0;
  const currentController = props.match?.controllers?.[String(props.match?.priority_player ?? 1)] ?? "human";
  const interruptWindowLive = props.responseCountdown !== null;
  const replacementPaused = replacementMoves.length > 0 || Boolean(props.match?.pending_replacement_choice);
  const triggerOrderPaused = triggerOrderMoves.length > 0 || Boolean(props.match?.pending_trigger_order);
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
      <h2>Match Controls</h2>
      <div className="row">
        <select value={props.selectedA ?? ""} onChange={(e) => props.setSelectedA(Number(e.target.value))}>
          <option value="">Deck A</option>
          {props.decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select value={props.selectedB ?? ""} onChange={(e) => props.setSelectedB(Number(e.target.value))}>
          <option value="">Deck B</option>
          {props.decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>
      <div className="row">
        <select value={props.startMode} onChange={(e) => {
          const mode = e.currentTarget.value;
          if (mode === "player_vs_ai" || mode === "ai_vs_ai" || mode === "human_vs_human") {
            props.setStartMode(mode);
          }
        }}>
          <option value="player_vs_ai">Player vs AI</option>
          <option value="ai_vs_ai">AI vs AI</option>
          <option value="human_vs_human">Human vs Human</option>
        </select>
        <select value={props.difficulty} onChange={(e) => props.setDifficulty(e.target.value)}>
          <option value="casual">Casual</option>
          <option value="strong">Strong</option>
          <option value="master">Master</option>
          <option value="master_plus">Master+</option>
        </select>
        <select value={props.bestOf} onChange={(e) => props.setBestOf(Number(e.target.value))}>
          <option value={3}>Best-of-3</option>
          <option value={5}>Best-of-5</option>
          <option value={7}>Best-of-7</option>
          <option value={9}>Best-of-9</option>
        </select>
      </div>
      <button onClick={props.onStart}>Start Best-of-{props.bestOf} Match</button>
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
          {mechanicMove.kind === "combat_damage" ? <>
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
          </> : mechanicMove.kind === "draw" ? (mechanicMove.options ?? []).map((cid) => (
            <button key={cid} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", choice_id: cid })}>{mechanicMove.option_labels?.[cid] ?? cid}</button>
          )) : mechanicMove.kind === "look_top_choose" || mechanicMove.kind === "topdeck_bottom_order" ? <>
            <p>{mechanicMove.kind === "look_top_choose" ? "Pick a hand card, then an exile card, then the bottom cards in order." : "Pick the bottom cards in order, bottommost first."}</p>
            {(mechanicMove.options ?? []).map((cid) => (
              <button key={cid} disabled={mechanicSelections.includes(cid)} onClick={() => setMechanicSelections((selected) => [...selected, cid])}>{mechanicMove.option_labels?.[cid] ?? cid}</button>
            ))}
            <p>{mechanicSelections.map((cid, index) => `${mechanicMove.kind === "look_top_choose" ? index === 0 ? "Hand" : index === 1 ? "Exile" : `Bottom ${index - 1}` : `Bottom ${index + 1}`}: ${mechanicMove.option_labels?.[cid] ?? cid}`).join(" | ")}</p>
            <button onClick={() => setMechanicSelections([])}>Reset Order</button>
            <button disabled={mechanicSelections.length !== mechanicMove.count} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", card_ids: mechanicSelections })}>Confirm Order</button>
          </> : <>
            <p>{mechanicMove.kind === "topdeck_put" || mechanicMove.kind === "search_library" ? `Select up to ${mechanicMove.count} card(s).` : `Select exactly ${mechanicMove.count} card(s).`}</p>
            {(mechanicMove.options ?? []).map((cid) => <label key={cid}>
              <input type="checkbox" checked={mechanicSelections.includes(cid)} onChange={(event) => setMechanicSelections((selected) => event.target.checked ? [...selected, cid] : selected.filter((id) => id !== cid))} />
              {mechanicMove.option_labels?.[cid] ?? cid}
            </label>)}
            {mechanicMove.kind === "search_library" && mechanicSelections.length > 0 ? <p>Selection order: {mechanicSelections.map((cid) => mechanicMove.option_labels?.[cid] ?? cid).join(" then ")}</p> : null}
            <button disabled={mechanicMove.kind === "topdeck_put" || mechanicMove.kind === "search_library" ? mechanicSelections.length > (mechanicMove.count ?? 0) : mechanicSelections.length !== mechanicMove.count} onClick={() => props.onChooseMechanic(mechanicMove.player_id!, { type: "choose_mechanic", card_ids: mechanicSelections })}>Confirm Selection</button>
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
                key={`${move.stack_id}-${move.target_card_id}`}
                onClick={() => props.onChooseTriggerTarget(move.stack_id ?? "", move.target_card_id ?? "")}
              >
                {move.target_name ?? move.target_card_id ?? "Choose target"}
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
      <div className="block-panel">
        <h3>AI Playback Speed</h3>
        <p>{(props.autoplayDelayMs / 1000).toFixed(1)}s per AI beat</p>
        <input
          type="range"
          min={600}
          max={3500}
          step={100}
          value={props.autoplayDelayMs}
          onChange={(e) => props.setAutoplayDelayMs(Number(e.target.value))}
        />
      </div>
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
      {props.match ? (
        <div className="block-panel">
          <h3>Priority Stops</h3>
          <div className="row">
            <select value={stopPlayer} onChange={(e) => setStopPlayer(Number(e.target.value))}>
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
        </div>
      ) : null}
      <div className="grid-actions">
        <button onClick={props.onPassPriority} disabled={!props.match || replacementPaused || triggerOrderPaused || mechanicPaused}>
          Pass Priority
        </button>
        <button onClick={props.onNextStep} disabled={!props.match || replacementPaused || triggerOrderPaused || mechanicPaused}>
          Next Step
        </button>
        <button onClick={() => props.onAutoplayTick(1)} disabled={!props.match || replacementPaused || triggerOrderPaused || mechanicPaused}>
          Auto-pass Until Response
        </button>
        <button onClick={() => props.onAutoplayTick(30)} disabled={!props.match || replacementPaused || triggerOrderPaused || mechanicPaused}>
          AI Step x30
        </button>
      </div>
      {props.match?.pregame_pending && props.match.controllers?.[String(pregameActor)] !== "ai" ? (
        <div className="block-panel">
          <h3>London Mulligan</h3>
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
            <button disabled={bottomCards.length !== bottomCount} onClick={() => props.onKeepHand(bottomCards)}>Keep Hand</button>
            <button disabled={!props.legalMoves.some((move) => move.type === "mulligan")} onClick={props.onMulligan}>Mulligan</button>
          </div>
        </div>
      ) : null}

      {blockMove ? (
        <div className="block-panel">
          <h3>Declare Blockers</h3>
          {blockMove.attackers?.map((atk) => (
            <div className="row" key={atk.id}>
              <span>{atk.name}</span>
              <select
                multiple
                value={blockMap[atk.id] ?? []}
                onChange={(e) =>
                  setBlockMap((prev) => ({
                    ...prev,
                    [atk.id]: Array.from(e.target.selectedOptions).map((o) => o.value),
                  }))
                }
              >
                {blockMove.blockers?.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <button onClick={() => props.onSubmitBlocks(Object.fromEntries(Object.entries(blockMap).filter(([, v]) => v.length > 0)))}>
            Submit Blocks
          </button>
        </div>
      ) : null}

      {attackMove ? (
        <div className="block-panel">
          <h3>Declare Attackers</h3>
          <p>Select attackers. To form a band, give its members the same band number; a band needs at least one creature with banding and at most one without.</p>
          {(attackMove.options ?? []).map((attackerId) => {
            const attacker = props.match?.players?.["1"]?.battlefield?.find((c) => c.id === attackerId)
              || props.match?.players?.["2"]?.battlefield?.find((c) => c.id === attackerId);
            return (
              <div className="row" key={`atk-${attackerId}`}>
                <input type="checkbox" aria-label={`Attack with ${attacker?.name ?? attackerId}`} checked={!excludedAttackers.includes(attackerId)} onChange={(e) => setExcludedAttackers((prev) => e.target.checked ? prev.filter((id) => id !== attackerId) : [...prev, attackerId])} />
                <span>{attacker?.name ?? attackerId}</span>
                <label>Band <input type="number" min="0" max="125" aria-label={`Band number for ${attacker?.name ?? attackerId}`} value={attackBandNumbers[attackerId] ?? 0} onChange={(e) => setAttackBandNumbers((prev) => ({ ...prev, [attackerId]: Number(e.target.value) || 0 }))} /></label>
                <select
                  value={attackTargets[attackerId] ?? ""}
                  onChange={(e) =>
                    setAttackTargets((prev) => ({
                      ...prev,
                      [attackerId]: e.target.value,
                    }))
                  }
                >
                  <option value="">Default Defender</option>
                  {attackMove.defenders?.map((d) => (
                    <option key={`${attackerId}-def-${d.id}`} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
          <button onClick={() => {
            const attackers = (attackMove.options ?? []).filter((id) => !excludedAttackers.includes(id));
            const targets = Object.fromEntries(Object.entries(attackTargets).filter(([id, target]) => attackers.includes(id) && target));
            const grouped = new Map<number, string[]>();
            for (const id of attackers) {
              const number = attackBandNumbers[id] ?? 0;
              if (number > 0) grouped.set(number, [...(grouped.get(number) ?? []), id]);
            }
            props.onSubmitAttack(attackers, targets, [...grouped.values()]);
          }}>
            Submit Attackers
          </button>
        </div>
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
          <p className="status-line">Game complete. Human-controlled seats may sideboard once before the next game.</p>
          <div className="row">
            {humanSeats.length > 0 ? <>
              <select aria-label="Sideboarding player" value={selectedSbPlayer} onChange={(e) => setSbPlayer(Number(e.target.value))}>
                {humanSeats.map((pid) => <option key={pid} value={pid}>Player {pid}</option>)}
              </select>
              <button disabled={sideboardInventory?.applied} onClick={() => props.onApplySideboard(selectedSbPlayer, parseDeckLines(sbOut), parseDeckLines(sbIn))}>
                {sideboardInventory?.applied ? "Sideboard Applied" : "Apply Sideboard Swaps"}
              </button>
            </> : <span className="status-line">AI sideboarding strategy is not implemented.</span>}
            {props.match?.next_play_draw_chooser && props.match.controllers?.[String(props.match.next_play_draw_chooser)] === "human" ? <>
              <button onClick={() => props.onNextGame(true)}>P{props.match.next_play_draw_chooser} Play First</button>
              <button onClick={() => props.onNextGame(false)}>P{props.match.next_play_draw_chooser} Draw First</button>
            </> : <button onClick={() => props.onNextGame()}>Start Next Game (AI chooses play)</button>}
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
      ) : props.match?.winner && matchComplete ? (
        <div className="sideboard-panel">
          <h3>Match Complete</h3>
          <p className="status-line">The match is finished. Start a new match to sideboard again.</p>
        </div>
      ) : null}
    </section>
  );
}
