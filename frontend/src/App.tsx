import { useCallback, useEffect, useRef, useState } from "react";
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
  const [bestOf, setBestOf] = useState<number>(3);
  const [match, setMatch] = useState<MatchState | null>(null);
  const [legalMoves, setLegalMoves] = useState<LegalMove[]>([]);
  const [legalPlayerId, setLegalPlayerId] = useState<number>(1);
  const [responseCountdown, setResponseCountdown] = useState<number | null>(null);
  const [autoResponsePaused, setAutoResponsePaused] = useState(false);
  const autoTickInFlight = useRef(false);
  const responsePassInFlight = useRef(false);
  const responseWindowSigRef = useRef("");

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
      best_of: bestOf,
    });
    setMatch(data);
    const legal = await api.legalMoves(data.id, data.priority_player);
    setLegalPlayerId(legal.player_id);
    setLegalMoves(legal.moves);
  }

  const syncMoves = useCallback(async (nextMatch: MatchState) => {
    const legal = await api.legalMoves(nextMatch.id);
    setLegalPlayerId(legal.player_id);
    setLegalMoves(legal.moves);
  }, []);

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

  async function onSubmitAttack(attackers: string[], attackTargets: Record<string, string>) {
    if (!match) return;
    const nextMatch = await api.act(match.id, match.priority_player, {
      type: "attack",
      attackers,
      attack_targets: attackTargets,
    });
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

  async function onSetPriorityStops(playerId: number, stops: string[]) {
    if (!match) return;
    const nextMatch = await api.setPriorityStops(match.id, playerId, stops);
    setMatch(nextMatch);
    await syncMoves(nextMatch);
  }

  useEffect(() => {
    if (!match) return;
    if (autoTickInFlight.current) return;
    if (match.match_complete) return;

    const aiVsAi = mode === "ai_vs_ai";
    const aiTurnInPvA = mode === "player_vs_ai" && legalPlayerId === 2;
    const shouldAutoRun = aiVsAi || aiTurnInPvA;
    if (!shouldAutoRun) return;

    const timer = window.setTimeout(async () => {
      if (!match || autoTickInFlight.current) return;
      autoTickInFlight.current = true;
      try {
        if (aiVsAi && match.winner && !match.match_complete) {
          const next = await api.nextGame(match.id);
          setMatch(next);
          await syncMoves(next);
          return;
        }
        const ticks = aiVsAi ? 20 : 1;
        const next = await api.autoplay(match.id, ticks);
        setMatch(next);
        await syncMoves(next);
      } finally {
        autoTickInFlight.current = false;
      }
    }, 160);

    return () => window.clearTimeout(timer);
  }, [match, legalPlayerId, mode, syncMoves]);

  const humanResponseWindowActive =
    mode === "player_vs_ai"
    && !!match
    && !match.pregame_pending
    && !match.match_complete
    && legalPlayerId === 1
    && (match.stack?.length ?? 0) > 0
    && legalMoves.some((m) => m.type !== "pass_priority");

  useEffect(() => {
    if (!humanResponseWindowActive) {
      setResponseCountdown(null);
      setAutoResponsePaused(false);
      responseWindowSigRef.current = "";
      return;
    }
    if (autoResponsePaused) {
      setResponseCountdown(null);
      return;
    }
    const sig = `${match?.id ?? ""}|${(match?.stack ?? []).map((s) => s.id).join(",")}|${legalPlayerId}`;
    if (responseWindowSigRef.current !== sig) {
      responseWindowSigRef.current = sig;
      setResponseCountdown(6);
    }
  }, [humanResponseWindowActive, autoResponsePaused, match, legalPlayerId]);

  useEffect(() => {
    if (!humanResponseWindowActive) return;
    if (autoResponsePaused) return;
    if (responseCountdown === null) return;
    if (responseCountdown <= 0) return;
    const timer = window.setTimeout(() => setResponseCountdown((v) => (v === null ? null : v - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [humanResponseWindowActive, autoResponsePaused, responseCountdown]);

  useEffect(() => {
    if (!humanResponseWindowActive) return;
    if (autoResponsePaused) return;
    if (responseCountdown !== 0) return;
    if (!match || responsePassInFlight.current) return;
    responsePassInFlight.current = true;
    void (async () => {
      try {
        const nextMatch = await api.act(match.id, 1, { type: "pass_priority" });
        setMatch(nextMatch);
        await syncMoves(nextMatch);
      } finally {
        responsePassInFlight.current = false;
        setResponseCountdown(null);
      }
    })();
  }, [humanResponseWindowActive, autoResponsePaused, responseCountdown, match, syncMoves]);

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
          bestOf={bestOf}
          setBestOf={setBestOf}
          onStart={startMatch}
          onPassPriority={passPriority}
          onKeepHand={keepHand}
          onMulligan={mulligan}
          onNextStep={nextStep}
          onAutoplayTick={autoplayTick}
          onSubmitBlocks={onSubmitBlocks}
          onSubmitAttack={onSubmitAttack}
          onApplySideboard={onApplySideboard}
          onNextGame={onNextGame}
          onSetPriorityStops={onSetPriorityStops}
          responseCountdown={responseCountdown}
          autoResponsePaused={autoResponsePaused}
          onToggleAutoResponsePause={() => setAutoResponsePaused((v) => !v)}
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
