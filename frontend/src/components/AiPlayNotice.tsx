import {useEffect, useState} from "react";
import type {AiPlay} from "../lib/ai-plays";
import {CardArt} from "./CardArt";
import "../styles/ai-play-notice.css";

export type {AiPlay} from "../lib/ai-plays";

function PlayNotice({play}: {play: AiPlay}) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), 6_000);
    return () => window.clearTimeout(timer);
  }, []);
  if (!visible) return null;
  return <article className="ai-play-notice">
    <div className="ai-play-notice-art" aria-hidden="true">
      <CardArt uri={play.imageUri} name={play.name} />
    </div>
    <div className="ai-play-notice-copy">
      <p className="ai-play-notice-context">{play.playerName} · Turn {play.turn}</p>
      <p className="ai-play-notice-title">AI P{play.controller} played <strong>{play.name}</strong></p>
      {play.targets.length ? <p className="ai-play-notice-targets">Targets: {play.targets.join(", ")}</p> : null}
    </div>
  </article>;
}

export function AiPlayNotice({plays}: {plays: AiPlay[]}) {
  return <aside className="ai-play-notices" role="status" aria-live="polite"
    aria-atomic={false} aria-relevant="additions">
    {plays.slice(-3).map(play => <PlayNotice key={play.id} play={play} />)}
  </aside>;
}
