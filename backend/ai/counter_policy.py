"""AI-only preferences over public counter replacement outcomes."""
from functools import lru_cache
from rules_engine.counter_replacements import modified_count

def preferred_counter_option(pending):
    """Bounded exact amount ordering; large boards use deterministic heuristics."""
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
