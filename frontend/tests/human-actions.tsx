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
  async function nextGame(playFirst: boolean) {
    if (!match?.next_play_draw_chooser) throw new Error("No play/draw chooser");
    setReady(false);
    window.fixtureActions?.push({ type: "next_game", player_id: match.next_play_draw_chooser, play_first: playFirst });
    const response = await fetch(`${BASE}/matches/${match.id}/next-game`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: match.next_play_draw_chooser, play_first: playFirst }),
    });
    if (!response.ok) throw new Error(`Next game HTTP ${response.status}`);
    await load(await response.json());
  }
  return <>
    <p data-testid="ready">{ready ? "Ready" : "Loading"}</p>
    <button onClick={() => reset().catch((failure) => setError(String(failure)))}>Reset Fixture</button>
    <button onClick={() => reset(false, false, 3, "modal_targetless").catch((failure) => setError(String(failure)))}>Modal Targetless Fixture</button>
    <button onClick={() => reset(false, false, 3, "modal_two_targets").catch((failure) => setError(String(failure)))}>Modal Two Targets Fixture</button>
    <button onClick={() => reset(false, false, 3, "modal_same_kind").catch((failure) => setError(String(failure)))}>Modal Same Kind Fixture</button>
    <button onClick={() => reset(false, false, 3, "each_player_discard").catch((failure) => setError(String(failure)))}>Each Player Discard Fixture</button>
    <button onClick={() => reset(false, false, 3, "revealed_discard").catch((failure) => setError(String(failure)))}>Revealed Discard Fixture</button>
    <button onClick={() => reset(false, false, 3, "thoughtseize").catch((failure) => setError(String(failure)))}>Thoughtseize Fixture</button>
    <button onClick={() => reset(false, false, 3, "duress").catch((failure) => setError(String(failure)))}>Duress Fixture</button>
    <button onClick={() => reset(true).catch((failure) => setError(String(failure)))}>Pregame Fixture</button>
    <button onClick={() => reset(false, true).catch((failure) => setError(String(failure)))}>Modal Fixture</button>
    <button onClick={() => reset(false, true, 5).catch((failure) => setError(String(failure)))}>Modal Choice Fixture</button>
    <button onClick={() => reset(false, false, 3, "land").catch((failure) => setError(String(failure)))}>Land Face Fixture</button>
    <button onClick={() => reset(false, false, 3, "conditional_land").catch((failure) => setError(String(failure)))}>Conditional Land Fixture</button>
    <button onClick={() => reset(false, false, 3, "conditional_land_effect").catch((failure) => setError(String(failure)))}>Conditional Land Effect Fixture</button>
    <button onClick={() => reset(false, false, 3, "adventure").catch((failure) => setError(String(failure)))}>Adventure Fixture</button>
    <button onClick={() => reset(false, false, 3, "trigger").catch((failure) => setError(String(failure)))}>Trigger Fixture</button>
    <button onClick={() => reset(false, false, 3, "damage_trigger").catch((failure) => setError(String(failure)))}>Damage Trigger Fixture</button>
    <button onClick={() => reset(false, false, 3, "player_hexproof").catch((failure) => setError(String(failure)))}>Player Hexproof Fixture</button>
    <button onClick={() => reset(false, false, 3, "cast_trigger").catch((failure) => setError(String(failure)))}>Cast Trigger Fixture</button>
    <button onClick={() => reset(false, false, 3, "alternative_target").catch((failure) => setError(String(failure)))}>Alternative Target Fixture</button>
    <button onClick={() => reset(false, false, 3, "variable_life_x").catch((failure) => setError(String(failure)))}>Variable Life X Fixture</button>
    <button onClick={() => reset(false, false, 3, "first_strike_window").catch((failure) => setError(String(failure)))}>First Strike Fixture</button>
    <button onClick={() => reset(false, false, 3, "combat_damage_assignment").catch((failure) => setError(String(failure)))}>Damage Assignment Fixture</button>
    <button onClick={() => reset(false, false, 3, "shared_trample").catch((failure) => setError(String(failure)))}>Shared Trample Fixture</button>
    <button onClick={() => reset(false, false, 3, "banding_damage").catch((failure) => setError(String(failure)))}>Banding Damage Fixture</button>
    <button onClick={() => reset(false, false, 3, "attacking_band").catch((failure) => setError(String(failure)))}>Attacking Band Fixture</button>
    <button onClick={() => reset(false, false, 3, "iteration").catch((failure) => setError(String(failure)))}>Iteration Fixture</button>
    <button onClick={() => reset(false, false, 3, "company").catch((failure) => setError(String(failure)))}>Company Fixture</button>
    <button onClick={() => reset(false, false, 3, "search").catch((failure) => setError(String(failure)))}>Search Fixture</button>
    <button onClick={() => reset(false, false, 3, "draw_replacement").catch((failure) => setError(String(failure)))}>Draw Replacement Fixture</button>
    <button onClick={() => reset(false, false, 3, "nonland_mana").catch((failure) => setError(String(failure)))}>Nonland Mana Fixture</button>
    <button onClick={() => reset(false, false, 3, "draw_cap").catch((failure) => setError(String(failure)))}>Draw Cap Fixture</button>
    <button onClick={() => reset(false, false, 3, "bo3").catch((failure) => setError(String(failure)))}>BO3 Fixture</button>
    <button onClick={async () => { try { if (!match) return; const next = await act(match.priority_player, { type: "pass_priority" }); await act(next.priority_player, { type: "pass_priority" }); } catch (failure) { setError(String(failure)); } }}>Resolve Stack</button>
    {error ? <p role="alert">{error}</p> : null}
    {match ? <Controls
      decks={[]} selectedA={null} selectedB={null}
      setSelectedA={() => {}} setSelectedB={() => {}}
      startMode="human_vs_human" setStartMode={() => {}}
      difficulty="master" setDifficulty={() => {}} bestOf={3} setBestOf={() => {}}
      onStart={() => {}} onPassPriority={() => { act(actor, { type: "pass_priority" }).catch((failure) => setError(String(failure))); }}
      onKeepHand={(ids) => { act(actor, { type: "keep_hand", bottom_card_ids: ids }).catch((failure) => setError(String(failure))); }}
      onMulligan={() => { act(actor, { type: "mulligan" }).catch((failure) => setError(String(failure))); }}
      onNextStep={() => {}} onAutoplayTick={() => {}}
      autoplayDelayMs={1800} setAutoplayDelayMs={() => {}}
      onSubmitBlocks={(blocks) => { act(actor, { type: "block", blocks }).catch((failure) => setError(String(failure))); }}
      onSubmitAttack={(attackers, attackTargets, bands) => { act(actor, { type: "attack", attackers, attack_targets: attackTargets, bands }).catch((failure) => setError(String(failure))); }}
      onApplySideboard={() => {}} onNextGame={(playFirst) => { nextGame(Boolean(playFirst)).catch((failure) => setError(String(failure))); }} onSetPriorityStops={() => {}}
      onChooseReplacement={(sourceId) => { act(actor, { type: "choose_replacement", replacement_source_id: sourceId }).catch((failure) => setError(String(failure))); }} onChooseTriggerOrder={() => {}}
      onChooseTriggerTarget={(stackId, targetCardId, targetPlayer) => { act(actor, { type: "choose_trigger_target", stack_id: stackId, ...(targetCardId ? { target_card_id: targetCardId } : { target_player: targetPlayer }) }).catch((failure) => setError(String(failure))); }}
      onChooseOptionalEffect={(stackId, accept) => { act(actor, { type: "choose_optional_effect", stack_id: stackId, accept }).catch((failure) => setError(String(failure))); }}
      onChooseMechanic={(playerId, action) => { act(playerId, action).catch((failure) => setError(String(failure))); }}
      responseCountdown={null} autoResponsePaused={false} onToggleAutoResponsePause={() => {}}
      legalMoves={moves} match={match} actingPlayerId={actor}
    /> : null}
    {match ? <Battlefield match={match} legalMoves={moves} actingPlayerId={actor} onCardAction={(playerId, action) => { act(playerId, action).catch((failure) => setError(String(failure))); }} /> : null}
  </>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
