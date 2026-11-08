"""Fresh stdlib import/protocol control, with no Magic card-data claims."""
from pathlib import Path
import json
import os
import pickle
import sys


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    mode = sys.argv[1]
    assert mode in {'copying-first', 'typing-first', 'custom-reducer',
                    'preexisting-args-reducer', 'preexisting-kwargs-reducer'}
    denied = []

    def audit(event, args):
        blocked = event.startswith(('sqlite3.', 'socket.', 'subprocess.')) or event in {
            'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.exec',
        }
        if event == 'open' and isinstance(args[0], (str, bytes)):
            name = Path(os.fsdecode(args[0])).name
            blocked |= name.endswith('capacity-owner.lock') or name in {
                'MODEL.private.json', 'FEATURES.private.json',
            }
        if blocked:
            denied.append(event)
            raise PermissionError('Copy import control forbids private/runtime IO')

    sys.addaudithook(audit)
    reducer_calls = []
    preexisting = mode.startswith('preexisting-')
    if preexisting:
        import copyreg
        from _typing import ParamSpec, ParamSpecArgs, ParamSpecKwargs

        kind = ParamSpecArgs if mode == 'preexisting-args-reducer' else ParamSpecKwargs

        def prior_reducer(value):
            reducer_calls.append(type(value))
            return tuple, (('preserved preexisting reducer',),)

        copyreg.pickle(kind, prior_reducer)
        parameter = ParamSpec('ImportOrderControl')
        foreign = parameter.args if kind is ParamSpecArgs else parameter.kwargs
    if mode in {'typing-first', 'custom-reducer'}:
        import typing
    from game_state import copying
    if preexisting:
        assert copyreg.dispatch_table[kind] is prior_reducer, 'Copier import replaced a caller reducer'
    import typing
    from game_state.state import CardInstance, MatchState

    metadata = {f'key-{index}': [[index, str(index)]] for index in range(512)}
    if preexisting:
        metadata['preexisting'] = foreign
    if mode == 'custom-reducer':
        import copyreg

        class Foreign:
            pass

        def reduce_foreign(value):
            reducer_calls.append(type(value))
            return tuple, (('reduced foreign value',),)

        copyreg.pickle(Foreign, reduce_foreign)
        metadata['foreign'] = Foreign()

    card = object.__new__(CardInstance)
    card.__dict__ = {'metadata': metadata}
    state = object.__new__(MatchState)
    state.__dict__ = {'log': ['retained source history'], 'cards': {'card': card}}
    before = pickle.dumps(state, protocol=5) if mode in {'copying-first', 'typing-first'} else None

    def observed(**kwargs):
        calls = {'keep_alive': 0, 'prefix': 0}

        def profile(frame, event, arg):
            if event == 'call':
                if frame.f_code is copying._keep_alive.__code__:
                    calls['keep_alive'] += 1
                elif frame.f_code is copying._copy_card_field_prefix.__code__:
                    calls['prefix'] += 1

        previous = sys.getprofile()
        sys.setprofile(profile)
        try:
            clone = copying.copy_match_state(state, include_history=False, **kwargs)
        finally:
            sys.setprofile(previous)
        return clone, calls

    slow, slow_calls = observed(memo={})
    fast, fast_calls = observed()
    assert fast.cards['card'].metadata == slow.cards['card'].metadata
    assert fast.cards['card'].metadata is not metadata
    assert fast.log == slow.log == [] and state.log == ['retained source history']
    if preexisting:
        assert len(reducer_calls) == 2
        assert fast.cards['card'].metadata['preexisting'] == ('preserved preexisting reducer',)
        assert metadata['preexisting'] is foreign
    elif mode == 'custom-reducer':
        assert len(reducer_calls) == 2
        assert fast.cards['card'].metadata['foreign'] == ('reduced foreign value',)
        assert type(metadata['foreign']) is Foreign
        assert fast_calls['prefix'] == 0
        assert fast_calls['keep_alive'] == slow_calls['keep_alive']
    else:
        assert pickle.dumps(state, protocol=5) == before
        assert slow_calls['keep_alive'] >= 1024
        assert fast_calls['prefix'] > 0, 'Ordinary stdlib import disabled the native prefix'
        assert fast_calls['keep_alive'] * 4 < slow_calls['keep_alive']
    assert denied == []
    print(json.dumps({'mode': mode, 'slow_calls': slow_calls, 'fast_calls': fast_calls,
                      'reducer_calls': len(reducer_calls), 'denied_events': denied}))


if __name__ == '__main__':
    main()
