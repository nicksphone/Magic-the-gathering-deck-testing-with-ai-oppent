import { useEffect, useRef } from "react";
import type { LegalMove, MatchState } from "../types";
import { getPlayGuidance } from "./play-guidance";

type Props = {
  match: MatchState;
  moves: LegalMove[];
  actor: number;
  passDisabled: boolean;
  onPassPriority: () => void;
  combatForm?: "attack-declaration" | "block-declaration";
  combatDisabled: boolean;
  choiceRequired: boolean;
  draftGuidance: string | null;
  autoProgressPaused: boolean;
  onToggleAutomaticPlay?: () => void;
  automaticPlayDisabled?: boolean;
};

export function TurnCommandBar(props: Props) {
  const element = useRef<HTMLElement>(null);
  useEffect(() => {
    const bar = element.current;
    if (!bar) return;
    const style = document.documentElement.style;
    const previous = style.getPropertyValue("--turn-command-space");
    const measure = () => {
      // CSS layout units avoid applying page zoom twice to the reserved space.
      const value = `${bar.offsetHeight + 24}px`;
      if (style.getPropertyValue("--turn-command-space") !== value) style.setProperty("--turn-command-space", value);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(bar);
    measure();
    return () => {
      observer.disconnect();
      if (previous) style.setProperty("--turn-command-space", previous);
      else style.removeProperty("--turn-command-space");
    };
  }, []);

  const guide = getPlayGuidance(props.match, props.moves, props.actor, props.autoProgressPaused);
  const phase = typeof props.match.step === "string" ? props.match.step.replaceAll("_", " ") : "Awaiting phase";
  const human = (props.match.controllers?.[String(props.actor)] ?? "human") === "human";
  const humanChoice = human && props.choiceRequired;
  const combat = human && !props.choiceRequired && props.match.winner === null ? props.combatForm : undefined;
  const hint = !human || props.match.winner !== null ? guide.detail
    : humanChoice ? "Complete the required choice before continuing."
    : combat ? props.draftGuidance : "Passing gives up this chance to act, not your whole turn.";

  return <section className="turn-command-bar" aria-label="Turn commands" ref={element} id="turn-commands" tabIndex={-1}>
    <div className="turn-command-context">
      <span className="turn-command-kicker">Turn {props.match.turn ?? "?"} / {phase}</span>
      <p className="turn-command-title" role="status">{guide.title}</p>
      <p className="turn-command-hint">{hint}</p>
    </div>
    <div className="turn-command-actions">
      {humanChoice ? <a className="turn-command-primary" href="#match-controls">Review required choice</a>
        : combat ? <button className="turn-command-primary" type="submit" form={combat} disabled={props.combatDisabled}>
          {combat === "block-declaration" ? "Submit Blocks" : "Submit Attackers"}
        </button> : null}
      <button className={humanChoice || combat || !human ? "turn-command-secondary" : "turn-command-primary"}
        type="button" onClick={props.onPassPriority} disabled={props.passDisabled}>Pass Priority</button>
      {props.onToggleAutomaticPlay ? <button className={!human && props.autoProgressPaused ? "turn-command-primary" : "turn-command-auto"} type="button" id="automatic-play-toggle"
        disabled={props.automaticPlayDisabled} onClick={props.onToggleAutomaticPlay}>
        {props.autoProgressPaused ? "Resume automatic play" : "Pause automatic play"}
      </button> : null}
    </div>
  </section>;
}
