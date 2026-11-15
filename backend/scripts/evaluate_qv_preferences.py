"""Teacher agreement and state contrasts; neither demonstrates game strength."""
import math

from scripts.train_qv_preferences import semantic_action_key, validate_preferences


def evaluate_preferences(policy, rows, *, contract):
    """Require state-dependent success, not just an action/card-family bias.

    A contrast has the same semantic candidate set in different states with
    different preferred actions. All members must be strictly correct; ties
    fail. No contrast data means unavailable, not perfect conditional accuracy.
    """
    validate_preferences(rows, contract=contract)
    groups, labels, identities = {}, {}, []
    for row in rows:
        keys = [semantic_action_key(action)
                for action in [row['preferred'], *row['alternatives']]]
        group = tuple(sorted(keys))
        state = semantic_action_key(row['state'])
        identity = (group, state)
        if identity in labels and labels[identity] != keys[0]:
            raise ValueError('Conflicting preferences for equivalent state and actions')
        labels[identity] = keys[0]
        entry = groups.setdefault(group, {'preferred': set(), 'correct': []})
        entry['preferred'].add(keys[0])
        identities.append(group)

    correct = 0
    for row, group in zip(rows, identities):
        prepared = policy.prepare(row['state'])
        scores = [prepared.predict(action)['q']
                  for action in [row['preferred'], *row['alternatives']]]
        if any(type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1
               for value in scores):
            raise ValueError('Finite bounded Q scores required')
        success = scores[0] > max(scores[1:])
        correct += success
        groups[group]['correct'].append(success)
    contrasts = [group['correct'] for group in groups.values() if len(group['preferred']) > 1]
    passed = sum(all(results) for results in contrasts)
    return {'rows': len(rows), 'strict_top1': correct / len(rows),
            'contrast_groups': len(contrasts), 'contrast_groups_correct': passed,
            'contrast_accuracy': passed / len(contrasts) if contrasts else None,
            'contrast_rows': sum(map(len, contrasts)),
            'contrast_rows_correct': sum(map(sum, contrasts))}
