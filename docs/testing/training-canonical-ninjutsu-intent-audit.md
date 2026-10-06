# Canonical Ninjutsu Intake And Intent Audit

## Official Intake

The previous missing-copied-fixture limitation is resolved by a direct public
HTTPS request to the official Scryfall API, with no key or paid service:
`https://api.scryfall.com/cards/named?exact=Ninja%20of%20the%20Deep%20Hours`.
Request start/end: `2026-10-06T05:28:54Z` / `2026-10-06T05:29:00Z`.
HTTP 200, curl exit 0. Full response body SHA256:
`d5c28c0171ed64bf41b2435a9edcf4ebcef7cc5d121e27996c74b9a1a8f41b0f`.

The exact raw body is copied unchanged to
`backend/tests/fixtures/ninjutsu_canonical/ninja-of-the-deep-hours.json`.
No Oracle, reminder text, keyword, type, cost, power, toughness or other
response field was shortened, rewritten or removed. The sibling provenance
JSON records URL, UTC timestamps, HTTP/curl status and response hash.
Tests assert byte hash and canonical field equality; the reused factory's
keyword omission is hydrated from the original raw `keywords` list, not an
invented card fact. Other cards are existing canonical Grizzly Bears fixtures
and committed builtin Island data.

Response, headers, request URL, timestamps and provenance were archived and
checksum/readback verified **before any offline test** at:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/training-groundwork/ninjutsu-canonical-intake-tDLWCm`.
Tests forbid external socket connections; all subsequent HTTP is the local
ASGI TestClient, using this checkout's fresh local SQLite, never NFS/live DB.

## Exact Source

Source reconstructed from frozen `foretell-intent-guard-9mxvBK`'s
`evidence/qualified-backend-source.tar.gz`; it was not copied from parent K
or moving main. All 961 files matched the archived manifest before intake
and after copying; they still match at completion. Manifest SHA256:
`61cd7f0f682c557728f8392daefa68afc0ebb812afab52fc20f984a0ea8d4b89`.
That source includes frozen foretell patch SHA256
`10eec65425cd092eaa27628143effeec96bee67275743a2d99c3af732516973c`.
Its graph report was read first; the new isolated graph is AST-refreshed.

All production bytes are unchanged, including all 18 existing consumer model
bindings (the prior 17 plus foretell). `training/environment.py` remains
`8416c70395a0c6436d7cb40e20824beac5c88cfdb65bc4be7c8c68fb29e9d017`.
No guard, helper, schema, producer, engine, agent, parent or main edit.

Public contract: `api_contracts.py::NinjutsuAction(CardAction)` has
`type='ninjutsu'`, required `card_id`, required `return_card_id`, and inherited
`extra='forbid'`. Actual producer:
`rules_engine/keyword_actions.py::ninjutsu_moves`; actual dispatcher/resolver:
`engine.py` / `activate_ninjutsu` / `resolve_ninjutsu`.

## Terminal Ledger

One complete 44-case module, serial, bound 900s, verbose/durations output:
**16 consumer RED + 26 independent PASS + 2 separate incarnation RED**,
103 warnings, 71.07s, exit 1. No skip, xfail, deselection or stateful acceptance
trick. This is a red diagnostic baseline, not a release qualification.

The 964-file source manifest (961 base plus raw fixture, provenance and new
test) is identical before/after the gate:
`20a1c153e3f2b85fc827735e3545cc4412b4c521787763674fc0e8fd4aa3f179`.
Test module SHA256:
`998ae3572682d0db09d30794ac7fee051172a992830cb515ce23e6eee4f20ba0`.
Docs and graph were added afterward, outside the tested backend manifest.

### Consumer Gap: 16 RED

Both seats: unsupported `return_card_ids`, `targets`, `cost_choice`, and
`resolving_item`, each non-null/null. Strict typed lookup rejects; real raw
HTTP returns 422 with full root, controller and SQLite dump unchanged.
The sole intent rejection assertion then fails with `DID NOT RAISE`:
`lookup_intent` passes this unguarded family to `complete_action`, which
discards those requested fields. The original root and caller dictionary
remain unchanged during trial lookup. No contradictory accepted-unsupported
execution witness is used.

### Independent Controls: 26 PASS

Both seats reach the window through real typed attack and empty block
declarations. Two canonical controlled Bears are actually unblocked; the
deliberate action returns the second, leaving the first attacking. Two real
Islands fund the exact ninjutsu cost. The actual source enters tapped and
attacking the same explicitly declared defender, via a non-spell stack item.
Chosen `return_card_id` survives canonical action encoding, trial lookup,
whole engine/HTTP hints, snapshot replay, HTTP execution and restart both
before and after resolution.

Invalid blocked return, pre-block timing, source zone, foreign return,
insufficient mana and missing/null/nested-alias return fields reject in both
lookup paths and raw HTTP, with root/DB atomicity. Missing return is not
inferred from a view. Actor input is byte-identical under adversarial opposing
hidden identity/order permutations; the Ninja is hidden before activation.

The full fetched combat-damage clause is exercised, not stripped: the Ninja
and remaining Bear deal four total actual combat damage. A Ninja-source
trigger reaches its real optional choice. Deliberate accept/decline draws
exactly one/zero actual top library cards; that future card is unknown before
the choice and hidden from the opponent afterward. Pending snapshots replay
deterministically; the same choice executes via HTTP across restart on both
seats. This does not redesign HTTP's existing two-human hot-seat policy or
claim exhaustive hidden-memory/public-reveal semantics.

### Incarnation Probe: 2 Separate RED

After paying/returning and placing the ninjutsu ability on the stack, the
trusted test root moves the source hand -> exile -> hand using actual
`CardInstance.move_to_zone`, maintaining both zone lists. Its zone-change
sequence increases. Snapshot restore and subsequent resolution reproduce
the same root, but the resolver moves the re-entered card to battlefield;
the test's stale-object expectation is HAND.

`activate_ninjutsu` queues only the attack target, and `resolve_ninjutsu`
checks source CardID/hand membership without the saved source sequence.
This is distinct from the consumer field-loss gap. It is a controlled direct
zone-transition probe, **not** a qualified HTTP causal exile/return spell
sequence, a comprehensive rules audit, or an implemented engine fix. Both
red assertions stay ordinary failures, not xfails/skips.

## Bounded Proposal

Consumer-only proposal: add public `NinjutsuAction` to `lookup_intent`'s
pre-normalization validation, reject unknown/null requested fields, and
qualify only actual `card_name`, `mana_cost`, HTTP `card_view` presentation.
Preserve the explicitly selected source and return CardIDs; never derive
them or a target/cost/context from suggestions. Qualify whole views and exact
metadata shape before widening the display allowlist. No implementation is
included until scope is approved.

Separate engine proposal: review source incarnation capture/check across
the pending ninjutsu stack boundary and qualify a real causal zone-changing
response before claiming that seam fixed. This test-only artifact does not
authorize or include engine work. No broad ninjutsu mechanics, GUI completion,
expert data or neural-policy competence claim follows from the 26 controls.
