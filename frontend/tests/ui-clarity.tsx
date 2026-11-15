import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Battlefield} from '../src/components/Battlefield';
import {Controls} from '../src/components/Controls';
import {PlayGuide} from '../src/components/PlayGuide';
import {emptyCombatDraft} from '../src/components/combat-selection';
import type {CardView, LegalMove, MatchState, PlayerView} from '../src/types';
import '../src/styles/app.css';

type Scenario = 'creature' | 'permanent' | 'etb' | 'attack' | 'block';
type Action = {type: string; [key: string]: unknown};
const labels: Record<Scenario, string> = {
  creature: 'Creature target', permanent: 'Permanent target', etb: 'Untargeted ETB',
  attack: 'Attack draft', block: 'Block draft',
};
const card = (id: string, name: string, types = ['Creature']): CardView => ({
  id, name, types, tapped: false, summoning_sick: false, power: 2, toughness: 2,
  type_line: types.join(' '), keywords: [],
});
const player = (id: number): PlayerView => ({
  id, name: 'Protocol player ' + id, life: 20, hand: [], battlefield: [], graveyard: [],
  exile: [], graveyard_count: 0, exile_count: 0, library_count: 10, hand_count: 0, mana_pool: {},
});

function Fixture() {
  const [scenario, setScenario] = useState<Scenario>('creature');
  const [seat, setSeat] = useState<1 | 2>(1);
  const [epoch, setEpoch] = useState(0);
  const [offers, setOffers] = useState<'initial' | 'stale' | 'empty'>('initial');
  const [draft, setDraft] = useState(emptyCombatDraft);
  const [actions, setActions] = useState<Action[]>([]);
  const [busy, setBusy] = useState(false);
  const [aiActor, setAiActor] = useState(false);
  const [requiredChoice, setRequiredChoice] = useState(false);
  const [attackPayment, setAttackPayment] = useState(false);
  const [autoPaused, setAutoPaused] = useState(false);
  const own = player(seat), other = player(3 - seat);
  const spell = {...card('spell', scenario === 'etb' ? 'Protocol ETB creature' : 'Protocol removal',
    scenario === 'etb' ? ['Creature'] : ['Instant']), mana_cost: '{B}',
    oracle_text: scenario === 'etb' ? 'When this enters, destroy target creature.'
      : scenario === 'permanent' ? 'Destroy target nonland permanent.' : 'Destroy target creature.'};
  own.hand = ['creature', 'permanent', 'etb'].includes(scenario) ? [spell] : [];
  own.hand_count = own.hand.length;
  own.battlefield = [{...card(scenario === 'block' ? 'blocker' : 'attacker', 'Draft creature'),
    ...(scenario === 'etb' ? {summoning_sick: true, keywords: ['haste']} : {})}];
  other.battlefield = [card('target-creature', 'Protocol creature'),
    card('target-artifact', 'Protocol artifact', ['Artifact']), card('incoming', 'Incoming creature')];
  const match: MatchState = {id: 'ui-clarity-' + epoch, revision: 7, game_number: 1,
    mode: 'player_vs_ai', controllers: {[seat]: aiActor ? 'ai' : 'human', [3 - seat]: aiActor ? 'human' : 'ai'},
    players: {[seat]: own, [3 - seat]: other}, score: {'1': 0, '2': 0},
    turn: 3, active_player: scenario === 'block' ? 3 - seat : seat, priority_player: seat,
    step: scenario === 'attack' ? 'declare_attackers' : scenario === 'block' ? 'declare_blockers' : 'precombat_main',
    stack: [], log: [], winner: null, attackers: scenario === 'block' ? ['incoming'] : [],
    blocks: {}, attack_targets: {},
    pending_replacement_choice: requiredChoice ? {event: 'Synthetic protocol choice', player_id: seat, options: []} : null};
  const candidates = offers === 'empty' ? [] : offers === 'stale'
    ? [{id: 'incoming', name: 'Incoming creature'}] : [{id: 'target-creature', name: 'Protocol creature'}];
  const hints = {action_has_target_text: scenario !== 'etb', creature_targets: candidates,
    ...(scenario === 'permanent' ? {permanent_targets: offers === 'initial'
      ? [...candidates, {id: 'target-artifact', name: 'Protocol artifact'}] : candidates} : {}),
    target_restrictions: scenario === 'permanent' ? {exclude_types: ['Land'], mana_value_max: 3}
      : {allowed_types: ['Creature'], mana_value_max: 2},
    choice_schema: {target_card_id: {type: 'string', required: false},
      replacement_source_id: {type: 'string', required: false}}};
  const moves: LegalMove[] = [{type: 'pass_priority'}];
  if (own.hand.length) moves.push({type: 'cast_spell', card_id: spell.id, card_name: spell.name,
    target_hints: hints, cost_options: [{id: 'normal', label: 'Normal', mana_cost: '{B}',
      pay_life: 0, discard_cards: 0, sacrifice_creatures: 0, target_hints: hints}]});
  if (scenario === 'attack') moves.push({type: 'attack', options: ['attacker'],
    defenders: [{id: 'player:' + (3 - seat), label: 'Opponent', kind: 'player'}],
    attack_costs: attackPayment ? {attacker: {['player:' + (3 - seat)]: {
      mana_cost: '{W/U}', hybrid_symbols: [{symbol: 'W/U', choices: ['W', 'U']}],
    }}} : undefined});
  if (scenario === 'block') moves.push({type: 'block',
    attackers: [{id: 'incoming', name: 'Incoming creature'}], blockers: [{id: 'blocker', name: 'Draft creature'}],
    legal_blocks: {blocker: ['incoming']}, blocker_capacities: {blocker: 1}});
  useEffect(() => {Object.assign(window, {fixtureActions: actions, fixtureState: match,
    fixtureDraft: draft, fixtureScenario: scenario, fixtureSeat: seat, fixtureBusy: busy});});
  const record = (type: string, value: Record<string, unknown> = {}) => setActions(previous => [...previous, {type, ...value}]);
  function reset(next: Scenario, nextSeat = seat) {
    setScenario(next); setSeat(nextSeat); setEpoch(previous => previous + 1);
    setOffers('initial'); setDraft(emptyCombatDraft()); setActions([]);
    setBusy(false); setAiActor(false); setRequiredChoice(false); setAttackPayment(false); setAutoPaused(false);
  }
  const unused = () => record('unexpected-control');
  const controls: React.ComponentProps<typeof Controls> = {
    decks: [], selectedA: null, selectedB: null, setSelectedA: unused, setSelectedB: unused,
    startMode: 'player_vs_ai', setStartMode: unused, humanSeat: seat, setHumanSeat: unused,
    difficulty: 'strong', setDifficulty: unused, bestOf: 3, setBestOf: unused, onStart: unused,
    startDisabled: true, onPassPriority: () => record('pass_priority'),
    onKeepHand: unused, onMulligan: unused, onNextStep: unused, onAutoplayTick: unused,
    autoplayDelayMs: 1000, setAutoplayDelayMs: unused, onApplySideboard: unused, onNextGame: unused,
    onSetPriorityStops: unused, onChooseReplacement: unused, onChooseTriggerOrder: unused,
    onChooseTriggerTarget: unused, onChooseOptionalEffect: unused, onChooseMechanic: unused,
    responseCountdown: null, autoResponsePaused: true, onToggleAutoResponsePause: unused,
    autoProgressPaused: autoPaused,
    onToggleAutomaticPlay: () => {setAutoPaused(value => !value); record('toggle_auto');},
    onSubmitAttack: (attackers, attackTargets, bands) => record('attack', {attackers, attackTargets, bands}),
    onSubmitBlocks: blocks => record('block', {blocks}), actingPlayerId: seat,
    match, legalMoves: moves, combatDraft: draft, onCombatDraftChange: setDraft,
  };
  return <main className="layout workspace-match">
    <section className="panel">
      <h1>UI clarity fixture</h1>
      <p>Synthetic UI vectors only. No API, backend, or game engine.</p>
      <div className="grid-actions">
        {([1, 2] as const).map(value => <button key={value} onClick={() => reset(scenario, value)}>Fixture seat {value}</button>)}
        {(Object.keys(labels) as Scenario[]).map(value => <button key={value} onClick={() => reset(value)}>Reset {labels[value]}</button>)}
        <button onClick={() => setOffers('stale')}>Replace offered targets</button>
        <button onClick={() => setOffers('empty')}>Clear offered targets</button>
        <button onClick={() => setBusy(value => !value)}>Toggle busy</button>
        <button onClick={() => setAiActor(value => !value)}>Toggle AI actor</button>
        <button onClick={() => setRequiredChoice(value => !value)}>Toggle required choice</button>
        <button onClick={() => setAttackPayment(value => !value)}>Toggle attack payment</button>
      </div>
      <output data-testid="fixture-ready">Ready: {labels[scenario]}, seat {seat}</output>
    </section>
    <div className="play-guide-slot"><PlayGuide match={match} legalMoves={moves} actingPlayerId={seat} autoProgressPaused={false} /></div>
    <section className="left-column" id="match-controls" tabIndex={-1}>
      <fieldset disabled={busy} style={{border: 0, margin: 0, padding: 0, minWidth: 0}}>
        <Controls key={'controls-' + epoch} {...controls} />
      </fieldset>
    </section>
    <section className="right-column" id="table" tabIndex={-1}>
    <Battlefield key={'battlefield-' + epoch} match={match} legalMoves={moves} actingPlayerId={seat}
      combatDraft={draft} onCombatDraftChange={setDraft}
      onCardAction={(player_id, action) => record('card', {player_id, action})} />
    </section>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Fixture />);
