"""AI-only preferences over public counter replacement outcomes."""
from functools import lru_cache
from rules_engine.counter_replacements import modified_count

def preferred_counter_option(pending):
    """Bounded exact amount ordering; large boards use deterministic heuristics."""
    if 'counter_amounts' in pending['counter_payload']:
        return preferred_counter_vector_option(pending)
    options = pending['options']
    forecast = pending.get('forecast_options') or options
    amount = int(pending['counter_payload']['amount'])
    harmful = pending['counter_payload']['counter'] in {'poison', '-1/-1', 'stun'}
    operations = tuple(sorted({(o['operation'], o.get('operand', 1)) for o in forecast}))
    counts = tuple(sum((o['operation'], o.get('operand', 1)) == op for o in forecast)
                   for op in operations)

    @lru_cache(maxsize=None)
    def final_count(value, remaining):
        if not value or not any(remaining):
            return value
        results = []
        for index, (op, operand) in enumerate(operations):
            if remaining[index]:
                rest = list(remaining)
                rest[index] -= 1
                results.append(final_count(modified_count(value, op, operand), tuple(rest)))
        return min(results) if harmful else max(results)

    def score(option):
        operation = (option['operation'], option.get('operand', 1))
        value = modified_count(amount, *operation)
        if len(forecast) <= 24:
            remaining = list(counts)
            remaining[operations.index(operation)] -= 1
            value = final_count(value, tuple(remaining))
        return -value if harmful else value

    return max(options, key=score)['source_id']


def preferred_counter_vector_option(pending):
    from ai.proliferation_policy import counter_weight
    options = pending['options']
    forecast = pending.get('forecast_options') or options
    payload = pending['counter_payload']
    kinds = tuple(sorted(payload['counter_amounts']))
    initial = tuple(payload['counter_amounts'][kind] for kind in kinds)
    weights = tuple(counter_weight(kind, player=payload.get('target_player') is not None) for kind in kinds)

    def signature(option):
        return (option['operation'], option.get('operand', 1),
                tuple(kinds.index(kind) for kind in option['counter_kinds']))

    operations = tuple(sorted({signature(option) for option in forecast}))
    counts = tuple(sum(signature(option) == operation for option in forecast) for operation in operations)

    def apply(values, operation):
        op, operand, indices = operation
        return tuple(modified_count(value, op, operand) if index in indices and value else value
                     for index, value in enumerate(values))

    @lru_cache(maxsize=None)
    def best(values, remaining):
        score = sum(value*weight for value, weight in zip(values, weights))
        if not any(remaining) or not any(values):
            return score
        scores = []
        for index, operation in enumerate(operations):
            if remaining[index]:
                rest = list(remaining)
                rest[index] -= 1
                scores.append(best(apply(values, operation), tuple(rest)))
        return max(scores)

    def score(option):
        operation = signature(option)
        values = apply(initial, operation)
        if len(forecast) <= 24:
            remaining = list(counts)
            remaining[operations.index(operation)] -= 1
            return best(values, tuple(remaining))
        return sum(value*weight for value, weight in zip(values, weights))

    return max(options, key=score)['source_id']
