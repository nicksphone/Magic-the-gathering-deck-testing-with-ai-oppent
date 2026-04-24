import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DeckRecord } from "../types";

type Props = {
  decks: DeckRecord[];
  onDecksLoaded: (decks: DeckRecord[]) => void;
};

export function DeckPanel({ decks, onDecksLoaded }: Props) {
  const [builtins, setBuiltins] = useState<string[]>([]);
  const [selectedBuiltin, setSelectedBuiltin] = useState("");
  const [deckText, setDeckText] = useState("");
  const [deckName, setDeckName] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    void (async () => {
      setBuiltins(await api.listBuiltins());
      onDecksLoaded(await api.listDecks());
    })();
  }, [onDecksLoaded]);

  async function loadBuiltin() {
    if (!selectedBuiltin) return;
    const data = await api.getBuiltinText(selectedBuiltin);
    setDeckName(data.name);
    setDeckText(data.deck_text.trim());
  }

  async function importDeck() {
    const data = await api.importDeck(deckName || "Imported Deck", deckText, "user");
    if (data.errors?.length) {
      setStatus(`Import errors: ${data.errors.join(" | ")}`);
      return;
    }
    setStatus(`Saved deck #${data.deck_id} (${data.archetype_guess})`);
    onDecksLoaded(await api.listDecks());
  }

  return (
    <section className="panel deck-panel">
      <h2>Deck Import Lab</h2>
      <div className="row">
        <select value={selectedBuiltin} onChange={(e) => setSelectedBuiltin(e.target.value)}>
          <option value="">Built-in Master Decks</option>
          {builtins.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <button onClick={loadBuiltin}>Load Built-in</button>
      </div>
      <input placeholder="Deck Name" value={deckName} onChange={(e) => setDeckName(e.target.value)} />
      <textarea
        value={deckText}
        onChange={(e) => setDeckText(e.target.value)}
        placeholder="Paste decklist, e.g. 4 Lightning Bolt"
        rows={10}
      />
      <button onClick={importDeck}>Save Deck</button>
      <p className="status">{status}</p>
      <div className="deck-list">
        {decks.map((d) => (
          <div className="deck-chip" key={d.id}>
            <strong>{d.name}</strong>
            <span>{d.archetype_guess}</span>
            <span>{d.mainboard.reduce((a, c) => a + c.quantity, 0)} cards</span>
          </div>
        ))}
      </div>
    </section>
  );
}
