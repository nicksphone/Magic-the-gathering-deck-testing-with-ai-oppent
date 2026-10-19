# Ninjutsu Pending Source Identity

Production ownership is limited to `rules_engine/keyword_actions.py`:
`activate_ninjutsu` and `resolve_ninjutsu`. No consumer, API, schema, shared helper,
generic stack dispatch, cycling, or main/live files are changed.

The stack's existing source card ID plus its private `__source_zone_sequence`
payload identifies the hand object at activation. Capture occurs before mana
payment and returning the selected attacker. Resolution requires that same
sequence, the hand zone, and the controller's hand membership. A source that
left and reentered is not moved. The ability still resolves; paid mana and the
returned attacker are not restored. Snapshot serialization already preserves
both the payload and the card sequence; no persistence migration is needed.

Legacy pending ninjutsu payloads without a trustworthy integer reference resolve
without moving a card, even if it currently appears in hand. This is a deliberate
fail-closed compatibility limitation: the old payload cannot distinguish the
original object from a reentered one. Do not reconstruct a reference from the
current card. Boolean/string references are also rejected. Other abilities are
not subjected to this requirement. Actual canonical cycling still draws after
its discarded source is moved to exile in a controlled test.

Rules basis: the official September 25, 2026 Comprehensive Rules, 400.7,
702.49a-c, and 113.7a:
https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt

Dependencies are Lagrange's immutable foretell `9mxvBK` source archive and the
NEW canonical ninjutsu audit patch `ee419ebdf069ce8a097d115bf077fbf4267a16ca506e5eff82372676f626c648`.
The original 44-case module and full official Ninja intake are unchanged.
The 16 unsupported-intent consumer failures are separately owned by Lagrange;
this engine increment does not resolve or reclassify them.

`tests/test_ninjutsu_source_identity.py` adds both-seat controls for unchanged,
departed, and reentered sources; replay; actual checked HTTP activation and
priority passes; SQLite restart; private actor observations; retention of costs;
conservative legacy payload handling; and a later valid activation of the new
hand object. Before/pending/after private snapshots are retained by pytest.

Exile and return transitions are explicit controlled state setup using the real
zone transition method. They are **not** an actual causal HTTP exile-return spell
sequence. HTTP activation, passes, persistence/restoration, and cycling payment
are actual. Lonely Sandbar is the unmodified existing full canonical fixture in
`tests/fixtures/death_cycle_ordering/canonical.json`, with its existing provenance.
No Oracle edits, fake names, guessed sequence increments, or replacement support
are introduced. Existing battlefield entry bookkeeping is outside this fix.

Run with the main external virtualenv from the isolated backend, fresh local
SQLite, and the archived offline/SQLite-root guard. The authoritative terminal
logs and complete commands are in the accompanying evidence package. The final
52-case engine gate explicitly excludes only the separately owned 16 consumer
cases; it is not a claim that the full 44-case consumer audit is green.
