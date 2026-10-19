# Stage1 Forward Resource Limits

Local single-process limits are fixed trusted code policy, not client/operator knobs.
Background admission preserves key replay/conflict before checking NEW request JSON;
a rejected oversized request creates no queued cache entry, cancellation event, slot
reservation, worker, or durable row. Legacy replay does not erase stored records.

Default encoded request limit: 2 MiB. Individual result and snapshot JSON: 1 MiB
each. Error text: 1024 UTF-8 bytes. Trace line including prefix: 64 KiB;
trace scalar: 8192 UTF-8 bytes; trace nodes: 8192; depth: 32.
Per-game logs: 4 MiB / 32768 entries. Cumulative call logs: 32 MiB / 131072
entries. Ordinary action log growth has a conservative 64 KiB reserve before
cloning. A 600-second monotonic deadline is checked cooperatively between steps.
The independent diagnostics loop shares one budget across its pairs/games.

Repository preflight checks exact default JSON escaping BEFORE any Session
operation, then uses its original default encoder and the same checked string.
Producers preflight trace references before trace/LKI copying, bound trace
encoding before checked_action, validate candidate log growth before adoption,
and bound final result before the first snapshot write. Resource-limit failures
are explicit failures, never truncated successful results or fabricated outcomes.
An oversized uncommitted worker result is cleared so bounded failed-status
persistence can succeed; oversized exception text becomes a fixed error reason.

Scope limits: already-built inputs, rule/AI internal allocations, blocked calls,
and whole-process peak RAM are not hard-bounded. Deadline checks cannot preempt
an individual stuck engine/agent operation. Existing synchronous endpoint error
translation and shutdown/drain qualification remain separate work. No schema,
aggregate storage quota, escrow, tombstone, online pruning, TTL, or legacy data
rewrite is implemented here. Existing row/cache caps and offline maintenance
remain in place. Logical individual-field limits do not cap SQLite/WAL sizes.

Qualification distinguishes fake Session protocol checks from native gameplay.
The native canonical workloads retain their 500-tick limit and normal timeout
outcomes; they are not winning-game, AI-strength, latency, or SQL certificates.
