# Library Choice Intent Audit

NEW tests/report/fixture only. Baseline is the previous exact qualified consumer
source archive, SHA256
`501760495cf3555cd0c70a46e841a88d4782d6c35c6edd49cff9f831c7e75da6`.
No parent H/K source/database reads beyond reading the declared H path pointer;
no production, policy, action schema, metadata allowlist or Ninjutsu edits.

## Actual Contract

All tested phases use public `MechanicChoice`, action type `choose_mechanic`,
with explicit `card_ids`. Its optional nullable siblings remain compatible;
no chosen list is inferred from display or a null-only selection. Actor identity
is the checked request seat, not a chosen payload alias. Raw action API packets
remain strict and reject whole legal views rather than dropping metadata.

Actual initial scry/surveil views carry `controller`, `amount` and `top_ids`;
they also carry `continuation_controller` and `continuation_effects`, preserved
through their top-order phases, which add `bottom_ids`. Look-select views carry
`effect_key`, `effect_payload`, `top_ids`, inspected IDs/cards and paused
resolution context; explicit bottom-order continuation carries `bottom_ids`,
`continuation_effects`, `counter_continuation_queue` and `draw_continuation_queue`.
Fields are measured from actual generated engine/API views, not invented aliases.

Canonical coverage is deliberately bounded to Opt/Preordain (scry),
Consider/Notion Rain (surveil), Impulse/Memory Deluge (look-select), both seats.
Scry and surveil partition choices cover keep all, one selected, all selected;
multi-card keep cases then explicitly order the retained cards. Impulse selects
a non-first offered card and explicitly orders the other three bottom cards.
Memory Deluge uses the actual paid printed cost and random-bottom continuation;
no flashback or arbitrary-family certification is claimed. Spells are actually
cast with offered cost IDs and resolved by priority passes before inspection.

Preordain is complete raw JSON from
`https://api.scryfall.com/cards/named?exact=Preordain`; provenance records its
actual Scryfall URI/IDs/hash and response date. Existing complete Oracle/stats
fixtures for the other five cards are reused without mutation. No shortened
Oracle, manufactured card/type, fake alternative or guessed target/cost.

## Findings And Controls

Whole actual raw views fail `TrainingEnvironment.lookup_intent` for each tested
initial/order phase: `controller`, `amount`, `bottom_ids`, `effect_key` and/or
the continuation fields/queues listed above are not recognized by its mechanic
metadata sets. Existing recognized metadata
is exact-matched, but these actual continuation fields fail the unsupported-key
guard. This is a supported whole-view consumer gap, not an engine choice failure
or permission to relax the raw API schema. Proposed next seam only: validate
supplied actor-owned continuation metadata against authoritative pending/current
views before stripping it. No blind allowlisting or consumer change here.

Independent controls retain minimal/policy-view explicit actions and selections,
exact card partition/order/hand/graveyard/life/draw effects, snapshot/RNG replay,
wrong seat and typed unavailable/duplicate/stale rejection, hidden own-library
prefix/foreign hand privacy, unknown/null/nested aliases before completion,
root/input immutability and exact real-HTTP SQLite/controller state across
rejection, successful checked actions, revision conflict and process restart.
Nullable sibling compatibility remains an explicit ordinary positive control.

## Receipt Representation Correction

An initial HTTP assertion compared Python RNG tuples/integer dictionary keys
directly to their JSON wire representation. Single-case receipt comparison
confirmed only tuple/list and integer/string-key differences. The expected
snapshot now uses a normal JSON round-trip before exact whole-state comparison;
no fields/assertions removed. Original failed client source and logs remain in
private evidence. Product code is unchanged throughout.

## Run And Limits

Use a fresh LOCAL source-only copy of the exact dependency, no SQLite/cache/
runtime/dependencies/`.git`. Apply this NEW-file delta; reuse external Python.

```sh
printf '%s' "$PWD" > .private-choice-audit-source
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q -s \
 backend/tests/test_library_choice_intent_audit.py \
 backend/tests/test_library_choice_http_audit.py
```

This is an intentionally strict diagnostic gate; whole-view expectations remain
RED until an authorized later consumer correction. No skips/xfails/legacy bypass.
HTTP uses the frozen guarded test-only Training bridge plus one NEW fixture route,
actual production legal/action/restore paths, fresh local SQLite and random
loopback ports; only spawned processes are stopped. This does not claim a
production Training HTTP endpoint, actual-App qualification, Training provenance
restore or new hotseat authentication. Explicit canonical retained positions
are not natural game histories or deck admission claims. The exact ledger,
source/receipt hashes and observed timings are in the terminal artifact; private
synthetic SQLite/response evidence stays under verified project NFS.
