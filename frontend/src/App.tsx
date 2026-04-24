import { useCallback, useState } from "react";
import { api } from "./api/client";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { Battlefield } from "./components/Battlefield";
import { Controls } from "./components/Controls";
import { DeckPanel } from "./components/DeckPanel";
import { StackLog } from "./components/StackLog";
import type { DeckItem, DeckRecord, LegalMove, MatchState } from "./types";

export function App() {
  const [decks, setDecks] = useState<DeckRecord[]>([]);
  const [selectedA, setSelectedA] = useState<number | null>(null);
  const [selectedB, setSelectedB] = useState<number | null>(null);
  const [mode, setMode] = useState<"player_vs_ai" | "ai_vs_ai" | "human_vs_human">("player_vs_ai");
  const [difficulty, setDifficulty] = useState("master");
  const [match, setMatch] = useState<MatchState | null>(null);
  const [legalMoves, setLegalMoves] = useState<LegalMove[]>([]);
  const [legalPlayerId, setLegalPlayerId] = useState<number>(1);

  const onDecksLoaded = useCallback((records: DeckRecord[]) => {
    setDecks(records);
  }, []);

  async function startMatch() {
    const deckA = decks.find((d) => d.id === selectedA);
    const deckB = decks.find((d) => d.id === selectedB);
    if (!deckA || !deckB) return;
    const data = await api.startMatch({
      deck_a: deckA.mainboard,
      deck_b: deckB.mainboard,
      deck_a_sideboard: deckA.sideboard,
      deck_b_sideboard: deckB.sideboard,
      deck_a_id: deckA.id,
      deck_b_id: deckB.id,
      controller_a: mode === "ai_vs_ai" ? "ai" : "human",
      controller_b: mode === "human_vs_human" ? "human" : "ai",
      ai_difficulty: difficulty,
      mode,
    });
    setMatch(data);
    const legal = await api.legalMoves(data.id, data.priority_player);
    setLegalPlayerId(legal.player_id);
    setLegalMoves(legal.moves);
  }

  async function syncMoves(nextMatch: MatchState) {
    const legal = await api.legalMoves(nextMatch.id);
    setLegalPlayerId(legal.player_id);
    setLegalMoves(legal.moves);
  }

  async function passPriority() {
    if (!match) return;
    const nextMatch = await api.act(match.id, legalPlayerId, { type: "pass_priority" });
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function keepHand() {
    if (!match) return;
    const nextMatch = await api.act(match.id, legalPlayerId, { type: "keep_hand", bottom_card_ids: [] });
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function mulligan() {
    if (!match) return;
    const nextMatch = await api.act(match.id, legalPlayerId, { type: "mulligan" });
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function nextStep() {
    if (!match) return;
    const nextMatch = await api.autoplay(match.id, 1);
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function autoplayTick(ticks: number) {
    if (!match) return;
    const nextMatch = await api.autoplay(match.id, ticks);
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function onCardAction(playerId: number, action: Record<string, unknown>) {
    if (!match) return;
    const nextMatch = await api.act(match.id, playerId, action);
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function onSubmitBlocks(blocks: Record<string, string[]>) {
    if (!match) return;
    const filtered = Object.fromEntries(Object.entries(blocks).filter(([, v]) => v.length > 0));
    const nextMatch = await api.act(match.id, match.priority_player, { type: "block", blocks: filtered });
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function onApplySideboard(playerId: number, outCards: DeckItem[], inCards: DeckItem[]) {
    if (!match) return;
    const nextMatch = await api.sideboard(match.id, playerId, outCards, inCards);
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  async function onNextGame() {
    if (!match) return;
    const nextMatch = await api.nextGame(match.id);
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  return (
    <main className="layout">
      <header className="topbar">
        <h1>MTG Deck Testing Lab</h1>
        <p>Rules-aware 2-player testing simulator for competitive deck validation</p>
      </header>

      <section className="left-column">
        <DeckPanel decks={decks} onDecksLoaded={onDecksLoaded} />
        <Controls
          decks={decks}
          selectedA={selectedA}
          selectedB={selectedB}
          setSelectedA={setSelectedA}
          setSelectedB={setSelectedB}
          startMode={mode}
          setStartMode={setMode}
          difficulty={difficulty}
          setDifficulty={setDifficulty}
          onStart={startMatch}
          onPassPriority={passPriority}
          onKeepHand={keepHand}
          onMulligan={mulligan}
          onNextStep={nextStep}
          onAutoplayTick={autoplayTick}
          onSubmitBlocks={onSubmitBlocks}
          onApplySideboard={onApplySideboard}
          onNextGame={onNextGame}
          legalMoves={legalMoves}
          match={match}
        />
        <AnalyticsPanel decks={decks} />
      </section>

      <section className="right-column">
        {match ? (
          <>
            <Battlefield match={match} legalMoves={legalMoves} onCardAction={onCardAction} />
            <StackLog match={match} />
          </>
        ) : (
          <article className="panel empty-state">
            <h2>Ready for Testing</h2>
            <p>Import decks, choose matchup roles, and start a match.</p>
          </article>
        )}
      </section>
    </main>
  );
}
