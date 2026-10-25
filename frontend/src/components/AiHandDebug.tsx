import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AiDebugHands } from '../api/match-contract';
import type { MatchState } from '../types';
import { CardArt } from './CardArt';

export function AiHandDebug({ match }: { match: MatchState }) {
  const [enabled, setEnabled] = useState(false);
  const [snapshot, setSnapshot] = useState<AiDebugHands>();
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  const hasAi = Object.values(match.controllers ?? {}).includes('ai');
  useEffect(() => {
    setSnapshot(undefined);
    setError('');
    if (!enabled || !hasAi) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    void api.aiDebugHands(match.id).then(value => {
      if (cancelled) return;
      if (value.match_id === match.id && value.game_number === match.game_number) setSnapshot(value);
      else setError('The match or game changed during inspection. Refresh the snapshot.');
      setLoading(false);
    }).catch((reason: unknown) => {
      if (!cancelled) {
        setError(reason instanceof Error ? reason.message : String(reason));
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [enabled, hasAi, match.id, match.game_number, refresh]);
  if (!hasAi) return null;
  const current = snapshot?.match_id === match.id && snapshot.game_number === match.game_number
    ? snapshot : undefined;
  return <section className="panel debug-ai-hands" aria-label="AI hand debug inspection">
    <label><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} /> Reveal AI hands (debug)</label>
    {enabled ? <>
      <p>Hidden information for bug testing only. This does not change what the AI knows. Click a card to read its text.</p>
      <button type="button" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh AI hand snapshot</button>
      {error ? <p role="alert">{error}</p> : !current ? <p role="status">Loading AI hand snapshot...</p> : <>
        <small>Captured snapshot: game {current.game_number}, turn {current.turn}, revision {current.revision}; current match revision {match.revision ?? 'unknown'}.</small>
        <p>This snapshot does not auto-refresh as play advances. Refresh to inspect again.</p>
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
