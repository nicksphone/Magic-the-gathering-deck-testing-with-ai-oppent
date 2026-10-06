# Extra Sequence Readiness Audit

Scope: two canonical families only, on frozen M plus the qualified nth-cast
increment. NEW tests/fixtures/document only; no production change. This is
not the parent's separate 279-case funded composition qualification.

## Canonical Intake

`backend/tests/fixtures/extra_sequence/canonical.json` contains complete,
unmodified archived Scryfall raw rows for Time Warp, Aggravated Assault, and
the existing real Island/Grizzly Bears controls. `provenance.json` pins the
compressed bulk archive, exact row locations, IDs, Oracle IDs and hashes.
Intake was captured before the first tests. Scryfall serialization is not
represented as Wizards data. The official release notes independently
corroborate the costs, types and mechanics. The older Assault release notes
use a different conditional wording; current corpus Oracle is retained,
never shortened or rewritten to fit the engine.

- [Official Time Warp release notes](https://media.wizards.com/2021/downloads/STX_Release_Notes/EN_MTGSTX_FAQ_04122021.pdf), page 65.
- [Official Assault release notes](https://media.wizards.com/2023/downloads/WOE_Release_Notes_9S5bvPQTjRwh/EN_MTGWOE_ReleaseNotes_20230518.pdf), page 64.
- [Official Comprehensive Rules, effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).

Desired contracts use CR 500.7 (insertion and newest extra turn first), 500.8
(phase insertion), 505.1a (additional main phases are postcombat), 302.6
(continuous control since most recent turn began), and ordinary untap/draw
rules 502 and 504. They do not assume that an additional combat includes
untap, upkeep, draw or a new turn. Assault untaps controlled creatures, not
lands or opposing creatures, and its sorcery timing remains mandatory.

## Layers And Findings

Time Warp: metadata intake is complete and `ready_for_match` is true.
Both player targets are recognized. The spell compiler reports fallback
and `noop`; the legal move path nevertheless permits an actual paid cast.
Five mana is spent and resolution moves the real spell to the graveyard.
The state then follows ordinary alternating turns, not the targeted extra
turn. The known-gap enumerator returns no marker. This is fail-open spell
admission, not a working extra-turn effect.

Aggravated Assault: metadata is ready; extraction preserves the full
activated text and `{3}{R}{R}` cost. Casting the enchantment with no spell
effect is correct and is not an activation support certificate. Its actual
activation proxy compiles to fallback/noop. Legal generation withholds it;
checked action and HTTP reject before payment. Untap-all-creatures itself
is unsupported in this trace, so there is no observed first-clause success
masking later phases. Known-gap enumeration still has no marker.

The inspected state/serializer and fixed `TURN_STEPS` progression have no
admitted insertion queue on this frozen source. State scheduling, ordering
and restoration of queued extra turns/phases therefore remain unsupported,
not verified by ordinary snapshot round trips. Desired fixtures stop at the
first real blocker. Assertions after that blocker are future contracts,
not executed evidence.

## Test Separation

Default `test_extra_sequence_readiness_audit.py` is a green characterization
module. It checks both seats, complete fixture hashes, actual targets,
payment, legal activation omission, pre/postcombat main and upkeep rejection,
original-root/RNG purity, ordinary progression, and snapshot round trips.
It uses an exact copy of the production activated proxy, never injects an
effect key or synthesized scheduler. Unsupported witnesses must be adapted
explicitly if production gains real support.

`desired_extra_sequence_contracts.py` is deliberately NOT default collected.
Explicit execution gives ordinary red desired tests, without xfail or weakened
assertions. It covers target vs controller, multiple-resolution ordering,
payment/source identity, queued snapshot restore, untap/draw/sickness and
combat/main progression. Do not promote it as a passing release gate.

Four isolated two-process TestClient cases use actual `/matches/start`,
`/action` and `/rules-diagnostics` routes plus production startup/restore.
They persist synthetic states to local SQLite, both human-controlled seats,
no external network or listener. They prove pending paid-noop restoration
and fail-closed rejection, not extra scheduling through HTTP. Snapshot,
configuration, RNG and mutation receipts survive exactly. Read diagnostics
are byte-pure; rejected writes compare all root facts plus RNG/config/SQL
because production rollback deep-copies object alias topology.

## Reproduction And Limits

Run from `backend` using an isolation wrapper rebinding the default DB before
importing `main`; never run these startup tests against a live database.

```sh
pytest -q tests/test_extra_sequence_readiness_audit.py
pytest -q tests/desired_extra_sequence_contracts.py
```

The archive contains the wrapper, official document hashes, terminal logs,
machine-readable traces/findings and exact source manifest. The first
development run's two receipt replay harness failures are preserved: it
omitted the required revision header. Final requests supply the same original
header pair; no production behavior was changed.

No AI quality, balance, win-rate, opponent hidden-hand or unseen-library
claim is made. No scheduling fix is authorized or included. A future fix
needs separately declared effect/admission/state/serialization scope and
generic turn/phase insertion; name-based dispatch or forced paid casts are
not suitable corrections.
