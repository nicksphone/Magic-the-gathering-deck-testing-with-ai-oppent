import { useMemo, useState } from "react";
import { resolveCardMediaUrl } from "../api/client";
import type { LegalMove, MatchState } from "../types";

type Props = {
  match: MatchState;
  legalMoves: LegalMove[];
  onCardAction: (playerId: number, action: Record<string, unknown>) => void;
};

type HoverPreview = {
  name: string;
  manaCost?: string;
  oracleText?: string;
  imageUri?: string;
  types?: string[];
  power?: number | null;
  toughness?: number | null;
  loyalty?: number | null;
};

type LandPile = {
  key: string;
  name: string;
  imageUri?: string;
  total: number;
  untapped: number;
  tapped: number;
  color: string;
};

type ManaSymbol = "W" | "U" | "B" | "R" | "G" | "C";

function inferLandColor(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("plains")) return "W";
  if (n.includes("island")) return "U";
  if (n.includes("swamp")) return "B";
  if (n.includes("mountain")) return "R";
  if (n.includes("forest")) return "G";
  return "C";
}

function groupBattlefield(cards: MatchState["players"]["1"]["battlefield"]): { nonLands: typeof cards; lands: LandPile[] } {
  const nonLands = cards.filter((c) => !c.types.includes("Land"));
  const piles = new Map<string, LandPile>();
  for (const card of cards) {
    if (!card.types.includes("Land")) continue;
    const key = `${card.name}|${card.image_uri ?? ""}`;
    const existing = piles.get(key) ?? {
      key,
      name: card.name,
      imageUri: card.image_uri,
      total: 0,
      untapped: 0,
      tapped: 0,
      color: inferLandColor(card.name),
    };
    existing.total += 1;
    if (card.tapped) existing.tapped += 1;
    else existing.untapped += 1;
    piles.set(key, existing);
  }
  return { nonLands, lands: Array.from(piles.values()).sort((a, b) => a.name.localeCompare(b.name)) };
}

function manaSummary(lands: LandPile[]): string {
  const counts: Record<string, number> = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
  for (const pile of lands) counts[pile.color] = (counts[pile.color] ?? 0) + pile.untapped;
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([c, n]) => `${c}:${n}`)
    .join("  ");
}

function manaPoolPips(pool: Record<string, number>): { symbol: ManaSymbol; count: number }[] {
  const order: ManaSymbol[] = ["W", "U", "B", "R", "G", "C"];
  return order
    .map((symbol) => ({ symbol, count: Number(pool[symbol] ?? 0) }))
    .filter((entry) => entry.count > 0);
}

export function Battlefield({ match, legalMoves, onCardAction }: Props) {
  const p1 = match.players["1"];
  const p2 = match.players["2"];
  const p1Groups = useMemo(() => groupBattlefield(p1.battlefield), [p1.battlefield]);
  const p2Groups = useMemo(() => groupBattlefield(p2.battlefield), [p2.battlefield]);
  const p1ManaPool = useMemo(() => manaPoolPips(p1.mana_pool), [p1.mana_pool]);
  const p2ManaPool = useMemo(() => manaPoolPips(p2.mana_pool), [p2.mana_pool]);
  const battlefieldCount = p1Groups.nonLands.length + p1Groups.lands.length + p2Groups.nonLands.length + p2Groups.lands.length;
  const battlefieldDensityClass =
    battlefieldCount >= 16 ? "battlefield-packed" : battlefieldCount >= 9 ? "battlefield-dense" : battlefieldCount >= 5 ? "battlefield-comfort" : "battlefield-open";
  const castMoves = useMemo(() => legalMoves.filter((m) => m.type === "cast_spell"), [legalMoves]);
  const playLandMoves = useMemo(() => legalMoves.filter((m) => m.type === "play_land"), [legalMoves]);
  const restrictedCastMoves = useMemo(() => legalMoves.filter((m) => m.type === "cast_spell_restricted"), [legalMoves]);
  const loyaltyMoves = useMemo(() => legalMoves.filter((m) => m.type === "activate_loyalty"), [legalMoves]);
  const equipMoves = useMemo(() => legalMoves.filter((m) => m.type === "equip"), [legalMoves]);
  const [targets, setTargets] = useState<Record<string, Record<string, unknown>>>({});
  const [costChoice, setCostChoice] = useState<Record<string, string>>({});
  const [faceChoices, setFaceChoices] = useState<Record<string, number>>({});
  const [divideInputs, setDivideInputs] = useState<Record<string, Record<string, number>>>({});
  const [landTapCounts, setLandTapCounts] = useState<Record<string, number>>({});
  const [hoverPreview, setHoverPreview] = useState<HoverPreview | null>(null);
  const canManualTapP1 = match.priority_player === 1;

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
    };
  }

  function castAction(cardId: string, selectedFaceIndex?: number) {
    const t = targets[cardId] ?? {};
    onCardAction(1, {
      type: "cast_spell",
      card_id: cardId,
      targets: t,
      cost_choice: costChoice[cardId] ? { id: costChoice[cardId] } : undefined,
      selected_face_index: selectedFaceIndex,
    });
  }

  return (
    <section className={`panel battlefield ${battlefieldDensityClass}`}>
      <header>
        <div>
          <h2>Battlefield</h2>
          <p>
            Turn {match.turn} | Step {match.step} | Priority: P{match.priority_player}
            {match.game_number ? ` | Game ${match.game_number}` : ""}
          </p>
        </div>
        <div className="life-counters">
          <span>P2 Life: {p2.life}</span>
          <span>P1 Life: {p1.life}</span>
        </div>
      </header>

      <div className="player-row opponent">
        <div className="zone-meta">
          <span>Library {p2.library_count}</span>
          <span>GY {p2.graveyard_count}</span>
          <span>Exile {p2.exile_count}</span>
          <span>Hand {p2.hand_count}</span>
          <span>Untapped Mana {manaSummary(p2Groups.lands) || "-"}</span>
          <span className="mana-pool">
            Pool{" "}
            {p2ManaPool.length ? (
              <span className="mana-pips">
                {p2ManaPool.map((entry) => (
                  <span key={`p2-${entry.symbol}`} className={`mana-pip mana-pip-${entry.symbol.toLowerCase()}`}>
                    {entry.symbol}
                    <small>{entry.count}</small>
                  </span>
                ))}
              </span>
            ) : (
              "-"
            )}
          </span>
        </div>
        <div className="cards">
          {p2Groups.nonLands.map((card) => (
            <article
              key={card.id}
              className={`card ${card.tapped ? "tapped" : ""}`}
              title={card.name}
              onMouseEnter={() => setHoverPreview(previewFromCard(card))}
              onMouseLeave={() => setHoverPreview(null)}
            >
              {resolveCardMediaUrl(card.image_uri) ? <img src={resolveCardMediaUrl(card.image_uri)} alt={card.name} loading="lazy" /> : null}
              <h4>{card.name}</h4>
              {card.mana_cost ? <small>{card.mana_cost}</small> : null}
              <p>{card.types.join(" ")}</p>
              <small>
                {card.power ?? "-"}/{card.toughness ?? "-"}
              </small>
              {"Planeswalker" === card.types[0] || card.types.includes("Planeswalker") ? <small>LOY: {card.loyalty ?? 0}</small> : null}
            </article>
          ))}
        </div>
        {p2Groups.lands.length ? (
          <div className="land-stacks">
            {p2Groups.lands.map((pile) => (
              <article
                key={pile.key}
                className="land-stack"
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
          <span>Library {p1.library_count}</span>
          <span>GY {p1.graveyard_count}</span>
          <span>Exile {p1.exile_count}</span>
          <span>Hand {p1.hand_count}</span>
          <span>Untapped Mana {manaSummary(p1Groups.lands) || "-"}</span>
          <span className="mana-pool">
            Pool{" "}
            {p1ManaPool.length ? (
              <span className="mana-pips">
                {p1ManaPool.map((entry) => (
                  <span key={`p1-${entry.symbol}`} className={`mana-pip mana-pip-${entry.symbol.toLowerCase()}`}>
                    {entry.symbol}
                    <small>{entry.count}</small>
                  </span>
                ))}
              </span>
            ) : (
              "-"
            )}
          </span>
        </div>
        <div className="cards">
          {p1Groups.nonLands.map((card) => (
            <article
              key={card.id}
              className={`card ${card.tapped ? "tapped" : ""}`}
              title={card.name}
              onMouseEnter={() => setHoverPreview(previewFromCard(card))}
              onMouseLeave={() => setHoverPreview(null)}
            >
              {resolveCardMediaUrl(card.image_uri) ? <img src={resolveCardMediaUrl(card.image_uri)} alt={card.name} loading="lazy" /> : null}
              <h4>{card.name}</h4>
              {card.mana_cost ? <small>{card.mana_cost}</small> : null}
              <p>{card.types.join(" ")}</p>
              <small>
                {card.power ?? "-"}/{card.toughness ?? "-"}
              </small>
              {"Planeswalker" === card.types[0] || card.types.includes("Planeswalker") ? <small>LOY: {card.loyalty ?? 0}</small> : null}
            </article>
          ))}
        </div>
        {p1Groups.lands.length ? (
          <div className="land-stacks">
            {p1Groups.lands.map((pile) => (
              <article
                key={pile.key}
                className="land-stack"
                onMouseEnter={() => setHoverPreview({ name: pile.name, imageUri: pile.imageUri, types: ["Land"] })}
                onMouseLeave={() => setHoverPreview(null)}
                >
                {resolveCardMediaUrl(pile.imageUri) ? <img src={resolveCardMediaUrl(pile.imageUri)} alt={pile.name} loading="lazy" /> : null}
                <div>
                  <strong>{pile.name}</strong>
                  <p>{pile.total}x | Ready {pile.untapped} | Tapped {pile.tapped}</p>
                  {canManualTapP1 && pile.untapped > 0 ? (
                    <div className="row" style={{ marginBottom: 0 }}>
                      <select
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
                      <button
                        onClick={() =>
                          onCardAction(1, {
                            type: "tap_lands_bulk",
                            land_name: pile.name,
                            count: landTapCounts[pile.key] ?? 1,
                          })
                        }
                      >
                        Add {pile.color}
                      </button>
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
              return (
                <div key={key} className="cast-card-box">
                  <button
                    onClick={() =>
                      onCardAction(1, {
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
                          [key]: { ...prev[key], target_player: Number(e.target.value) },
                        }))
                      }
                      defaultValue=""
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
                          [key]: { ...prev[key], target_card_id: e.target.value },
                        }))
                      }
                      defaultValue=""
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
                      onCardAction(1, {
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
        <div className="hand-row">
          {p1.hand.map((card) => {
            const move = castMoves.find((m) => m.card_id === card.id);
            const landMove = playLandMoves.find((m) => m.card_id === card.id);
            const restrictedMove = restrictedCastMoves.find((m) => m.card_id === card.id);
            const faceNames = move?.target_hints?.face_names ?? [];
            const selectedFaceIndex = faceChoices[card.id] ?? 0;
            if (!move) {
              return (
                <div
                  key={card.id}
                  className="cast-card-box"
                  onMouseEnter={() => setHoverPreview(previewFromCard(card))}
                  onMouseLeave={() => setHoverPreview(null)}
                >
                  {landMove ? (
                    <button onClick={() => onCardAction(1, { type: "play_land", card_id: card.id })}>
                      Play Land {card.name}
                    </button>
                  ) : (
                    <button disabled>
                      {card.name} {card.mana_cost ? `(${card.mana_cost}) ` : ""}(not castable)
                    </button>
                  )}
                  {restrictedMove?.reason ? <small>Restriction: {restrictedMove.reason}</small> : null}
                </div>
              );
            }
            const hints = move.target_hints;
            return (
              <div
                key={card.id}
                className="cast-card-box"
                onMouseEnter={() => setHoverPreview(previewFromCard(card))}
                onMouseLeave={() => setHoverPreview(null)}
              >
                <button
                  onClick={() => castAction(card.id, faceNames.length > 1 ? selectedFaceIndex : undefined)}
                >
                  Cast {card.name} {move.mana_cost ? `(${move.mana_cost})` : ""}
                </button>
                {faceNames.length > 1 ? (
                  <select
                    value={selectedFaceIndex}
                    onChange={(e) =>
                      setFaceChoices((prev) => ({
                        ...prev,
                        [card.id]: Number(e.target.value) || 0,
                      }))
                    }
                  >
                    {faceNames.map((faceName, idx) => (
                      <option key={`${card.id}-face-${idx}`} value={idx}>
                        Face {idx + 1}: {faceName}
                      </option>
                    ))}
                  </select>
                ) : null}
                {move.cost_options?.length ? (
                  <select value={costChoice[card.id] ?? ""} onChange={(e) => setCostChoice((prev) => ({ ...prev, [card.id]: e.target.value }))}>
                    <option value="">Cost Option</option>
                    {move.cost_options.map((c) => (
                      <option key={`${card.id}-cost-${c.id}`} value={c.id}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                ) : null}
                {hints?.player_targets?.length ? (
                  <select
                    onChange={(e) =>
                      setTargets((prev) => ({
                        ...prev,
                        [card.id]: { ...prev[card.id], target_player: Number(e.target.value) },
                      }))
                    }
                    defaultValue=""
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
                      multiple
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [card.id]: {
                            ...prev[card.id],
                            mode_texts: Array.from(e.target.selectedOptions).map((o) => o.value),
                          },
                        }))
                      }
                    >
                      {hints.modes.map((m, i) => (
                        <option key={`${card.id}-mode2-${i}`} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <select
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [card.id]: { ...prev[card.id], mode_text: e.target.value },
                        }))
                      }
                      defaultValue=""
                    >
                      <option value="">Choose Mode</option>
                      {hints.modes.map((m, i) => (
                        <option key={`${card.id}-mode-${i}`} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  )
                ) : null}
                {hints?.requires_x_value ? (
                  <input
                    type="number"
                    min={0}
                    placeholder="X value"
                    onChange={(e) =>
                      setTargets((prev) => ({
                        ...prev,
                        [card.id]: { ...prev[card.id], x_value: Number(e.target.value) || 0 },
                      }))
                    }
                  />
                ) : null}
                {hints?.creature_targets?.length || hints?.planeswalker_targets?.length ? (
                  hints.up_to_target_count && hints.up_to_target_count > 1 ? (
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
                      {(hints.creature_targets ?? []).map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                      {(hints.planeswalker_targets ?? []).map((t) => (
                        <option key={`pw-multi-${t.id}`} value={t.id}>
                          {t.name} (Planeswalker)
                        </option>
                      ))}
                    </select>
                  ) : (
                    <select
                      onChange={(e) =>
                        setTargets((prev) => ({
                          ...prev,
                          [card.id]: { ...prev[card.id], target_card_id: e.target.value },
                        }))
                      }
                      defaultValue=""
                    >
                      <option value="">Target Creature</option>
                      {(hints.creature_targets ?? []).map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                      {(hints.planeswalker_targets ?? []).map((t) => (
                        <option key={`pw-${t.id}`} value={t.id}>
                          {t.name} (Planeswalker)
                        </option>
                      ))}
                    </select>
                  )
                ) : null}
                {hints?.supports_divide ? (
                  <div className="divide-box">
                    <p style={{ margin: "0.2rem 0" }}>Damage Distribution</p>
                    {[...(hints.player_targets ?? []).map((p) => ({ id: String(p.id), name: p.name })), ...(hints.creature_targets ?? [])].map(
                      (targetOption) => (
                        <div key={`${card.id}-dist-${targetOption.id}`} className="row">
                          <span>{targetOption.name}</span>
                          <input
                            type="number"
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
                {hints?.stack_targets?.length ? (
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
        </div>
      </div>
      {hoverPreview ? (
        <aside className="card-hover-preview">
          {resolveCardMediaUrl(hoverPreview.imageUri) ? (
            <img src={resolveCardMediaUrl(hoverPreview.imageUri)} alt={hoverPreview.name} loading="lazy" />
          ) : null}
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
            {hoverPreview.oracleText ? <small>{hoverPreview.oracleText}</small> : null}
          </div>
        </aside>
      ) : null}
    </section>
  );
}
