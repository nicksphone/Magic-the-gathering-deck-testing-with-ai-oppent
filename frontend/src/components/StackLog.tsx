import { useState } from "react";
import type { MatchState } from "../types";

export function StackLog({ match }: { match: MatchState }) {
  const [limit, setLimit] = useState(5);
  return (
    <section className="panel stack-log" aria-label="Stack and match log">
      <h2>Stack <span className="count-badge">{match.stack.length}</span></h2>
      <div className="stack-box stack-box-compact" aria-live="polite">
        {match.stack.length === 0 ? <p className="quiet">No spells or abilities waiting</p> : null}
        {[...match.stack].reverse().map((item, index) => (
          <div key={item.id} className="stack-item">
            <strong>{item.label}</strong>
            <span>Controller P{item.controller} · {index === 0 ? "Top of stack" : `Below ${index}`}</span>
            <details className="stack-technical"><summary>Effect details</summary><code>{item.effect_key}</code></details>
          </div>
        ))}
      </div>
      <details className="match-log">
        <summary>Match log <span>{match.log.length} events</span></summary>
        <div id="match-log-lines" className="log-box">
          {match.log.slice(-limit).map((line, i) => <p key={`${match.log.length - limit + i}-${line}`}>{line}</p>)}
        </div>
        {match.log.length > limit ? <button aria-controls="match-log-lines" onClick={() => setLimit(value => value + 20)}>Show more log events</button> : null}
        {limit > 5 ? <button aria-controls="match-log-lines" onClick={() => setLimit(5)}>Show fewer log events</button> : null}
      </details>
    </section>
  );
}
