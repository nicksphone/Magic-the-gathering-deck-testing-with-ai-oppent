# Generic Self-Land Animation Candidate

## Baseline And Scope

Owned source-only Git archive of `55ebc8c6cba982300f85289bdbe3d114fa29b2e5`,
plus the unchanged canonical land-animation audit dependency. Not a current
parent/main qualification. No AI, engine, stack, model, schema, repository,
importer, or live-database change. No paid API calls or application lifespan.
SQLite used by tests is local or memory-only. Test processes are terminal.

The initial tests-only patch SHA-256 is
`ab9b583ceed38d8bda87f3a742e911d38bc86af4a7c712539a4f43fd05aa948d`.
Both original audit modules and their four full canonical raw fixtures are
unchanged. Ghostly Flicker was added through one bounded official public API
request before response tests, with full raw bytes, identity, digest, headers,
timestamp and URL in a separate provenance ledger. Official API documentation
again returned 403; successful documentation retrieval is not claimed.

## Shared ABI And Ownership

`rules_engine.land_animation.compile_self_land_animation(state, source,
instruction)` is a pure full-body query returning `(effect_key, payload)` or
`None`. `animation_candidate` delegates self-animation bodies before generic
clause splitting; a candidate that cannot be compiled becomes explicit
unsupported noop, never a supported fragment. Numeric printed P/T, bounded
evergreen grants, literal colors/subtypes, full duration and land-retention
wording must match. Unknown compound/conditional bodies remain unsupported.
Grammar-negative and self-reference probes are labelled parser inputs, not
rewritten canonical cards used for execution.

`resolve_self_land_animation(state, controller, payload)` uses existing real
stack/payment execution and `add_type_effect`, `set_base_stats`, and
`add_keyword_effect`. The payload captures source ID, incarnation and zone
sequence; the resolver requires both identity guards and battlefield presence.
No new source IDs, future IDs, activation events or animation flags are injected.
No card-name dispatch, fake Changeling keyword or printed-color mutation.

`add_type_effect` gains optional `creature_subtypes` and `colors` arguments.
These become optional keys on existing timestamped/incarnation-bound records,
not new model fields. One resolution timestamp is shared across layers.
Existing type-effect cleanup/departure and snapshot deep-copy serialization
carry and expire the records unchanged. `creature_types(card, state=None)`
remains backward compatible; stateful consumers use the layer-four type line.
The effective color query uses resolved color timestamps, including competition
with the existing colorless permanent-land replacement. Printed characteristics
remain unchanged. All creature types are layer-four subtypes, not a keyword.

Existing production changes are confined to:

- `oracle_effects.infer_effect_from_oracle`: one additive compiler delegation.
- `effects.registry`: one additive `animate_self_land` key/import.
- `type_effects.add_type_effect`: optional record keys.
- `basic_land_layer.layer_four_view`, `_type_operations`, `_resolve`: subtype
  operations and effective lines in existing layer order.
- `colors.card_color_symbols`: effective color overlay.
- `library_permissions.creature_types`, its two existing callers, and
  `continuous._has_subtype`: effective subtype query.
- `_matches` in affinity, `_eligible_sacrifice_ids` in costs,
  `_has_creature_subtype` in graveyard permissions,
  `_matches_enters_battlefield_trigger` in events and
  `temporary_pt_buff_all` in handlers: state forwarding only.

Jason's engine/stack source, Erdos's `_infer_targeted_search_effect`, all other
Oracle helpers, and Sagan's AI are unchanged. Lagrange owns complete blink
compilation/resolution separately; no blink, target-hint or source-entry handler
was edited here. Compose additive Oracle/registry hunks surgically, not by whole
file replacement. Exact baseline/current hashes and AST scope accompany the
artifact. No direct agent messaging tool was available; seams were relayed
through the parent before editing and as required callers were discovered.

## Terminal Ledger

All ordinary tests; no skips, xfails, case exclusions or expectation adapters.

| Gate | Cases | Pass | Fail | Exit | Seconds |
|---|---:|---:|---:|---:|---:|
| First unchanged audit | 68 | 60 | 8 | 1 | 10.35 |
| Intermediate three-module audit | 102 | 86 | 16 | 1 | 18.55 |
| Expanded three-module audit | 118 | 102 | 16 | 1 | 16.68 |
| Final same three whole modules | 118 | 106 | 12 | 1 | 17.54 |
| Eighteen whole neighbor modules | 722 | 722 | 0 | 0 | 84.57 |
| Separate whole pending/replay module | 8 | 4 | 4 | 1 | 3.17 |

Final distinct coverage is **848 checks: 832 pass / 16 fail**. Earlier executions
are repeats and distinct source/test revisions, not additional coverage.
Original 68 alone are **60 pass / 8 fail**, with every initial animation
admission prerequisite removed. Eight layer/roundtrip and eight sickness/combat/
mana/cleanup cases execute and pass. Four original Flicker cases execute the
animation and then expose the unrelated blink failure. The original files
remain byte-identical rather than rewriting their ledger.

The terminal failures are:

- Four original and four new pending Flicker reentry requirements: the baseline
  compiler executes only exile, not the canonical immediate return.
- Four original empty-pool Mutavault rejection expectations: the untapped
  noncreature land itself can tap for the required one mana. Correct execution
  is accepted and pays, including same-turn entry. New strict positive tests
  prove that payment; separate native tap/phase-clear controls prove genuinely
  unavailable payment rejects atomically. Forbidding self-payment to turn stale
  assertions green would be a rules regression.
- Four Ghostly Flicker pending-response requirements: actual checked cast
  admission rejects the canonical two-target response. This is a distinct
  target/compiler dependency, not an animation-incarnation failure.

The intermediate pending-departure control mistakenly budgeted Flicker at
`{2}{W}`. Its raw cost is `{1}{W}`. Only the new control's initial mana budget
was corrected; old ledgers and runtime pins are preserved. Final four controls
use two real animations plus real flash-granted Flicker, pay the full exact
budget and resolve pending animation after source departure without overlays.
They characterize the baseline's exile-only blink, not correct blink semantics.
They must not become a requirement that a future correct blink stays exiled.

## Qualified Boundaries And Remaining Dependency

Both seats qualify retained/newly played animation admission, native checked
cost/payment and stack resolution, P/T, effective subtype/color/keyword views,
sickness/attack/mana restrictions, vigilance, full native cleanup, snapshot
roundtrip, and both timestamp orders against real cast Song of the Dryads.
Off-turn priority activation replays deterministically from the same complete
saved snapshot without root/RNG mutation.

Eight original HTTP cases execute real requests: funded cases succeed; empty
Mutavault is also genuinely payable; empty Colonnade rejects. Four new both-seat
HTTP cases qualify activation and human pass, then a native checked AI pass,
resolved public views and in-process memory-SQLite persistence restore. The
AI-controlled actor is never impersonated over HTTP. Opponent held-card IDs are
absent public responses/views. Existing owned default DB bytes are fenced by
the unchanged memory-HTTP fixture. This is not a cold-server restart certificate.

**Pending source departure is proven; pending departure/reentry is NOT fully
qualified.** Reentry remains blocked by the separately owned blink dependency.
Parent must couple that reviewed compiler/handler and run the unchanged desired
reentry assertions before claiming it. Ghostly Flicker's two-target contract
may require separate ownership, not broadening the animation parser. The four
stale empty-pool rejection expectations need an explicitly approved test-only
adaptation, not cost or action-policy weakening. No fully green original-68 or
deployment claim is made by this candidate.

Mechanic metadata and unsupported-clause classifier coverage are unchanged.
They do not certify rules support, all manlands, all layers or trained AI
competence. Generic recognition remains bounded to the implemented complete
grammar; unrecognized other animation clauses remain unknown/unsupported.
