# Event / Release Named Fixtures: Static Preparation

This document below records the immutable earlier static stage, including its
then-unresolved sacrifice-site HOLD. The later
[genuine Smothering identity correction](canonical-smothering-sacrifice-T57-prep.md)
is now tested: all73 event/release/sacrifice cases pass within the separate
seven-whole-module100-case declaration on October18. No historical preparation
archive is rewritten, and no whole-phase or full-backend acceptance is claimed.

## Historical Preparation

This unexecuted test/data preparation is based on the frozen T57 source, not
the moving worktree. No Phase1, whole-backend, runtime or mixed-HTTP acceptance
is claimed. The old player/planeswalker27 preparation is not included or changed.

## Four Reviewed Sites

| Whole Module | Named Positive | Existing Materializer |
| --- | --- | --- |
| `test_events_apnap.py` | Wrongly named Blood Artist in the sacrifice test | BLOCKED: original function remains byte-identical |
| `test_interactions_expanded.py` | Rest in Peace in combat; Blood Artist in lethal SBA | Same |
| `test_release_card_contracts.py` | Tarmogoyf in characteristic-stat rendering | `static_layers_canonical_a32.entry` plus actual Factory and `dataclasses.replace` |

At the three migrated sites, all printed facts precede native
`CardInstance.__post_init__` capture. The
Tarmogoyf template is an independent eight-card seed0 Factory; only its physical
pose is replaced. The original match's decks, stock, quantities, IDs, RNG,
graveyard land, owner/controller, actions and assertions are not repaired or
recaptured. Actual printed `*` / `1+*` remain strings; their numeric birth fields
are unknown, not invented 4/5 or zero. The original rendered 1/2 assertion stays.

The two old Blood Artist bodies incorrectly printed draw triggers. The complete
official print instead triggers on its own or another creature's death and
targets a player for life loss/gain. Native `handlers.sacrifice` emits a genuine
`creature_dies` event when the sacrificed creature enters the graveyard; the SBA
path likewise emits creature death. Existing assertions only require a trigger
controlled by seat1. However, replacing the sacrifice-only print with canonical
Blood Artist would silently move that test from the sacrifice-specific matcher
to the creature-death matcher. Its coarse stack assertion would not detect the
lost route coverage. That entire original function is therefore left unchanged,
including its wrong named Oracle. This is a static HOLD, not a literal waiver.
Its strict NEW first-consumer fidelity remains present and would reject that
old print; it is not skipped, xfailed, relabeled or softened. A truthful separate
protocol specification or explicit fixture-scope correction requires parent
review. No actual RED is claimed. The lethal SBA test still uses its original
creature-death consumer with canonical Blood Artist; its assertions are intact.

## Independent Fidelity

The NEW module declares fifteen cases: three full-RAW/provenance admissions,
four original first-consumer bodies, and eight explicitly invalid metadata
controls. Expectations come directly from the complete seed155 bytes, not the
fixture producer or normalizer. The observer captures printed fields before
native initialization, verifies retained physical/copiable fields, checks a
real snapshot round trip, then forwards the original consumer. The original
test body and its assertions still execute. Main-match stock/decks/RNG are
checked against their actual Factory-return baseline, not rebuilt. Anonymous
cards and legacy postconstruction creature poses remain unwaived protocol data.

## Whole-Module IO Boundary

All fifty original tests (135 assert ASTs) and all fifteen NEW cases are declared
whole: four modules, prospective65, not collected. There are also two preserved
original module helpers. No test/import/runtime scan has run. The whole set is
mixed, not a pure qualification, and the retained blocked site prevents claiming
the candidate is a ready GREEN migration:

- `test_release_card_contracts` imports real Main inside two original bodies.
  Main constructs its DB engine without establishing a connection and installs
  local media at import. No startup is requested by the source's non-context
  `TestClient(main.app)` construction; actual observed lifecycle counts remain
  pending.
- The original HTTP test retains POST `/matches/start` (assert200) and GET of
  that returned match ID (subsequent JSON assertions). It retains its existing
  repository dependency override and `_persist_active_match` patch, not new
  ones. Real MatchController construction, hydration and transform/snapshot
  code are unchanged. Any unexpected native IO needs review, not permission
  broadening or an assumed zero-SQL result.
- The original generic-token-art test writes only its pytest `tmp_path` and
  retains its preexisting token-search stub and cache cleanup. Existing printed
  facts and Main also require the genuine local placeholder/generic media
  paths, redirected only by a separately reviewed future harness.
- No new network, SQL, child, service, provider, native lease, or positive IO
  role is supplied here. No runner or activation grant is created.

Apply `SUPPORT_AND_FIDELITY.patch` to the exact frozen base for a future reviewed
whole-module RED, then `FIXTURE_MIGRATION.patch` once for the corresponding
candidate. Alternatively apply `PUBLIC.patch` once, never both recipes.
Clean-apply and postimage hashes are administrative byte checks only. Neither
baseline nor candidate was imported, collected or executed. Any future gate
must retain the entire original mixed module and preserve unexpected failures.

Other named/manual positives, cached face ABI rows, parser/error vectors,
generated-token strings, Wood Elemental's intentionally absent stats, and
Farewell are not migrated or waived. The static literal inventory is a
scheduling input, not a completeness certificate.
