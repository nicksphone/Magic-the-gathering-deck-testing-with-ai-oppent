# Bounded Generic Damage Protection

## Root cause and production boundary

Actual paid Sickening Dreams has a genuine resolving spell source. Existing
`stack_engine.resolve_top_of_stack` writes `__source_card_id` from the actual
stack item. `damage_each_creature_and_player` and `deal_damage_batch` forward
that field and optional retained `__source_lki` unchanged. Recorded real damage
packets show the canonical Sickening Dreams card in STACK with black color.
There is no missing source-forwarding seam in these episodes.

The old final `handlers.deal_damage` reader tested only individual source color
strings against individual protection keywords. It omitted the already shared
generic protection matcher, including protection from everything. This caused
the original six strict Progenitus protection failures. Production changes
ONLY the `deal_damage` body, with a local import of unchanged
`rules_engine.protection.protection_match_reason`. No parser, registry, stack,
helper, events, executor, batch, legend, Aura, cost or engine change.

Internal ABI unchanged: actual `__source_card_id` identifies the live source;
`__source_lki`, when present, is authoritative retained source characteristics.
The target's current effective protection remains authoritative. Live source
color/type queries remain state-aware. A missing source is not fabricated or
inferred as colorless/nonartifact. Only the source-independent `everything`
result may prevent a missing-source primitive. Existing prevention locks skip
protection prevention, including everything. No StackItem, causal receipt,
Oracle, card name exception or zone fiction is created.

## Executed strict ledgers

Final NEW56, unchanged before/after:
- Frozen preimage: **46 PASS / 10 FAIL**, 2 warnings, 36.07s, exit1, bound600.
- Final reader: **54 PASS / 2 FAIL** within the final focused gate.
- Eight ordinary damage-reader reds become green: actual paid black damage,
  canonical black/colorless primitive sources, and source-independent all-damage
  prevention with omitted source. No skip/xfail/deselection.

Original unchanged42 plus NEW56 after repair: **96 PASS / 2 FAIL**, 422
warnings, 39.22s, exit1, bound600. Every original42 assertion passes unchanged,
including the former six direct/HTTP Progenitus protection failures, both seats,
memory/file SQL, actual paid simultaneous episodes, private views, cold restore,
subprocess snapshots and explicit APNAP/atomic rejection controls.

13 whole affected neighbor modules: **321 PASS**, 7 warnings, 39.07s, exit0,
bound900. Includes canonical state colors/layers, actual stack source departure
and retention, global protection, damage/counter replacements, prevention-lock
scope, LKI, lifelink, conditional damage materialization and real HTTP routes.
Across final gates: **419 distinct cases, 417 PASS / 2 FAIL**.
No historical995/1471 suite or current parent release certification.

## Explicit unclosed activation ledger

Two NEW desired Walking Ballista activation cases with White Knight targets
still fail at `checked_action`: no Ballista activations are offered in this
frozen position, despite retained counters. They fail before damage. Actual
compiler/admission root cause is NOT diagnosed or repaired by this reader
increment. The other two Ballista/Progenitus rejection cases demonstrate only
atomic rejection, NOT that Ballista was admitted and then protection matched.
No claim of whole Walking Ballista support or successful colorless activation.
Canonical colorless damage prevention itself is independently exercised by
explicit primitive controls. These are not fabricated paid ability episodes.
Both activation failures stay ordinary, visible and unexcluded.

## Canonical and controlled coverage

Full existing canonical Progenitus, White Knight, Kor Firewalker, Walking
Ballista, Lightning Bolt, Sickening Dreams, Wrath of God and Humility fixtures
are reused unchanged. Ballista bytes match its existing retrieved-full-raw
provenance SHA. Other source fixture/provenance bytes remain exactly inherited.
No new Oracle or card/deck balance is invented.

Both-seat lawful paid black nontargeted damage proves prevention on Progenitus
and White Knight. Red targeted Bolt is checked-rejected atomically on protected
targets, but lawfully resolves on nonmatching White Knight. Actually paid
Humility removes protection before subsequent legal targeted/nontargeted damage.
Untargeted paid Wrath remains destruction, not prevented damage; Progenitus's
actual library replacement and White Knight's graveyard destination are retained.

Missing-source and cannot-prevent controls are explicitly engine primitives;
the latter uses existing `set_turn_restriction`, not a claimed canonical spell.
Walking Ballista counters are a controlled starting position, not a cast/entry
episode. Real canonical Prodigal Pyromancer live and captured LKI characteristics
are checked with and without the actual layer-four Song attachment seam. The
Song attachment and return primitive are CONTROLLED, not sorcery-in-response or
illegal converted-land target claims. `capture_last_known_battlefield` provides
the retained receipt; tests do not fabricate its characteristic dictionary.
Existing neighbor actual stack tests additionally preserve departing-source
reference/incarnation and live target legality.

## Frozen inputs and evidence

Own source-only input from death-batch-entry-publication-product/
mtg-death-batch-product-qERfB0/candidate-source.tar.gz, SHA256
`9284f86a5611ce485eab7d6f7c7bb9232d2dd322824b893e8a677e18d86f604c`.
This already contains the qualified destroy-all/SBA increment and zonef790;
it is NOT the subsequently moving published parent composition.

Handlers preimage `a3e10ba8cd357be2e8913e10e265a0292d669a258fd5726a6632ad05f52614e2`
-> postimage `1cb8f683c791a80ef5c242eb43455f7abb43178f57937462b9df39db83f6f7fa`.
Protection `b3475295156d7d9a857742ab08e68ea8d248d9aab5d15268f7dadea495a3456c`
and stack `d805c4ac4210905c08be8ee7b0e49c9c43d9a5c51b36e4408d65a3fb28f6338e`
remain unchanged. AST outside `deal_damage` is identical. All1267 inherited
backend files checked; only that handler file differs. Original42 bytes remain
`2882932c12d6798a651e5d907215cd23534c895fa31c556cce997eba532d948a`.
Apply surgical hunk only; disjoint mill/destroy-all/SBA ownership is preserved.

Primary rules: full official archived CR20260925, SHA256
`8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`.
702.16e/j govern prevention from matching sources/everything, 702.16b governs
target restrictions, 615.12 preserves unpreventable damage. The archived text
supports the missing-source everything assertion; missing characteristics do
not establish a color/type quality. No all-protection/all-combat claim.

Existing qualified Python3.12.3 and pinned dependencies reused; pip check clean,
no installs. Socket and foreign-SQLite audit guard active throughout. Fresh
memory/file SQL only inside own local source. No parent/main/live reads or
writes, no NFS SQLite execution. Commands, full raw gates, actual damage packets,
complete snapshots, immutable before ledgers, dependency/source/AST proof and
per-node XML are archived. AST-only graph update, no API cost.

Initial diagnostic44:36PASS/8FAIL8.26s. Initial repaired86:84PASS/2FAIL39.42s.
Those ledgers remain immutable; missing-source everything expectations were
strengthened and matching-red/LKI controls added BEFORE final56 strict-red and
final qualification. Final56 assertions then remained byte-identical.
Initial neighbor321:299PASS/22 setup FAIL46.51s, solely missing
`MTG_HEAT_WITNESS`; preserved before supplying the immutable pinned witness
`c2eac237fe12c4783e65ccf692c239591378e3d6ad893fcbec31cecf8af9f653`.
The corrected gate runs the identical whole modules, no test edits/exclusions.
