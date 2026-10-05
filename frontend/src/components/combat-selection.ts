import type { LegalMove } from "../types";

export type CombatDraft = {
  attackers: string[];
  attackTargets: Record<string, string>;
  bands: string[][];
  blocks: Record<string, string[]>;
  selectedBlocker: string | null;
};

export function emptyCombatDraft(): CombatDraft {
  return { attackers: [], attackTargets: {}, bands: [], blocks: {}, selectedBlocker: null };
}

export function selectAttackers(draft: CombatDraft, attackers: string[]): CombatDraft {
  return { ...draft, attackers: [...new Set(attackers)],
    bands: draft.bands.map(band => band.filter(id => attackers.includes(id))).filter(band => band.length > 1) };
}

export function toggleAttacker(draft: CombatDraft, id: string): CombatDraft {
  return selectAttackers(draft, draft.attackers.includes(id) ? draft.attackers.filter(cid => cid !== id) : [...draft.attackers, id]);
}

export function bandAttackers(draft: CombatDraft, source: string, target: string, move: LegalMove, defaultDefender: string) {
  const group = [...new Set([source, target, ...draft.bands.filter(band => band.includes(source) || band.includes(target)).flat()])];
  if (source === target || group.some(id => !move.options?.includes(id))) {
    return { draft, error: "Choose two different eligible attackers." };
  }
  if (group.filter(id => !move.banding_attackers?.includes(id)).length > 1) {
    return { draft, error: "A band needs banding; at most one member may lack it." };
  }
  if (new Set(group.map(id => draft.attackTargets[id] || defaultDefender)).size > 1) {
    return { draft, error: "Band members must attack the same defender." };
  }
  return { draft: { ...selectAttackers(draft, [...draft.attackers, ...group]),
    bands: [...draft.bands.filter(band => !band.some(id => group.includes(id))), group] }, error: null };
}

export function assignBlocker(draft: CombatDraft, blocker: string, attacker: string, move: LegalMove) {
  if (!move.blockers?.some(card => card.id === blocker) || !move.attackers?.some(card => card.id === attacker)
    || !move.legal_blocks?.[blocker]?.includes(attacker)) {
    return { draft, error: "That creature cannot block this attacker." };
  }
  const capacity = move.blocker_capacities?.[blocker] ?? (move.blocker_capacities?.[blocker] === null ? Infinity : 1);
  const previous = Object.entries(draft.blocks).filter(([, ids]) => ids.includes(blocker)).map(([id]) => id);
  if (capacity > 1 && !previous.includes(attacker) && previous.length >= capacity) {
    return { draft, error: "This blocker has reached its blocking capacity. Clear an assignment first." };
  }
  const blocks = Object.fromEntries(Object.entries(draft.blocks).map(([id, ids]) => [id,
    capacity === 1 && id !== attacker ? ids.filter(cid => cid !== blocker) : [...ids]]));
  blocks[attacker] = [...new Set([...(blocks[attacker] ?? []), blocker])];
  return { draft: { ...draft, blocks, selectedBlocker: null }, error: null };
}
