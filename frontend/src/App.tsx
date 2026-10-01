import { useCallback, useEffect, useRef, useState } from "react";
import { api, type MatchWrite, type SavedMatch, type StartMatchPayload } from "./api/client";
import { HttpResponseError } from "./api/errors";
import { createMutationGate, newMutationKey } from "./api/mutation-gate";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { Battlefield } from "./components/Battlefield";
import { Controls } from "./components/Controls";
import { DeckPanel } from "./components/DeckPanel";
import { StackLog } from "./components/StackLog";
import type { DeckItem, DeckRecord, LegalMove, MatchState } from "./types";

const PENDING_START_KEY = "mtg.pendingStart";
type PendingStart = { key: string; payload: StartMatchPayload };

function readPendingStart(): PendingStart | null {
  try {
    const raw = localStorage.getItem(PENDING_START_KEY);
    if (!raw || raw.length > 100000) return null;
    const value: unknown = JSON.parse(raw);
    if (value && typeof value === "object" && "key" in value && "payload" in value
      && typeof value.key === "string" && /^[0-9a-f]{32}$/.test(value.key)
      && value.payload && typeof value.payload === "object"
      && "deck_a" in value.payload && "deck_b" in value.payload
      && Array.isArray(value.payload.deck_a) && Array.isArray(value.payload.deck_b)) {
      return value as PendingStart;
    }
  } catch { /* Optional local recovery data may be unavailable. */ }
  return null;
}

function clearPendingStart() {
  try { localStorage.removeItem(PENDING_START_KEY); } catch { /* Optional storage. */ }
}

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
  const [autoLoopBeat, setAutoLoopBeat] = useState(0);
  const [autoplayDelayMs, setAutoplayDelayMs] = useState<number>(1800);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [actionError, setActionError] = useState("");
  const [savedMatches, setSavedMatches] = useState<SavedMatch[]>([]);
  const [savedMatchLimit, setSavedMatchLimit] = useState(3);
  const [mutationPending, setMutationPending] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [autoProgressPaused, setAutoProgressPaused] = useState(false);
  const gate = useRef(createMutationGate());
  const currentMatch = useRef<MatchState | null>(null);
  const autoTickInFlight = useRef(false);
  const responsePassInFlight = useRef(false);
  const responseWindowSigRef = useRef("");

  const applyMatch = useCallback(async (next: MatchState) => {
    let data = next;
    let legal = await api.legalMoves(data.id);
    if (legal.revision !== undefined && legal.revision !== data.revision) {
      data = await api.getMatch(data.id);
      legal = await api.legalMoves(data.id);
      if (legal.revision !== data.revision) throw new Error("Match keeps changing in another window. Pause it, then reload.");
    }
    currentMatch.current = data;
    setMatch(data);
    setLegalPlayerId(legal.player_id);
    setLegalMoves(legal.moves);
    setMode(data.mode ?? "player_vs_ai");
    try { localStorage.setItem("mtg.activeMatch", data.id); } catch { /* Storage may be disabled. */ }
  }, []);

  const mutateMatch = useCallback(async (operation: (state: MatchState, write: MatchWrite) => Promise<MatchState>) => {
    await gate.current.run(async () => {
      const state = currentMatch.current;
      if (!state || restoring) return;
      setMutationPending(true);
      setLegalMoves([]);
      try {
        await applyMatch(await operation(state, { revision: state.revision ?? 0, key: newMutationKey() }));
      } catch (error) {
        setAutoProgressPaused(true);
        try { await applyMatch(await api.getMatch(state.id)); }
        catch { throw new Error("Write outcome is uncertain. Automatic play is paused; reconnect and resume the saved match before retrying."); }
        throw error;
      } finally { setMutationPending(false); }
    });
  }, [applyMatch, restoring]);

  async function resumeMatch(id: string) {
    await gate.current.run(async () => {
      setMutationPending(true);
      setAutoProgressPaused(true);
      try { await applyMatch(await api.getMatch(id)); }
      finally { setMutationPending(false); }
    });
  }

  useEffect(() => {
    let disposed = false;
    void (async () => {
      try {
        const records = await api.savedMatches();
        if (disposed) return;
        setSavedMatches(records);
        const pending = readPendingStart();
        let pendingMatch: MatchState | null = null;
        if (pending) {
          try { pendingMatch = await api.startMatch(pending.payload, pending.key); }
          catch (error) {
            if (error instanceof HttpResponseError && error.status < 500) clearPendingStart();
            if (!disposed) setActionError(`Pending match creation could not be recovered: ${String(error)}`);
          }
        }
        let id: string | null = null;
        try { id = pendingMatch?.id ?? localStorage.getItem("mtg.activeMatch"); } catch { /* Optional persistence. */ }
        if (id) {
          const data = pendingMatch ?? await api.getMatch(id);
          const legal = await api.legalMoves(id);
          if (disposed) return;
          if (legal.revision !== undefined && legal.revision !== data.revision) throw new Error("Saved match changed during restore. Resume it again.");
          currentMatch.current = data;
          setMatch(data); setMode(data.mode ?? "player_vs_ai");
          setLegalPlayerId(legal.player_id); setLegalMoves(legal.moves);
          setAutoProgressPaused(true);
          if (pendingMatch) {
            try { localStorage.setItem("mtg.activeMatch", id); } catch { /* Optional persistence. */ }
            clearPendingStart();
            try { setSavedMatches(await api.savedMatches()); } catch { /* Match is already restored. */ }
          }
        }
      } catch (error) {
        if (!disposed) setActionError(error instanceof Error ? error.message : String(error));
      } finally { if (!disposed) setRestoring(false); }
    })();
    return () => { disposed = true; };
  }, []);

  function reportAction<Args extends unknown[]>(operation: (...args: Args) => Promise<void>) {
    return (...args: Args) => {
      setActionError("");
      void operation(...args).catch((error: unknown) => setActionError(error instanceof Error ? error.message : String(error)));
    };
  }

  const checkApiHealth = useCallback(async () => {
    try {
      await api.health();
      setApiStatus("online");
    } catch (error) {
      console.error("Backend health check failed", error);
      setApiStatus("offline");
    }
  }, []);

  useEffect(() => {
    void checkApiHealth();
    const timer = window.setInterval(() => void checkApiHealth(), 15000);
    return () => window.clearInterval(timer);
  }, [checkApiHealth]);

  const onDecksLoaded = useCallback((records: DeckRecord[]) => {
    setDecks(records);
  }, []);

  async function startMatch() {
    if (restoring) return;
    const previousPending = readPendingStart();
    const deckA = decks.find((d) => d.id === selectedA);
    const deckB = decks.find((d) => d.id === selectedB);
    if (!previousPending && (!deckA || !deckB)) return;
    await gate.current.run(async () => {
      setMutationPending(true);
      try {
        const payload: StartMatchPayload = previousPending?.payload ?? {
          deck_a: deckA?.mainboard ?? [],
          deck_b: deckB?.mainboard ?? [],
          deck_a_sideboard: deckA?.sideboard,
          deck_b_sideboard: deckB?.sideboard,
          deck_a_id: deckA?.id,
          deck_b_id: deckB?.id,
          controller_a: mode === "ai_vs_ai" ? "ai" : "human",
          controller_b: mode === "human_vs_human" ? "human" : "ai",
          ai_difficulty: difficulty,
          mode,
          best_of: bestOf,
        };
        const pending = previousPending ?? { key: newMutationKey(), payload };
        try { localStorage.setItem(PENDING_START_KEY, JSON.stringify(pending)); } catch { /* Optional storage. */ }
        try {
          await applyMatch(await api.startMatch(payload, pending.key));
        } catch (error) {
          if (error instanceof HttpResponseError && error.status < 500) {
            clearPendingStart();
            throw error;
          }
          try { await applyMatch(await api.startMatch(payload, pending.key)); }
          catch (retryError) {
            if (retryError instanceof HttpResponseError && retryError.status < 500) clearPendingStart();
            throw new Error(`Match creation outcome is uncertain. Refresh to recover it: ${String(retryError)}`, { cause: retryError });
          }
        }
        clearPendingStart();
        setAutoProgressPaused(false);
        setSavedMatches(await api.savedMatches());
      } finally { setMutationPending(false); }
    });
  }

  const passPriority = useCallback(async () => {
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, { type: "pass_priority" }, write));
  }, [legalPlayerId, mutateMatch]);

  async function keepHand(bottomCardIds: string[]) {
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, { type: "keep_hand", bottom_card_ids: bottomCardIds }, write));
  }

  async function mulligan() {
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, { type: "mulligan" }, write));
  }

  async function nextStep() {
    await autoplayTick(1);
  }

  const autoplayTick = useCallback(async (ticks: number) => {
    await mutateMatch((state, write) => api.autoplay(state.id, ticks, write));
  }, [mutateMatch]);

  async function onCardAction(playerId: number, action: Record<string, unknown>) {
    await mutateMatch((state, write) => api.act(state.id, playerId, action, write));
  }

  async function onChooseReplacement(sourceId: string) {
    if (!sourceId) return;
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, {
      type: "choose_replacement",
      replacement_source_id: sourceId,
    }, write));
  }

  async function onChooseTriggerOrder(order: string[]) {
    if (order.length === 0) return;
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, {
      type: "choose_trigger_order",
      trigger_order: order,
    }, write));
  }

  async function onChooseTriggerTarget(stackId: string, targetCardId?: string, targetPlayer?: number) {
    if (!stackId || Boolean(targetCardId) === (targetPlayer !== undefined)) return;
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, {
      type: "choose_trigger_target",
      stack_id: stackId,
      ...(targetCardId ? { target_card_id: targetCardId } : { target_player: targetPlayer }),
    }, write));
  }

  async function onChooseOptionalEffect(stackId: string, accept: boolean) {
    if (!stackId) return;
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, {
      type: "choose_optional_effect",
      stack_id: stackId,
      accept,
    }, write));
  }

  async function onSubmitBlocks(blocks: Record<string, string[]>) {
    const filtered = Object.fromEntries(Object.entries(blocks).filter(([, v]) => v.length > 0));
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, { type: "block", blocks: filtered }, write));
  }

  async function onSubmitAttack(attackers: string[], attackTargets: Record<string, string>, bands: string[][]) {
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, {
      type: "attack",
      attackers,
      attack_targets: attackTargets,
      bands,
    }, write));
  }

  async function onApplySideboard(playerId: number, outCards: DeckItem[], inCards: DeckItem[]) {
    await mutateMatch((state, write) => api.sideboard(state.id, playerId, outCards, inCards, write));
  }

  async function onNextGame(playFirst?: boolean) {
    await mutateMatch((state, write) => {
      const chooser = state.next_play_draw_chooser;
      const choice = chooser && state.controllers?.[String(chooser)] === "human" && playFirst !== undefined
        ? { player_id: chooser, play_first: playFirst } : null;
      return api.nextGame(state.id, choice, write);
    });
  }

  async function onSetPriorityStops(playerId: number, stops: string[]) {
    await mutateMatch((state, write) => api.setPriorityStops(state.id, playerId, stops, write));
  }

  useEffect(() => {
    if (!match || restoring || mutationPending || autoProgressPaused) return;
    if (autoTickInFlight.current) return;
    if (match.match_complete) return;
    const controllers = match.controllers ?? {};
    const uiAiVsAi = match.mode === "ai_vs_ai";
    const actingPlayer = match.priority_player;
    const actingController = controllers[String(actingPlayer)] ?? (uiAiVsAi ? "ai" : "human");
    const bothAi = ((controllers["1"] ?? "human") === "ai" && (controllers["2"] ?? "human") === "ai") || uiAiVsAi;
    const shouldAutoRun = actingController === "ai" || (bothAi && match.winner !== null && !match.match_complete);
    if (!shouldAutoRun) return;

    const timer = window.setTimeout(async () => {
      if (!match || autoTickInFlight.current || gate.current.busy) return;
      autoTickInFlight.current = true;
      try {
        const ticks = bothAi ? 3 : 1;
        await autoplayTick(ticks);
      } catch (error) {
        console.error("Auto progression tick failed", error);
        setActionError(error instanceof Error ? error.message : String(error));
        setAutoProgressPaused(true);
      } finally {
        autoTickInFlight.current = false;
        setAutoLoopBeat((v) => v + 1);
      }
    }, autoplayDelayMs);

    return () => window.clearTimeout(timer);
  }, [match, autoLoopBeat, autoplayDelayMs, mutationPending, restoring, autoProgressPaused, autoplayTick]);

  const humanResponseWindowActive =
    match?.mode === "player_vs_ai"
    && !restoring && !mutationPending && !autoProgressPaused
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
    if (!match || responsePassInFlight.current || gate.current.busy) return;
    responsePassInFlight.current = true;
    void (async () => {
      try {
        await passPriority();
      } catch (error) {
        setActionError(error instanceof Error ? error.message : String(error));
        setAutoProgressPaused(true);
      } finally {
        responsePassInFlight.current = false;
        setResponseCountdown(null);
      }
    })();
  }, [humanResponseWindowActive, autoResponsePaused, responseCountdown, match, passPriority]);

  return (
    <main className="layout">
      <header className="topbar">
        <h1>MTG Deck Testing Lab</h1>
        <p>Rules-aware 2-player testing simulator for competitive deck validation</p>
        <div className={`api-status api-status-${apiStatus}`} role="status">
          <span aria-hidden="true" />
          Backend {apiStatus === "checking" ? "checking..." : apiStatus}
          {apiStatus === "offline" && (
            <button type="button" onClick={() => void checkApiHealth()}>
              Retry
            </button>
          )}
        </div>
      </header>

      <section className="left-column">
        {actionError ? <p role="alert">Match operation: {actionError}</p> : null}
        <article className="panel">
          <h2>Saved matches</h2>
          {restoring ? <p role="status">Restoring saved session...</p> : null}
          <button disabled={mutationPending || restoring} onClick={reportAction(async () => { setSavedMatches(await api.savedMatches()); })}>Refresh saved matches</button>
          <div id="saved-match-list" style={{ display: "grid", gap: "0.5rem", maxHeight: "16rem", overflowY: "auto" }}>
            {savedMatches.slice(0, savedMatchLimit).map((saved) => <button key={saved.id} disabled={mutationPending || restoring} onClick={reportAction(() => resumeMatch(saved.id))}>Resume {saved.players.join(" vs ")} | game {saved.game_number}, turn {saved.turn} | {saved.id.slice(0, 8)}</button>)}
          </div>
          {savedMatches.length > savedMatchLimit ? <button type="button" aria-controls="saved-match-list" onClick={() => setSavedMatchLimit((limit) => limit + 3)}>Show more saved matches</button> : null}
          {savedMatchLimit > 3 && savedMatches.length > 3 ? <button type="button" aria-controls="saved-match-list" onClick={() => setSavedMatchLimit(3)}>Show fewer saved matches</button> : null}
          {match ? <button disabled={mutationPending || restoring} onClick={() => setAutoProgressPaused((value) => !value)}>{autoProgressPaused ? "Resume automatic play" : "Pause automatic play"}</button> : null}
          {mutationPending ? <p role="status">Match operation pending...</p> : null}
        </article>
        <DeckPanel decks={decks} onDecksLoaded={onDecksLoaded} />
        <fieldset disabled={mutationPending || restoring} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
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
          onStart={reportAction(startMatch)}
          onPassPriority={reportAction(passPriority)}
          onKeepHand={reportAction(keepHand)}
          onMulligan={reportAction(mulligan)}
          onNextStep={reportAction(nextStep)}
          onAutoplayTick={reportAction(autoplayTick)}
          autoplayDelayMs={autoplayDelayMs}
          setAutoplayDelayMs={setAutoplayDelayMs}
          onSubmitBlocks={reportAction(onSubmitBlocks)}
          onSubmitAttack={reportAction(onSubmitAttack)}
          onApplySideboard={reportAction(onApplySideboard)}
          onNextGame={reportAction(onNextGame)}
          onSetPriorityStops={reportAction(onSetPriorityStops)}
          onChooseReplacement={reportAction(onChooseReplacement)}
          onChooseTriggerOrder={reportAction(onChooseTriggerOrder)}
          onChooseTriggerTarget={reportAction(onChooseTriggerTarget)}
          onChooseOptionalEffect={reportAction(onChooseOptionalEffect)}
          onChooseMechanic={reportAction(onCardAction)}
          responseCountdown={responseCountdown}
          autoResponsePaused={autoResponsePaused}
          onToggleAutoResponsePause={() => setAutoResponsePaused((v) => !v)}
          legalMoves={legalMoves}
          actingPlayerId={legalPlayerId}
          match={match}
        />
        </fieldset>
        <AnalyticsPanel decks={decks} />
      </section>

      <section className="right-column">
        {match ? (
          <>
            <fieldset disabled={mutationPending || restoring} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
              <Battlefield match={match} legalMoves={legalMoves} actingPlayerId={legalPlayerId} onCardAction={reportAction(onCardAction)} />
            </fieldset>
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
