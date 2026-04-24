import type { MatchState } from "../types";

type Props = {
  match: MatchState;
};

export function StackLog({ match }: Props) {
  return (
    <section className="panel stack-log">
      <h2>Stack + Match Log</h2>
      <div className="stack-box">
        {match.stack.length === 0 ? <p>Stack Empty</p> : null}
        {match.stack.map((item) => (
          <div key={item.id} className="stack-item">
            <strong>{item.label}</strong>
            <span>
              P{item.controller} | {item.effect_key}
            </span>
          </div>
        ))}
      </div>
      <div className="log-box">
        {match.log.slice().reverse().map((line, i) => (
          <p key={`${line}-${i}`}>{line}</p>
        ))}
      </div>
    </section>
  );
}
