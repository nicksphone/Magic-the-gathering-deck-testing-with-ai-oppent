# Native Search Practical Comparison

Use the already-built, pinned Forge engine and original credited match probe.
No production app, upstream source, rules, training weights or live DB changes.

1. Add a default-off per-spec native Flat-MC switch and per-game native statistics.
   Keep MAX/LITE off, profile Default and native five-second AI timeout. Verify
   the switch with a failing then passing native configuration test.
2. Extract unchanged application Burn and White Weenie main decks. Use empty
   sideboards, explicitly not a sideboarding-strength evaluation. Two declared
   seeds each run search off/on in independent offline JVMs, bound 300 seconds,
   at most four concurrent two-GiB heaps. Record actual rollouts, failures,
   latency, natural terminal results and actor-scoped observations privately.
3. Check all inputs, completed outcomes, inventories and observed search work.
   A timeout is censored, never a forced draw. Two seeds cannot establish a
   strength ranking. Preserve unfavorable results. Review, publish the small
   credited probe change and honest result, then archive/verify closed evidence.

Next integration work is the real native UI/IPC and persistence bridge, not more
rare naming cases. Full-policy fairness and RC remain separate acceptance work.
