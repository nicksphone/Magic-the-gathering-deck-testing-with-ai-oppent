import type { ResourceCandidates, ResourcePaymentChoice } from '../types';

type Props = {
  name: string;
  candidates: ResourceCandidates;
  names: Record<string, string>;
  choice?: ResourcePaymentChoice;
  onChange: (choice: ResourcePaymentChoice | undefined) => void;
};

export function CastingResources({ name, candidates, names, choice, onChange }: Props) {
  return <details className="casting-resources">
    <summary>Casting resources: delve / convoke / improvise</summary>
    <label><input type="checkbox" aria-label={`Automatic resources ${name}`} checked={choice === undefined}
      onChange={event => onChange(event.target.checked ? undefined : {delve: [], convoke: [], improvise: []})} />Automatic resource payment</label>
    <p>Manual selection substitutes for mana; it does not produce mana. Choose no resources to preserve them.</p>
    {choice ? <>
      {(['delve', 'improvise'] as const).map(kind => candidates[kind].map(id => <label key={`${kind}-${id}`}>
        <input type="checkbox" data-resource-kind={kind} data-resource-card={id} checked={choice[kind].includes(id)}
          onChange={event => onChange({...choice, [kind]: event.target.checked ? [...choice[kind], id] : choice[kind].filter(cid => cid !== id)})} />
        {kind === 'delve' ? 'Exile' : 'Tap artifact'} {names[id] ?? id}
      </label>))}
      {candidates.convoke.map(row => {
        const selected = choice.convoke.find(card => card.card_id === row.card_id);
        return <label key={row.card_id}>
          <input type="checkbox" data-resource-kind="convoke" data-resource-card={row.card_id} checked={!!selected}
            onChange={event => onChange({...choice, convoke: event.target.checked ? [...choice.convoke,
              {card_id: row.card_id, pay_as: 'generic'}] : choice.convoke.filter(card => card.card_id !== row.card_id)})} />
          Tap creature {names[row.card_id] ?? row.card_id}
          <select aria-label={`Convoke payment ${names[row.card_id] ?? row.card_id}`} data-convoke-card={row.card_id}
            disabled={!selected} value={selected?.pay_as ?? 'generic'} onChange={event => {
              const color = row.pay_as.find(color => color === event.target.value);
              if (color) onChange({...choice, convoke: choice.convoke.map(card => card.card_id === row.card_id ? {...card, pay_as: color} : card)});
            }}>
            {row.pay_as.map(color => <option key={color} value={color}>{color === 'generic' ? '1 generic' : color}</option>)}
          </select>
        </label>;
      })}
    </> : null}
  </details>;
}
