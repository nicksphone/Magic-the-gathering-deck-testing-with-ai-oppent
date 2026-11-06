import type { DeckItem, DeckRecord } from '../types';
import { API_BASE } from './client.ts';

const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const CAPABILITY = /^[0-9a-f]{64}$/;
const ID = /^[a-zA-Z0-9_-]{1,100}$/;
const SESSION_KEY = 'mtg.forge.session';
const START_KEY = 'mtg.forge.pendingStart';
export const FORGE_ZONES = ['Hand', 'Library', 'Battlefield', 'Graveyard', 'Exile', 'Command', 'Sideboard'] as const;
type Face = { name: string; type: string; mana_cost: string; oracle_text: string; power: number; toughness: number };
export type ForgeCard = { card_id: number; controller_id: number; owner_id: number; tapped: boolean; face_down: boolean; face: Face; known_face?: Face };
export type ForgeDisplay = string | number | boolean | ForgeCard | { hidden: true }
  | { player_id: number; name: string } | { ability_id: number; description: string; source: ForgeCard }
  | { stack_id: number; source: ForgeCard | { hidden: true } };
export type ForgeState = { actor_id: number; turn: number; phase: string;
  players: { player_id: number; name: string; life: number;
    zones: Record<typeof FORGE_ZONES[number], { count: number; visible_cards: ForgeCard[] }> }[];
  stack: { stack_id: number; source: ForgeCard | { hidden: true } }[] };
export type ForgeQuestion = { actor_id: number; request_id: string; kind: string; min: number; max: number;
  choices: { token: string; display: ForgeDisplay }[] };
type ForgeInputMetadata = { input: string; generation: number; priority_epoch: number; revision: number; actor: number };
export type ForgeInfo = { prompt?: string; title?: string; labels?: string[]; ok_label?: string; cancel_label?: string;
  selection?: ForgeInputMetadata & { min: number; max: number; chosen: (ForgeCard | {hidden: true} | {player_id: number; name: string})[] };
  stack_selection?: ForgeInputMetadata & { chosen: {stack_id: number; source: ForgeCard | {hidden: true}}[] } };
export type ForgeSnapshot = { engine: 'forge'; session_id: string; sequence: number;
  status: 'starting' | 'running' | 'completed' | 'aborted' | 'failed'; actor_id: number | null;
  state: ForgeState | null; question: ForgeQuestion | null; info: ForgeInfo;
  last_answer: { action_id: string; request_id: string; status: 'submitted' | 'processing' | 'processed' | 'rejected' | 'uncertain'; reason: string | null } | null;
  result: { outcomes: string[]; turns: number; draw: boolean; win_condition: string } | null;
  error: string | { code: string; message: string } | null };
export type ForgeStart = { deck_a: DeckItem[]; deck_b: DeckItem[]; name_a: string; name_b: string; human_seat: 0 | 1; seed?: number };
export type ForgeIntent = { key: string; capability: string; payload: ForgeStart };
export type ForgeIdentity = { session_id: string; capability: string };
export type ForgeAnswer = { request_id: string; tokens: string[]; sequence: number; action_id: string };
type StorageAccess = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function record(v: unknown): v is Record<string, unknown> { return typeof v === 'object' && v !== null && !Array.isArray(v); }
function keys(v: Record<string, unknown>, required: string[], optional: string[] = []) {
  return required.every(k => Object.hasOwn(v, k)) && Object.keys(v).every(k => required.includes(k) || optional.includes(k));
}
const text = (v: unknown): v is string => typeof v === 'string' && v.length <= 100000;
const integer = (v: unknown): v is number => Number.isSafeInteger(v);
const count = (v: unknown): v is number => integer(v) && v >= 0;
function need(ok: unknown, message = 'Invalid Forge response'): asserts ok { if (!ok) throw new Error(message); }
function face(v: unknown) {
  return record(v) && keys(v, ['name','type','mana_cost','oracle_text','power','toughness'])
    && ['name','type','mana_cost','oracle_text'].every(k => text(v[k])) && integer(v.power) && integer(v.toughness);
}
function card(v: unknown): v is ForgeCard {
  return record(v) && keys(v, ['card_id','controller_id','owner_id','tapped','face_down','face'], ['known_face'])
    && ['card_id','controller_id','owner_id'].every(k => count(v[k])) && typeof v.tapped === 'boolean'
    && typeof v.face_down === 'boolean' && face(v.face) && (v.known_face === undefined || face(v.known_face));
}
function hidden(v: unknown) { return record(v) && keys(v, ['hidden']) && v.hidden === true; }
function stack(v: unknown) { return record(v) && keys(v, ['stack_id','source']) && count(v.stack_id) && (card(v.source) || hidden(v.source)); }
function player(v: unknown) { return record(v) && keys(v, ['player_id','name']) && count(v.player_id) && text(v.name); }
function display(v: unknown): boolean {
  return text(v) || typeof v === 'boolean' || integer(v) || card(v) || hidden(v) || stack(v)
    || player(v)
    || (record(v) && keys(v, ['ability_id','description','source']) && count(v.ability_id) && text(v.description) && card(v.source));
}
function state(v: unknown): v is ForgeState {
  return record(v) && keys(v, ['actor_id','turn','phase','players','stack']) && count(v.actor_id) && count(v.turn) && text(v.phase)
    && Array.isArray(v.stack) && v.stack.length <= 1000 && v.stack.every(stack)
    && Array.isArray(v.players) && v.players.length === 2 && v.players.every(p => record(p)
      && keys(p, ['player_id','name','life','zones']) && count(p.player_id) && text(p.name) && integer(p.life)
      && record(p.zones) && keys(p.zones, [...FORGE_ZONES]) && Object.values(p.zones).every(z => record(z)
        && keys(z, ['count','visible_cards']) && count(z.count) && Array.isArray(z.visible_cards)
        && z.visible_cards.length <= z.count && z.visible_cards.length <= 1000 && z.visible_cards.every(card)))
    && new Set(v.players.map(p => p.player_id)).size === 2 && v.players.some(p => p.player_id === v.actor_id);
}
function question(v: unknown): v is ForgeQuestion {
  return record(v) && keys(v, ['actor_id','request_id','kind','min','max','choices']) && count(v.actor_id)
    && typeof v.request_id === 'string' && UUID.test(v.request_id) && text(v.kind) && v.kind.length > 0
    && count(v.min) && count(v.max) && v.min <= v.max && Array.isArray(v.choices) && v.max <= v.choices.length
    && v.choices.length <= 1000 && v.choices.every(c => record(c) && keys(c, ['token','display'])
      && typeof c.token === 'string' && UUID.test(c.token) && display(c.display))
    && new Set(v.choices.map(c => c.token)).size === v.choices.length;
}
function inputMetadata(v: unknown, actor: unknown, stackSelection: boolean) {
  return record(v) && keys(v, ['chosen','input','generation','priority_epoch','revision','actor', ...(stackSelection ? [] : ['min','max'])])
    && text(v.input) && v.input.length > 0 && v.input.length <= 200 && count(v.actor) && v.actor === actor
    && ['generation','priority_epoch','revision'].every(k => count(v[k]))
    && Array.isArray(v.chosen) && v.chosen.length <= 1000
    && v.chosen.every(c => stackSelection ? stack(c) : card(c) || hidden(c) || player(c))
    // A live selection may still be below its minimum while the actor is choosing.
    && (stackSelection || (count(v.min) && count(v.max) && v.min <= v.max && v.chosen.length <= v.max));
}
function optionLabels(v: unknown, q: ForgeQuestion | null) {
  if (!Array.isArray(v) || v.length > 1000 || !v.every(text)) return false;
  if (!q) return true;
  // Native confirmations use booleans; option dialogs use numeric label indices.
  if (q.choices.length === 2 && q.choices.every(c => typeof c.display === 'boolean'))
    return new Set(q.choices.map(c => c.display)).size === 2 && (v.length === 0 || v.length === 2);
  return v.length === q.choices.length && new Set(q.choices.map(c => c.display)).size === q.choices.length
    && q.choices.every(c => count(c.display) && c.display < v.length);
}
function info(v: unknown, actor: unknown, q: ForgeQuestion | null): v is ForgeInfo {
  return record(v) && keys(v, [], ['prompt','title','labels','ok_label','cancel_label','selection','stack_selection'])
    && ['prompt','title','ok_label','cancel_label'].every(k => v[k] === undefined || text(v[k]))
    && (v.labels === undefined || optionLabels(v.labels, q))
    && (v.selection === undefined || inputMetadata(v.selection, actor, false))
    && (v.stack_selection === undefined || inputMetadata(v.stack_selection, actor, true));
}
export function parseForgeSnapshot(v: unknown): ForgeSnapshot {
  need(record(v) && keys(v, ['engine','session_id','sequence','status','actor_id','state','question','info','last_answer','result','error']));
  need(v.engine === 'forge' && typeof v.session_id === 'string' && ID.test(v.session_id) && count(v.sequence)
    && typeof v.status === 'string' && ['starting','running','completed','aborted','failed'].includes(v.status)
    && (v.actor_id === null || count(v.actor_id)) && (v.state === null || state(v.state))
    && (v.question === null || question(v.question)) && info(v.info, v.actor_id, v.question));
  need(v.state === null || v.state.actor_id === v.actor_id);
  need(v.question === null || (v.state !== null && v.question.actor_id === v.actor_id));
  need(v.last_answer === null || (record(v.last_answer)
    && keys(v.last_answer, ['action_id','request_id','status','reason'])
    && typeof v.last_answer.action_id === 'string' && ID.test(v.last_answer.action_id)
    && typeof v.last_answer.request_id === 'string' && UUID.test(v.last_answer.request_id)
    && ['submitted','processing','processed','rejected','uncertain'].includes(String(v.last_answer.status))
    && (v.last_answer.reason === null || text(v.last_answer.reason))));
  need(v.result === null || (record(v.result) && keys(v.result, ['outcomes','turns','draw','win_condition'])
    && Array.isArray(v.result.outcomes) && v.result.outcomes.every(text) && count(v.result.turns)
    && typeof v.result.draw === 'boolean' && text(v.result.win_condition)));
  need((v.status === 'completed') === (v.result !== null));
  need(!['completed','aborted','failed'].includes(v.status) || v.question === null);
  need(v.error === null || text(v.error) || (record(v.error) && keys(v.error, ['code','message']) && text(v.error.code) && text(v.error.message)));
  return v as ForgeSnapshot;
}

export function canAnswerForge(s: ForgeSnapshot) {
  return s.status === 'running' && s.question !== null
    && (s.last_answer?.request_id !== s.question.request_id || s.last_answer.status === 'rejected');
}
export function makeForgeAnswer(s: ForgeSnapshot, tokens: string[], actionId: string): ForgeAnswer {
  const q = s.question;
  need(canAnswerForge(s) && q && ID.test(actionId) && tokens.length <= 256
    && tokens.length >= q.min && tokens.length <= q.max && new Set(tokens).size === tokens.length
    && tokens.every(t => q.choices.some(c => c.token === t)), 'Invalid native selection');
  return { request_id: q.request_id, tokens: [...tokens], sequence: s.sequence, action_id: actionId };
}
export function newerForgeSnapshot(previous: ForgeSnapshot | null, next: ForgeSnapshot) {
  need(!previous || previous.session_id === next.session_id, 'Invalid Forge session');
  need(!previous || previous.actor_id === null || previous.actor_id === next.actor_id, 'Invalid Forge actor');
  return previous && previous.sequence > next.sequence ? previous : next;
}
export function forgeChoiceLabel(value: ForgeDisplay, details: ForgeInfo): string {
  if (value === 'button_ok') return details.ok_label || 'OK';
  if (value === 'button_cancel') return details.cancel_label || 'Cancel';
  if (typeof value === 'boolean') return details.labels?.[value ? 0 : 1] || (value ? 'Yes' : 'No');
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return details.labels?.[value] ?? String(value);
  if ('hidden' in value) return 'Hidden card';
  if ('face' in value) return `${value.face.name} (native card ${value.card_id})`;
  if ('description' in value) return value.description;
  if ('name' in value) return value.name;
  return `Stack ${value.stack_id}: ${forgeChoiceLabel(value.source, details)}`;
}

export function newForgeKey(bytes = 16) {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes)), b => b.toString(16).padStart(2, '0')).join('');
}
function validStart(v: unknown): v is ForgeStart {
  const deck = (d: unknown) => Array.isArray(d) && d.length > 0 && d.length <= 60
    && d.every(c => record(c) && keys(c, ['quantity','card_name']) && count(c.quantity) && c.quantity > 0
      && typeof c.card_name === 'string' && c.card_name.trim().length > 0 && c.card_name.length <= 200
      && !['\r','\n','[',']','\0'].some(char => (c.card_name as string).includes(char)))
    && d.reduce((n,c) => n + c.quantity, 0) === 60;
  return record(v) && keys(v, ['deck_a','deck_b','name_a','name_b','human_seat'], ['seed'])
    && deck(v.deck_a) && deck(v.deck_b) && [v.name_a,v.name_b].every(n => typeof n === 'string' && n.trim().length > 0 && n.length <= 200 && !['\r','\n','\0'].some(char => n.includes(char)))
    && (v.human_seat === 0 || v.human_seat === 1) && (v.seed === undefined || integer(v.seed));
}
function privateWrite(storage: StorageAccess, key: string, value: unknown) {
  try {
    const raw = JSON.stringify(value); storage.setItem(key, raw);
    need(storage.getItem(key) === raw);
  } catch { throw new Error('Private browser storage is unavailable; no new native session was requested.'); }
}
export function readForgeSaved(storage?: StorageAccess): { session: ForgeIdentity | null; pending: ForgeIntent | null } {
  try {
    const target = storage ?? localStorage;
    const read = (key: string): unknown => { try { return JSON.parse(target.getItem(key) ?? 'null'); } catch { return null; } };
    const session = read(SESSION_KEY), pending = read(START_KEY);
    return {
      session: record(session) && keys(session, ['session_id','capability']) && typeof session.session_id === 'string'
        && ID.test(session.session_id) && typeof session.capability === 'string' && CAPABILITY.test(session.capability) ? session as ForgeIdentity : null,
      pending: record(pending) && keys(pending, ['key','capability','payload']) && typeof pending.key === 'string'
        && ID.test(pending.key) && typeof pending.capability === 'string' && CAPABILITY.test(pending.capability)
        && validStart(pending.payload) ? pending as ForgeIntent : null,
    };
  } catch { return { session: null, pending: null }; }
}
export function hasForgeSession() { const saved = readForgeSaved(); return Boolean(saved.session || saved.pending); }
export function prepareForgeStart(storage: StorageAccess, a: DeckRecord, b: DeckRecord, humanSeat: 1 | 2): ForgeIntent {
  const payload: ForgeStart = { deck_a: a.mainboard.map(c => ({quantity: c.quantity, card_name: c.card_name})),
    deck_b: b.mainboard.map(c => ({quantity: c.quantity, card_name: c.card_name})), name_a: a.name, name_b: b.name, human_seat: humanSeat === 1 ? 0 : 1 };
  need(validStart(payload) && [payload.name_a, payload.name_b, ...payload.deck_a.map(c => c.card_name),
    ...payload.deck_b.map(c => c.card_name)].every(safeNativeName),
  'Invalid native deck: select two exact 60-card mainboards with valid single-line names.');
  need(!hasSaved(storage), 'Recover the existing native session before starting another.');
  const intent = { key: newForgeKey(), capability: newForgeKey(32), payload };
  privateWrite(storage, START_KEY, intent); return intent;
}
function hasSaved(storage: StorageAccess) { const s = readForgeSaved(storage); return s.session || s.pending; }
function safeNativeName(value: string) {
  return ![...value].some(char => {
    const code = char.codePointAt(0)!;
    return code < 32 || code === 127 || (code >= 0xd800 && code <= 0xdfff) || '[]\u2028\u2029'.includes(char);
  });
}
export function rememberForgeSession(storage: StorageAccess, id: string, capability: string) {
  need(ID.test(id) && CAPABILITY.test(capability), 'Invalid Forge session identity');
  privateWrite(storage, SESSION_KEY, { session_id: id, capability });
  storage.removeItem(START_KEY);
}
export function clearForgeSaved(storage: StorageAccess) { storage.removeItem(SESSION_KEY); storage.removeItem(START_KEY); }

export function clearRejectedForgeStart(storage: StorageAccess, intent: ForgeIntent, error: unknown) {
  if (!(error instanceof ForgeHttpError) || error.status !== 422
    || !['invalid_start','invalid_deck','invalid_key','invalid_start_key'].includes(error.code ?? '')) return false;
  const saved = readForgeSaved(storage);
  if (saved.session || !saved.pending || saved.pending.key !== intent.key || saved.pending.capability !== intent.capability
    || JSON.stringify(saved.pending.payload) !== JSON.stringify(intent.payload)) return false;
  try {
    storage.removeItem(START_KEY);
    return storage.getItem(START_KEY) === null;
  } catch { return false; }
}

export class ForgeHttpError extends Error {
  readonly status: number;
  readonly code: string | null;
  constructor(status: number, code: string | null = null) {
    super(`Native request failed (${status}). Reconnect before taking another action.`);
    this.status = status; this.code = code;
  }
}
export function createForgeClient(base = API_BASE, fetcher: typeof fetch = fetch) {
  async function request(path: string, method: string, capability?: string, body?: unknown, key?: string, signal?: AbortSignal) {
    need(capability === undefined || CAPABILITY.test(capability), 'Invalid Forge capability');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (capability) headers.Authorization = `Bearer ${capability}`;
    if (key) headers['Idempotency-Key'] = key;
    let response: Response;
    try {
      const deadline = AbortSignal.timeout(path === '/sessions' ? 45000 : 15000);
      response = await fetcher(`${base}/forge${path}`, { method, headers, cache: 'no-store', redirect: 'error',
        referrerPolicy: 'no-referrer', body: body === undefined ? undefined : JSON.stringify(body), signal: signal ? AbortSignal.any([signal, deadline]) : deadline });
    } catch { throw new Error('Native connection unavailable. Reconnect; uncertain answers are never resent automatically.'); }
    if (!response.ok) {
      let code: string | null = null;
      try {
        const body: unknown = await response.json();
        if (record(body) && record(body.detail) && typeof body.detail.code === 'string'
          && /^[a-z_]{1,100}$/.test(body.detail.code)) code = body.detail.code;
      } catch { /* Unknown responses retain the delivery-uncertain fence. */ }
      throw new ForgeHttpError(response.status, code);
    }
    try { return await response.json() as unknown; }
    catch { throw new Error('Invalid Forge response'); }
  }
  const path = (id: string) => { need(ID.test(id), 'Invalid Forge session'); return `/sessions/${id}`; };
  async function session(id: string, response: Promise<unknown>) {
    const value = parseForgeSnapshot(await response);
    need(value.session_id === id, 'Invalid Forge session');
    return value;
  }
  return {
    async status(signal?: AbortSignal) {
      const value = await request('/status', 'GET', undefined, undefined, undefined, signal);
      need(record(value) && keys(value, ['available']) && typeof value.available === 'boolean');
      return { available: value.available };
    },
    async start(intent: ForgeIntent) { return parseForgeSnapshot(await request('/sessions', 'POST', intent.capability, intent.payload, intent.key)); },
    async get(id: string, cap: string, signal?: AbortSignal) { return session(id, request(path(id), 'GET', cap, undefined, undefined, signal)); },
    async answer(id: string, cap: string, answer: ForgeAnswer) { return session(id, request(`${path(id)}/answer`, 'POST', cap, answer)); },
    async close(id: string, cap: string) { return session(id, request(path(id), 'DELETE', cap)); },
  };
}
