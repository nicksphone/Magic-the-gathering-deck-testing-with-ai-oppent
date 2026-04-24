import { useState } from "react";
import { api } from "../api/client";
import type { DeckRecord } from "../types";

type Props = {
  decks: DeckRecord[];
};

export function AnalyticsPanel({ decks }: Props) {
  const [deckA, setDeckA] = useState<number | null>(null);
  const [deckB, setDeckB] = useState<number | null>(null);
  const [matches, setMatches] = useState(100);
  const [difficulty, setDifficulty] = useState("master_plus");
  const [result, setResult] = useState<string>("");

  async function runBatch() {
    const a = decks.find((d) => d.id === deckA);
    const b = decks.find((d) => d.id === deckB);
    if (!a || !b) return;
    const data = await api.simulateBatch(a.mainboard, b.mainboard, matches, difficulty);
    setResult(JSON.stringify(data, null, 2));
  }

  return (
    <section className="panel analytics">
      <h2>Testing Simulator</h2>
      <div className="row">
        <select value={deckA ?? ""} onChange={(e) => setDeckA(Number(e.target.value))}>
          <option value="">Deck A</option>
          {decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select value={deckB ?? ""} onChange={(e) => setDeckB(Number(e.target.value))}>
          <option value="">Deck B</option>
          {decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <input type="number" min={10} max={500} value={matches} onChange={(e) => setMatches(Number(e.target.value))} />
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="casual">Casual</option>
          <option value="strong">Strong</option>
          <option value="master">Master</option>
          <option value="master_plus">Master+</option>
        </select>
        <button onClick={runBatch}>Run {matches} Matches</button>
      </div>
      <pre>{result || "No simulation yet."}</pre>
    </section>
  );
}
