"""AI-only preferences over public counter replacement outcomes."""
from functools import lru_cache
from rules_engine.counter_replacements import modified_count

def preferred_counter_option(pending):
    """Bounded exact amount ordering; large boards use deterministic heuristics."""
    options = pending['options']
    forecast = pending.get('forecast_options') or options
    amount = int(pending['counter_payload']['amount'])
    harmful = pending['counter_payload']['counter'] in {'poison', '-1/-1', 'stun'}
    counts = tuple(sum(o['operation'] == op for o in forecast) for op in ('double', 'half', 'add'))

    @lru_cache(maxsize=None)
    def final_count(value, remaining):
        if not value or not any(remaining):
            return value
        results = []
        for index, op in enumerate(('double', 'half', 'add')):
            if remaining[index]:
                rest = list(remaining)
                rest[index] -= 1
                results.append(final_count(modified_count(value, op), tuple(rest)))
        return min(results) if harmful else max(results)

    def score(option):
        value = modified_count(amount, option['operation'])
        if len(forecast) <= 24:
            remaining = list(counts)
            remaining[('double', 'half', 'add').index(option['operation'])] -= 1
            value = final_count(value, tuple(remaining))
        return -value if harmful else value

    return max(options, key=score)['source_id']
