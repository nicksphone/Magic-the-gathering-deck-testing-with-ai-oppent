/** Display engine vectors without interpreting Oracle or joining alternative outputs. */
const symbols = ['W', 'U', 'B', 'R', 'G', 'C'] as const;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function formatManaVector(value: unknown): string | null {
  if (!record(value) || !Object.entries(value).every(([symbol, amount]) =>
    symbols.some(known => known === symbol) && Number.isSafeInteger(amount) && Number(amount) >= 0)) return null;
  const parts = symbols.filter(symbol => Number(value[symbol] ?? 0) > 0)
    .map(symbol => `${value[symbol]} ${symbol}`);
  return parts.length ? parts.join(' + ') : null;
}

export function legacyManaOutput(move: { outputs?: unknown; output_bundles?: unknown }, color: string) {
  const amount = record(move.outputs) ? move.outputs[color] : undefined;
  const effective = formatManaVector({ [color]: amount });
  if (!effective) return { effective: null, total: null, warning: 'No supported positive mana output is supplied.' };
  if (move.output_bundles === undefined) return { effective, total: effective, warning: null };
  const total = record(move.output_bundles) ? formatManaVector(move.output_bundles[color]) : null;
  return { effective, total, warning: total
    ? 'The legacy view combines trigger output in its total; separate printed base and trigger vectors are not supplied.'
    : 'The supplied combined mana vector is unsupported; do not activate using a partial display.' };
}

/** Only authoritative BASE options can become an explicit executor selection. */
export function baseManaOptions(move: { output_options?: unknown; base_output_bundles?: unknown }) {
  if (move.output_options === undefined && move.base_output_bundles === undefined) return null;
  if (!Array.isArray(move.output_options) || !move.output_options.length ||
      !Array.isArray(move.base_output_bundles) || !move.base_output_bundles.length) return [];
  const positiveVector = (value: unknown) => record(value) && formatManaVector(value) !== null &&
    Object.values(value).every(amount => Number(amount) > 0 && Number(amount) <= 100000);
  if (!move.base_output_bundles.every(positiveVector)) return [];
  const bases = new Set(move.base_output_bundles.map(formatManaVector));
  const options: {color: string; output_bundle: Record<string, number>; label: string}[] = [];
  for (const option of move.output_options) {
    if (!record(option) || typeof option.color !== 'string' || !positiveVector(option.output_bundle) ||
        !record(option.output_bundle) || Number(option.output_bundle[option.color] ?? 0) <= 0) return [];
    const label = formatManaVector(option.output_bundle)!;
    if (!bases.has(label)) return [];
    options.push({color: option.color, output_bundle: {...option.output_bundle} as Record<string, number>, label});
  }
  if (new Set(options.map(option => option.label)).size !== bases.size) return [];
  return options;
}
