import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AiDebugHands } from '../api/match-contract';
import type { MatchState } from '../types';
import { CardArt } from './CardArt';

export function AiHandDebug({ match }: { match: MatchState }) {
  const [enabled, setEnabled] = useState(false);
  const [snapshot, setSnapshot] = useState<AiDebugHands>();
  const [error, setError] = useState('');
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setError('');
    void api.aiDebugHands(match.id).then(value => {
      if (!cancelled) setSnapshot(value);
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { cancelled = true; };
  }, [enabled, match.id, match.revision]);
  if (!Object.values(match.controllers ?? {}).includes('ai')) return null;
  const current = snapshot?.match_id === match.id && snapshot.game_number === match.game_number
    && snapshot.revision >= (match.revision ?? 0) ? snapshot : undefined;
  return <section className="panel debug-ai-hands" aria-label="AI hand debug inspection">
    <label><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} /> Reveal AI hands (debug)</label>
    {enabled ? <>
      <p>Hidden information for bug testing only. This does not change what the AI knows. Click a card to read its text.</p>
      {error ? <p role="alert">{error}</p> : !current ? <p role="status">Loading current AI hands...</p> : <>
        <small>Game {current.game_number}, turn {current.turn}, revision {current.revision}</small>
        {Object.entries(current.hands).map(([seat, cards]) => <div key={seat}>
          <h3>P{seat} AI hand · {cards.length} cards</h3>
          <div className="debug-ai-hand-cards">{cards.map(card => <details key={card.id}>
            <summary><CardArt name={card.name} uri={card.image_uri} /><strong>{card.name}</strong><span>{card.mana_cost || 'No mana cost'}</span></summary>
            <p>{card.type_line}</p><p>{card.oracle_text}</p>
          </details>)}</div>
          {!cards.length ? <p>Empty hand.</p> : null}
        </div>)}
      </>}
    </> : null}
  </section>;
}
