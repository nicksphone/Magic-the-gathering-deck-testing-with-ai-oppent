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

export function combatDraftGuidance(draft?: CombatDraft, attackMove?: LegalMove, blockMove?: LegalMove): string | null {
  if (!draft) return null;
  if (blockMove) {
    const selected = blockMove.blockers?.find(card => card.id === draft.selectedBlocker);
    if (selected) {
      return `Block draft: not submitted. ${selected.name} is selected; click an attacker to assign it, then Submit Blocks.`;
    }
    const attackers = new Set(blockMove.attackers?.map(card => card.id));
    const blockers = new Set(blockMove.blockers?.map(card => card.id));
    const count = Object.entries(draft.blocks).filter(([id]) => attackers.has(id))
      .reduce((total, [, ids]) => total + new Set(ids.filter(id => blockers.has(id))).size, 0);
    return count
      ? `${count} block ${count === 1 ? "assignment" : "assignments"} drafted, not submitted. Submit Blocks to confirm.`
      : "No blocks drafted. Select a blocker, then an attacker. Submit Blocks confirms your assignments.";
  }
  if (attackMove) {
    const count = new Set(draft.attackers.filter(id => attackMove.options?.includes(id))).size;
    return count
      ? `${count} ${count === 1 ? "attacker" : "attackers"} selected, not submitted. Submit Attackers to declare your attack.`
      : "No attackers selected. Select attackers and review before submitting.";
  }
  return null;
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
