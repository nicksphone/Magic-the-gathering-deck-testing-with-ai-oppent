import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Battlefield } from "../src/components/Battlefield";
import { Controls } from "../src/components/Controls";
import type { LegalMove, MatchState } from "../src/types";

const BASE = "http://127.0.0.1:10199";
declare global { interface Window { fixtureState?: MatchState; fixtureActions?: unknown[] } }

function Harness() {
  const [match, setMatch] = useState<MatchState | null>(null);
  const [moves, setMoves] = useState<LegalMove[]>([]);
  const [actor, setActor] = useState(2);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  async function load(next: MatchState) {
    const response = await fetch(`${BASE}/matches/${next.id}/legal-moves`);
    if (!response.ok) throw new Error(`Legal moves HTTP ${response.status}`);
    const legal = await response.json();
    setMatch(next); setMoves(legal.moves); setActor(legal.player_id);
    window.fixtureState = next; setReady(true);
  }
  async function reset(pregame = false, modal = false, modalMana = 3, faceKind = "") {
    setReady(false); setError(""); window.fixtureActions = [];
    const response = await fetch(BASE + "/fixture?pregame=" + pregame + "&modal=" + modal + "&modal_mana=" + modalMana + "&face_kind=" + faceKind, { method: "POST" });
    if (!response.ok) throw new Error(`Fixture HTTP ${response.status}`);
    await load(await response.json());
  }
  useEffect(() => { reset().catch((failure) => setError(String(failure))); }, []);
  async function act(playerId: number, action: Record<string, unknown>) {
    if (!match) throw new Error("Missing fixture match");
    setReady(false);
    window.fixtureActions?.push({ player_id: playerId, action });
    const response = await fetch(`${BASE}/matches/${match.id}/action`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ player_id: playerId, action }) });
    if (!response.ok) throw new Error(`Action HTTP ${response.status}`);
    const next = await response.json();
    await load(next);
    return next as MatchState;
  }
  return <>
    <p data-testid="ready">{ready ? "Ready" : "Loading"}</p>
    <button onClick={() => reset().catch((failure) => setError(String(failure)))}>Reset Fixture</button>
    <button onClick={() => reset(true).catch((failure) => setError(String(failure)))}>Pregame Fixture</button>
    <button onClick={() => reset(false, true).catch((failure) => setError(String(failure)))}>Modal Fixture</button>
    <button onClick={() => reset(false, true, 5).catch((failure) => setError(String(failure)))}>Modal Choice Fixture</button>
    <button onClick={() => reset(false, false, 3, "land").catch((failure) => setError(String(failure)))}>Land Face Fixture</button>
    <button onClick={() => reset(false, false, 3, "adventure").catch((failure) => setError(String(failure)))}>Adventure Fixture</button>
    <button onClick={() => reset(false, false, 3, "trigger").catch((failure) => setError(String(failure)))}>Trigger Fixture</button>
    <button onClick={async () => { try { if (!match) return; const next = await act(match.priority_player, { type: "pass_priority" }); await act(next.priority_player, { type: "pass_priority" }); } catch (failure) { setError(String(failure)); } }}>Resolve Stack</button>
    {error ? <p role="alert">{error}</p> : null}
    {match ? <Controls
      decks={[]} selectedA={null} selectedB={null}
      setSelectedA={() => {}} setSelectedB={() => {}}
      startMode="human_vs_human" setStartMode={() => {}}
      difficulty="master" setDifficulty={() => {}} bestOf={3} setBestOf={() => {}}
      onStart={() => {}} onPassPriority={() => {}}
      onKeepHand={(ids) => { act(actor, { type: "keep_hand", bottom_card_ids: ids }).catch((failure) => setError(String(failure))); }}
      onMulligan={() => { act(actor, { type: "mulligan" }).catch((failure) => setError(String(failure))); }}
      onNextStep={() => {}} onAutoplayTick={() => {}}
      autoplayDelayMs={1800} setAutoplayDelayMs={() => {}}
      onSubmitBlocks={() => {}} onSubmitAttack={() => {}}
      onApplySideboard={() => {}} onNextGame={() => {}} onSetPriorityStops={() => {}}
      onChooseReplacement={() => {}} onChooseTriggerOrder={() => {}}
      onChooseTriggerTarget={(stackId, targetCardId) => { act(actor, { type: "choose_trigger_target", stack_id: stackId, target_card_id: targetCardId }).catch((failure) => setError(String(failure))); }}
      onChooseMechanic={() => {}}
      responseCountdown={null} autoResponsePaused={false} onToggleAutoResponsePause={() => {}}
      legalMoves={moves} match={match} actingPlayerId={actor}
    /> : null}
    {match ? <Battlefield match={match} legalMoves={moves} actingPlayerId={actor} onCardAction={(playerId, action) => { act(playerId, action).catch((failure) => setError(String(failure))); }} /> : null}
  </>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
