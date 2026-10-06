import { useCallback, useEffect, useRef, useState } from "react";
import { api, type MatchWrite, type SavedMatch, type StartMatchPayload } from "./api/client";
import { HttpResponseError } from "./api/errors";
import { createMutationGate, newMutationKey } from "./api/mutation-gate";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { AiHandDebug } from "./components/AiHandDebug";
import { Battlefield } from "./components/Battlefield";
import { Controls } from "./components/Controls";
import { DeckPanel } from "./components/DeckPanel";
import { StackLog } from "./components/StackLog";
import type { DeckItem, DeckRecord, LegalMove, MatchState } from "./types";
import { emptyCombatDraft } from "./components/combat-selection";
import { canStartReviewed, parsePendingInteractiveStart, reviewMatchesPayload, startSignature,
  type InteractiveReview, type PendingInteractiveStart } from "./lib/interactive-preflight";

const PENDING_START_KEY = "mtg.pendingStart";
type PendingStart = PendingInteractiveStart;

function isAiSeries(state: MatchState) {
  return state.mode === "ai_vs_ai" || (state.controllers?.["1"] === "ai" && state.controllers?.["2"] === "ai");
}

function readPendingStart(): PendingStart | null {
  try {
    return parsePendingInteractiveStart(localStorage.getItem(PENDING_START_KEY));
  } catch { /* Optional local recovery data may be unavailable. */ }
  return null;
}

function clearPendingStart(key: string | undefined) {
  try {
    if (readPendingStart()?.key === key && key) localStorage.removeItem(PENDING_START_KEY);
  } catch { /* Optional storage. */ }
}

export function App() {
  const [decks, setDecks] = useState<DeckRecord[]>([]);
  const [labOpen, setLabOpen] = useState(false);
  const [selectedA, setSelectedA] = useState<number | null>(null);
  const [selectedB, setSelectedB] = useState<number | null>(null);
  const [mode, setMode] = useState<"player_vs_ai" | "ai_vs_ai" | "human_vs_human">("player_vs_ai");
  const [difficulty, setDifficulty] = useState("master");
  const [bestOf, setBestOf] = useState<number>(3);
  const [match, setMatch] = useState<MatchState | null>(null);
  const [legalMoves, setLegalMoves] = useState<LegalMove[]>([]);
  const [legalPlayerId, setLegalPlayerId] = useState<number>(1);
  const [canAutoPass, setCanAutoPass] = useState(false);
  const [combatDraft, setCombatDraft] = useState(emptyCombatDraft);
  useEffect(() => { setCombatDraft(emptyCombatDraft()); }, [match?.id, match?.game_number, match?.turn, match?.step]);
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
  const [pendingStart, setPendingStart] = useState(readPendingStart);
  const pendingStartRef = useRef(pendingStart);
  const pendingStartPersisted = useRef(pendingStart !== null);
  const [startReview, setStartReview] = useState<InteractiveReview | null>(pendingStart?.review ?? null);
  const [preflightChecking, setPreflightChecking] = useState(false);
  const [preflightNote, setPreflightNote] = useState("");
  const startIntentInFlight = useRef(false);
  const preflightGeneration = useRef(0);
  const gate = useRef(createMutationGate());
  const currentMatch = useRef<MatchState | null>(null);
  const autoTickInFlight = useRef(false);
  const responsePassInFlight = useRef(false);
  const responseWindowSigRef = useRef("");

  const deckA = decks.find(deck => deck.id === selectedA);
  const deckB = decks.find(deck => deck.id === selectedB);
  const selectedStart: StartMatchPayload | null = deckA && deckB ? {
    deck_a: deckA.mainboard, deck_b: deckB.mainboard,
    deck_a_sideboard: deckA.sideboard, deck_b_sideboard: deckB.sideboard,
    deck_a_id: deckA.id, deck_b_id: deckB.id,
    controller_a: mode === "ai_vs_ai" ? "ai" : "human",
    controller_b: mode === "human_vs_human" ? "human" : "ai",
    ai_difficulty: difficulty, mode, best_of: bestOf,
  } : null;
  const reviewTarget = pendingStart?.payload ?? selectedStart;
  const reviewSignature = reviewTarget ? startSignature(reviewTarget) : "";
  const reviewSignatureRef = useRef(reviewSignature);
  reviewSignatureRef.current = reviewSignature;
  const visibleReview = reviewTarget && reviewMatchesPayload(startReview, reviewTarget) ? startReview : null;

  useEffect(() => {
    preflightGeneration.current++;
    setStartReview(pendingStart?.review ?? null);
  }, [reviewSignature, pendingStart]);

  function invalidateStartReview() {
    preflightGeneration.current++;
    setStartReview(null);
  }

  const rememberPendingStart = useCallback((pending: PendingStart) => {
    pendingStartRef.current = pending;
    setPendingStart(pending);
    try {
      localStorage.setItem(PENDING_START_KEY, JSON.stringify(pending));
      pendingStartPersisted.current = true;
    } catch { pendingStartPersisted.current = false; }
  }, []);

  const forgetPendingStart = useCallback((key: string) => {
    if (pendingStartRef.current?.key === key) {
      pendingStartRef.current = null;
      setPendingStart(null);
      setStartReview(null);
      preflightGeneration.current++;
    }
    clearPendingStart(key);
  }, []);

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
    setLegalMoves(data.winner != null ? [] : legal.moves);
    setCanAutoPass(data.winner == null && legal.can_auto_pass === true);
    setMode(data.mode ?? "player_vs_ai");
    try { localStorage.setItem("mtg.activeMatch", data.id); } catch { /* Storage may be disabled. */ }
  }, []);

  const mutateMatch = useCallback(async (operation: (state: MatchState, write: MatchWrite) => Promise<MatchState>, allowBetweenGames = false) => {
    await gate.current.run(async () => {
      const state = currentMatch.current;
      if (!state || restoring || state.match_complete || (state.winner != null && !allowBetweenGames)) return;
      setMutationPending(true);
      setLegalMoves([]);
      setCanAutoPass(false);
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
        const pending = pendingStartRef.current;
        let pendingMatch: MatchState | null = null;
        if (pending && canStartReviewed(pending.review, pending.payload)) {
          try { pendingMatch = await api.startMatch(pending.payload, pending.key); }
          catch (error) {
            if (error instanceof HttpResponseError && error.status < 500) forgetPendingStart(pending.key);
            if (!disposed) setActionError(`Pending match creation could not be recovered: ${String(error)}`);
          }
        } else if (pending) {
          setPreflightNote("Pending start has no acknowledged support review. Review its original decks and configuration before recovering it.");
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
          setLegalPlayerId(legal.player_id); setLegalMoves(data.winner != null ? [] : legal.moves);
          setCanAutoPass(data.winner == null && legal.can_auto_pass === true);
          setAutoProgressPaused(true);
          if (pendingMatch && pending) {
            try { localStorage.setItem("mtg.activeMatch", id); } catch { /* Optional persistence. */ }
            forgetPendingStart(pending.key);
            try { setSavedMatches(await api.savedMatches()); } catch { /* Match is already restored. */ }
          }
        }
      } catch (error) {
        if (!disposed) setActionError(error instanceof Error ? error.message : String(error));
      } finally { if (!disposed) setRestoring(false); }
    })();
    return () => { disposed = true; };
  }, [forgetPendingStart]);

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

  async function startMatch(recover = false) {
    if (restoring || startIntentInFlight.current) return;
    const previousPending = pendingStartRef.current;
    const storedPending = readPendingStart();
    if (storedPending && !previousPending) {
      pendingStartRef.current = storedPending;
      pendingStartPersisted.current = true;
      setPendingStart(storedPending);
      setStartReview(storedPending.review ?? null);
      preflightGeneration.current++;
      setPreflightNote("An existing pending start was found. Use its recovery control; the current selectors do not replace its intent.");
      return;
    }
    if (storedPending && previousPending && (storedPending.key !== previousPending.key
      || startSignature(storedPending.payload) !== startSignature(previousPending.payload))) {
      throw new Error("Another window changed the stored pending start. No start was submitted; resolve that intent before retrying here.");
    }
    if (previousPending && !recover) throw new Error("Recover the original pending start before creating another match.");
    const requested = recover ? previousPending?.payload : selectedStart;
    if (!requested) return;
    const payload = JSON.parse(JSON.stringify(requested)) as StartMatchPayload;
    const signature = startSignature(payload);
    const generation = preflightGeneration.current;
    const isCurrent = () => generation === preflightGeneration.current && signature === reviewSignatureRef.current;
    startIntentInFlight.current = true;
    try {
      if (!canStartReviewed(startReview, payload)) {
        setStartReview(null);
        setPreflightChecking(true);
        setPreflightNote("Checking known rules gaps in both mainboards and sideboards...");
        try {
          const coverage = await api.preflightSimulateBatch(
            [...payload.deck_a, ...(payload.deck_a_sideboard ?? [])],
            [...payload.deck_b, ...(payload.deck_b_sideboard ?? [])],
          );
          if (!isCurrent()) {
            setPreflightNote("Decks or configuration changed. The stale preflight was discarded; check again.");
            return;
          }
          setStartReview({ version: 1, signature, coverage, exploratoryAcknowledged: false });
          setPreflightNote("");
        } catch (error) {
          if (!isCurrent()) {
            setPreflightNote("Decks or configuration changed. The stale preflight error was discarded; check again.");
            return;
          }
          setPreflightNote("Support preflight failed. No start was submitted; retry the check.");
          throw error;
        } finally { setPreflightChecking(false); }
        return;
      }
      await gate.current.run(async () => {
        if (!isCurrent()) return;
        setMutationPending(true);
        const pending: PendingStart = { key: previousPending?.key ?? newMutationKey(), payload, review: startReview };
        try {
          const stored = readPendingStart();
          if (stored && stored.key !== pending.key) throw new Error("Another window has a pending start. No start was submitted; recover it before creating another match.");
          rememberPendingStart(pending);
          try {
            await applyMatch(await api.startMatch(payload, pending.key));
          } catch (error) {
            if (error instanceof HttpResponseError && error.status < 500) {
              forgetPendingStart(pending.key);
              throw error;
            }
            try { await applyMatch(await api.startMatch(payload, pending.key)); }
            catch (retryError) {
              if (retryError instanceof HttpResponseError && retryError.status < 500) forgetPendingStart(pending.key);
              const recovery = pendingStartPersisted.current ? "Refresh to recover it" : "Browser persistence is unavailable. Keep this window open and use Recover pending match start";
              throw new Error(`Match creation outcome is uncertain. ${recovery}: ${String(retryError)}`, { cause: retryError });
            }
          }
          forgetPendingStart(pending.key);
          setAutoProgressPaused(false);
          setSavedMatches(await api.savedMatches());
        } finally { setMutationPending(false); }
      });
    } finally { startIntentInFlight.current = false; }
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
    await mutateMatch((state, write) => (state.controllers?.[String(legalPlayerId)] ?? "human") === "human"
      ? api.act(state.id, legalPlayerId, { type: "pass_priority" }, write)
      : api.autoplay(state.id, 1, write));
  }

  const autoplayTick = useCallback(async (ticks: number) => {
    await mutateMatch((state, write) => state.winner != null && !isAiSeries(state)
      ? Promise.resolve(state) : api.autoplay(state.id, ticks, write), true);
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

  async function onSubmitBlocks(blocks: Record<string, string[]>, hybridChoices?: string[]) {
    const filtered = Object.fromEntries(Object.entries(blocks).filter(([, v]) => v.length > 0));
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, { type: "block", blocks: filtered, hybrid_choices: hybridChoices }, write));
  }

  async function onSubmitAttack(attackers: string[], attackTargets: Record<string, string>, bands: string[][], hybridChoices?: string[]) {
    await mutateMatch((state, write) => api.act(state.id, legalPlayerId, {
      type: "attack",
      attackers,
      attack_targets: attackTargets,
      bands,
      hybrid_choices: hybridChoices,
    }, write));
  }

  async function onApplySideboard(playerId: number, outCards: DeckItem[], inCards: DeckItem[]) {
    await mutateMatch((state, write) => api.sideboard(state.id, playerId, outCards, inCards, write), true);
  }

  async function onNextGame(playFirst?: boolean) {
    await mutateMatch((state, write) => {
      const chooser = state.next_play_draw_chooser;
      const choice = chooser && state.controllers?.[String(chooser)] === "human" && playFirst !== undefined
        ? { player_id: chooser, play_first: playFirst } : null;
      return api.nextGame(state.id, choice, write);
    }, true);
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
    const actingPlayer = legalPlayerId;
    const actingController = controllers[String(actingPlayer)] ?? (uiAiVsAi ? "ai" : "human");
    const bothAi = isAiSeries(match);
    if (match.winner != null && !bothAi) return;
    const emptyHumanWindow = match.mode === "player_vs_ai" && canAutoPass && match.winner === null;
    const shouldAutoRun = actingController === "ai" || emptyHumanWindow || (bothAi && match.winner !== null && !match.match_complete);
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
    }, emptyHumanWindow ? 150 : autoplayDelayMs);

    return () => window.clearTimeout(timer);
  }, [match, legalPlayerId, canAutoPass, autoLoopBeat, autoplayDelayMs, mutationPending, restoring, autoProgressPaused, autoplayTick]);

  const humanResponseWindowActive =
    match?.mode === "player_vs_ai"
    && !restoring && !mutationPending && !autoProgressPaused
    && !!match
    && !match.pregame_pending
    && !match.match_complete
    && match.winner == null
    && legalPlayerId === 1
    && (match.stack?.length ?? 0) > 0
    && legalMoves.some((move) => move.type === "pass_priority")
    && !canAutoPass;

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
    <main className={`layout ${match ? "workspace-match" : "workspace-lobby"}${match?.winner != null ? " game-ended" : ""}`}>
      <header className="topbar">
        <h1>MTG Deck Testing Lab</h1>
        <p>THE PLAYTEST TABLE · Two seats. Real decisions.</p>
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

      {actionError ? <p className="operation-alert" role="alert">Match operation: {actionError}</p> : null}
      <nav className="table-navigation" aria-label="Workspace">
        <a href="#table">{match ? "01 / Table" : "01 / Play"}</a><a href="#match-controls">{match ? "02 / Actions & choices" : "02 / Matchup"}{match?.stack.length ? ` · Stack ${match.stack.length}` : ""}</a><a href="#lab-tools" aria-expanded={labOpen} onClick={() => setLabOpen(true)}>03 / Decks & lab</a>
        {match && (match.pending_mechanic_choice || match.pending_replacement_choice || match.pending_trigger_order || match.pregame_pending) ? <a className="choice-notice" href="#match-controls" role="status">Choice required · P{legalPlayerId} · {match.pending_mechanic_choice?.label ?? (match.pregame_pending ? "Opening hand" : "Review pending decision")} →</a> : null}
        {match ? <button disabled={mutationPending || restoring || !!match.match_complete || (match.winner != null && !isAiSeries(match))} onClick={() => setAutoProgressPaused((value) => !value)}>{autoProgressPaused ? "Resume automatic play" : "Pause automatic play"}</button> : null}
        {mutationPending ? <span role="status">Match operation pending...</span> : null}
      </nav>
      <section className="lab-tools" id="lab-tools" aria-label="Lab tools" hidden={!labOpen}>
        <header className="workspace-heading"><div><span className="eyebrow">The workbench</span><h2>Prepare. Review. Refine.</h2></div><button onClick={() => { setLabOpen(false); document.querySelector<HTMLAnchorElement>('a[href="#lab-tools"]')?.focus(); }}>Close lab</button></header>
        <details className="panel saved-games">
          <summary>Saved matches <span>{savedMatches.length} sessions</span></summary>
          {restoring ? <p role="status">Restoring saved session...</p> : null}
          <button disabled={mutationPending || restoring} onClick={reportAction(async () => { setSavedMatches(await api.savedMatches()); })}>Refresh saved matches</button>
          <div id="saved-match-list" style={{ display: "grid", gap: "0.5rem", maxHeight: "16rem", overflowY: "auto" }}>
            {savedMatches.slice(0, savedMatchLimit).map((saved) => <button key={saved.id} disabled={mutationPending || restoring} onClick={reportAction(() => resumeMatch(saved.id))}>Resume {saved.players.join(" vs ")} | game {saved.game_number}, turn {saved.turn} | {saved.id.slice(0, 8)}</button>)}
          </div>
          {savedMatches.length > savedMatchLimit ? <button type="button" aria-controls="saved-match-list" onClick={() => setSavedMatchLimit((limit) => limit + 3)}>Show more saved matches</button> : null}
          {savedMatchLimit > 3 && savedMatches.length > 3 ? <button type="button" aria-controls="saved-match-list" onClick={() => setSavedMatchLimit(3)}>Show fewer saved matches</button> : null}
        </details>
        <details className="panel tool-disclosure" open={!match}><summary>Deck library & import</summary><DeckPanel decks={decks} onDecksLoaded={onDecksLoaded} /></details>
        <details className="panel tool-disclosure"><summary>Simulator & diagnostics</summary><AnalyticsPanel decks={decks} /></details>
      </section>
      <section className="left-column" id="match-controls" tabIndex={-1} aria-label="Actions and choices">
        {match ? <header className="command-heading"><div><span className="eyebrow">{match.stack.length ? "Response window" : "At the table"}</span><h2>{match.winner != null ? (match.match_complete ? "Series complete" : "Between games") : match.pending_mechanic_choice || match.pending_replacement_choice || match.pending_trigger_order || match.pregame_pending ? `Decision required · P${legalPlayerId}` : `P${match.priority_player} holds priority`}</h2><p>{match.winner != null ? "This game is over. Review the result above and the series controls below." : match.pending_mechanic_choice || match.pending_replacement_choice || match.pending_trigger_order || match.pregame_pending ? "Complete the required choice below before continuing." : match.stack.length ? `${match.stack[match.stack.length - 1].label} · top of stack. Passing gives the other seat a chance to act.` : "Choose an available play, or pass priority to the other seat."}</p></div><a href="#table">Return to cards ↑</a></header> : null}
        {match ? <StackLog match={match} /> : null}
        <section className="panel" aria-label="Interactive match support preflight">
          <h3>Rules support preflight</h3>
          <p>Interactive matches are exploratory, not rules-certified. This check reports known gaps only; an empty result is not certification.</p>
          {preflightNote ? <p role="status">{preflightNote}</p> : null}
          {pendingStart && !pendingStartPersisted.current ? <p role="status">Browser persistence is unavailable. Keep this window open to recover the original pending start.</p> : null}
          {reviewTarget ? <>
            <p>{pendingStart ? "Original pending start" : "Selected configuration"}: A {decks.find(deck => deck.id === reviewTarget.deck_a_id)?.name ?? "Deck"} (#{reviewTarget.deck_a_id ?? "unsaved"}) vs B {decks.find(deck => deck.id === reviewTarget.deck_b_id)?.name ?? "Deck"} (#{reviewTarget.deck_b_id ?? "unsaved"}); {reviewTarget.mode}; seats {reviewTarget.controller_a}/{reviewTarget.controller_b}; {reviewTarget.ai_difficulty}; best-of-{reviewTarget.best_of}.</p>
            {pendingStart ? <details><summary>Original pending deck lists (not the current selectors)</summary>
              {(["a", "b"] as const).map(seat => <div key={seat}><strong>Deck {seat.toUpperCase()}</strong>
                <p>Mainboard: {reviewTarget[`deck_${seat}`].map(card => `${card.quantity} ${card.card_name}`).join("; ")}</p>
                <p>Sideboard: {(reviewTarget[`deck_${seat}_sideboard`] ?? []).map(card => `${card.quantity} ${card.card_name}`).join("; ") || "None"}</p>
              </div>)}
            </details> : null}
          </> : <p>Select both decks, then use Start to check support before creation.</p>}
          {visibleReview ? <>
            <p>{visibleReview.coverage.known_unsupported_cards.length ? "Known unsupported gaps (mainboards and sideboards):" : "No known unsupported gaps were reported in these lists. Coverage is incomplete; this is still exploratory, not certification."}</p>
            <ul style={{ maxHeight: "16rem", overflowY: "auto" }}>
              {visibleReview.coverage.known_unsupported_cards.map((card, index) => <li key={`${card.deck}:${card.card_name}:${index}`}>
                <strong>Deck {card.deck}: {card.card_name}</strong><p>Mechanics: {card.mechanics.join(", ") || "None reported"}</p>
                {card.static_clause_gaps?.map((gap, gapIndex) => <p key={gapIndex}>
                  Face: {gap.face_name}; index: {gap.face_index ?? "none"}; clause: <code>{gap.clause}</code>; condition: {gap.condition}; reasons: {gap.reasons.join(", ")}
                </p>)}
              </li>)}
            </ul>
            <label><input type="checkbox" aria-label="Acknowledge exploratory interactive match" disabled={preflightChecking || mutationPending || restoring}
              checked={visibleReview.exploratoryAcknowledged} onChange={event => {
                const checked = event.currentTarget.checked;
                setStartReview(review => review && review.signature === reviewSignature ? { ...review, exploratoryAcknowledged: checked } : null);
              }} /> I understand this exact deck pair and configuration is exploratory, not rules-certified.</label>
          </> : null}
          {pendingStart ? <button disabled={restoring || mutationPending || preflightChecking || (!!visibleReview && !visibleReview.exploratoryAcknowledged)} onClick={reportAction(() => startMatch(true))}>Recover pending match start</button> : null}
        </section>
        <fieldset disabled={mutationPending || restoring} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <Controls
          decks={decks}
          selectedA={selectedA}
          selectedB={selectedB}
          setSelectedA={value => { invalidateStartReview(); setSelectedA(value); }}
          setSelectedB={value => { invalidateStartReview(); setSelectedB(value); }}
          startMode={mode}
          setStartMode={value => { invalidateStartReview(); setMode(value); }}
          difficulty={difficulty}
          setDifficulty={value => { invalidateStartReview(); setDifficulty(value); }}
          bestOf={bestOf}
          setBestOf={value => { invalidateStartReview(); setBestOf(value); }}
          onStart={reportAction(() => startMatch())}
          startDisabled={restoring || mutationPending || preflightChecking || !!pendingStart || !selectedStart || (!!visibleReview && !visibleReview.exploratoryAcknowledged)}
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
          combatDraft={combatDraft}
          onCombatDraftChange={setCombatDraft}
        />
        </fieldset>
      </section>

      <section className="right-column" id="table" aria-label="Card table">
        {match ? <AiHandDebug match={match} /> : null}
        {match ? (
          <>
            {match.winner != null ? <section className="game-result" role="status" aria-label="Game result">
              <span className="eyebrow">{match.match_complete ? "Series complete" : "Between games"}</span>
              <h2>Game {match.game_number ?? 1} over: {match.winner === 0 ? "Draw" : `P${match.winner} wins`}</h2>
              <p>Series score: P1 {match.score["1"] ?? 0} - {match.score["2"] ?? 0} P2 · Best of {match.best_of ?? 3}.</p>
              <p>{match.match_complete ? "The series is finished." : isAiSeries(match) ? "AI series continues when automatic play is running." : "Game actions are stopped. Sideboard and choose the next game when ready."}</p>
              {!match.match_complete ? <a href="#match-controls">Sideboard & next game</a> : null}
            </section> : null}
            <fieldset disabled={mutationPending || restoring || match.winner != null} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
              <Battlefield match={match} legalMoves={legalMoves} actingPlayerId={legalPlayerId} onCardAction={reportAction(onCardAction)} combatDraft={combatDraft} onCombatDraftChange={setCombatDraft} />
            </fieldset>
          </>
        ) : (
          <article className="panel empty-state">
            <span className="eyebrow">Your next matchup starts here</span>
            <h2>Every card.<br />A decision.</h2>
            <p>A focused table for testing your list, learning a matchup, and playing the next line.</p>
            <div className="lobby-steps"><span><b>01</b> Choose two decks</span><span><b>02</b> Set your seats</span><span><b>03</b> Take the table</span></div>
            <a href="#lab-tools" onClick={() => setLabOpen(true)}>Build your library · Import & saved matches ↗</a>
          </article>
        )}
      </section>
    </main>
  );
}
