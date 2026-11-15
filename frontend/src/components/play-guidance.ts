import type {LegalMove, MatchState} from "../types";

type PlayGuidance = {
  title: string;
  detail: string;
  href: "#match-controls" | "#table" | "#automatic-play-toggle" | "#your-hand"
    | "#attack-declaration" | "#block-declaration" | "#opening-hand-choice" | "#turn-commands";
  linkLabel: string;
};
const guide = (title: string, detail: string, href: PlayGuidance["href"] = "#match-controls",
  linkLabel = "Show actions and choices"): PlayGuidance => ({title, detail, href, linkLabel});

export function getPlayGuidance(
  match: MatchState | null, moves: LegalMove[], actor: number, autoPaused: boolean,
): PlayGuidance {
  if (!match) return guide("Choose a matchup",
    "Choose a deck for each seat, review the setup, then start the match.", "#match-controls", "Show match setup");
  if (match.match_complete) return guide("Series complete",
    "Review the series result at the table.", "#table", "Review the result");
  if (match.winner !== null) return guide(match.winner === 0 ? "Game drawn" : "Game over",
    "Review the result and between-games controls before the next game.", "#match-controls", "Show between-games controls");
  if (match.controllers?.[String(actor)] === "ai") return autoPaused
    ? guide("Automatic play is paused", `Player ${actor} is AI-controlled. Resume automatic play to let that seat continue.`,
      "#automatic-play-toggle", "Show automatic-play control")
    : guide("AI controls this decision", `Player ${actor} is AI-controlled. Watch the table while that seat handles its decision.`,
      "#table", "Watch the table");

  const humans = [1, 2].filter(seat => match.controllers?.[String(seat)] === "human");
  const who = match.mode !== "ai_vs_ai" && humans.length === 1 && humans[0] === actor ? "You" : `Player ${actor}`;
  const offered = (...types: string[]) => moves.some(move => types.includes(move.type));
  if (match.pending_replacement_choice || offered("choose_replacement")) return guide(`${who}: choose how this event happens`,
    "Review the offered replacement-effect choices for the pending event before continuing.");
  const pending = match.pending_trigger_order;
  if (pending?.phase === "targets" || offered("choose_trigger_target")) return guide(`${who}: choose a target`,
    "Choose an offered target in the required-choice controls below. Nothing is selected automatically.");
  if (pending?.phase === "optional" || offered("choose_optional_effect")) return guide(`${who}: accept or decline the effect`,
    "Review the offered options for this optional effect. Nothing is accepted or declined automatically.");
  if (pending || offered("choose_trigger_order")) return guide(`${who}: choose the order of effects`,
    "Review and confirm the required order below before continuing.");
  if (match.pending_mechanic_choice || offered("choose_mechanic")) return guide(`${who}: a choice is required`,
    "Review the required-choice controls below. If the choice is unsupported, do not advance.");
  if (match.pregame_pending) return guide(`${who}: review the opening hand`,
    "Use the opening-hand controls to keep or redraw. Review any required cards to put on the bottom before confirming.",
    "#opening-hand-choice", "Review the opening hand");
  if (offered("block")) return guide(`${who}: assign blockers`,
    "Select a blocker, then an attacker. Assignments stay a draft until Submit Blocks is used.", "#block-declaration", "Review and submit blocks");
  if (offered("attack")) return guide(`${who}: select attackers`,
    "Select attackers and review the draft. Use Submit Attackers to declare the attack.", "#attack-declaration", "Review and submit attackers");

  const handPlay = offered("cast_spell", "cycle_card", "foretell", "suspend");
  const hasPlay = handPlay || offered("activate_ability", "activate_loyalty", "activate_mana_ability", "equip", "crew", "ninjutsu");
  const playLocation = handPlay ? "#your-hand" : "#table";
  if (match.stack.length) {
    if (hasPlay) return guide(`${who}: an effect is waiting`,
      "Review the offered response plays at the table. The stack is the spells and abilities waiting to resolve.",
      playLocation, "Review offered responses");
    return guide(`${who}: an effect is waiting`, offered("pass_priority")
      ? "Pass Priority means taking no action now. The waiting effect resolves only after both players pass."
      : "Review the waiting effects and required-choice messages. No response action is currently offered.",
    offered("pass_priority") ? "#turn-commands" : "#match-controls", "Review the response window");
  }
  if (offered("play_land")) return guide(`${who}: a land play is offered`,
    "Find the offered land play in Hand & permitted plays. Choose it there only when ready.", "#your-hand", "Find the land play");
  if (hasPlay) return guide(`${who}: review offered plays`,
    "The table shows available spell and ability controls. Review their targets and costs before choosing; nothing is selected automatically.",
    playLocation, "Find available plays");
  if (moves.length && moves.every(move => move.type === "pass_priority")) return guide(`${who}: take no action for now`,
    "Pass Priority takes no action now; it does not end the turn. The other player gets a chance to act.",
    "#turn-commands", "Show turn commands");
  return guide(moves.length ? "No guided action for this move" : "No action is offered",
    "Review the current state and required-choice messages. This guide does not invent a legal action or advance play.");
}
