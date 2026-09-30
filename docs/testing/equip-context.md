# Target-aware equipment and attachment identity

Date: 2026-09-30 UTC. Parent: `85a7d0e1ac0e92e0760b4d9cc8c85756b7d8bb37`.

## Implemented

- Supported ordinary equip discounts use source/target identity and actual payer
  control. Generic reductions stack but do not remove colored requirements or
  apply to unrelated activations. Effective-power reductions use current combat
  characteristics, not printed power or an announced X choice.
- Legal moves filter each target through the same payment context used by the
  accepted activation. Free activation does not unnecessarily consume restricted
  mana. Rejected unpaid targets preserve authoritative state.
- Shared AI planning projects payable equip targets with real activation and
  effect handlers. It emits a concrete target, avoids unchanged attachments and
  requires improved board valuation. List-valued legal target metadata no longer
  crashes the stable move sorter. This is bounded tactical improvement, not
  seasoned-player certification or opponent-response search.
- Attached base power/toughness setters apply to the attached permanent in
  layer 7b, including opposing-controller targets. Supported explicit global
  base setters apply to both boards. Unattached equipment does not buff the
  whole controller's board via a generic text-prefix fallback.
- Becoming attached renews the continuous-effect timestamp, separately from
  battlefield incarnation. Counters and linked/stack identity guards survive
  reattachment; actual battlefield reentry receives a new incarnation. Snapshot
  persistence retains both, with a legacy timestamp fallback. Identical existing
  attachment does not renew its timestamp.

## Evidence

Twenty-five canonical Scryfall fixture rows were extracted from read-only local
knowledge data. No cards or built-in decklists were invented or rebalanced.
Twenty-one new tests cover both seats, ownership, generic/colored requirements,
effective stats, restricted-resource preservation, stack identity, snapshots,
timestamp ordering and concrete master AI actions across ten archetype labels.

An isolated parent probe reproduces three distinct failures: an unattached Belt
of Giant Strength sets an unrelated Elf to 10 power instead of 1, a zero-mana
Fervent Champion equip is not offered, and list-valued equip metadata causes an
AI AttributeError. These are direct bounded reproductions, not a full parent
suite or statistical strength comparison.

The new real browser scenario equips Bonesplitter onto Fervent Champion as human
seat two with no mana, resolves the stack, and verifies effective power 3 while
the unrelated Elf remains power 1. API/browser/full-suite tests run in disposable
source/database/cache copies, never the user's live database. Installed
dependencies are reused, not freshly installed.

Final focused checks pass 157 tests. The full isolated backend suite passes
2,020 tests with 292 existing deprecation warnings in 189.85 seconds. Frontend
lint, TypeScript/Vite build and runtime/unit gates pass. The full Chromium
harness passes action/choice scenarios, simulator preflight/recovery, saved-match
refresh/process restart, creation recovery, sideboarding and natural AI,
human-versus-AI and human-versus-human BO3 flows.

[Eight seeded seat-paired BO1 games](equip-context.json) repeat identical complete
reported game objects/logs across sixteen executions. All match the parent,
without timeout or logged cast/target rejection. Production-source hashes are
verified against the isolated execution copy. An optional Spell Pierce payment
failure is an ordinary declined payment, not rejected casting. These unchanged
smoke results do not exercise the new equipment fixtures or certify optimal
play/balance; targeted canonical and browser tests verify the new mechanics.

## Known Limitations and Next Upgrades

Strong Back's supported equip reduction no longer warns, but its Aura spell
cost reduction remains explicitly unsupported. This milestone does not add
Aura target-aware cast payment, alternate/multiple equip costs, equip timing
overrides, reconfigure, fortify or arbitrary activated/granted abilities.
Humility's explicit base-stat clause is supported, not its full ability removal;
full ability suppression receives a preflight warning. General dependencies,
conditional base setters, color/type layers and all-zone object identity require
further work. A positive board-score equip projection is not deep strategic
planning: transfer opportunities, mana reservation, removal exposure and
multi-action sequencing need decision-quality fixtures and larger evaluation.
