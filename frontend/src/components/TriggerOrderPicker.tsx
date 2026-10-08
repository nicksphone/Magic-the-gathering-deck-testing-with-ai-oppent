import { useState } from "react";

export function TriggerOrderPicker(props: {
  ids: string[];
  labels?: string[];
  onChoose: (order: string[]) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const complete = props.ids.length > 0 && selected.length === props.ids.length
    && new Set(selected).size === props.ids.length && selected.every(id => props.ids.includes(id));
  return (
    <div>
      <p>Choose triggers from bottom to top. The last chosen trigger resolves first.</p>
      <ol aria-label="Chosen trigger order">
        {selected.map(id => <li key={id}>{props.labels?.[props.ids.indexOf(id)] ?? id}</li>)}
      </ol>
      <div className="row">
        {props.ids.map((id, index) => (
          <button key={id} data-trigger-id={id} disabled={selected.includes(id)}
            onClick={() => setSelected(previous => previous.includes(id) ? previous : [...previous, id])}>
            {index + 1}. {props.labels?.[index] ?? id}
          </button>
        ))}
      </div>
      <div className="row">
        <button disabled={selected.length === 0} onClick={() => setSelected(previous => previous.slice(0, -1))}>Undo last trigger</button>
        <button disabled={selected.length === 0} onClick={() => setSelected([])}>Reset trigger order</button>
        <button disabled={!complete} onClick={() => { if (complete) props.onChoose([...selected]); }}>Submit trigger order</button>
      </div>
    </div>
  );
}
