import { useState } from 'react';
import type { LegalMove } from '../types';
import { PermanentActions } from './PermanentActions';
import { baseManaOptions, formatManaVector, legacyManaOutput } from './manual-mana-output';

type ManaView = LegalMove & {
  activation_costs?: LegalMove['payment_options'];
  output_options?: unknown;
  base_output_bundles?: unknown;
  output_bundles?: unknown;
};
type Props = {move: LegalMove; playerId: number; cards: {id: string; name: string}[];
  onAction: (playerId: number, action: Record<string, unknown>) => void};

export function ManualManaOutput({move, playerId, cards, onAction}: Props) {
  const view = move as ManaView;
  const [selected, setSelected] = useState('');
  const [branches, setBranches] = useState<Record<number, string>>({});
  const [error, setError] = useState('');
  const options = baseManaOptions(view);
  const hybrid = move.hybrid_symbols ?? [];
  const payment = view.activation_costs;
  const ownIds = new Set(cards.map(card => card.id));
  const unsafeCandidates = payment && [...payment.discard_card_ids, ...payment.sacrifice_card_ids].some(id => !ownIds.has(id));
  const plain = (!move.cost_text?.trim() || /^\{T\}$/i.test(move.cost_text.trim())) &&
    !hybrid.length && !(payment?.discard_cards || payment?.sacrifice_creatures || payment?.pay_life);
  const warning = unsafeCandidates ? 'Unsupported payment view: a candidate is not in your hand or battlefield.'
    : /\{X\}/i.test(move.cost_text ?? '') ? 'Variable X mana payment is not supported by this action contract.'
    : !plain && (!payment || move.hybrid_symbols === undefined || !move.required_choices) ? 'Manual payment metadata is unavailable; do not activate this ability.'
    : hybrid.some(symbol => !symbol.choices.length) ? 'Explicit hybrid branches are unavailable.'
    : options?.length === 0 ? 'Unsupported base mana choices.' : null;
  const legacy = options === null || (plain && options.every(option => Object.keys(option.output_bundle).length === 1)
    && options.every(option => new Set(options.filter(other => other.color === option.color).map(other => other.label)).size <= 1));
  const choices = legacy ? Object.keys(move.outputs ?? {}).map(color => ({color,
    output_bundle: undefined, label: legacyManaOutput(view, color).total})) : options;
  const choice = choices[Number(selected)];
  const hybridChoices = hybrid.map((symbol, index) => symbol.choices.includes(branches[index]) ? branches[index] : '');
  const ready = selected !== '' && Boolean(choice?.label) && hybridChoices.every(Boolean) && !warning;
  const action = (output: typeof choice, paymentChoices?: unknown) => ({type: 'activate_mana_ability',
    card_id: move.card_id, ability_index: move.ability_index, color: output.color,
    ...(output.output_bundle ? {output_bundle: {...output.output_bundle}} : {}),
    ...(paymentChoices ? {payment_choices: paymentChoices} : {}),
    ...(hybridChoices.length ? {hybrid_choices: [...hybridChoices]} : {})});
  return <article className="cast-card-box" data-mana-source={move.card_id} data-mana-index={move.ability_index}>
    <strong>{move.card_name}: {move.cost_text}</strong>
    {warning ? <p role="alert">{warning}</p> : null}
    {options !== null ? <p>Base output before replacements and triggered bonuses. Separate final and trigger vectors are not supplied.</p> : null}
    {view.output_bundles && typeof view.output_bundles === 'object' ? <p role="status">
      Combined compatibility previews (including bonuses, not selectable base choices):
      {' '}{[...new Set(Object.values(view.output_bundles).map(formatManaVector))].map(vector => vector ?? 'unsupported vector').join(' / ')}
    </p> : null}
    {plain ? choices.map((output, index) => <button key={index} disabled={Boolean(warning || !output.label)}
      onClick={() => {if (!warning && output.label) onAction(playerId, action(output));}}>
      {legacy ? 'Add projected ' : 'Choose base '}{output.label ?? 'unsupported output'}
    </button>) : <>
      <label>Base mana output<select aria-label={`Base mana output for ${move.card_name}`} value={selected}
        onChange={event => {setSelected(event.target.value); setError('');}}>
        <option value="">Choose complete output</option>
        {choices.map((output, index) => <option key={index} value={index}>{output.label} (anchor {output.color})</option>)}
      </select></label>
      {hybrid.map((symbol, index) => <label key={index}>Pay {`{${symbol.symbol}}`}
        <select aria-label={`Mana hybrid symbol ${index + 1} for ${move.card_name}`} value={branches[index] ?? ''}
          onChange={event => setBranches(prior => ({...prior, [index]: event.target.value}))}>
          <option value="">Choose payment branch</option>
          {symbol.choices.map(branch => <option key={branch} value={branch}>{branch}</option>)}
        </select>
      </label>)}
      {payment && !unsafeCandidates ? <fieldset disabled={!ready}>
        <legend>Choose your activation payment</legend>
        <PermanentActions key={`${selected}:${hybridChoices.join('/')}`} playerId={playerId} cards={cards}
          moves={[{...move, type: 'activate_ability', ability_label: move.cost_text,
            payment_options: payment, hybrid_symbols: [], mana_cost: undefined, target_hints: undefined}]}
          onAction={(seat, proposed) => {
            if (!ready) return;
            if (proposed.targets && Object.keys(proposed.targets as object).length) {
              setError('Extra target or advanced choices are not supported for this mana ability.'); return;
            }
            onAction(seat, action(choice, proposed.payment_choices));
          }} />
      </fieldset> : null}
    </>}
    {error ? <p role="alert">{error}</p> : null}
  </article>;
}
