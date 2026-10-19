# Legacy Player Prevention Inventory Veto

Independent one-condition increment over the reviewed numeric inventory adapter. The public inventory's existing player-context guard now includes `or player.prevent_damage_shield != 0`. Metadata validation remains first, so malformed boolean/null scalars are rejected without evaluating or repairing their amount. Exact zero preserves existing coverage checks; any nonzero integer is unknown. No snapshot migration, fake receipt, source lookup, gameplay prevention, schema, numeric producer or AI algorithm changes.

The old four strict legacy probes are unchanged and now pass. NEW32 controls cover both actors and both player recipients, zero/positive/negative/bool/null values, cold legacy snapshot omission, private identity mutation and complete root pickle-byte purity. Supported positive amounts use the existing anonymous `add_player_prevention_shield` compatibility helper; invalid metadata is explicitly fault injection, not an invented paid card instruction.

Baseline NEW32:20PASS12FAIL. Four whole modules after product:221PASS2 known strict native Gearhulk graveyard target-reference failures,28.94s; zero errors/skips/deselections. Whole module counts are NEW32PASS,unchanged adapter36PASS,numeric receipts46PASS,original public inventory107PASS2FAIL. No adaptation of the two unrelated failures or promotion claim.

Use the pinned shared interpreter with `inventory-adapter/run_pure.py`, which installs denial of all SQLite connect/socket events before pytest import. This qualification is pure only: no HTTP/SQL permission, parent-source certification or complete prevention-ordering claim. Prior numeric and adapter archives remain immutable; apply only this separate incremental patch after their dependencies.
