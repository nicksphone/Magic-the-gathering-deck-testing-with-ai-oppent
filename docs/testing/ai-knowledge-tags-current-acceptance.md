# Persisted Tactical Tags: Current Bounded Acceptance

This increment is based on immutable `4ff6a814cb3488ddd5062b8794a68bf4f7eeeb15`.
It consumes the existing canonical `CardKnowledge.profiles_json.tactical_profile`
without changing numeric AI scoring, matchup weights, target legality, mana,
layers, X payment policy, effect handlers, or the profile producer.

## Data Flow

`hydrate_deck_cards` bulk-loads local knowledge as before. After final cache
characteristics are selected, `knowledge.service.snapshot_for` validates the
canonical row/printing/Oracle identity, full-RAW profile input hash, profile
version, indexed faces, persisted tag consistency and final printed surface.
Inbound deck-supplied `knowledge_snapshot` is always discarded first.

The compact `CardInstance.knowledge_snapshot` is a private, match-frozen dict:
`schema_version`, `estimator_version`, `scryfall_id`, `oracle_id`,
`source_sha256`, `layout`, `root`, `faces`, `rulings_pending`, `limitations`,
`snapshot_sha256`. Root/face descriptors contain only printed Oracle/type/mana,
printed types and persisted role tags. No scoring values, corpus inventory,
ruling text, art, or repository/session handle is carried. The consistency
seal is not a client authorization, signature, gameplay permission, or source
execution certificate. Rulings-pending/verified flag transport is distinct from
actual official ruling intake and qualification.

MatchFactory copies the carrier, with the new dataclass field appended to
preserve existing positional constructor slots. Private snapshot serde copies
known shapes, semantically validates tags on cold restore, and drops malformed
or unknown-version carriers to empty. Old snapshots remain valid and use a
visible fallback. New matches can hydrate new data; existing games do not
refresh repository rows during search or cold restore.

`AIAgent._spell_tags` consumes persisted tags when the actual printed surface,
layout, complete face roster and explicit selected index match. A recognized
front-default layout with no selected index uses face0 only when the actual
surface agrees. Unselected composite/split descriptors, changed live Oracle,
invalid indices, stale shapes and missing metadata fall back to the exact
existing `card_data.tactical.tactical_tags`. No new Oracle parser is added.
Indexed modal proxies transport metadata only for the real original face
object at the caller's explicit index; detached equal copies cannot acquire it.
A proxy does not gain a physical `id` that could alter existing engine-layer
lookups. Positive persisted lookups do not re-run the tactical parser.

## Private Usage And Privacy

Each actual `choose_action` returns optional `AIDecision.knowledge_usage` with
anonymous `persisted`, `fallback`, `opaque` counts and finite fallback reasons
`missing`, `shape`, `face`, `surface`. Counts deduplicate repeated consulted
identity/surfaces within that decision and reset even on exceptions. Existing
action/reasoning fields remain unchanged. This is the private per-decision
source/fallback why sink; no names, hashes, tags or candidate inventories are
returned in it. This increment does not wire it into shared logs, public APIs,
observer/teacher metadata, or analytics Oracle-resolution failure counters.

The existing decision-view mask creates fresh opaque CardInstances before
planning deepcopy, leaving the carrier empty, including all identity/hash/face
metadata. Existing authorized observations preserve legitimate old carriers;
a hidden library trip does not restore them. Public serialization retains every existing field and recursively discards only
`knowledge_snapshot`, including nested pending projections and tuple/list
containers. Tuple/list and scalar types are preserved. Private cold observation
records also validate their carrier before legitimate known-memory reconstruction.

## Observed Gates

- Initial NEW12 API/field-absence gate: 12 strict failures, 0 errors/skips, 1.39s.
- Initial both-seat NEW14 behavior gate: 14 strict carrier-absence failures,
  0 errors/skips, 1.36s. Neither absence gate is a gameplay or semantic proof.
- First implementation: 12 pass /14 fail, 2.72s, because the NEW fixture used
  obsolete `tap_for_mana` rather than actual `tap_land_for_mana`.
- Correct typed tap: 24 pass /2 fail, 2.83s, because the NEW assertion accessed
  nonexistent `StackItem.kind`. It now uses actual retained stack-kind/mana
  predicates, plus actual priority passes/resolution; no production workaround.
- NEW26 actual implementation cases passed in 3.13s.
- Boundary draft: 19 pass /2 fail, 1.51s, including accidental imported-TestCase
  recollection and one source-write-denied offline art setup. Both preserved.
  NEW plumbing uses the real official image URI without fetching and imports
  helpers as a module. Clean constructor-slot RED: 1 fail /8 pass, 1.52s.
- A whole-roster launch exited4 before collection because two public modules
  were absent from the small copy; exact immutable Git blobs were recovered.
- Pre-privacy-correction whole gate: 95 ordinary pass +10 subtests, 64
  deprecation warnings, 4.16s. Nested public pending projections then reproduced
  two strict privacy failures (9 pass), including tuple/list controls; an
  eleven-case boundary gate retained those failures, 3.27s. Narrow recursive
  omission produced a whole97+10-subtest pass in 4.31s.
- Cold known-memory resealed-tag controls: 2 strict failures /11 pass, 1.76s.
  Observation-carrier validation was added without changing other record fields.
- Final seven WHOLE modules: 99 ordinary pass +10 subtests, 80 deprecation
  warnings, 4.48s, exit0. Counts are 39 NEW +60 old ordinary cases, not99 NEW.
  Source-before/end hashes equal; three actual SQLite/socket/Popen constructor
  attempts were denied before resource creation; `UNEXPECTED=[]`.

The real core tests use genuine published full-RAW fixtures, actual
CardKnowledge model values through an explicitly inert read-only lookup,
real hydration/MatchFactory/agent choices and checked paid cast/resolution
for both seats. Initial board positioning is trusted fixture setup, not a
naturally replayed opening hand. They cover private cold serde (not an HTTP or
file-DB restart), original-versus-missing-profile decision parity, hidden
identity substitutions, authorized memory, explicit Adventure face transport,
forged client/semantic snapshots, changed-body/composite fallbacks and counters.
They do not certify actual repository reads, public HTTP, a full match,
head-to-head decision quality, UI, expert strength or arbitrary rules.

## Remaining Original Acceptance

Independent peer review/composition is required before promotion. Full pytest
and the original planned `scripts/debug_head_to_head.py --deck-a Tempo --deck-b
"Blue Control" --matches 1` have not been executed here: this scope denies SQL,
network and child processes. A separately reviewed parent runtime scope must
qualify actual persisted-row integration and the original smoke, with deck
availability verified rather than silently substituting a different named
cohort. Task2.3 threat/answerability scoring and measured A/B quality remain
separate work. No D13 SDK/source/root/capture/budget authority is inferred.

## Modal Usage Counter Correction

Independent review found that two physical cards' indexed modal proxies could
collapse into one usage entry because proxies deliberately have no engine `id`.
A separate correction transports the original physical card ID privately as
`_knowledge_source_id` only for usage deduplication, and only with the existing
original-face-reference/index check. It adds no engine-facing proxy ID, scoring
change, name/value identity inference, or source authority.

Two NEW both-seat cases consult two genuine canonical physical CardInstances'
actual indexed proxies inside an actual decision, then repeat and rebuild those
same proxies. These are instrumented telemetry controls with trusted hand
positioning, not modal-policy quality or a naturally replayed match. The first
NEW fixture draft failed at the combined-name/front-alias lookup (99 pass /2
fail, 4.71s); that log is preserved. Correcting only the new lookup produced the
strict counter RED: 99 pass /2 fail +10 subtests, 5.29s, both observing one
persisted consultation where two were required. The minimal private-ID change
produced seven WHOLE modules: 101 ordinary pass +10 subtests, 88 warnings,
4.66s, exit0 (41 NEW +60 old ordinary cases). Source-before/end hashes equal,
all three actual IO-denial canaries retained, `UNEXPECTED=[]`. The prior frozen
99-case packet and all its gates remain historical, not relabeled.

Anonymous usage is programmatic `AIDecision` visibility only. Existing
AnalyticsService, debug/overnight trace forwarding and any private export
integration require separate parent qualification; this slice does not certify
HTTP traces or declare all of Task2.2 complete.
