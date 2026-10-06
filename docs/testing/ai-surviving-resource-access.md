# Surviving Known Inventory Access

## Incremental Contract

Only resource_delta's access grouping changes. Original actor-hand IDs are
grouped by the unchanged printed cost/text/effective-before-type key. For each
ready state, a class has access if ANY original ID still in that actor's hand
is affordable, using that state's card object, mana_cost and effective types.
The existing payment planner applies that state's cost modifiers and the
parent's source reservation. Missing original classes have no access. Newly
drawn cards never become new members, even with identical printed identity.

Weight remains 3.0 per class, not per copy. Anonymous capacity probes, known
color demand, enemy public demand, excluded source IDs, X exclusions and
private-zone boundaries are unchanged. No search cutoff, named-card handler,
new numerical value, _can_pay change or full casting-legality claim is added.
Byte equality outside resource_delta is independently checked; its prefix
through resource-capacity/public-private construction is also byte-identical.

## Qualification

Parent supplied baseline:
current-ai-mana-frontend-static-qualified-source.tar.gz, SHA256
a853b32bee1f50caa06e510da7a2af7410cd24077bc24799fcaded4f4cf8ab7b.
Baseline mana_resource_policy.py SHA256:
31f98a8287b5566bfcdc8f38a292659dff90e9cc01caa95fd234720ad0bb5897.
Patched file SHA256:
939d82a97ad4ac3a0e3e3c2b52277f2a988e3aa26f9de9d3217f3fe3c2a01a09.
The archive already includes both parent source-forwarding fixes; this delta
must be applied after those, not the earlier unforwarded source. Archive bytes
are pinned, extracted locally and content-checked; the hash is a reproducibility
pin, not an independent signature or publisher-authentication claim.

Final strict requirements: baseline 8 failures/12 passes; patched 20 passes
within the final 307-pass core gate. Both seats cover duplicate victim,
remaining alternate, first original leaving, entire class disappearing,
same-name drawn replacement, new drawn class, exactly one class weight,
excluded source identity, private/copy identity, anonymous capacity, and real
Goblin Electromancer cost reduction. All source snapshots are immutable across
queries; tests use actual Familiar activation and draw_card where applicable.
The reducer comparison uses explicit canonical positions, not a claimed played
or naturally chosen episode.

Core gate includes the complete announced-source, mana-resources, cast-resource
policy, resource-forecast, fixed-cost witness, consumption-reservation and
fixed-color-feasibility suites, canonical provenance verification, plus six
explicit public-resource/privacy neighbor functions. 307 passed in 30.75s,
no exclusions, deselections, skips or expected failures in that selected gate.
It is not the entire backend/API/browser suite. SQLite and socket connection
audit hooks reject connections; no live DB or API lifespan was used.

An earlier 16-case gate had 8 failures/8 passes before and 16 passes after;
its neighbor gate had 289 passes. An initial fixture adapter assumed Mountain
was in the overlap ledger (10 failures/6 passes); corrected by reusing exact
existing ward.json Mountain without changing any fixture facts. These attempts
are retained separately and are not qualification counts.

Run from the composed backend:

```sh
python -m pytest -q tests/test_ai_surviving_resource_access.py
```

## Actual Score Receipts

The archived score_receipts.py invokes both pinned production implementations,
and separately records unchanged capacity and source-safe access on surviving
original IDs. score-receipts.json has twelve receipts, six scenarios per seat.

| Scenario | Baseline Score | Patched Score | Patched Access Delta |
| --- | --- | --- | --- |
| Familiar discards last duplicate; other survives | -1 | -4 | -1 |
| Alternate survives with a Swamp | -0.25 | -0.25 | 0 |
| Entire original class discarded with Swamp present | -1 | -4 | -1 |
| Same-name new draw replaces discarded original | 0 | -3 | -1 |
| New draw with no original class | 0 | 0 | 0 |
| Two original copies gain access from a Swamp | 4.5 | 4.5 | +1 |

Actual after-activation black floating mana can pay the surviving spell.
The readiness projection intentionally clears it; it is this retained-resource
access comparison that loses access, not immediate authoritative castability.
No naturally chosen full AI episode, competitive win rate or unrestricted
card correctness is inferred from these focused score receipts.

## Canonical Provenance And Historical Evidence

Reuses the reviewed cost-overlap canonical fixture (SHA256
fd6c5a98c5d88557589f6fa5f7b87dcb33a88be5bff76aa6a316595d1aa1f9ec)
and existing ward.json and announced_costs/goblin-electromancer.json. Per-record
canonical IDs/raw hashes and source file pins accompany the archive. Nullable
missing power/toughness fields are adapter-only, not fabricated card data.
No HTTP refresh or current-live Oracle freshness is claimed.

The earlier held-resource-identity characterization archive is immutable and
not included in this positive gate: it deliberately asserts the old routing.
The original six helper omissions remain genuine bugs resolved by the parent,
not invalid tests. Remaining escape-fuel limitations and broader additional-cost
AI heuristic boundaries are outside this incremental change.
## Parent Composition Receipt

Composed with the current selected-mana, cost-witness, planner-pruning and bounded
layer/LKI/attachment candidate, not only the worker's prior frozen baseline.
The nine-module parent gate passes 672 checks, six existing datetime warnings,
195.29 seconds, exit 0; no skips, deselections or expected failures. It includes
all new surviving-access regressions, announced-source availability, AI mana,
resource forecasts, recurring engines, cast-resource policy, public mana changes,
fixed spell-cost witnesses and spell-consumption reservations. Counts overlap
prior gates and are not additive. A contemporaneous actual-App mana run passes
14 cases, both seats and restart; it is not the full shared-browser gate.

No main/live promotion or arbitrary-deck expert-play claim is implied. Raw
parent evidence is stored in the project NFS archive under
`parent-integration/spell-reservations-d88dbf0/current-surviving-access/`.
