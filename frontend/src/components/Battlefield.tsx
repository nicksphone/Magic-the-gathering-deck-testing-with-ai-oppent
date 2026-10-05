import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { resolveCardMediaUrl } from "../api/client";
import { cardStates, groupBattlefield, landPlayHint, phases, phaseIndex, type LandPile } from "./table-model";
import type { LegalMove, MatchState, PlayerView } from "../types";
import { PermanentActions } from "./PermanentActions";
import { CardRail } from "./CardRail";
import { CardArt } from "./CardArt";

type Props = {
  match: MatchState;
  legalMoves: LegalMove[];
  actingPlayerId?: number;
  onCardAction: (playerId: number, action: Record<string, unknown>) => void;
};

function restrictedMana(player: PlayerView) {
  return player.restricted_mana_pool?.length ? <span className="restricted-mana">
    Restricted: {player.restricted_mana_pool.map((lot) => {
      const purposes = [lot.rule.cast_types?.length ? `${lot.rule.cast_types.join("/")} spells` : "",
        lot.rule.activate_types?.length ? `${lot.rule.activate_types.join("/")} abilities` : ""].filter(Boolean).join(" or ");
      return `${lot.amount} ${lot.color}${lot.snow ? " (snow)" : ""}: ${lot.rule.unsupported ? "unsupported spending rule" : purposes}`;
    }).join("; ")}
  </span> : null;
}

type HoverPreview = {
  name: string;
  manaCost?: string;
  oracleText?: string;
  imageUri?: string;
  types?: string[];
  power?: number | null;
  toughness?: number | null;
  loyalty?: number | null;
  basePower?: number | null;
  baseToughness?: number | null;
  printedPower?: string | null;
  printedToughness?: string | null;
  damage?: number;
  keywords?: string[];
  colors?: string[];
  counters?: Record<string, number>;
  faces?: PlayerView["hand"][number]["card_faces"];
};

type ManaSymbol = "W" | "U" | "B" | "R" | "G" | "C";

function manaSummary(lands: LandPile[]): string {
  const counts: Record<string, number> = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
  for (const pile of lands) for (const color of pile.colors) counts[color] = (counts[color] ?? 0) + pile.untapped * (pile.amounts[color] ?? 1);
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([c, n]) => `${c}:${n}`)
    .join("  ");
}

function manaPoolPips(pool: Record<string, number>, snowPool: Record<string, number> = {}): { symbol: ManaSymbol; count: number; snow: number }[] {
  const order: ManaSymbol[] = ["W", "U", "B", "R", "G", "C"];
  return order
    .map((symbol) => ({ symbol, count: Number(pool[symbol] ?? 0), snow: Number(snowPool[symbol] ?? 0) }))
    .filter((entry) => entry.count > 0);
}

export function Battlefield({ match, legalMoves: authoritativeMoves, onCardAction, actingPlayerId = match.priority_player }: Props) {
  const humanActor = (match.controllers?.[String(actingPlayerId)] ?? "human") === "human";
  const viewerSeat = humanActor ? actingPlayerId : ([1, 2].find((seat) => match.controllers?.[String(seat)] === "human") ?? 1);
  const opponentSeat = viewerSeat === 1 ? 2 : 1;
  const legalMoves = useMemo(() => humanActor ? authoritativeMoves : [], [humanActor, authoritativeMoves]);
  const p1 = match.players[String(viewerSeat)];
  const p2 = match.players[String(opponentSeat)];
  const p1Groups = useMemo(() => groupBattlefield(p1.battlefield), [p1.battlefield]);
  const p2Groups = useMemo(() => groupBattlefield(p2.battlefield), [p2.battlefield]);
  const p1ManaPool = useMemo(() => manaPoolPips(p1.mana_pool, p1.snow_mana_pool), [p1.mana_pool, p1.snow_mana_pool]);
  const p2ManaPool = useMemo(() => manaPoolPips(p2.mana_pool, p2.snow_mana_pool), [p2.mana_pool, p2.snow_mana_pool]);
  const battlefieldCount = p1Groups.nonLands.length + p1Groups.lands.length + p2Groups.nonLands.length + p2Groups.lands.length;
  const battlefieldDensityClass =
    battlefieldCount >= 16 ? "battlefield-packed" : battlefieldCount >= 9 ? "battlefield-dense" : battlefieldCount >= 5 ? "battlefield-comfort" : "battlefield-open";
  const castMoves = useMemo(() => legalMoves.filter((m) => m.type === "cast_spell"), [legalMoves]);
  const cycleMoves = useMemo(() => legalMoves.filter((m) => m.type === "cycle_card"), [legalMoves]);
  const foretellMoves = useMemo(() => legalMoves.filter((m) => m.type === "foretell"), [legalMoves]);
  const playLandMoves = useMemo(() => legalMoves.filter((m) => m.type === "play_land"), [legalMoves]);
  const restrictedCastMoves = useMemo(() => legalMoves.filter((m) => m.type === "cast_spell_restricted"), [legalMoves]);
  const loyaltyMoves = useMemo(() => legalMoves.filter((m) => m.type === "activate_loyalty"), [legalMoves]);
  const equipMoves = useMemo(() => legalMoves.filter((m) => m.type === "equip"), [legalMoves]);
  const manaMoves = useMemo(() => legalMoves.filter((m) => m.type === 'activate_mana_ability'), [legalMoves]);
  const [targets, setTargets] = useState<Record<string, Record<string, unknown>>>({});
  const [costChoice, setCostChoice] = useState<Record<string, string>>({});
  const [costCards, setCostCards] = useState<Record<string, string[]>>({});
  const [hybridChoice, setHybridChoice] = useState<Record<string, string>>({});
  const [faceChoices, setFaceChoices] = useState<Record<string, number>>({});
  const [cycleChoices, setCycleChoices] = useState<Record<string, number>>({});
  const [divideInputs, setDivideInputs] = useState<Record<string, Record<string, number>>>({});
  const [landTapCounts, setLandTapCounts] = useState<Record<string, number>>({});
  const [landSelections, setLandSelections] = useState<Record<string, string>>({});
  const [transientPreview, setHoverPreview] = useState<HoverPreview | null>(null);
  const [pinnedPreview, setPinnedPreview] = useState<HoverPreview | null>(null);
  const previewOrigin = useRef<HTMLElement | null>(null);
  const hoverPreview = pinnedPreview ?? transientPreview;
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") {
      previewOrigin.current?.focus({preventScroll:true}); previewOrigin.current = null;
      setHoverPreview(null); setPinnedPreview(null);
    } };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  useEffect(() => {
    setTargets({});
    setCostChoice({});
    setCostCards({});
    setHybridChoice({});
    setFaceChoices({});
    setCycleChoices({});
    setDivideInputs({});
    setLandSelections({});
    setLandTapCounts({});
    setHoverPreview(null);
    setPinnedPreview(null);
    previewOrigin.current = null;
  }, [match.id, match.game_number, viewerSeat]);
  const canManualTap = humanActor && match.winner === null && !match.match_complete && match.priority_player === viewerSeat && !match.pregame_pending
    && !match.pending_mechanic_choice && !match.pending_replacement_choice && !match.pending_trigger_order
    && match.step !== "cleanup";
  const playableCards = [...new Map([...p1.hand, ...legalMoves.filter((move) => move.card_view && (move.type === "cast_spell" || move.type === "play_land")).map((move) => move.card_view!)].map((card) => [card.id, card])).values()];

  function previewFromCard(card: MatchState["players"]["1"]["battlefield"][number] | MatchState["players"]["1"]["hand"][number]): HoverPreview {
    return {
      name: card.name,
      manaCost: card.mana_cost,
      oracleText: card.oracle_text,
      imageUri: card.image_uri,
      types: card.types,
      power: "power" in card ? card.power : null,
      toughness: "toughness" in card ? card.toughness : null,
      loyalty: "loyalty" in card ? card.loyalty : null,
      basePower: card.base_power,
      baseToughness: card.base_toughness,
      printedPower: card.printed_power,
      printedToughness: card.printed_toughness,
      damage: card.damage_marked,
      keywords: card.keywords,
      colors: card.colors,
      counters: card.counters,
      faces: card.card_faces,
    };
  }

  function zoneTray(seat: number, zone: "graveyard" | "exile", cards: typeof p1.graveyard, count: number) {
    return <details className="graveyard-tray">
      <summary aria-label={`Player ${seat} ${zone}`}>{zone === "graveyard" ? "GY" : "EX"} {count}</summary>
      <div className="graveyard-tray-list">
        {cards.length ? cards.map((card) => <button
          key={card.id}
          type="button"
          onMouseEnter={() => setHoverPreview(previewFromCard(card))}
          onMouseLeave={() => setHoverPreview(null)}
          onFocus={() => setHoverPreview(previewFromCard(card))}
          onBlur={() => setHoverPreview(null)}
          onClick={event => { previewOrigin.current = event.currentTarget; setPinnedPreview(previewFromCard(card)); }}
        >
          {card.name}{card.mana_cost ? <small>{card.mana_cost}</small> : null}
        </button>) : count === 0 ? <span>Empty</span> : null}
        {count > cards.length ? <span>{count - cards.length} face-down card(s)</span> : null}
      </div>
    </details>;
  }

  function statusBadges(card: typeof p1.battlefield[number]) {
    const selected = Object.values(targets).some(choice => choice.target_card_id === card.id || (Array.isArray(choice.target_card_ids) && choice.target_card_ids.includes(card.id)));
    const targetable = legalMoves.some(move => move.target_card_id === card.id || move.targets?.some(target => target.id === card.id) || Object.entries(move.target_hints ?? {}).some(([key, list]) => key.endsWith("_targets") && Array.isArray(list) && list.some(target => typeof target === "object" && target !== null && "id" in target && target.id === card.id)));
    return <div className="card-badges">
      {cardStates(card, match, targetable, selected).map(state => <span key={state} className={`badge badge-${state.toLowerCase().replaceAll(" ", "-")}`}>{state}</span>)}
      {card.damage_marked ? <span className="badge">Damage {card.damage_marked}</span> : null}
      {Object.entries(card.counters ?? {}).filter(([name, n]) => !name.startsWith("__") && n > 0).map(([name,n]) => <span className="badge" key={name}>{name} ×{n}</span>)}
      {card.keywords?.length ? <small>{card.keywords.join(" · ")}</small> : null}
    </div>;
  }

  function handFace(card: typeof p1.hand[number]) {
    return <button type="button" className="hand-face" aria-label={`Inspect ${card.name}`} onClick={event => { previewOrigin.current = event.currentTarget; setPinnedPreview(previewFromCard(card)); }}>
      <CardArt uri={card.image_uri} name={card.name} />
      <strong>{card.name}</strong><small>{card.mana_cost || card.type_line || card.types.join(" ")}</small>
    </button>;
  }

  function castAction(cardId: string, selectedFaceIndex?: number) {
    const t = targets[cardId] ?? {};
    const move = castMoves.find((candidate) => candidate.card_id === cardId &&
      (candidate.selected_face_index ?? 0) === (selectedFaceIndex ?? 0) &&
      (!costChoice[cardId] || candidate.cost_options?.some((option) => option.id === costChoice[cardId])));
    const selectedModes = Array.isArray(t.mode_texts) ? t.mode_texts as string[] : [];
    const modeTargets = (t.mode_targets ?? {}) as Record<string, Record<string, unknown>>;
    const announced = move?.target_hints?.choose_two_modes && selectedModes.length === 2
      ? { ...t, target_card_id: undefined, target_player: undefined, target_stack_id: undefined,
          mode_targets: Object.fromEntries(selectedModes.map((mode) => [mode, modeTargets[mode] ?? {}])) }
      : t;
    const optionId = costChoice[cardId] || move?.cost_options?.[0]?.id;
    const symbols = move?.cost_options?.find((option) => option.id === optionId)?.hybrid_symbols ?? [];
    const branches = symbols.map((_, index) => hybridChoice[`${cardId}:${selectedFaceIndex ?? 0}:${optionId}:${index}`] ?? "");
    onCardAction(viewerSeat, {
      type: "cast_spell",
      card_id: cardId,
      targets: announced,
      cost_choice: optionId ? {
        id: optionId,
        discard_card_ids: costCards[`${cardId}:${optionId}:discard_card_ids`],
        sacrifice_card_ids: costCards[`${cardId}:${optionId}:sacrifice_card_ids`],
      } : undefined,
      hybrid_choices: branches.length && branches.every(Boolean) ? branches : undefined,
      selected_face_index: selectedFaceIndex,
      from_exile: move?.from_exile,
      from_library: move?.from_library,
      from_graveyard: move?.from_graveyard,
    });
  }

  function setModeTarget(cardId: string, mode: string, selection: Record<string, unknown>) {
    setTargets((prev) => {
      const previous = (prev[cardId]?.mode_targets ?? {}) as Record<string, Record<string, unknown>>;
      return { ...prev, [cardId]: { ...prev[cardId], mode_targets: { ...previous, [mode]: selection } } };
    });
  }

  return (
    <section className={`panel battlefield ${battlefieldDensityClass}`} data-match-revision={match.revision}>
      {manaMoves.length > 0 ? <details className="zone-tray">
        <summary>Mana abilities ({manaMoves.length})</summary>
        {manaMoves.map(move => <div className="row" key={`${move.card_id}-mana-${move.ability_index}`}>
          <span>{move.card_name}: {move.cost_text}</span>
          {Object.entries(move.outputs ?? {}).map(([color, amount]) => <button key={color} title={move.label}
            onClick={() => onCardAction(viewerSeat, {type: 'activate_mana_ability', card_id: move.card_id,
              ability_index: move.ability_index, color})}>
            Add {amount} {color}
          </button>)}
        </div>)}
      </details> : null}
      <header>
        <div>
          <h2>Battlefield</h2>
          <p>
            Turn {match.turn} | {match.step.replaceAll("_", " ")} | Priority: P{match.priority_player}
            {match.step === "combat_damage" && match.combat_damage_stage === "first" ? " | First-strike damage" : ""}
            {match.step === "combat_damage" && match.combat_damage_stage === "regular" ? " | Regular damage" : ""}
            {match.game_number ? ` | Game ${match.game_number}` : ""}
            {match.day_night && match.day_night !== "none" ? ` | ${match.day_night}` : ""}
          </p>
        </div>
        <div className="life-counters">
          <span>P{opponentSeat} Life: {p2.life}</span>
          <span>P{viewerSeat} Life: {p1.life}</span>
        </div>
      </header>

      <ol className="phase-track" aria-label="Turn progression">{phases.map((phase, index) => <li key={phase} aria-current={phaseIndex(match.step) === index ? "step" : undefined}>{phase}</li>)}</ol>

      <div className="player-row opponent">
        <div className="zone-meta">
          <strong className="seat-label">P{opponentSeat} · Opponent <b>{p2.life}</b> life</strong>
          <span className="seat-state">{match.active_player === opponentSeat ? "◆ Active turn" : "◇ Waiting"}{match.priority_player === opponentSeat ? " · Priority" : ""}</span>
          <span>Library {p2.library_count}</span>
          {zoneTray(opponentSeat, "graveyard", p2.graveyard, p2.graveyard_count)}
          {zoneTray(opponentSeat, "exile", p2.exile, p2.exile_count)}
          <span>Hand {p2.hand_count}</span>
          {Object.entries(p2.counters ?? {}).filter(([, amount]) => amount > 0).map(([kind, amount]) => (
            <span key={kind} data-player-counter={`${opponentSeat}-${kind}`}>{kind[0].toUpperCase() + kind.slice(1)} {amount}</span>
          ))}
          {restrictedMana(p2)}
          <span>Ready Mana Options (shared sources) {manaSummary(p2Groups.lands) || "-"}</span>
          <span className="mana-pool">
            Pool{" "}
            {p2ManaPool.length ? (
              <span className="mana-pips">
                {p2ManaPool.map((entry) => (
                  <span key={`p2-${entry.symbol}`} className={`mana-pip mana-pip-${entry.symbol.toLowerCase()}`}>
                    {entry.symbol}
                    <small>{entry.count}{entry.snow ? ` (${entry.snow}S)` : ""}</small>
                  </span>
                ))}
              </span>
            ) : (
              "-"
            )}
          </span>
        </div>
        <CardRail className="cards" label="Opponent permanents">
          {p2Groups.nonLands.map((card) => (
            <article
              key={card.id}
              className={`card ${card.tapped ? "tapped" : ""}`}
              tabIndex={0}
              data-card-id={card.id}
              aria-label={`Inspect ${card.name}; Enter to pin preview`}
              onKeyDown={event => { if (event.key === "Enter" && event.target === event.currentTarget) { previewOrigin.current = event.currentTarget; setPinnedPreview(previewFromCard(card)); } }}
              onFocus={() => setHoverPreview(previewFromCard(card))}
              onBlur={() => setHoverPreview(null)}
              title={card.name}
              onMouseEnter={() => setHoverPreview(previewFromCard(card))}
              onMouseLeave={() => setHoverPreview(null)}
            >
              <CardArt uri={card.image_uri} name={card.name} />
              <h4>{card.name}</h4>
              {statusBadges(card)}
              {card.effect_warnings?.length ? <small role="status" title={card.effect_warnings.join("\n")}>Unsupported static effect</small> : null}
              {card.mana_cost ? <small className="card-mana">{card.mana_cost}</small> : null}
              <p className="card-type">{card.types.join(" ")}</p>
              <small className="card-stats">
                {card.power ?? "-"}/{card.toughness ?? "-"}
              </small>
              {"Planeswalker" === card.types[0] || card.types.includes("Planeswalker") ? <small>LOY: {card.loyalty ?? 0}</small> : null}
              {card.type_line?.includes("Saga") ? <small>LORE: {card.counters?.lore ?? 0}</small> : null}
            </article>
          ))}
        </CardRail>
        {p2Groups.lands.length ? (
          <div className="land-stacks">
            {p2Groups.lands.map((pile) => (
              <article
                key={pile.key}
                className="land-stack"
                tabIndex={0}
                onKeyDown={event => { if (event.key === "Enter" && event.target === event.currentTarget) { previewOrigin.current = event.currentTarget; setPinnedPreview(previewFromCard(pile.cards[0])); } }}
                onFocus={() => setHoverPreview(previewFromCard(pile.cards[0]))}
                onBlur={() => setHoverPreview(null)}
                onMouseEnter={() => setHoverPreview({ name: pile.name, imageUri: pile.imageUri, types: ["Land"] })}
                onMouseLeave={() => setHoverPreview(null)}
              >
                {resolveCardMediaUrl(pile.imageUri) ? <img src={resolveCardMediaUrl(pile.imageUri)} alt={pile.name} loading="lazy" /> : null}
                <div>
                  <strong>{pile.name}</strong>
                  <p>Total {pile.total} | Ready {pile.untapped} | Tapped {pile.tapped}</p>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </div>

      <div className="player-row player">
        <div className="zone-meta">
          <strong className="seat-label">P{viewerSeat} · Your seat <b>{p1.life}</b> life</strong>
          <span className="seat-state">{match.active_player === viewerSeat ? "◆ Active turn" : "◇ Waiting"}{match.priority_player === viewerSeat ? " · Priority" : ""}</span>
          <span>Library {p1.library_count}</span>
          {zoneTray(viewerSeat, "graveyard", p1.graveyard, p1.graveyard_count)}
          {zoneTray(viewerSeat, "exile", p1.exile, p1.exile_count)}
          <span>Hand {p1.hand_count}</span>
          {Object.entries(p1.counters ?? {}).filter(([, amount]) => amount > 0).map(([kind, amount]) => (
            <span key={kind} data-player-counter={`${viewerSeat}-${kind}`}>{kind[0].toUpperCase() + kind.slice(1)} {amount}</span>
          ))}
          {restrictedMana(p1)}
          <span>Ready Mana Options (shared sources) {manaSummary(p1Groups.lands) || "-"}</span>
          <span className="mana-pool">
            Pool{" "}
            {p1ManaPool.length ? (
              <span className="mana-pips">
                {p1ManaPool.map((entry) => (
                  <span key={`p1-${entry.symbol}`} className={`mana-pip mana-pip-${entry.symbol.toLowerCase()}`}>
                    {entry.symbol}
                    <small>{entry.count}{entry.snow ? ` (${entry.snow}S)` : ""}</small>
                  </span>
                ))}
              </span>
            ) : (
              "-"
            )}
          </span>
        </div>
        <CardRail className="cards" label="Your permanents">
          {p1Groups.nonLands.map((card) => (
            <article
              key={card.id}
              className={`card ${card.tapped ? "tapped" : ""}`}
              tabIndex={0}
              data-card-id={card.id}
              aria-label={`Inspect ${card.name}; Enter to pin preview`}
              onKeyDown={event => { if (event.key === "Enter" && event.target === event.currentTarget) { previewOrigin.current = event.currentTarget; setPinnedPreview(previewFromCard(card)); } }}
              onFocus={() => setHoverPreview(previewFromCard(card))}
              onBlur={() => setHoverPreview(null)}
              title={card.name}
              onMouseEnter={() => setHoverPreview(previewFromCard(card))}
              onMouseLeave={() => setHoverPreview(null)}
            >
              <CardArt uri={card.image_uri} name={card.name} />
              <h4>{card.name}</h4>
              {statusBadges(card)}
              {card.effect_warnings?.length ? <small role="status" title={card.effect_warnings.join("\n")}>Unsupported static effect</small> : null}
              {card.mana_cost ? <small className="card-mana">{card.mana_cost}</small> : null}
              <p className="card-type">{card.types.join(" ")}</p>
              <small className="card-stats">
                {card.power ?? "-"}/{card.toughness ?? "-"}
              </small>
              {"Planeswalker" === card.types[0] || card.types.includes("Planeswalker") ? <small>LOY: {card.loyalty ?? 0}</small> : null}
              {card.type_line?.includes("Saga") ? <small>LORE: {card.counters?.lore ?? 0}</small> : null}
              {canManualTap && card.mana_source_colors?.length ? (
                <div className="row" style={{ marginBottom: 0 }}>
                  {card.mana_source_colors.map((color) => (
                    <button
                      key={`${card.id}-mana-${color}`}
                      disabled={card.tapped || (card.types.includes("Creature") && card.summoning_sick && !card.keywords?.includes("haste"))}
                      onClick={() => onCardAction(viewerSeat, { type: card.types.includes("Land") ? "tap_land_for_mana" : "tap_nonland_for_mana", card_id: card.id, color })}
                      title={`Activate ${card.name} for ${color}`}
                    >
                      Add {(card.mana_source_amounts?.[color] ?? 1) > 1 ? `${card.mana_source_amounts?.[color]} ` : ""}{color}
                    </button>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </CardRail>
        {p1Groups.lands.length ? (
          <div className="land-stacks">
            {p1Groups.lands.map((pile) => (
              <article
                key={pile.key}
                className="land-stack"
                tabIndex={0}
                onKeyDown={event => { if (event.key === "Enter" && event.target === event.currentTarget) { previewOrigin.current = event.currentTarget; setPinnedPreview(previewFromCard(pile.cards[0])); } }}
                onFocus={() => setHoverPreview(previewFromCard(pile.cards[0]))}
                onBlur={() => setHoverPreview(null)}
                onMouseEnter={() => setHoverPreview({ name: pile.name, imageUri: pile.imageUri, types: ["Land"] })}
                onMouseLeave={() => setHoverPreview(null)}
                >
                {resolveCardMediaUrl(pile.imageUri) ? <img src={resolveCardMediaUrl(pile.imageUri)} alt={pile.name} loading="lazy" /> : null}
                <div>
                  <strong>{pile.name}</strong>
                  <p>{pile.total}x | Ready {pile.untapped} | Tapped {pile.tapped}</p>
                  <details className="land-members"><summary>Individual lands ({pile.total})</summary>
                    <select aria-label={`Individual ${pile.name}`} value={landSelections[pile.key] ?? pile.cards[0].id} onChange={event => setLandSelections(previous => ({...previous, [pile.key]: event.target.value}))}>
                      {pile.cards.map((card, index) => <option value={card.id} key={card.id}>{index + 1}. {card.name} · {card.tapped ? "Tapped" : "Untapped"} · {card.id}</option>)}
                    </select>
                    {pile.colors.map(color => {
                      const card = pile.cards.find(member => member.id === landSelections[pile.key]) ?? pile.cards[0];
                      return <button key={color} disabled={!canManualTap || card.tapped} onClick={() => onCardAction(viewerSeat, {type: "tap_land_for_mana", card_id: card.id, color})}>Tap selected for {color}</button>;
                    })}
                  </details>
                  {canManualTap && pile.untapped > 0 && p1Groups.lands.filter(group => group.name === pile.name).length === 1 ? (
                    <div className="row" style={{ marginBottom: 0 }}>
                      <select
                        aria-label={`Number of ${pile.name} to tap`}
                        value={landTapCounts[pile.key] ?? 1}
                        onChange={(e) =>
                          setLandTapCounts((prev) => ({
                            ...prev,
                            [pile.key]: Math.max(1, Math.min(pile.untapped, Number(e.target.value) || 1)),
                          }))
                        }
                      >
                        {Array.from({ length: pile.untapped }, (_, i) => i + 1).map((n) => (
                          <option key={`${pile.key}-tap-${n}`} value={n}>
                            Tap {n}
                          </option>
                        ))}
                      </select>
                      {pile.colors.map((color) => <button key={color}
                        onClick={() =>
                          onCardAction(viewerSeat, {
                            type: "tap_lands_bulk",
                            land_name: pile.name,
                            count: Math.min(pile.untapped, landTapCounts[pile.key] ?? 1),
                            color,
                          })
                        }
                      >
                        Add {(pile.amounts[color] ?? 1) > 1 ? `${pile.amounts[color]} ` : ""}{color}
                      </button>)}
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : null}
        {loyaltyMoves.length ? (
          <div className="hand-row">
            {loyaltyMoves.map((move, i) => {
              const key = `${move.card_id}-loyalty-${move.ability_index ?? i}`;
              const hints = move.target_hints;
              const targetText = move.ability_label ?? "";
              const exclusiveTarget = Boolean(hints?.single_target_alternative || (/\bany target\b/i.test(targetText) && (targetText.match(/\btarget\b/gi)?.length ?? 0) === 1));
              return (
                <div key={key} className="cast-card-box">
                  <button
                    onClick={() =>
                      onCardAction(viewerSeat, {
                        type: "activate_loyalty",
                        card_id: move.card_id,
                        ability_index: move.ability_index,
                        targets: targets[key] ?? {},
                      })
                    }
                  >
                    {move.card_name}: {move.ability_label}
                  </button>
                  {hints?.player_targets?.length ? (
                    <select
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], target_player: e.target.value ? Number(e.target.value) : undefined, ...(exclusiveTarget ? { target_card_id: undefined } : {}) },
                        }))
                      }
                      value={String(targets[key]?.target_player ?? "")}
                    >
                      <option value="">Target Player</option>
                      {hints.player_targets.map((t) => (
                        <option key={`${key}-p-${t.id}`} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  ) : null}
                  {hints?.creature_targets?.length || hints?.planeswalker_targets?.length ? (
                    <select
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], target_card_id: e.target.value || undefined, ...(exclusiveTarget ? { target_player: undefined } : {}) },
                        }))
                      }
                      value={String(targets[key]?.target_card_id ?? "")}
                    >
                      <option value="">Target Permanent</option>
                      {(hints.creature_targets ?? []).map((t) => (
                        <option key={`${key}-c-${t.id}`} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                      {(hints.planeswalker_targets ?? []).map((t) => (
                        <option key={`${key}-pw-${t.id}`} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : null}
        {equipMoves.length ? (
          <div className="hand-row">
            {equipMoves.map((move, i) => {
              const key = `${move.card_id}-equip-${i}`;
              return (
                <div key={key} className="cast-card-box">
                  <button
                    onClick={() =>
                      onCardAction(viewerSeat, {
                        type: "equip",
                        card_id: move.card_id,
                        target_card_id: (targets[key]?.target_card_id as string) || move.targets?.[0]?.id,
                      })
                    }
                  >
                    Equip {move.card_name} {move.mana_cost ? `(${move.mana_cost})` : ""}
                  </button>
                  <select
                    onChange={(e) =>
                      setTargets((prev) => ({
                        ...prev,
                        [key]: { ...prev[key], target_card_id: e.target.value },
                      }))
                    }
                    defaultValue={move.targets?.[0]?.id ?? ""}
                  >
                    {(move.targets ?? []).map((t) => (
                      <option key={`${key}-t-${t.id}`} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        ) : null}
        <h3 className="zone-heading">Hand & permitted plays <span>{playableCards.length}</span></h3>
        <CardRail className="hand-row playable-hand" label="Hand and permitted plays">
          {playableCards.map((card) => {
            const cardCastMoves = castMoves.filter((m) => m.card_id === card.id);
            const selectedFaceIndex = faceChoices[card.id] ?? cardCastMoves[0]?.selected_face_index ?? 0;
            const faceCastMoves = cardCastMoves.filter((m) => (m.selected_face_index ?? 0) === selectedFaceIndex);
            const castCostOptions = [...new Map(faceCastMoves.flatMap((m) => m.cost_options ?? []).map((option) => [option.id, option])).values()];
            const move = faceCastMoves.find((m) => !costChoice[card.id] || m.cost_options?.some((option) => option.id === costChoice[card.id])) ?? faceCastMoves[0];
            const cycleMove = cycleMoves.find((m) => m.card_id === card.id);
            const foretellMove = foretellMoves.find((m) => m.card_id === card.id);
            const foretellControl = foretellMove ? <button onClick={() => onCardAction(viewerSeat, { type: "foretell", card_id: card.id })}>
              Foretell {card.name} ({foretellMove.mana_cost})
            </button> : null;
            const cardCycleMoves = cycleMoves.filter((m) => m.card_id === card.id);
            const cardLandMoves = playLandMoves.filter((m) => m.card_id === card.id);
            const landControls = cardLandMoves.map((landMove) => <button key={`${card.id}-land-${landMove.selected_face_index ?? 0}-${landMove.entry_choice ?? "normal"}`}
              onClick={() => onCardAction(viewerSeat, { type: "play_land", card_id: card.id, selected_face_index: landMove.selected_face_index, from_exile: landMove.from_exile, entry_choice: landMove.entry_choice })}>
              Play Land {landMove.card_name ?? card.card_faces?.[landMove.selected_face_index ?? 0]?.name ?? card.name}{landMove.entry_choice === "pay_two_life" ? " (pay 2 life, untapped)" : landMove.entry_choice === "tapped" ? " (tapped)" : ""}
            </button>);
            const restrictedMove = restrictedCastMoves.find((m) => m.card_id === card.id);
            const faceNames = move?.target_hints?.face_names ?? [];
            if (!move) {
              return (
                <div
                  key={card.id}
                  className="cast-card-box hand-card"
                  tabIndex={0}
                  data-hand-card-id={card.id}
                  onFocus={() => setHoverPreview(previewFromCard(card))}
                  onBlur={() => setHoverPreview(null)}
                  onMouseEnter={() => setHoverPreview(previewFromCard(card))}
                  onMouseLeave={() => setHoverPreview(null)}
                >
                  {handFace(card)}
                  {landControls.length ? landControls : cycleMove ? (
                    <>
                    {cardCycleMoves.some((m) => m.x_value !== undefined) ? (
                      <select
                        value={cycleChoices[card.id] ?? 0}
                        onChange={(e) => setCycleChoices((prev) => ({ ...prev, [card.id]: Number(e.target.value) || 0 }))}
                      >
                        {cardCycleMoves.map((m) => <option key={`${card.id}-x-${m.x_value}`} value={m.x_value}>{`X=${m.x_value}`}</option>)}
                      </select>
                    ) : null}
                    <button onClick={() => onCardAction(viewerSeat, { type: "cycle_card", card_id: card.id, x_value: cycleChoices[card.id] ?? cycleMove.x_value ?? 0 })}>
                      Cycle {card.name} {cycleMove.mana_cost ? `(${cycleMove.mana_cost})` : ""}
                    </button>
                    </>
                  ) : (
                    <button disabled>
                      {card.types.includes("Land") ? `${card.name} · ${landPlayHint(match, viewerSeat)}`
                        : `${card.name} ${card.mana_cost ? `(${card.mana_cost}) ` : ""}(not castable)`}
                    </button>
                  )}
                  {restrictedMove?.reason ? <small>Restriction: {restrictedMove.reason}</small> : null}
                  {foretellControl}
                </div>
              );
            }
            const selectedCostId = costChoice[card.id] || move.cost_options?.[0]?.id;
            const selectedCost = move.cost_options?.find((option) => option.id === selectedCostId);
            const hints = selectedCost?.target_hints ?? move.target_hints;
            const linkedPairs = hints?.linked_target_pairs;
            const linkedPairIndex = linkedPairs?.findIndex(pair =>
              pair.targets.target_player === targets[card.id]?.target_player
              && pair.targets.target_card_id === targets[card.id]?.target_card_id
              && JSON.stringify(pair.targets.target_card_ids ?? []) === JSON.stringify(targets[card.id]?.target_card_ids ?? [])) ?? -1;
            const incompleteLinkedPair = Boolean(linkedPairs && linkedPairIndex < 0);
            const distinctTargets = Boolean(hints?.required_distinct_target_count);
            const orderedCount = hints?.required_distinct_target_count ?? hints?.required_target_instance_count ?? 0;
            const orderedTargets = Array.isArray(targets[card.id]?.target_card_ids)
              ? targets[card.id].target_card_ids as string[] : [];
            const incompleteOrderedTargets = orderedCount > 0 && (
              orderedTargets.length !== orderedCount || !orderedTargets.every(Boolean)
              || (distinctTargets && new Set(orderedTargets).size !== orderedCount)
              || orderedTargets.some(id => !hints?.creature_targets?.some(target => target.id === id))
            );
            const targetText = card.card_faces?.[selectedFaceIndex]?.oracle_text ?? card.oracle_text ?? "";
            const chosenModes = targets[card.id]?.mode_texts;
            const selectedModeTexts = Array.isArray(chosenModes) ? chosenModes as string[] : [];
            const perModeSelected = Boolean(hints?.choose_two_modes && selectedModeTexts.length === 2);
            const chosenMode = targets[card.id]?.mode_text;
            const targetingText = Array.isArray(chosenModes) && chosenModes.length
              ? chosenModes.join(" ") : typeof chosenMode === "string" && chosenMode ? chosenMode : targetText;
            const exclusiveTarget = Boolean(hints?.single_target_alternative || (/\bany target\b/i.test(targetText) && (targetText.match(/\btarget\b/gi)?.length ?? 0) === 1));
            const alternativeTargets = !hints?.aura_targets?.length && !/\btargets?\b/i.test(targetingText) ? [] : [...new Map([
              ...(hints?.creature_targets ?? []), ...(hints?.planeswalker_targets ?? []),
              ...(hints?.permanent_targets ?? []), ...(hints?.artifact_targets ?? []),
              ...(hints?.enchantment_targets ?? []), ...(hints?.land_targets ?? []),
              ...(hints?.graveyard_card_targets ?? []), ...(hints?.graveyard_creature_targets ?? []), ...(hints?.graveyard_permanent_targets ?? []),
            ].map((target) => [target.id, target])).values()];
            const showAlternativeSelect = Boolean(!perModeSelected && hints?.single_target_alternative && hints?.player_targets?.length && alternativeTargets.length);
            const payments = [
              { key: 'discard_card_ids', count: (selectedCost?.discard_cards ?? 0) + (selectedCost?.discard_x ? Math.max(0, Number(targets[card.id]?.x_value ?? 0)) : 0), candidates: selectedCost?.discard_card_ids ?? [], label: 'Discard for cost' },
              { key: 'sacrifice_card_ids', count: selectedCost?.sacrifice_creatures ?? 0, candidates: selectedCost?.sacrifice_card_ids ?? [], label: 'Sacrifice for cost' },
            ];
            const incompleteCostCards = payments.some(payment => payment.count > 0 &&
              ((costCards[`${card.id}:${selectedCostId}:${payment.key}`]?.length ?? 0) !== payment.count ||
                costCards[`${card.id}:${selectedCostId}:${payment.key}`]?.some(id => !payment.candidates.includes(id))));
            const selectedManaCost = move.cost_options?.find((option) => option.id === selectedCostId)?.mana_cost ?? move.mana_cost;
            const selectedAuraTarget = String(targets[card.id]?.target_card_id ?? "");
            const incompatibleAuraCost = Boolean(hints?.aura_cost_options && (!selectedAuraTarget || !hints.aura_cost_options[selectedAuraTarget]?.includes(selectedCostId ?? "")));
            const hybridSymbols = move.cost_options?.find((option) => option.id === selectedCostId)?.hybrid_symbols ?? [];
            const chosenHybridBranches = hybridSymbols.map((_, index) => hybridChoice[`${card.id}:${selectedFaceIndex}:${selectedCostId}:${index}`] ?? "");
            const incompleteHybridChoice = chosenHybridBranches.some(Boolean) && !chosenHybridBranches.every(Boolean);
            return (
              <div
                key={card.id}
                className="cast-card-box hand-card playable"
                tabIndex={0}
                data-hand-card-id={card.id}
                onFocus={() => setHoverPreview(previewFromCard(card))}
                onBlur={() => setHoverPreview(null)}
                onMouseEnter={() => setHoverPreview(previewFromCard(card))}
                onMouseLeave={() => setHoverPreview(null)}
              >
                {handFace(card)}
                {landControls}
                {foretellControl}
                <button
                  disabled={incompleteHybridChoice || incompatibleAuraCost || incompleteCostCards || incompleteOrderedTargets || incompleteLinkedPair}
                  onClick={() => castAction(card.id, faceNames.length > 1 ? selectedFaceIndex : undefined)}
                >
                  Cast {move.card_name ?? card.name} {selectedManaCost ? `(${selectedManaCost})` : ""}
                </button>
                {cycleMove ? (
                  <button onClick={() => onCardAction(viewerSeat, { type: "cycle_card", card_id: card.id, x_value: cycleChoices[card.id] ?? cycleMove.x_value ?? 0 })}>
                    Cycle {cycleMove.mana_cost ? `(${cycleMove.mana_cost})` : ""}
                  </button>
                ) : null}
                {faceNames.length > 1 ? (
                  <select
                    value={selectedFaceIndex}
                    onChange={(e) => {
                      setFaceChoices((prev) => ({
                        ...prev,
                        [card.id]: Number(e.target.value) || 0,
                      }));
                      setTargets((prev) => ({ ...prev, [card.id]: {} }));
                      setCostChoice((prev) => ({ ...prev, [card.id]: "" }));
                    }}
                  >
                    {faceNames.map((faceName, idx) => (
                      <option key={`${card.id}-face-${idx}`} value={idx}
                        disabled={["modal_dfc", "adventure", "split", "transform", "meld", "flip", "double_faced_token"].includes(card.layout ?? "") && !cardCastMoves.some((m) => (m.selected_face_index ?? 0) === idx)}>
                        Face {idx + 1}: {faceName}
                      </option>
                    ))}
                  </select>
                ) : null}
                {castCostOptions.length ? (
                  <select value={costChoice[card.id] ?? ""} onChange={(e) => {
                    const value = e.target.value;
                    setCostChoice((prev) => ({ ...prev, [card.id]: value }));
                    setTargets((prev) => ({ ...prev, [card.id]: {} }));
                  }}>
                    <option value="">Cost Option</option>
                    {castCostOptions.map((c) => (
                      <option key={`${card.id}-cost-${c.id}`} value={c.id} disabled={Boolean(move.cost_options?.some((option) => option.id === c.id) && hints?.aura_cost_options && selectedAuraTarget && !hints.aura_cost_options[selectedAuraTarget]?.includes(c.id))}>
                        {c.label} {c.mana_cost ? `(${c.mana_cost})` : ""}
                      </option>
                    ))}
                  </select>
                ) : null}
                {selectedCost?.discard_all ? <p>Additional cost: discard your entire hand (excluding this spell).</p> : null}
                {selectedCost?.sacrifice_all ? <p>Additional cost: sacrifice all permanents you control.</p> : null}
                {payments.filter(payment => payment.count > 0).map(payment => {
                  const key = `${card.id}:${selectedCostId}:${payment.key}`;
                  return <label key={key}>
                    {payment.label}: choose {payment.count}
                    <select multiple aria-label={`${payment.label} ${card.name}`}
                      value={costCards[key] ?? []}
                      onChange={event => setCostCards(previous => ({ ...previous,
                        [key]: Array.from(event.target.selectedOptions).map(option => option.value),
                      }))}>
                      {payment.candidates.map(id => <option key={id} value={id}>
                        {[...p1.hand, ...p1.battlefield].find(candidate => candidate.id === id)?.name ?? id}
                      </option>)}
                    </select>
                  </label>;
                })}
                {hybridSymbols.map((symbol, index) => (
                  <label key={`${card.id}-hybrid-${selectedCostId}-${index}`}>
                    {`Pay {${symbol.symbol}}`}
                    <select
                      aria-label={`Pay hybrid symbol ${index + 1} {${symbol.symbol}}`}
                      value={chosenHybridBranches[index]}
                      onChange={(e) => setHybridChoice((prev) => ({ ...prev, [`${card.id}:${selectedFaceIndex}:${selectedCostId}:${index}`]: e.target.value }))}
                    >
                      <option value="">Auto</option>
                      {symbol.choices.map((branch) => <option key={`${symbol.symbol}-${branch}`} value={branch}>{branch === "2" ? "2 generic mana" : branch === "P" ? "Pay 2 life" : branch}</option>)}
                    </select>
                  </label>
                ))}
                {showAlternativeSelect ? (
                  <select
                    value={targets[card.id]?.target_card_id ? `card:${targets[card.id].target_card_id}` : targets[card.id]?.target_player ? `player:${targets[card.id].target_player}` : ""}
                    onChange={(e) => {
                      const [kind, value] = e.target.value.split(":", 2);
                      setTargets((prev) => ({
                        ...prev,
                        [card.id]: { ...prev[card.id], target_player: kind === "player" ? Number(value) : undefined, target_card_id: kind === "card" ? value : undefined },
                      }));
                    }}
                  >
                    <option value="">Choose Target</option>
                    {hints?.player_targets?.map((target) => <option key={`player-${target.id}`} value={`player:${target.id}`}>{target.name}</option>)}
                    {alternativeTargets.map((target) => <option key={`card-${target.id}`} value={`card:${target.id}`}>{target.name}</option>)}
                  </select>
                ) : null}
                {linkedPairs ? <label>
                  Choose both linked targets
                  <select aria-label={`Linked targets for ${card.name}`} value={linkedPairIndex < 0 ? '' : linkedPairIndex}
                    onChange={event => {
                      const pair = event.target.value === '' ? undefined : linkedPairs[Number(event.target.value)];
                      setTargets(previous => ({ ...previous, [card.id]: pair ? { ...pair.targets } : {} }));
                    }}>
                    <option value="">Choose player or planeswalker and its controller's creature</option>
                    {linkedPairs.map((pair, index) => <option key={`${pair.primary_kind}:${pair.primary_id}:${pair.creature_id}`} value={index}>
                      {pair.primary_name} + {pair.creature_name} ({pair.creature_id.slice(-6)})
                    </option>)}
                  </select>
                </label> : null}
                {!linkedPairs && !perModeSelected && !showAlternativeSelect && hints?.player_targets?.length ? (
                  <select
                    aria-label="Player target"
                    onChange={(e) =>
                      setTargets((prev) => ({
                        ...prev,
                        [card.id]: { ...prev[card.id], target_player: e.target.value ? Number(e.target.value) : undefined, ...(exclusiveTarget ? { target_card_id: undefined } : {}) },
                      }))
                    }
                    value={String(targets[card.id]?.target_player ?? "")}
                  >
                    <option value="">Target Player</option>
                    {hints.player_targets.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                ) : null}
                {hints?.modes?.length ? (
                  hints.choose_two_modes ? (
                    <select
                      aria-label="Spell modes"
                      multiple
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [card.id]: {
                            ...prev[card.id],
                            mode_texts: Array.from(e.target.selectedOptions).map((o) => o.value),
                            mode_targets: {},
                            target_card_id: undefined,
                            target_player: undefined,
                            target_stack_id: undefined,
                          },
                        }))
                      }
                    >
                      {(hints.available_modes ?? hints.modes).map((m, i) => (
                        <option key={`${card.id}-mode2-${i}`} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <select
                      aria-label="Spell mode"
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [card.id]: { ...prev[card.id], mode_text: e.target.value },
                        }))
                      }
                      defaultValue=""
                    >
                      <option value="">Choose Mode</option>
                      {(hints.available_modes ?? hints.modes).map((m, i) => (
                        <option key={`${card.id}-mode-${i}`} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  )
                ) : null}
                {perModeSelected ? selectedModeTexts.map((mode) => {
                  const modeHints = hints?.mode_target_hints?.[mode];
                  const modeChoices = (targets[card.id]?.mode_targets ?? {}) as Record<string, Record<string, unknown>>;
                  const current = modeChoices[mode] ?? {};
                  const cardOptions = [...new Map([
                    ...(modeHints?.creature_targets ?? []), ...(modeHints?.planeswalker_targets ?? []),
                    ...(modeHints?.permanent_targets ?? []), ...(modeHints?.artifact_targets ?? []),
                    ...(modeHints?.enchantment_targets ?? []), ...(modeHints?.land_targets ?? []),
                    ...(modeHints?.graveyard_card_targets ?? []), ...(modeHints?.graveyard_creature_targets ?? []), ...(modeHints?.graveyard_permanent_targets ?? []),
                  ].map((option) => [option.id, option])).values()];
                  return <div key={`${card.id}-${mode}`} className="mode-target-choice">
                    <label>{mode}</label>
                    {modeHints?.stack_targets?.length ? <select
                      aria-label={`Target for ${mode}`}
                      value={String(current.target_stack_id ?? "")}
                      onChange={(e) => setModeTarget(card.id, mode, e.target.value ? { target_stack_id: e.target.value } : {})}
                    >
                      <option value="">Target Stack Item</option>
                      {modeHints.stack_targets.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                    </select> : null}
                    {modeHints?.player_targets?.length || cardOptions.length ? <select
                      aria-label={`Target for ${mode}`}
                      value={current.target_card_id ? `card:${current.target_card_id}` : current.target_player ? `player:${current.target_player}` : ""}
                      onChange={(e) => {
                        const [kind, value] = e.target.value.split(":", 2);
                        setModeTarget(card.id, mode, kind === "card" ? { target_card_id: value } : kind === "player" ? { target_player: Number(value) } : {});
                      }}
                    >
                      <option value="">Choose Target</option>
                      {modeHints?.player_targets?.map((option) => <option key={`player-${option.id}`} value={`player:${option.id}`}>{option.name}</option>)}
                      {cardOptions.map((option) => <option key={`card-${option.id}`} value={`card:${option.id}`}>{option.name}</option>)}
                    </select> : null}
                  </div>;
                }) : null}
                {hints?.requires_x_value ? (
                  <input
                    type="number"
                    min={0}
                    max={hints.x_value_max}
                    placeholder={move.cost_options?.some((option) => option.pay_life_x) ? "X life to pay" : "X value"}
                    onChange={(e) =>
                      setTargets((prev) => ({
                        ...prev,
                        [card.id]: { ...prev[card.id], x_value: Number(e.target.value) || 0 },
                      }))
                    }
                  />
                ) : null}
                {orderedCount > 0 ? <fieldset>
                  <legend>{distinctTargets ? `Choose ${orderedCount} different creatures` : `Choose ${orderedCount} targets; the same creature may be chosen again`}</legend>
                  {Array.from({ length: orderedCount }, (_, index) => <label key={index}>
                    Target {index + 1}: {distinctTargets
                      ? `${hints?.ordered_counter_amounts?.[index]} ${hints?.ordered_counter_type} counters`
                      : `${hints?.ordered_creature_modifiers?.[index]?.power}/${hints?.ordered_creature_modifiers?.[index]?.toughness} until end of turn`}
                    <select aria-label={`Target ${index + 1} for ${card.name}`}
                      value={orderedTargets[index] ?? ""}
                      onChange={event => {
                        const value = event.target.value;
                        setTargets(previous => {
                          const current = previous[card.id]?.target_card_ids;
                          const selected = Array.from({ length: orderedCount }, (_, slot) => Array.isArray(current) ? current[slot] ?? "" : "");
                          selected[index] = value;
                          return { ...previous, [card.id]: { ...previous[card.id], target_card_id: undefined, target_card_ids: selected } };
                        });
                      }}>
                      <option value="">Choose creature</option>
                      {(hints?.creature_targets ?? []).map(target => <option key={target.id} value={target.id}
                        disabled={distinctTargets && orderedTargets.some((id, slot) => slot !== index && id === target.id)}>{target.name} ({target.id.slice(-6)})</option>)}
                    </select>
                  </label>)}
                </fieldset> : null}
                {!linkedPairs && !orderedCount && !perModeSelected && !showAlternativeSelect && alternativeTargets.length ? (
                  hints?.up_to_target_count && hints.up_to_target_count > 1 ? (
                    <select
                      multiple
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [card.id]: {
                            ...prev[card.id],
                            target_card_ids: Array.from(e.target.selectedOptions).map((o) => o.value),
                          },
                        }))
                      }
                    >
                      {alternativeTargets.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <select
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [card.id]: { ...prev[card.id], target_card_id: e.target.value || undefined, ...(exclusiveTarget ? { target_player: undefined } : {}) },
                        }))
                      }
                      value={String(targets[card.id]?.target_card_id ?? "")}
                    >
                      <option value="">{hints?.permanent_targets?.length ? "Target Permanent" : "Target Creature"}</option>
                      {alternativeTargets.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  )
                ) : null}
                {hints?.supports_divide ? (
                  <div className="divide-box">
                    <p style={{ margin: "0.2rem 0" }}>Damage Distribution{hints.divide_max_targets ? ` (up to ${hints.divide_max_targets} targets)` : ""}</p>
                    {[...(hints.player_targets ?? []).map((p) => ({ id: String(p.id), name: p.name })), ...(hints.creature_targets ?? []), ...(hints.planeswalker_targets ?? [])].map(
                      (targetOption) => (
                        <div key={`${card.id}-dist-${targetOption.id}`} className="row">
                          <span>{targetOption.name}</span>
                          <input
                            type="number"
                            aria-label={`Damage to ${targetOption.name} for ${card.name}`}
                            min={0}
                            value={divideInputs[card.id]?.[targetOption.id] ?? 0}
                            onChange={(e) => {
                              const amount = Math.max(0, Number(e.target.value) || 0);
                              const cardDist = { ...(divideInputs[card.id] ?? {}), [targetOption.id]: amount };
                              const filtered = Object.fromEntries(Object.entries(cardDist).filter(([, v]) => Number(v) > 0));
                              setDivideInputs((prev) => ({ ...prev, [card.id]: cardDist }));
                              setTargets((prev) => ({ ...prev, [card.id]: { ...prev[card.id], target_distribution: filtered } }));
                            }}
                          />
                        </div>
                      ),
                    )}
                  </div>
                ) : null}
                {!perModeSelected && hints?.stack_targets?.length ? (
                  <select
                    onChange={(e) =>
                      setTargets((prev) => ({
                        ...prev,
                        [card.id]: { ...prev[card.id], target_stack_id: e.target.value },
                      }))
                    }
                    defaultValue=""
                  >
                    <option value="">Target Stack Item</option>
                    {hints.stack_targets.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                ) : null}
              </div>
            );
          })}
        </CardRail>
      </div>

      <PermanentActions key={match.id} moves={legalMoves} playerId={viewerSeat} onAction={onCardAction} />
      {hoverPreview ? createPortal(
        <aside className="card-hover-preview" data-pinned={Boolean(pinnedPreview)} aria-label="Card inspection" tabIndex={0}>
          <button className="preview-close" onClick={() => { previewOrigin.current?.focus({preventScroll:true}); previewOrigin.current = null; setHoverPreview(null); setPinnedPreview(null); }}>Close inspection · Esc</button>
          <CardArt uri={hoverPreview.imageUri} name={hoverPreview.name} />
          <div className="card-hover-meta">
            <h4>{hoverPreview.name}</h4>
            {hoverPreview.manaCost ? <p>{hoverPreview.manaCost}</p> : null}
            {hoverPreview.types?.length ? <p>{hoverPreview.types.join(" ")}</p> : null}
            {(hoverPreview.power !== null && hoverPreview.power !== undefined) || (hoverPreview.toughness !== null && hoverPreview.toughness !== undefined) ? (
              <p>
                {hoverPreview.power ?? "-"}/{hoverPreview.toughness ?? "-"}
              </p>
            ) : null}
            {hoverPreview.loyalty !== null && hoverPreview.loyalty !== undefined ? <p>LOY: {hoverPreview.loyalty}</p> : null}
            {hoverPreview.printedPower !== null && hoverPreview.printedPower !== undefined ? <p>Printed: {hoverPreview.printedPower}/{hoverPreview.printedToughness ?? "-"}</p> : null}
            {hoverPreview.basePower !== null && hoverPreview.basePower !== undefined && (hoverPreview.power !== hoverPreview.basePower || hoverPreview.toughness !== hoverPreview.baseToughness) ? <p>Base: {hoverPreview.basePower}/{hoverPreview.baseToughness}</p> : null}
            {hoverPreview.damage ? <p>Damage marked: {hoverPreview.damage}</p> : null}
            {hoverPreview.keywords?.length ? <p>{hoverPreview.keywords.join(", ")}</p> : null}
            {hoverPreview.colors?.length ? <p>Color: {hoverPreview.colors.map((color) => ({ W: "White", U: "Blue", B: "Black", R: "Red", G: "Green" }[color] ?? color)).join(", ")}</p> : null}
            {hoverPreview.counters ? Object.entries(hoverPreview.counters).filter(([name, count]) => !name.startsWith("__") && count > 0).map(([name, count]) => <p key={name}>{name}: {count}</p>) : null}
            {hoverPreview.oracleText ? <small>{hoverPreview.oracleText}</small> : null}
            {hoverPreview.faces && hoverPreview.faces.length > 1 ? <div className="inspection-faces"><h3>Available faces · inspection only</h3>{hoverPreview.faces.map((face, index) => <details key={index}>
              <summary>{face.name ?? `Face ${index + 1}`}</summary>
              <CardArt uri={face.image_uri} name={face.name ?? `Face ${index + 1}`} />
              <p>{face.mana_cost} · {face.type_line}</p><small>{face.oracle_text}</small>
            </details>)}</div> : null}
          </div>
        </aside>, document.body
      ) : null}
    </section>
  );
}
