import type { LegalMove, MatchState } from "../types";
import { getPlayGuidance } from "./play-guidance";

type Props = {
  match: MatchState | null;
  legalMoves: LegalMove[];
  actingPlayerId: number;
  autoProgressPaused: boolean;
  compact?: boolean;
};

export function PlayGuide({ match, legalMoves, actingPlayerId, autoProgressPaused, compact = false }: Props) {
  const guide = getPlayGuidance(match, legalMoves, actingPlayerId, autoProgressPaused);
  return <section className="panel play-guide" aria-label="Play guide">
    <details open={!compact}>
      <summary>What to do next <small>Show or hide guidance</small></summary>
      <div className="play-guide-content">
        <div><h2>{guide.title}</h2><p>{guide.detail}</p></div>
        <a className="guide-link" href={guide.href}>{guide.linkLabel}</a>
      </div>
    </details>
    <details className="quick-glossary">
      <summary>New to Magic? A few useful terms</summary>
      <dl>
        <div><dt>Priority</dt><dd>Your chance to play a spell or ability. You can have priority during either player's turn. Passing is not the same as ending your turn.</dd></div>
        <div><dt>Stack</dt><dd>Spells and abilities waiting to resolve. The newest is on top; it resolves when both players pass in succession.</dd></div>
        <div><dt>Mana</dt><dd>The resource you spend to cast spells and pay costs. Most lands can be tapped to produce mana.</dd></div>
        <div><dt>Tapped</dt><dd>A card turned sideways. Many actions tap a card, and it normally untaps at the beginning of its controller's next turn.</dd></div>
      </dl>
    </details>
  </section>;
}
