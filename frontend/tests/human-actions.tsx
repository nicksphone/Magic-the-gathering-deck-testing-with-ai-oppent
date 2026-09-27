import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Battlefield } from "../src/components/Battlefield";
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
  async function reset() {
    setReady(false); setError(""); window.fixtureActions = [];
    const response = await fetch(`${BASE}/fixture`, { method: "POST" });
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
    <button onClick={async () => { try { if (!match) return; const next = await act(match.priority_player, { type: "pass_priority" }); await act(next.priority_player, { type: "pass_priority" }); } catch (failure) { setError(String(failure)); } }}>Resolve Stack</button>
    {error ? <p role="alert">{error}</p> : null}
    {match ? <Battlefield match={match} legalMoves={moves} actingPlayerId={actor} onCardAction={(playerId, action) => { act(playerId, action).catch((failure) => setError(String(failure))); }} /> : null}
  </>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
