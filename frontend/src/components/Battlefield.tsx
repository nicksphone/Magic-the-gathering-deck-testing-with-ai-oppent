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
  const [targets, setTargets] = useState<Record<string, Record<string, unknown>>>({});
  const [costChoice, setCostChoice] = useState<Record<string, string>>({});

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
            </article>
          ))}
        </div>
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
                {hints?.creature_targets?.length ? (
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
                      {hints.creature_targets.map((t) => (
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
                          [card.id]: { ...prev[card.id], target_card_id: e.target.value },
                        }))
                      }
                      defaultValue=""
                    >
                      <option value="">Target Creature</option>
                      {hints.creature_targets.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  )
                ) : null}
                {hints?.supports_divide ? (
                  <input
                    placeholder='Divide distribution JSON, e.g. {"1":2,"2":1}'
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value || "{}");
                        setTargets((prev) => ({ ...prev, [card.id]: { ...prev[card.id], target_distribution: parsed } }));
                      } catch {
                        // ignore invalid json input until parsable
                      }
                    }}
                  />
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
