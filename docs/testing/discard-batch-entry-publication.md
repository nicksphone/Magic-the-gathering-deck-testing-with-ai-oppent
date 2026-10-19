# Committed discard-batch publication

One-file incremental product over frozen simultaneous audit source 6e7e89f5,
fc225 plus consumer/emitter/reference/keyword/handlers dependencies. Zone
preimage 3b317d5e, handlers e03f643a and events 890f0d1d. No parent/main or
moving source reads. Existing canonical audit modules and fixtures unchanged.

## Contract

`execute_graveyard_entry` has private trusted `_entry_receipts=None`.
The default emits the genuine committed PRE/POST receipt immediately, as
before. A plain list retains exactly that receipt after actual graveyard
insertion/transition; non-graveyard and same-graveyard destinations add none.
Invalid sink rejects before movement. No public API/choice or collector ABI.

Only `discard_simultaneous` opts into retention. All selection/replacement/
static-cause validation still precedes mutation. Every selected movement,
discard log and both-player counter update completes before existing
`emit_event_batch` collects the retained genuine entry receipts, followed by
the original discard batch. Static replacement shuffles retain their actual
typed cause; unrelated event publication is not suppressed.

## Actual qualification

- Three complete focused modules: 56 PASS, 310 warnings, 26.84 seconds,
  exit 0. Original audit24 unchanged, including both formerly strict RED
  committed-batch observations, plus NEW32 controls. No exclusions/xfail/skip.
- Eight whole neighbors: 358 PASS, 1183 warnings, 73.85 seconds, exit 0:
  discard history, entry product seams/episodes, shuffle reference lifecycle,
  selected graveyard costs, static producer resolution/HTTP and replacement
  interactions. Fresh local SQL and offline socket/SQLite guard; bound900 each.
- New actual both-seat memory/file HTTP Delirium Skeins episodes observe all
  six cards and both discard counters committed at each collection. Duplicate
  selection rejects422 with root/controller/SQL unchanged before any event;
  first valid selection emits none while the other choice is pending.
- Empty/invalid/competing batches emit none, preserving complete snapshots.
  Library/exile replacements emit no false entry, printed static causes retain
  exact PRE references, Humility does not suppress hand abilities. Single-entry
  publication remains immediate. APNAP/private/cold HTTP restore and genuine
  Tomb one-batch versus separate-departure counts remain qualified by original24.

All AST outside the two authorized zone functions is unchanged. Handlers and
events remain byte-identical, including Erdos's independently owned read-prefix
scope. Product zone postimage f790aabe65e93d1974def87fc831df6d4c83afbe011cdd56c463db9bce685a19.

No migration claim for other sacrifice/death/mill batch callers, no general
multiplayer/choice continuation or arbitrary partial-core-failure atomicity
claim. Restart evidence is subprocess snapshot roundtrip and cold controller
restore, not a live server restart. Frozen earlier RED ledgers remain immutable.
