"""Negative protocol instrumentation, applied only to detached serialized output."""


def corrupt_serialized_copy_descriptors(snapshot):
    mutations = 0
    for card in snapshot['cards'].values():
        last_known = card['last_known_battlefield']
        if '__copiable_lki' in last_known:
            copied = last_known['__copiable_lki']
            copied['descriptor'] = {**(copied['descriptor'] or {}), 'mana_cost': 'incorrect'}
            mutations += 1
    return mutations
