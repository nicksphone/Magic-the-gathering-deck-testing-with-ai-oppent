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
  const selectedExpansion = expansionDecks.find((deck) => deck.code === selectedExpansionCode);

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
    setStatus(`Imported built-in #${imported.deck_id} (${imported.archetype_guess}) - local metadata ${resolved}/${imported.mainboard.length} card entries`);
    await showCompleteness([...imported.mainboard, ...imported.sideboard].map((item) => item.card_name));
    await refreshDeckData();
  }

  async function loadExpansionTopDeck() {
    if (!selectedExpansionCode) return;
    const data = await api.getExpansionTopDeck(selectedExpansionCode);
    setDeckName(data.name);
    setDeckText(data.deck_text.trim());
    setStatus(data.kind === "tournament"
      ? `Loaded ${data.player_name}'s ${data.format} ${data.event_name} deck; historical list, current legality and rules support not certified. Source: ${data.decklist_source_url}`
      : `Loaded ${data.expansion} archetype template; not a historical or format-legal tournament list.`);
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
    setStatus(`Imported ${loaded.kind === "tournament" ? "historical tournament deck" : "archetype template"} #${imported.deck_id} (${imported.archetype_guess}) - local metadata ${resolved}/${imported.mainboard.length} card entries`);
    await showCompleteness([...imported.mainboard, ...imported.sideboard].map((item) => item.card_name));
    await refreshDeckData();
  }

  async function importAllExpansionTopDecks() {
    const data = await api.importAllExpansionTopDecks();
    setStatus(`Expansion catalog sync: ${data.imported}/${data.requested} succeeded (errors: ${data.with_errors})`);
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
    setStatus(`Saved deck #${data.deck_id} (${data.archetype_guess}) - local metadata ${resolved}/${data.mainboard.length} card entries`);
    await showCompleteness([...data.mainboard, ...data.sideboard].map((item) => item.card_name));
    await refreshDeckData();
  }

  function report(operation: () => Promise<void>) {
    return () => { void operation().catch((error: unknown) => setStatus(`Deck request failed: ${error instanceof Error ? error.message : String(error)}`)); };
  }

  return (
    <section className="panel deck-panel">
      <h2>Deck Import Lab</h2>
      <div className="row">
        <select aria-label="Built-in deck" value={selectedBuiltin} onChange={(e) => setSelectedBuiltin(e.target.value)}>
          <option value="">Built-in Master Decks</option>
          {builtins.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <button onClick={report(loadBuiltin)}>Load Built-in</button>
        <button onClick={report(importSelectedBuiltin)}>Import Built-in</button>
        <button onClick={report(refreshDeckData)}>Refresh Decks</button>
      </div>
      <div className="row">
        <select aria-label="Historical deck or archetype template" value={selectedExpansionCode} onChange={(e) => setSelectedExpansionCode(e.target.value)}>
          <option value="">Historical Decks and Archetype Templates</option>
          {expansionDecks.map((d) => (
            <option key={d.code} value={d.code}>
              {d.release_year} {d.code} - {d.expansion} ({d.kind === "tournament" ? `Tournament: ${d.player_name}` : `Template: ${d.archetype}`})
            </option>
          ))}
        </select>
        <button onClick={report(loadExpansionTopDeck)}>Load Expansion Deck</button>
        <button onClick={report(importSelectedExpansionTopDeck)}>Import Expansion Deck</button>
        <button onClick={report(importAllExpansionTopDecks)}>Sync Expansion Catalog</button>
      </div>
      {selectedExpansion?.kind === "tournament" && (
        <p className="status">
          Historical {selectedExpansion.format} list: {selectedExpansion.player_name}, {selectedExpansion.finish} at {selectedExpansion.event_name}.{" "}
          <a href={selectedExpansion.decklist_source_url ?? undefined} target="_blank" rel="noopener noreferrer">Decklist</a>
          {selectedExpansion.event_source_url && <> | <a href={selectedExpansion.event_source_url} target="_blank" rel="noopener noreferrer">Event result</a></>}
          . Current-format legality and full rules support are not certified.
        </p>
      )}
      <input aria-label="Deck name" placeholder="Deck Name" value={deckName} onChange={(e) => setDeckName(e.target.value)} />
      <textarea
        aria-label="Deck list"
        value={deckText}
        onChange={(e) => setDeckText(e.target.value)}
        placeholder="Paste decklist, e.g. 4 Lightning Bolt"
        rows={10}
      />
      <button onClick={report(importDeck)}>Save Deck</button>
      <p className="status" role={status.startsWith("Deck request failed:") || status.startsWith("Import errors:") ? "alert" : "status"}>{status}</p>
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
          <strong>Cached/knowledge Oracle records: {completeness.complete}/{completeness.requested} available</strong>
          <span>Offline seed Oracle: {completeness.cards.filter((card) => card.oracle_source === "fallback").length}</span>
          {completeness.cards.every((card) => typeof card.match_ready === "boolean") && <span>Local match data ready: {completeness.cards.filter((card) => card.match_ready).length}/{completeness.requested}. Art and rulings sync separately.</span>}
          {completeness.cards.some((card) => card.needs_card_sync) && <span role="alert">Sync complete card data before playing: {completeness.cards.filter((card) => card.needs_card_sync).map((card) => card.name).join(", ")}</span>}
          <span>Uncached: {completeness.missing.cached}</span>
          <span>Placeholder art: {completeness.missing.real_image}</span>
          {completeness.cards.every((card) => card.image_status) && <span>Art: {completeness.cards.filter((card) => card.image_status === "local").length} local; {completeness.cards.filter((card) => card.image_status === "remote").length} remote; {completeness.cards.filter((card) => card.image_status === "fallback").length} fallback.</span>}
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
