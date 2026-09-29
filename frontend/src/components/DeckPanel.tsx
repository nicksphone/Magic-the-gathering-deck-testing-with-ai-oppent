import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { DeckRecord } from "../types";
import type { DeckImportResponse, ExpansionTopDeckMeta } from "../api/client";
import type { CardCompletenessReport } from "../api/client";

type Props = {
  decks: DeckRecord[];
  onDecksLoaded: (decks: DeckRecord[]) => void;
};

export function DeckPanel({ decks, onDecksLoaded }: Props) {
  const [builtins, setBuiltins] = useState<string[]>([]);
  const [expansionDecks, setExpansionDecks] = useState<ExpansionTopDeckMeta[]>([]);
  const [selectedBuiltin, setSelectedBuiltin] = useState("");
  const [selectedExpansionCode, setSelectedExpansionCode] = useState("");
  const [deckText, setDeckText] = useState("");
  const [deckName, setDeckName] = useState("");
  const [status, setStatus] = useState("");
  const [completeness, setCompleteness] = useState<CardCompletenessReport | null>(null);
  const [importAnalysis, setImportAnalysis] = useState<DeckImportResponse | null>(null);

  const refreshDeckData = useCallback(async () => {
    const [builtinsRes, expansionRes, decksRes] = await Promise.allSettled([
      api.listBuiltins(),
      api.listExpansionTopDecks(),
      api.listDecks(),
    ]);
    if (builtinsRes.status === "fulfilled") {
      setBuiltins(builtinsRes.value);
    }
    if (expansionRes.status === "fulfilled") {
      setExpansionDecks(expansionRes.value);
    } else {
      setExpansionDecks([]);
    }
    if (decksRes.status === "fulfilled") {
      onDecksLoaded(decksRes.value);
      if (!decksRes.value.length) {
        setStatus("No saved decks found yet. Import a built-in deck to start AI vs AI testing.");
      }
    } else {
      onDecksLoaded([]);
      setStatus(`Deck load failed: ${String(decksRes.reason)}`);
    }
    if (builtinsRes.status === "rejected" || expansionRes.status === "rejected") {
      const builtinsErr = builtinsRes.status === "rejected" ? `built-ins: ${String(builtinsRes.reason)}` : "";
      const expansionErr = expansionRes.status === "rejected" ? `expansion decks: ${String(expansionRes.reason)}` : "";
      const detail = [builtinsErr, expansionErr].filter(Boolean).join(" | ");
      setStatus((prev) => (prev ? `${prev} | Optional sources failed: ${detail}` : `Optional sources failed: ${detail}`));
    }
  }, [onDecksLoaded]);

  useEffect(() => {
    void refreshDeckData();
  }, [refreshDeckData]);

  async function loadBuiltin() {
    if (!selectedBuiltin) return;
    const data = await api.getBuiltinText(selectedBuiltin);
    setDeckName(data.name);
    setDeckText(data.deck_text.trim());
  }

  async function showCompleteness(names: string[]) {
    try {
      setCompleteness(await api.cardCompleteness([...new Set(names)]));
    } catch (error) {
      setCompleteness(null);
      setStatus((prev) => `${prev}${prev ? " | " : ""}Card completeness unavailable: ${String(error)}`);
    }
  }

  async function importSelectedBuiltin() {
    if (!selectedBuiltin) return;
    const data = await api.getBuiltinText(selectedBuiltin);
    const imported = await api.importDeck(data.name, data.deck_text.trim(), "builtin");
    if (imported.errors?.length) {
      setImportAnalysis(null);
      setStatus(`Built-in import errors: ${imported.errors.join(" | ")}`);
      return;
    }
    setImportAnalysis(imported);
    setDeckName(data.name);
    setDeckText(data.deck_text.trim());
    const resolved = imported.resolved_mainboard_cards?.filter((item) => item.card_metadata).length ?? 0;
    setStatus(`Imported built-in #${imported.deck_id} (${imported.archetype_guess}) - resolved ${resolved}/${imported.mainboard.length} card entries`);
    await showCompleteness([...imported.mainboard, ...imported.sideboard].map((item) => item.card_name));
    await refreshDeckData();
  }

  async function loadExpansionTopDeck() {
    if (!selectedExpansionCode) return;
    const data = await api.getExpansionTopDeck(selectedExpansionCode);
    setDeckName(data.name);
    setDeckText(data.deck_text.trim());
    setStatus(`Loaded ${data.expansion} (${data.code}) ${data.archetype}`);
  }

  async function importSelectedExpansionTopDeck() {
    if (!selectedExpansionCode) return;
    const imported = await api.importExpansionTopDeck(selectedExpansionCode);
    if (imported.errors?.length) {
      setImportAnalysis(null);
      setStatus(`Expansion import errors: ${imported.errors.join(" | ")}`);
      return;
    }
    setImportAnalysis(imported);
    const loaded = await api.getExpansionTopDeck(selectedExpansionCode);
    setDeckName(loaded.name);
    setDeckText(loaded.deck_text.trim());
    const resolved = imported.resolved_mainboard_cards?.filter((item) => item.card_metadata).length ?? 0;
    setStatus(`Imported expansion top deck #${imported.deck_id} (${imported.archetype_guess}) - resolved ${resolved}/${imported.mainboard.length} card entries`);
    await showCompleteness([...imported.mainboard, ...imported.sideboard].map((item) => item.card_name));
    await refreshDeckData();
  }

  async function importAllExpansionTopDecks() {
    const data = await api.importAllExpansionTopDecks();
    setStatus(`Expansion import-all complete: imported ${data.imported}/${data.requested} (errors: ${data.with_errors})`);
    await refreshDeckData();
  }

  async function importDeck() {
    const data = await api.importDeck(deckName || "Imported Deck", deckText, "user");
    if (data.errors?.length) {
      setImportAnalysis(null);
      setStatus(`Import errors: ${data.errors.join(" | ")}`);
      return;
    }
    setImportAnalysis(data);
    const resolved = data.resolved_mainboard_cards?.filter((item) => item.card_metadata).length ?? 0;
    setStatus(`Saved deck #${data.deck_id} (${data.archetype_guess}) - resolved ${resolved}/${data.mainboard.length} card entries`);
    await showCompleteness([...data.mainboard, ...data.sideboard].map((item) => item.card_name));
    await refreshDeckData();
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
        <button onClick={importSelectedBuiltin}>Import Built-in</button>
        <button onClick={refreshDeckData}>Refresh Decks</button>
      </div>
      <div className="row">
        <select value={selectedExpansionCode} onChange={(e) => setSelectedExpansionCode(e.target.value)}>
          <option value="">Top Decks by Expansion</option>
          {expansionDecks.map((d) => (
            <option key={d.code} value={d.code}>
              {d.release_year} {d.code} - {d.expansion} ({d.archetype})
            </option>
          ))}
        </select>
        <button onClick={loadExpansionTopDeck}>Load Expansion Deck</button>
        <button onClick={importSelectedExpansionTopDeck}>Import Expansion Deck</button>
        <button onClick={importAllExpansionTopDecks}>Import All Expansions</button>
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
      {importAnalysis && (
        <div className="data-report" role="status">
          <strong>Imported deck analysis</strong>
          <span>Mana curve (spells): {(["0", "1", "2", "3", "4", "5+"] as const).map((cost) => `${cost}: ${importAnalysis.mana_curve[cost] ?? 0}`).join("  |  ")}</span>
          <span>Lands: {importAnalysis.mana_curve.lands ?? 0} | Unknown costs: {importAnalysis.mana_curve.unknown ?? 0}</span>
          <span>Spell colors (lands excluded): {(["W", "U", "B", "R", "G"] as const).map((color) => `${color}: ${importAnalysis.color_profile[color] ?? 0}`).join("  |  ")}</span>
        </div>
      )}
      {completeness && (
        <div className="data-report" role="status">
          <strong>Card metadata: {completeness.complete}/{completeness.requested} available</strong>
          <span>Oracle fallback: {completeness.cards.filter((card) => card.oracle_source === "fallback").length}</span>
          <span>Uncached: {completeness.missing.cached}</span>
          <span>Placeholder art: {completeness.missing.real_image}</span>
          <span>Rulings unavailable or unverified: {completeness.missing.rulings}</span>
          <span>Metadata availability does not guarantee rules support.</span>
          <span>Rules coverage: {completeness.cards.filter((card) => card.rules_coverage === "known_unsupported").length} known unsupported; {completeness.cards.filter((card) => card.rules_coverage !== "known_unsupported").length} not certified. Match statistics are exploratory.</span>
          {completeness.unsupported_count ? <span role="alert">Unsupported rules in this deck: {completeness.cards.filter((card) => card.unsupported_mechanics?.length).map((card) => `${card.name} (${card.unsupported_mechanics?.join(", ")})`).join("; ")}</span> : null}
        </div>
      )}
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
