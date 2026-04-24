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
  onStart: () => void;
  onPassPriority: () => void;
  onKeepHand: () => void;
  onMulligan: () => void;
  onNextStep: () => void;
  onAutoplayTick: (ticks: number) => void;
  onSubmitBlocks: (blocks: Record<string, string[]>) => void;
  onApplySideboard: (playerId: number, outCards: DeckItem[], inCards: DeckItem[]) => void;
  onNextGame: () => void;
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
  const blockMove = useMemo(() => props.legalMoves.find((m) => m.type === "block"), [props.legalMoves]);
  const [blockMap, setBlockMap] = useState<Record<string, string[]>>({});
  const [sbPlayer, setSbPlayer] = useState(1);
  const [sbOut, setSbOut] = useState("");
  const [sbIn, setSbIn] = useState("");

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
        </select>
      </div>
      <button onClick={props.onStart}>Start Best-of-3 Match</button>
      {props.match ? (
        <p>
          Score P1:{props.match.score?.["1"] ?? 0} P2:{props.match.score?.["2"] ?? 0} | Game {props.match.game_number ?? 1} | Best-of-{props.match.best_of ?? 3}
        </p>
      ) : null}
      <div className="grid-actions">
        <button onClick={props.onPassPriority} disabled={!props.match}>
          Pass Priority
        </button>
        <button onClick={props.onNextStep} disabled={!props.match}>
          Next Step
        </button>
        <button onClick={() => props.onAutoplayTick(1)} disabled={!props.match}>
          Auto-pass Until Response
        </button>
        <button onClick={() => props.onAutoplayTick(30)} disabled={!props.match}>
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

      {props.match?.winner && !props.match.match_complete ? (
        <div className="sideboard-panel">
          <h3>Between Games</h3>
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
      ) : null}
    </section>
  );
}
