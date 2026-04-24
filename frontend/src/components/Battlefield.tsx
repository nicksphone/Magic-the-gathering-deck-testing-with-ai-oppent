import { useMemo, useState } from "react";
import type { LegalMove, MatchState } from "../types";

type Props = {
  match: MatchState;
  legalMoves: LegalMove[];
  onCardAction: (playerId: number, action: Record<string, unknown>) => void;
};

export function Battlefield({ match, legalMoves, onCardAction }: Props) {
  const p1 = match.players["1"];
  const p2 = match.players["2"];
  const castMoves = useMemo(() => legalMoves.filter((m) => m.type === "cast_spell"), [legalMoves]);
  const loyaltyMoves = useMemo(() => legalMoves.filter((m) => m.type === "activate_loyalty"), [legalMoves]);
  const [targets, setTargets] = useState<Record<string, Record<string, unknown>>>({});
  const [costChoice, setCostChoice] = useState<Record<string, string>>({});
  const [divideInputs, setDivideInputs] = useState<Record<string, Record<string, number>>>({});

  function castAction(cardId: string) {
    const t = targets[cardId] ?? {};
    onCardAction(1, {
      type: "cast_spell",
      card_id: cardId,
      targets: t,
      cost_choice: costChoice[cardId] ? { id: costChoice[cardId] } : undefined,
    });
  }

  return (
    <section className="panel battlefield">
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
        </div>
        <div className="cards">
          {p2.battlefield.map((card) => (
            <article key={card.id} className={`card ${card.tapped ? "tapped" : ""}`} title={card.name}>
              <h4>{card.name}</h4>
              <p>{card.types.join(" ")}</p>
              <small>
                {card.power ?? "-"}/{card.toughness ?? "-"}
              </small>
              {"Planeswalker" === card.types[0] || card.types.includes("Planeswalker") ? <small>LOY: {card.loyalty ?? 0}</small> : null}
            </article>
          ))}
        </div>
      </div>

      <div className="player-row player">
        <div className="zone-meta">
          <span>Library {p1.library_count}</span>
          <span>GY {p1.graveyard_count}</span>
          <span>Exile {p1.exile_count}</span>
          <span>Hand {p1.hand_count}</span>
        </div>
        <div className="cards">
          {p1.battlefield.map((card) => (
            <article key={card.id} className={`card ${card.tapped ? "tapped" : ""}`} title={card.name}>
              <h4>{card.name}</h4>
              <p>{card.types.join(" ")}</p>
              <small>
                {card.power ?? "-"}/{card.toughness ?? "-"}
              </small>
              {"Planeswalker" === card.types[0] || card.types.includes("Planeswalker") ? <small>LOY: {card.loyalty ?? 0}</small> : null}
            </article>
          ))}
        </div>
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
        <div className="hand-row">
          {p1.hand.map((card) => {
            const move = castMoves.find((m) => m.card_id === card.id);
            if (!move) {
              return (
                <button key={card.id} disabled>
                  {card.name} (not castable)
                </button>
              );
            }
            const hints = move.target_hints;
            return (
              <div key={card.id} className="cast-card-box">
                <button onClick={() => castAction(card.id)}>
                  Cast {card.name} {move.mana_cost ? `(${move.mana_cost})` : ""}
                </button>
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
    </section>
  );
}
