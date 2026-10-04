import type { CardView, MatchState } from "../types";

export type LandPile = {
  key: string; name: string; imageUri?: string; total: number; untapped: number; tapped: number;
  colors: string[]; amounts: Record<string, number>; cards: CardView[];
};

// Group presentation only. Never discard identity or hide an animated land in a resource pile.
export function groupBattlefield(cards: CardView[]): { nonLands: CardView[]; lands: LandPile[] } {
  const isResource = (card: CardView) => card.types.includes("Land") && !card.types.includes("Creature");
  const piles = new Map<string, LandPile>();
  for (const card of cards.filter(isResource)) {
    const colors = [...(card.mana_source_colors ?? [])].sort();
    const amounts = card.mana_source_amounts ?? {};
    const surface = Object.fromEntries(Object.entries(card).filter(([key]) => !["id", "tapped", "summoning_sick"].includes(key)));
    // All characteristics other than tap status/identity must agree; conservative grouping is safer.
    const key = JSON.stringify(surface);
    const pile = piles.get(key) ?? { key, name: card.name, imageUri: card.image_uri, total: 0, untapped: 0, tapped: 0, colors, amounts, cards: [] };
    pile.cards.push(card);
    pile.total++;
    if (card.tapped) pile.tapped++; else pile.untapped++;
    piles.set(key, pile);
  }
  return { nonLands: cards.filter(card => !isResource(card)), lands: [...piles.values()].sort((a,b) => a.name.localeCompare(b.name)) };
}

export function cardStates(card: CardView, match: Pick<MatchState, "attackers" | "blocks">, targetable = false, selected = false): string[] {
  return [card.tapped && "Tapped", match.attackers?.includes(card.id) && "Attacking",
    Object.values(match.blocks ?? {}).some(ids => ids.includes(card.id)) && "Blocking",
    card.types.includes("Creature") && card.summoning_sick && "Summoning sick", targetable && "Targetable", selected && "Selected"].filter(Boolean) as string[];
}
export const phases = ["Beginning", "Main I", "Combat", "Main II", "Ending"];
export function phaseIndex(step: string) {
  if (["untap","upkeep","draw"].includes(step)) return 0;
  if (step === "precombat_main") return 1;
  if (["begin_combat","declare_attackers","declare_blockers","combat_damage","end_combat"].includes(step)) return 2;
  if (step === "postcombat_main") return 3;
  if (["end_step","cleanup"].includes(step)) return 4;
  return -1;
}
