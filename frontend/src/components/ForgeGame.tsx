// Native UI for the Forge Team/Card-Forge engine; no Python action conversion.
import { useEffect, useRef, useState } from 'react';
import type { DeckRecord } from '../types';
import { canAnswerForge, clearForgeSaved, clearRejectedForgeStart, createForgeClient, forgeChoiceLabel, ForgeHttpError,
  FORGE_ZONES, makeForgeAnswer, newerForgeSnapshot, newForgeKey, prepareForgeStart,
  readForgeSaved, rememberForgeSession, type ForgeCard, type ForgeIntent, type ForgeSnapshot } from '../api/forge';
import '../styles/forge-game.css';

const client = createForgeClient();
type Props = { deckA?: DeckRecord; deckB?: DeckRecord; humanSeat: 1 | 2; disabled: boolean;
  onActiveChange: (active: boolean) => boolean };
const message = (error: unknown) => error instanceof ForgeHttpError
  ? error.message : 'Native connection or storage unavailable. Reconnect before acting; no answer will be resent automatically.';

export function ForgeChoices({ snapshot, disabled, onAnswer }: { snapshot: ForgeSnapshot; disabled: boolean;
  onAnswer: (tokens: string[]) => void }) {
  const [selected, setSelected] = useState<string[]>([]);
  const q = snapshot.question;
  if (!q) return null;
  const nativeSelection = snapshot.info.selection;
  const nativeChosen = nativeSelection?.chosen ?? snapshot.info.stack_selection?.chosen;
  const blocked = disabled || !canAnswerForge(snapshot);
  const single = q.min === 1 && q.max === 1;
  const toggle = (token: string) => setSelected(current => current.includes(token)
    ? current.filter(t => t !== token) : current.length < q.max ? [...current, token] : current);
  function move(index: number, direction: number) {
    setSelected(current => {
      const next = [...current], to = index + direction;
      if (to >= 0 && to < next.length) [next[index], next[to]] = [next[to], next[index]];
      return next;
    });
  }
  return <section id="forge-native-choice" className="forge-choice" data-request-id={q.request_id} aria-label="Native choice">
    <h3>{snapshot.info.title || 'Your native decision'}</h3>
    {snapshot.info.prompt ? <p>{snapshot.info.prompt}</p> : null}
    <p className="forge-meta">{q.kind} / Native actor {q.actor_id}</p>
    {nativeSelection ? <p>Choose {nativeSelection.min === nativeSelection.max ? nativeSelection.min
      : `${nativeSelection.min} to ${nativeSelection.max}`} total. {nativeSelection.chosen.length} selected.</p> : null}
    {nativeChosen?.length ? <p>Selected: {nativeChosen.map(value => forgeChoiceLabel(value, snapshot.info)).join(', ')}</p> : null}
    {single ? <div className="forge-options">{q.choices.map(c => <button key={c.token} type="button"
      data-native-token={c.token} disabled={blocked} onClick={() => onAnswer([c.token])}>
      {forgeChoiceLabel(c.display, snapshot.info)}</button>)}</div> : <>
      <p>Select {q.min} to {q.max}. {q.kind === 'order' ? 'Every item must be explicitly selected and ordered.' : 'Selection order is preserved.'}</p>
      <div className="forge-options">{q.choices.map(c => <label key={c.token}>
        <input type="checkbox" data-native-token={c.token} checked={selected.includes(c.token)}
          disabled={blocked || (!selected.includes(c.token) && selected.length >= q.max)} onChange={() => toggle(c.token)} />
        {forgeChoiceLabel(c.display, snapshot.info)}</label>)}</div>
      <p role="status">{selected.length} selected / {q.min} to {q.max}</p>
      <ol className="forge-order">{selected.map((token, i) => <li key={token}>
        <span>{forgeChoiceLabel(q.choices.find(c => c.token === token)!.display, snapshot.info)}</span>
        <button type="button" aria-label={`Move selection ${i + 1} up`} disabled={blocked || i === 0}
          onClick={() => move(i, -1)}>Move selection {i + 1} up</button>
        <button type="button" aria-label={`Move selection ${i + 1} down`} disabled={blocked || i === selected.length - 1}
          onClick={() => move(i, 1)}>Move selection {i + 1} down</button>
      </li>)}</ol>
      <button type="button" disabled={blocked || selected.length < q.min || selected.length > q.max}
        onClick={() => onAnswer([...selected])}>Submit native selection</button>
    </>}
  </section>;
}

function NativeCard({ card }: { card: ForgeCard }) {
  return <article className={`forge-card${card.tapped ? ' forge-tapped' : ''}`}>
    <strong>{card.face.name || 'Face-down card'}</strong><span>{card.face.mana_cost}</span>
    <small>{card.face.type}</small>
    {/\bCreature\b/i.test(card.face.type) ? <span>Power / toughness: {card.face.power} / {card.face.toughness}</span> : null}
    {card.known_face ? <p>Known to you: {card.known_face.name}</p> : null}
    {card.face.oracle_text ? <details><summary>Card text</summary><p>{card.face.oracle_text}</p></details> : null}
    <small>Native card {card.card_id}{card.tapped ? ' / tapped' : ''}</small>
  </article>;
}
export function ForgeBoard({ snapshot }: { snapshot: ForgeSnapshot }) {
  const s = snapshot.state;
  if (!s) return <p role="status">Waiting for the native actor view...</p>;
  return <div className="forge-board">
    <header><h3>Native table</h3><p>Turn {s.turn} / {s.phase || 'Pregame'}</p></header>
    {[...s.players].sort((a, b) => Number(a.player_id === s.actor_id) - Number(b.player_id === s.actor_id)).map(p =>
      <section className="forge-seat" key={p.player_id} aria-label={`${p.name} native board`}>
        <h3>{p.name} {p.player_id === s.actor_id ? '(you)' : '(native AI)'} <b>{p.life} life</b></h3>
        <p className="forge-meta">Native player {p.player_id}</p>
        {FORGE_ZONES.map(zone => <section className="forge-zone" key={zone}>
          <h4>{zone} / {p.zones[zone].count}</h4>
          {p.zones[zone].visible_cards.length ? <div className="forge-cards">
            {p.zones[zone].visible_cards.map(c => <NativeCard key={c.card_id} card={c} />)}
          </div> : <p className="forge-meta">{p.zones[zone].count ? 'No card identities disclosed.' : 'Empty'}</p>}
        </section>)}
      </section>)}
    <section aria-label="Native public stack"><h3>Stack / {s.stack.length}</h3>
      {s.stack.length ? s.stack.map(item => <div key={item.stack_id} className="forge-stack-item">
        <strong>Native stack {item.stack_id}</strong>{'hidden' in item.source ? <p>Hidden source</p> : <NativeCard card={item.source} />}
      </div>) : <p>No public stack items.</p>}
    </section>
  </div>;
}

export function ForgeGame({ deckA, deckB, humanSeat, disabled, onActiveChange }: Props) {
  const [saved, setSaved] = useState(readForgeSaved);
  const [opened, setOpened] = useState(() => Boolean(saved.session || saved.pending));
  const [snapshot, setSnapshot] = useState<ForgeSnapshot | null>(null);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState<string | null>(null);
  const [controlUncertain, setControlUncertain] = useState(false);
  const [reload, setReload] = useState(0);
  const busyRef = useRef(false);
  const current = useRef<ForgeSnapshot | null>(null);
  const identity = saved.session;
  const sessionRef = useRef(identity?.session_id ?? null);
  const rejectedRequest = useRef<string | null>(null);
  const controlEpoch = useRef(0);

  function accept(next: ForgeSnapshot) {
    if (sessionRef.current !== next.session_id) return;
    current.current = newerForgeSnapshot(current.current, next);
    setSnapshot(current.current);
  }
  useEffect(() => {
    if (!opened) return;
    const controller = new AbortController();
    client.status(controller.signal).then(s => { if (!controller.signal.aborted) setAvailable(s.available); })
      .catch(() => { if (!controller.signal.aborted) setAvailable(false); });
    return () => controller.abort();
  }, [opened, reload]);
  useEffect(() => {
    if (!identity) return;
    let live = true;
    let timer: number | undefined;
    const controller = new AbortController();
    async function poll() {
      const rejected = rejectedRequest.current;
      const epoch = controlEpoch.current;
      try {
        const next = await client.get(identity!.session_id, identity!.capability, controller.signal);
        if (!live || sessionRef.current !== identity!.session_id || epoch !== controlEpoch.current || busyRef.current) return;
        accept(next); setError(''); setMissing(false); setControlUncertain(false);
        if (rejected !== null && rejectedRequest.current === rejected) {
          setUncertain(request => request === rejected ? null : request);
          rejectedRequest.current = null;
        }
        if (['starting','running','restoring'].includes(current.current!.status)) timer = window.setTimeout(() => void poll(), 500);
      } catch (e) {
        if (!live || sessionRef.current !== identity!.session_id || epoch !== controlEpoch.current || busyRef.current) return;
        setMissing(e instanceof ForgeHttpError && e.status === 404);
        setError(message(e));
      }
    }
    void poll();
    // Unmount/StrictMode only cancel reads; closing a worker is an explicit action.
    return () => { live = false; controller.abort(); window.clearTimeout(timer); };
  }, [identity, reload]);

  async function start(recover = false) {
    if (disabled || busyRef.current || (!recover && (!deckA || !deckB)) || available !== true) return;
    if (!onActiveChange(true)) return;
    busyRef.current = true; setBusy(true); setError('');
    let intent: ForgeIntent | null = null;
    try {
      intent = recover ? readForgeSaved().pending : prepareForgeStart(localStorage, deckA!, deckB!, humanSeat);
      if (!intent) throw new Error('Missing start intent');
      setSaved(readForgeSaved());
      const next = await client.start(intent);
      rememberForgeSession(localStorage, next.session_id, intent.capability);
      sessionRef.current = next.session_id;
      accept(next); setSaved(readForgeSaved());
    } catch (e) {
      const cleared = intent !== null && clearRejectedForgeStart(localStorage, intent, e);
      const latest = readForgeSaved(); setSaved(latest);
      setError(cleared ? 'Native start was rejected before launch. Correct the saved deck names or selection and try again.' : message(e));
      if (!latest.pending && !latest.session) onActiveChange(false);
    } finally { busyRef.current = false; setBusy(false); }
  }
  async function answer(tokens: string[]) {
    if (busyRef.current || !identity || !current.current || disabled || controlUncertain) return;
    const s = current.current;
    if (uncertain === s.question?.request_id && s.last_answer?.status !== 'rejected') return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      const value = makeForgeAnswer(s, tokens, newForgeKey());
      setUncertain(value.request_id);
      accept(await client.answer(identity.session_id, identity.capability, value));
    } catch (e) {
      if (e instanceof ForgeHttpError && e.status === 409 && e.code === 'stale_question')
        rejectedRequest.current = s.question?.request_id ?? null;
      setError(message(e));
    }
    finally { busyRef.current = false; setBusy(false); setReload(n => n + 1); }
  }
  async function checkpointControl(resume = false) {
    const s = current.current;
    if (busyRef.current || blocked || !identity || !s
      || (resume ? s.status !== 'suspended' : !canAnswerForge(s))) return;
    busyRef.current = true; controlEpoch.current++; setBusy(true); setError(''); setControlUncertain(true);
    try {
      const operation = {sequence: s.sequence, action_id: newForgeKey()};
      const next = resume ? await client.resume(identity.session_id, identity.capability, operation)
        : await client.checkpoint(identity.session_id, identity.capability, {...operation, request_id: s.question!.request_id});
      accept(next); setControlUncertain(false);
      if (!resume && current.current?.status !== 'suspended')
        setError('Save was not confirmed. Reconnect to read the native session before acting.');
    } catch (e) { setError(message(e)); }
    finally { controlEpoch.current++; busyRef.current = false; setBusy(false); setReload(n => n + 1); }
  }
  async function close() {
    if (busyRef.current || !identity || disabled) return;
    busyRef.current = true; setBusy(true);
    try {
      accept(await client.close(identity.session_id, identity.capability));
      clearForgeSaved(localStorage); setSaved(readForgeSaved());
      sessionRef.current = null; current.current = null; rejectedRequest.current = null;
      setSnapshot(null); setUncertain(null); setControlUncertain(false); setMissing(false); setError(''); onActiveChange(false);
    } catch (e) { setError(message(e)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  function forgetMissing() {
    if (!missing || busyRef.current) return;
    try {
      clearForgeSaved(localStorage); setSaved(readForgeSaved()); sessionRef.current = null; current.current = null; setSnapshot(null);
      rejectedRequest.current = null; setMissing(false); setUncertain(null); setControlUncertain(false); setError(''); onActiveChange(false);
    } catch { setError('Private browser storage is unavailable.'); }
  }
  const q = snapshot?.question;
  const blocked = busy || disabled || Boolean(error) || missing || controlUncertain
    || (uncertain === q?.request_id && snapshot?.last_answer?.status !== 'rejected');
  const deckIssue = !deckA || !deckB ? 'Select both saved decks in the matchup controls.'
    : deckA.mainboard.reduce((n,c) => n + c.quantity, 0) !== 60 || deckB.mainboard.reduce((n,c) => n + c.quantity, 0) !== 60
      ? 'Both mainboards must contain exactly 60 cards.' : '';

  return <section className="panel forge-game" aria-label="Forge native game"
    data-forge-session={snapshot?.session_id ?? identity?.session_id ?? ''}
    data-forge-sequence={snapshot?.sequence ?? ''} data-forge-status={snapshot?.status ?? 'idle'}>
    <header><span className="eyebrow">Experimental / Opt-in native engine</span><h2>Forge table</h2></header>
    <p>One human versus native AI: Default Forge heuristic. The legacy Master difficulty dropdown does not apply.
      Single game, 60-card mains, empty runtime sideboards, open decklists.
      No BO3 or cold app restore of unsaved progress. Explicitly saved games can be resumed after a backend restart.</p>
    <p>Manual save only: unsaved progress after the last save is not guaranteed. Keep this browser's private session handle to resume.</p>
    <p>Sideboards are not used in this single-game preview; saved decklists are unchanged.</p>
    <p className="forge-meta">Powered by Forge Team / Card-Forge.</p>
    {!opened ? <button type="button" disabled={disabled} onClick={() => setOpened(true)}>Open native table</button> : <>
    {available === null ? <p role="status">Checking native runtime...</p> : available === false ? <p role="status">Native runtime unavailable. Ask the operator to configure the qualified Forge runtime.</p> : null}
    {!identity && !saved.pending ? <>
      <p>{deckA?.name ?? 'Deck A'} versus {deckB?.name ?? 'Deck B'} / Human seat {humanSeat}</p>
      {deckIssue ? <p>{deckIssue}</p> : null}
      <button type="button" disabled={disabled || busy || available !== true || Boolean(deckIssue)} onClick={() => start()}>Start native single game</button>
    </> : null}
    {saved.pending && !identity ? <div role="status"><p>A native start is pending. Recover the original decks, key and capability; do not create another game.</p>
      <button type="button" disabled={disabled || busy || available !== true} onClick={() => start(true)}>Recover native start</button></div> : null}
    {identity ? <div className="forge-toolbar">
      <button type="button" disabled={busy} onClick={() => setReload(n => n + 1)}>Reconnect native session</button>
      <button type="button" disabled={blocked || !snapshot || !canAnswerForge(snapshot)} onClick={() => checkpointControl()}>Save and pause</button>
      <button type="button" disabled={blocked || snapshot?.status !== 'suspended'} onClick={() => checkpointControl(true)}>Resume saved game</button>
      <button type="button" disabled={busy || disabled} onClick={close}>Close native session</button>
      {missing ? <button type="button" disabled={busy} onClick={forgetMissing}>Forget unavailable native session</button> : null}
    </div> : null}
    {busy ? <p role="status">Native request pending...</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {missing ? <p>This server cannot find the session. Reconnect to the backend that owns its saved checkpoint before forgetting the private handle.</p> : null}
    {snapshot ? <>
      <p className="forge-meta" role="status">Native session {snapshot.status} / update {snapshot.sequence}</p>
      {snapshot.status === 'suspended' ? <p role="status">Saved and paused at the last saved point. Resume saved game when ready.</p> : null}
      {snapshot.status === 'restoring' ? <p role="status">Restoring the saved game. Native choices remain unavailable until verification finishes.</p> : null}
      {controlUncertain ? <p role="status">Save or resume delivery is uncertain. Reconnect to read the authoritative session; the request will not be resent automatically.</p> : null}
      {snapshot.last_answer ? <p role="status">Answer {snapshot.last_answer.status}{snapshot.last_answer.reason ? `: ${snapshot.last_answer.reason}` : ''}.
        {' '}This reports callback processing, not a successful cast or game action.</p> : null}
      {uncertain === q?.request_id && snapshot.last_answer?.status !== 'rejected' ? <p role="status">This answer was submitted or its delivery is uncertain. Reconnect to read the receipt; it will not be resent automatically.</p> : null}
      {snapshot.error ? <p role="alert">{typeof snapshot.error === 'string' ? snapshot.error : snapshot.error.message}</p> : null}
      {snapshot.result ? <section className="forge-result" aria-label="Native game result"><h3>{snapshot.result.draw ? 'Native game drawn' : 'Native game complete'}</h3>
        {snapshot.result.outcomes.map((outcome, i) => <p key={i}>{outcome}</p>)}<p>{snapshot.result.turns} turns / {snapshot.result.win_condition}</p></section> : null}
      {q ? <ForgeChoices key={q.request_id} snapshot={snapshot} disabled={blocked} onAnswer={answer} /> : null}
      <ForgeBoard snapshot={snapshot} />
    </> : null}
    </>}
  </section>;
}
