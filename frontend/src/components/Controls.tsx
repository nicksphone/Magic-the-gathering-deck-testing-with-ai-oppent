import { useMemo, useState } from "react";
import type { DeckItem, DeckRecord, LegalMove, MatchState } from "../types";

type Props = {
  decks: DeckRecord[];
  selectedA: number | null;
  selectedB: number | null;
  setSelectedA: (id: number) => void;
  setSelectedB: (id: number) => void;
  startMode: string;
  setStartMode: (mode: "player_vs_ai" | "ai_vs_ai" | "human_vs_human") => void;
  difficulty: string;
  setDifficulty: (d: string) => void;
  bestOf: number;
  setBestOf: (bestOf: number) => void;
  onStart: () => void;
  onPassPriority: () => void;
  onKeepHand: () => void;
  onMulligan: () => void;
  onNextStep: () => void;
  onAutoplayTick: (ticks: number) => void;
  autoplayDelayMs: number;
  setAutoplayDelayMs: (ms: number) => void;
  onSubmitBlocks: (blocks: Record<string, string[]>) => void;
  onSubmitAttack: (attackers: string[], attackTargets: Record<string, string>) => void;
  onApplySideboard: (playerId: number, outCards: DeckItem[], inCards: DeckItem[]) => void;
  onNextGame: () => void;
  onSetPriorityStops: (playerId: number, stops: string[]) => void;
  onChooseReplacement: (sourceId: string) => void;
  onChooseTriggerOrder: (order: string[]) => void;
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
  const [blockMap, setBlockMap] = useState<Record<string, string[]>>({});
  const [attackTargets, setAttackTargets] = useState<Record<string, string>>({});
  const [sbPlayer, setSbPlayer] = useState(1);
  const [sbOut, setSbOut] = useState("");
  const [sbIn, setSbIn] = useState("");
  const [stopPlayer, setStopPlayer] = useState(1);
  const matchComplete = Boolean(props.match?.match_complete);
  const betweenGames = Boolean(props.match?.winner && !matchComplete);
  const gamesNeeded = props.match?.games_needed ?? Math.floor((props.match?.best_of ?? 3) / 2) + 1;
  const p1Score = props.match?.score?.["1"] ?? 0;
  const p2Score = props.match?.score?.["2"] ?? 0;
  const scoreText = props.match ? `${p1Score}-${p2Score}` : "0-0";
  const sideboardStatus = betweenGames ? "Sideboarding open" : matchComplete ? "Match complete" : "Sideboarding locked";
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
        <select value={props.startMode} onChange={(e) => props.setStartMode(e.target.value as any)}>
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
      {triggerOrderPaused ? (
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
        <button onClick={props.onPassPriority} disabled={!props.match || replacementPaused || triggerOrderPaused}>
          Pass Priority
        </button>
        <button onClick={props.onNextStep} disabled={!props.match || replacementPaused || triggerOrderPaused}>
          Next Step
        </button>
        <button onClick={() => props.onAutoplayTick(1)} disabled={!props.match || replacementPaused || triggerOrderPaused}>
          Auto-pass Until Response
        </button>
        <button onClick={() => props.onAutoplayTick(30)} disabled={!props.match || replacementPaused || triggerOrderPaused}>
          AI Step x30
        </button>
      </div>
      {props.match?.pregame_pending ? (
        <div className="block-panel">
          <h3>London Mulligan</h3>
          <p>
            P1 mulligans: {props.match.mulligan_count?.["1"] ?? 0} | P2 mulligans: {props.match.mulligan_count?.["2"] ?? 0}
          </p>
          <div className="row">
            <button onClick={props.onKeepHand}>Keep Hand</button>
            <button onClick={props.onMulligan}>Mulligan</button>
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
          {(attackMove.options ?? []).map((attackerId) => {
            const attacker = props.match?.players?.["1"]?.battlefield?.find((c) => c.id === attackerId)
              || props.match?.players?.["2"]?.battlefield?.find((c) => c.id === attackerId);
            return (
              <div className="row" key={`atk-${attackerId}`}>
                <span>{attacker?.name ?? attackerId}</span>
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
          <button onClick={() => props.onSubmitAttack(attackMove.options ?? [], attackTargets)}>
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
          <p className="status-line">
            Game complete. Sideboarding is open until you start the next game.
          </p>
          <div className="row">
            <select value={sbPlayer} onChange={(e) => setSbPlayer(Number(e.target.value))}>
              <option value={1}>Player 1</option>
              <option value={2}>Player 2</option>
            </select>
            <button
              onClick={() => props.onApplySideboard(sbPlayer, parseDeckLines(sbOut), parseDeckLines(sbIn))}
            >
              Apply Sideboard Swaps
            </button>
            <button onClick={props.onNextGame}>Start Next Game</button>
          </div>
          <textarea rows={3} value={sbOut} onChange={(e) => setSbOut(e.target.value)} placeholder="Cards out: e.g. 2 Shock" />
          <textarea rows={3} value={sbIn} onChange={(e) => setSbIn(e.target.value)} placeholder="Cards in: e.g. 2 Negate" />
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
