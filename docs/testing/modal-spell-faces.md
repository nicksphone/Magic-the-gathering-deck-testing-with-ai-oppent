# Modal spell face boundary

The gameplay cache now preserves canonical Scryfall layout and face loyalty/colors. Shared hydration selects front-face characteristics for supported two-face layouts, instead of interpreting a combined type line as both types. Layout survives public views and saved snapshots. The SQLite compatibility migration adds metadata only; it contains no gameplay rules.

Selected spell faces use their own timing, costs, keywords, types, power/toughness and loyalty. Temporary characteristics are stored with the existing snapshot-safe printed-characteristic restoration. Instant/sorcery spell resolution moves the card to the graveyard and restores its printed identity; permanent faces retain their selected identity on the battlefield. Known transform/meld/flip back faces cannot be directly cast by ordinary actions.

Modal double-faced spell moves have independent cost and target surfaces. The human renderer defaults to an available face, disables unavailable faces, clears stale costs/targets when switching and submits the selected face. AI materialization preserves the offered face, derives its targets from that face, and scores that face in the cast-bias heuristic rather than borrowing the best alternative's value.

## Reproduction

Use the isolated backend/browser procedure in [human actions](human-actions-browser.md). The two modal scenarios use canonical Wandering Archaic / Explore the Vastlands: three mana offers only the sorcery; five mana permits a deliberate face switch and charges three mana, not five. The same browser runner retains the six existing human action cases.

`backend/tests/test_modal_spell_faces.py` covers layout/front hydration, codec restart with a selected spell on stack, graveyard restoration, Tibalt's selected planeswalker characteristics, independent affordable-face admission, AI payload materialization, repeatable old-cache migration and rejection of Delver's transform-only back face without mutation. Fixtures preserve actual Oracle IDs and bulk provenance; they never populate the gameplay card cache. These tests are boundary tests, not full semantics certification for the fixtures' entire Oracle text.

## Limits Still Open

- Older cached rows get an empty layout from schema migration. Force-sync affected cards to obtain canonical layout; the migration does not guess semantics from names or face count. Historical snapshots without layout retain the legacy compatibility path.
- Common land-face play and Adventure exile-permission paths have a separate [bounded implementation and test record](land-adventure-boundary.md). Conditional land entries, multi-target Adventure failures, fuse/aftermath and other split-card restrictions remain open.
- Selected-face browser acceptance does not prove target-heavy modes, transformations, card-image selection or a backend process restart during a face-specific spell.
- Face-specific cast bias and action materialization do not certify every AI scoring/search feature or strategically optimal face retention.
- Targeted-trigger choices, multi-clause ability compilation and broader beta/release gates remain open.

Rules grounding: Wizards describes choosing modal faces to play/cast and front-face characteristics outside the stack/battlefield in [Zendikar Rising mechanics](https://magic.wizards.com/en/news/feature/zendikar-rising-mechanics-2020-09-01) and [release notes](https://magic.wizards.com/en/news/feature/zendikar-rising-release-notes-2020-09-10). This implementation does not claim the complete double-faced-card rules chapter.
