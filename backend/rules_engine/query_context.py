"""Short-lived reuse for synchronous, nonmutating rules queries only."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_query = ContextVar('rules_query', default=None)


@contextmanager
def rule_query_scope(state):
    current = _query.get()
    if current is not None and current[0] is state:
        yield
        return
    token = _query.set((state, {}))
    try:
        yield
    finally:
        _query.reset(token)


def query_cache(state):
    context = _query.get()
    return context[1] if context is not None and context[0] is state else None


def scoped_query(function):
    """For pure queries with immutable arguments; do not decorate mutations."""
    @wraps(function)
    def query(state, *args, **kwargs):
        with rule_query_scope(state):
            cache = query_cache(state)
            if cache is None:
                return function(state, *args, **kwargs)
            key = (function, args, tuple(sorted(kwargs.items())))
            if key not in cache:
                cache[key] = function(state, *args, **kwargs)
            result = cache[key]
            return result.copy() if type(result) in (dict, list, set) else result
    return query
