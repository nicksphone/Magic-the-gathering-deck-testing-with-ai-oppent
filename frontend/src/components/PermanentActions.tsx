import { useState } from "react";
import type { LegalMove } from "../types";

type Props = { moves: LegalMove[]; playerId: number; onAction: (playerId: number, action: Record<string, unknown>) => void };
const handled = new Set(["cast_spell", "cast_spell_restricted", "cycle_card", "play_land", "activate_loyalty", "equip", "activate_ability", "crew", "ninjutsu", "pass_priority", "attack", "attack_restricted", "block", "keep_hand", "mulligan", "choose_mechanic", "choose_replacement", "choose_trigger_order"]);

function AbilityAction({ move, playerId, onAction }: Props & { move: LegalMove }) {
  const [targets, setTargets] = useState<Record<string, unknown>>({});
  const [advanced, setAdvanced] = useState("");
  let combined = targets;
  let inputError = "";
  if (advanced.trim()) {
    try {
      const parsed = JSON.parse(advanced);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Expected a JSON object");
      combined = { ...targets, ...parsed };
    } catch { inputError = "Advanced choices must be a valid JSON object."; }
  }
  const unsupportedCost = move.mana_cost?.toUpperCase().includes("{X}");
  const hints = move.target_hints;
  const options = [...new Map([...(hints?.creature_targets ?? []), ...(hints?.planeswalker_targets ?? []), ...(hints?.permanent_targets ?? []), ...(hints?.graveyard_creature_targets ?? []), ...(hints?.graveyard_permanent_targets ?? []), ...(hints?.land_targets ?? []), ...(hints?.artifact_targets ?? []), ...(hints?.enchantment_targets ?? []), ...(hints?.noncreature_permanent_targets ?? []), ...(hints?.aura_targets ?? []), ...(move.targets ?? [])].map((target) => [target.id, target])).values()];
  return <article className="cast-card-box">
    <strong>{move.card_name}: {move.ability_label}</strong>
    <small>{move.mana_cost}</small>
    {hints?.player_targets?.length ? <select aria-label="Ability target player" value={String(targets.target_player ?? "")} onChange={(event) => setTargets({ ...targets, target_player: event.target.value ? Number(event.target.value) : undefined })}>
      <option value="">Target player</option>{hints.player_targets.map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}
    </select> : null}
    {options.length ? <select aria-label="Ability target permanent" value={String(targets.target_card_id ?? "")} onChange={(event) => setTargets({ ...targets, target_card_id: event.target.value || undefined })}>
      <option value="">Target permanent</option>{options.map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}
    </select> : null}
    {hints?.stack_targets?.length ? <select aria-label="Ability stack target" onChange={(event) => setTargets({ ...targets, target_stack_id: event.target.value })}>
      <option value="">Target stack item</option>{hints.stack_targets.map((target) => <option key={target.id} value={target.id}>{target.label}</option>)}
    </select> : null}
    {hints?.modes?.length ? <select aria-label="Ability mode" onChange={(event) => setTargets({ ...targets, mode_text: event.target.value })}>
      <option value="">Choose mode</option>{hints.modes.map((mode) => <option key={mode} value={mode}>{mode}</option>)}
    </select> : null}
    {hints?.requires_x_value ? <label>X<input type="number" min={0} value={Number(targets.x_value ?? 0)} onChange={(event) => setTargets({ ...targets, x_value: Math.max(0, Number(event.target.value)) })} /></label> : null}
    <details><summary>Advanced choices</summary><p>Enter additional target/mode choices as JSON. The engine validates them before costs are paid.</p><pre>{JSON.stringify(hints?.choice_schema ?? {}, null, 2)}</pre><textarea aria-label="Advanced ability choices" value={advanced} onChange={(event) => setAdvanced(event.target.value)} /></details>
    {inputError ? <p role="alert">{inputError}</p> : null}
    {unsupportedCost ? <p role="alert">Variable activated costs are not implemented; this activation is disabled.</p> : null}
    <button disabled={Boolean(inputError || unsupportedCost)} onClick={() => onAction(playerId, { type: "activate_ability", card_id: move.card_id, ability_index: move.ability_index, targets: combined })}>Activate {move.card_name}</button>
  </article>;
}

function CrewAction({ move, playerId, onAction }: Props & { move: LegalMove }) {
  const [selected, setSelected] = useState<string[]>([]);
  const power = (move.crew_candidates ?? []).filter((candidate) => selected.includes(candidate.id)).reduce((sum, candidate) => sum + Math.max(0, candidate.power), 0);
  return <article className="cast-card-box">
    <strong>{move.card_name} - Crew {move.crew_value}</strong>
    {(move.crew_candidates ?? []).map((candidate) => <label key={candidate.id}><input type="checkbox" checked={selected.includes(candidate.id)} onChange={(event) => setSelected((ids) => event.target.checked ? [...ids, candidate.id] : ids.filter((id) => id !== candidate.id))} />{candidate.name} ({candidate.power} power)</label>)}
    <small>Selected power: {power}</small>
    <button disabled={power < (move.crew_value ?? 0)} onClick={() => onAction(playerId, { type: "crew", card_id: move.card_id, crew_card_ids: selected })}>Crew {move.card_name}</button>
  </article>;
}

export function PermanentActions(props: Props) {
  const actions = props.moves.filter((move) => ["activate_ability", "crew", "ninjutsu"].includes(move.type));
  const missing = props.moves.filter((move) => !handled.has(move.type));
  return <>
    {actions.length ? <div className="hand-row" aria-label="Permanent and combat abilities">{actions.map((move) => {
      const key = `${move.type}:${move.card_id}:${move.ability_index}:${move.return_card_id}`;
      if (move.type === "activate_ability") return <AbilityAction key={key} {...props} move={move} />;
      if (move.type === "crew") return <CrewAction key={key} {...props} move={move} />;
      return <button key={key} onClick={() => props.onAction(props.playerId, { type: "ninjutsu", card_id: move.card_id, return_card_id: move.return_card_id })}>Ninjutsu {move.card_name}: return {move.return_card_id}</button>;
    })}</div> : null}
    {missing.map((move, index) => <p role="alert" key={`${move.type}:${index}`}>No control is implemented for legal action: {move.type}. Do not advance if you need this action.</p>)}
  </>;
}
