import json,os
from pathlib import Path

def identity(pid):
    root = Path('/proc') / str(pid)
    try:
        fields = (root / 'stat').read_text().rsplit(')', 1)[1].split()
        return dict(pid=pid, start_ticks=fields[19], ppid=int(fields[1]), pgid=int(fields[2]),
                    exe=os.readlink(root / 'exe'), argv=(root / 'cmdline').read_bytes().decode().rstrip('\0').split('\0'))
    except (FileNotFoundError, ProcessLookupError):
        return None

def known_birth(pid, original):
    assert original is not None and original['pid'] == pid, 'UNADMITTED_KNOWN_PID'
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    assert fields[19] == original['start_ticks'], 'OWNED_PID_IDENTITY_DRIFT'
    return dict(pid=pid, start_ticks=fields[19], ppid=int(fields[1]), pgid=int(fields[2]))

def owned_group(pgid):
    known=_OWNED_FAMILIES.setdefault(pgid,{})
    if not known:
        first=identity(pgid)
        if first is None:return {}
        assert first["pgid"]==pgid
        known[pgid]=first
    O=OUT
    frontier=list(known);seen=set()
    while frontier:
        pid=frontier.pop()
        if pid in seen:continue
        seen.add(pid);original=known[pid];current=known_birth(pid,original)
        if current is None:continue
        assert original is not None and current['start_ticks']==original['start_ticks'],'OWNED_PID_IDENTITY_DRIFT'
        try:tasks=list(Path('/proc',str(pid),'task').iterdir())
        except FileNotFoundError:continue
        staged=[]
        for task in tasks:
            try:children=(task/'children').read_text().split()
            except (FileNotFoundError,ProcessLookupError):continue
            for value in children:
                child=int(value)
                if child not in known and child not in staged:staged.append(child)
        again=known_birth(pid,original)
        if again is None or again['start_ticks']!=original['start_ticks']:continue
        for child in staged:
            observed=identity(child)
            if observed is None:continue
            assert observed['ppid']==pid,'UNBOUND_CHILD_PARENT'
            known[child]=observed;frontier.append(child)
            with (O/'OWNED_FAMILY.jsonl').open('a') as ledger:ledger.write(json.dumps(dict(parent=pid,identity=observed))+'\n')
    return {pid:original for pid,original in known.items() if known_birth(pid,original) is not None}

def record(event,**values):
    with (OUT/"process-events.jsonl").open("a") as stream:stream.write(json.dumps({"event":event,**values})+"\n")
