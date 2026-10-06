# Local Import Metadata Projection

Base: `fc225406d56c1a2f177ccfa8fb0b6008448772f2`. This isolated increment changes
only `DeckService._resolve_card_metadata`, the matching frontend metadata type,
and DeckPanel metadata labels. No catalog route, schema, rule, or AI policy change.

## Contract

Cache rows take priority and retain their real SQL IDs and existing serialized
fields. Cache readiness is evaluated on those fields, not on a silently repaired
seed projection. On a cache miss, the existing read-only `hydrate_deck_cards`
contract admits complete canonical local seed/knowledge facts. These projections
have no SQL `id`; their actual Scryfall ID, `card_data_sources`, and `match_ready`
are returned. Untrusted or incomplete missing metadata remains null. A partial
cache row remains visible with `match_ready: false`.

`match_ready` describes metadata admission, not effect execution, format legality,
verified rulings, learned quality, or arbitrary-card completeness. Existing full
canonical fixtures are unchanged. `/cards` still lists only CardCache rows.
Completeness's legacy `complete` count still excludes seed-only Oracle records;
DeckPanel now labels that count accordingly and displays the separate seed count.

The compatible `materialize` keyword no longer causes resolver sync/upserts. Normal
valid deck saves and match persistence still write their existing tables. Explicit
sync methods are unchanged. Read-only resolution does not download data, invent
numeric IDs, union the listing cache, or silently change cache priority.

## Qualification

New backend regressions cover cold Burn and Dimir Control printed curve/colors,
cache IDs and field priority, genuine Time Warp absent/manual/partial/canonical
states, repeat resolution with no SQL changes, and typed start rejection. A
separate real loopback script starts five sequential production server processes,
checks imports/start/restart GET parity, and denies external DNS/connections.

The frontend regression renders the actual DeckPanel through React SSR with a
seeded hook value and checks its labels and optional type fields. This is not a
browser, LAN, or HTTPS qualification. Full existing lint/test/build commands use
the qualified external Python interpreter and read-only installed packages.

Two separately proposed test adapters truthfully transition historical cache-only
expectations: implicit import materialization, and zero seed-only display analysis
coverage. Original source preimages and terminal red logs remain in the archive.
All Oracle/curve/hydration, IDs, inventory/history and root assertions remain.
The archive report records terminal counts, commands and exact hashes.
