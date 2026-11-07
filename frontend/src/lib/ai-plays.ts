import type {MatchState} from '../types';

export type AiPlay = {
  id: string;
  name: string;
  controller: number;
  playerName: string;
  turn: number;
  imageUri?: string;
  targets: string[];
};

export function newAiPlays(previous: MatchState | null, next: MatchState, sequence: number): AiPlay[] {
  if (!previous || previous.id !== next.id || previous.game_number !== next.game_number
    || (previous.revision !== undefined && next.revision !== undefined && next.revision <= previous.revision)) return [];

  // The public log is a rolling tail, not an append-only array or event counter.
  let overlap = Math.min(previous.log.length, next.log.length);
  while (overlap > 0 && !previous.log.slice(-overlap).every((line, index) => line === next.log[index])) overlap--;
  if (!overlap && previous.log.length) return [];
  const lines = next.log.slice(overlap);
  const publicCards = Object.values(next.players).flatMap(player => [...player.battlefield, ...player.graveyard]);
  return lines.flatMap((line, index) => {
    if (typeof line !== 'string') return [];
    const actors = Object.values(next.players).filter(player => line.startsWith(`${player.name} casts/activates `));
    if (actors.length !== 1 || next.controllers?.[String(actors[0].id)] !== 'ai' || !line.endsWith('.')) return [];
    const actor = actors[0];
    const name = line.slice(`${actor.name} casts/activates `.length, -1);
    if (!name) return [];
    const stack = next.stack.filter(item => item.label === name && item.controller === actor.id
      && !previous.stack.some(old => old.id === item.id));
    const images = [...new Set(publicCards.filter(card => card.name === name && card.image_uri).map(card => card.image_uri))];
    const targetIds = stack.length === 1 && lines.filter(other => other === line).length === 1 ? stack[0].targets : undefined;
    const targets = Array.isArray(targetIds) ? targetIds.map(id => publicCards.find(card => card.id === id)?.name) : [];
    return [{id:`${next.id}:${next.game_number}:${sequence}:${index}`, name, controller:actor.id,
      playerName:actor.name, turn:next.turn, imageUri:images.length === 1 ? images[0] : undefined,
      targets:targets.every((target): target is string => typeof target === 'string') ? targets : []}];
  });
}
